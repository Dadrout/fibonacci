"""Server-side account deletion with media cleanup before auth record removal."""

from __future__ import annotations

import time
from urllib.parse import quote

import requests

from app.celery_utils import celery_app
from app.core.config import settings
from app.services.story_repository import story_repository
from app.services.document_repository import document_repository


class AccountDeletionError(RuntimeError):
    """Raised when account deletion cannot be completed safely."""


class AccountDeletionService:
    def __init__(
        self,
        session: requests.Session | None = None,
        repository=None,
        *,
        task_control=None,
        sleep=time.sleep,
        monotonic=time.monotonic,
        worker_stop_timeout: float = 30,
    ):
        self.session = session or requests.Session()
        self.repository = repository or story_repository
        self.task_control = task_control or celery_app
        self.sleep = sleep
        self.monotonic = monotonic
        self.worker_stop_timeout = worker_stop_timeout

    def _stop_generation(self, user_id: str) -> None:
        # The lock also protects against a request that passed authentication just
        # before logout and queues its task while deletion is in progress.
        self.repository.mark_user_deleting(user_id)
        jobs = self.repository.list_active_story_jobs(user_id)
        list_presentation_jobs = getattr(
            self.repository, "list_active_presentation_renders", None
        )
        presentation_jobs = (
            list_presentation_jobs(user_id) if list_presentation_jobs else []
        )
        list_teacher_video_jobs = getattr(
            self.repository, "list_active_teacher_video_renders", None
        )
        teacher_video_jobs = (
            list_teacher_video_jobs(user_id) if list_teacher_video_jobs else []
        )
        list_visual_jobs = getattr(self.repository, 'list_active_presentation_visuals', None)
        visual_jobs = list_visual_jobs(user_id) if list_visual_jobs else []
        cancel_visual_jobs = getattr(self.repository, 'cancel_active_presentation_visuals', None)
        if cancel_visual_jobs:
            cancel_visual_jobs(user_id)
        document_jobs = document_repository.active_jobs(user_id)
        document_repository.cancel_jobs(user_id)
        cancel_presentation_jobs = getattr(
            self.repository, "cancel_active_presentation_renders", None
        )
        if cancel_presentation_jobs:
            presentation_jobs = cancel_presentation_jobs(user_id) or presentation_jobs
        cancel_teacher_video_jobs = getattr(
            self.repository, "cancel_active_teacher_video_renders", None
        )
        if cancel_teacher_video_jobs:
            teacher_video_jobs = cancel_teacher_video_jobs(user_id) or teacher_video_jobs
        task_ids = {str(job["task_id"]) for job in jobs if job.get("task_id")}
        for task_id in task_ids:
            self.repository.cancel_story_job_for_deletion(task_id, user_id)
        task_ids.update(
            str(job["task_id"]) for job in document_jobs if job.get("task_id")
        )
        task_ids.update(
            str(job.get("id")) for job in presentation_jobs if job.get("id")
        )
        task_ids.update(
            str(job.get("id")) for job in teacher_video_jobs if job.get("id")
        )
        task_ids.update(str(job['id']) for job in visual_jobs if job.get('id'))
        for task_id in task_ids:
            self.task_control.control.revoke(task_id, terminate=True, signal="SIGTERM")

        if not task_ids:
            return

        deadline = self.monotonic() + self.worker_stop_timeout
        while True:
            inspector = self.task_control.control.inspect(timeout=5)
            active_by_worker = inspector.active() if inspector else None
            if active_by_worker is None:
                raise AccountDeletionError(
                    "Could not confirm that generation workers stopped"
                )
            active_ids = {
                str(task.get("id"))
                for tasks in active_by_worker.values()
                for task in tasks
                if task.get("id")
            }
            if not task_ids.intersection(active_ids):
                return
            if self.monotonic() >= deadline:
                raise AccountDeletionError(
                    "Generation workers did not stop before account cleanup"
                )
            self.sleep(0.25)

    def delete_account(self, user_id: str, access_token: str) -> None:
        if not user_id or "/" in user_id or user_id in {".", ".."}:
            raise AccountDeletionError("Invalid authenticated user")
        if not access_token:
            raise AccountDeletionError("A valid access token is required")
        if (
            not settings.SUPABASE_URL
            or not settings.SUPABASE_PUBLISHABLE_KEY
            or not settings.SUPABASE_SERVICE_ROLE_KEY
        ):
            raise AccountDeletionError("Account deletion is not configured")

        base_url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1"
        try:
            self._stop_generation(user_id)
            # Revoke sessions only after workers have stopped; storage cleanup must
            # happen after that point so a worker cannot upload media afterward.
            logout = self.session.post(
                f"{base_url}/logout?scope=global",
                headers={
                    "apikey": settings.SUPABASE_PUBLISHABLE_KEY,
                    "Authorization": f"Bearer {access_token}",
                },
                timeout=10,
            )
            logout.raise_for_status()
            self.repository.delete_user_assets(user_id)
            document_repository.delete_user_assets(user_id)
            deletion = self.session.delete(
                f"{base_url}/admin/users/{quote(user_id, safe='')}",
                headers={
                    "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
                    "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
                },
                timeout=10,
            )
            deletion.raise_for_status()
        except Exception as error:
            raise AccountDeletionError(
                "Account deletion could not be completed"
            ) from error


account_deletion_service = AccountDeletionService()
