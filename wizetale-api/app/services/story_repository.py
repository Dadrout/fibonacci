"""Small server-side PostgREST repository for TaleSpark learner records."""

from __future__ import annotations

from typing import Any
from pathlib import Path
from urllib.parse import quote

import requests

from app.core.config import settings
from app.services.media_storage import r2_media_storage


class SupabaseStoryRepository:
    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()

    def _request(
        self,
        method: str,
        table: str,
        *,
        params: dict[str, str] | None = None,
        payload: dict[str, Any] | None = None,
        prefer: str | None = None,
    ) -> Any:
        if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
            raise RuntimeError("Supabase story storage is not configured")

        headers = {
            "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": "application/json",
        }
        if prefer:
            headers["Prefer"] = prefer

        request_args = {
            "params": params,
            "json": payload,
            "headers": headers,
            "timeout": 10,
        }
        url = f"{settings.SUPABASE_URL.rstrip('/')}/rest/v1/{table}"
        try:
            response = self.session.request(method, url, **request_args)
        except (requests.ConnectionError, requests.Timeout):
            if method.upper() not in {"GET", "HEAD", "OPTIONS"}:
                raise
            # Long-running API and worker processes can hold a pooled Supabase
            # connection after the server has closed it, and reads can time out
            # during transient Supabase slowdowns. Retry only safe reads.
            response = self.session.request(method, url, **request_args)
        response.raise_for_status()
        if response.status_code == 204 or not response.content:
            return None
        return response.json()

    def create_draft(self, record: dict[str, Any]) -> dict[str, Any]:
        rows = self._request(
            "POST", "story_drafts", payload=record, prefer="return=representation"
        )
        if not rows:
            raise RuntimeError("Draft was not saved")
        return rows[0]

    def mark_user_deleting(self, user_id: str) -> None:
        """Persist a worker-visible lock before account cleanup begins."""
        self._request(
            "POST",
            "account_deletion_locks",
            params={"on_conflict": "user_id"},
            payload={"user_id": user_id},
            prefer="resolution=merge-duplicates,return=minimal",
        )

    def is_user_deleting(self, user_id: str) -> bool:
        rows = self._request(
            "GET",
            "account_deletion_locks",
            params={"user_id": f"eq.{user_id}", "select": "user_id", "limit": "1"},
        )
        return bool(rows)

    def list_active_story_jobs(self, user_id: str) -> list[dict[str, Any]]:
        return self._request(
            "GET",
            "stories",
            params={
                "user_id": f"eq.{user_id}",
                "status": "in.(PENDING,PROGRESS)",
                "select": "task_id,draft_id",
            },
        )

    def cancel_story_job_for_deletion(self, task_id: str, user_id: str) -> None:
        """Make cancellation durable before asking Celery to stop a worker."""
        rows = self._request(
            "PATCH",
            "stories",
            params={
                "task_id": f"eq.{task_id}",
                "user_id": f"eq.{user_id}",
                "status": "in.(PENDING,PROGRESS)",
            },
            payload={
                "status": "FAILURE",
                "progress": 0,
                "stage": "cancelled",
                "message": "Generation stopped because the account is being deleted.",
                "error": "Account deletion is in progress.",
            },
            prefer="return=representation",
        )
        for row in rows or []:
            draft_id = row.get("draft_id")
            if draft_id:
                self._request(
                    "PATCH",
                    "story_drafts",
                    params={
                        "id": f"eq.{draft_id}",
                        "user_id": f"eq.{user_id}",
                        "status": "eq.rendering",
                    },
                    payload={"status": "draft"},
                    prefer="return=minimal",
                )

    def create_presentation_render(
        self, record: dict[str, Any]
    ) -> dict[str, Any] | None:
        rows = self._request(
            "POST",
            "teacher_presentation_renders",
            payload=record,
            prefer="return=representation",
        )
        return rows[0] if rows else None

    def presentation_render(
        self, render_id: str, user_id: str
    ) -> dict[str, Any] | None:
        rows = self._request(
            "GET",
            "teacher_presentation_renders",
            params={
                "id": f"eq.{render_id}",
                "user_id": f"eq.{user_id}",
                "select": "*",
                "limit": "1",
            },
        )
        return rows[0] if rows else None

    def active_presentation_render(
        self, resource_id: str, user_id: str
    ) -> dict[str, Any] | None:
        rows = self._request(
            "GET",
            "teacher_presentation_renders",
            params={
                "resource_id": f"eq.{resource_id}",
                "user_id": f"eq.{user_id}",
                "status": "in.(queued,processing)",
                "select": "*",
                "order": "created_at.desc",
                "limit": "1",
            },
        )
        return rows[0] if rows else None

    def latest_presentation_render(
        self, resource_id: str, user_id: str
    ) -> dict[str, Any] | None:
        rows = self._request(
            "GET",
            "teacher_presentation_renders",
            params={
                "resource_id": f"eq.{resource_id}",
                "user_id": f"eq.{user_id}",
                "status": "not.eq.cancelled",
                "select": "*",
                "order": "created_at.desc",
                "limit": "1",
            },
        )
        return rows[0] if rows else None

    def update_presentation_render(
        self,
        render_id: str,
        user_id: str,
        changes: dict[str, Any],
        *,
        active_only: bool = False,
    ) -> dict[str, Any] | None:
        params = {"id": f"eq.{render_id}", "user_id": f"eq.{user_id}"}
        if active_only:
            params["status"] = "in.(queued,processing)"
        rows = self._request(
            "PATCH",
            "teacher_presentation_renders",
            params=params,
            payload=changes,
            prefer="return=representation",
        )
        return rows[0] if rows else None

    def list_active_presentation_renders(self, user_id: str) -> list[dict[str, Any]]:
        return self._request(
            "GET",
            "teacher_presentation_renders",
            params={
                "user_id": f"eq.{user_id}",
                "status": "in.(queued,processing)",
                "select": "id",
            },
        )

    def cancel_active_presentation_renders(self, user_id: str) -> list[dict[str, Any]]:
        return (
            self._request(
                "PATCH",
                "teacher_presentation_renders",
                params={
                    "user_id": f"eq.{user_id}",
                    "status": "in.(queued,processing)",
                    "select": "id",
                },
                payload={
                    "status": "cancelled",
                    "progress": 0,
                    "stage": "cancelled",
                    "message": "Rendering stopped because the account is being deleted.",
                    "error": "account_deletion",
                },
                prefer="return=representation",
            )
            or []
        )

    def create_teacher_video_render(
        self, record: dict[str, Any]
    ) -> dict[str, Any] | None:
        rows = self._request(
            "POST", "teacher_video_renders", payload=record,
            prefer="return=representation",
        )
        return rows[0] if rows else None

    def teacher_video_render(
        self, render_id: str, user_id: str
    ) -> dict[str, Any] | None:
        rows = self._request(
            "GET", "teacher_video_renders",
            params={
                "id": f"eq.{render_id}", "user_id": f"eq.{user_id}",
                "select": "*", "limit": "1",
            },
        )
        return rows[0] if rows else None

    def active_teacher_video_render(
        self, resource_id: str, user_id: str
    ) -> dict[str, Any] | None:
        rows = self._request(
            "GET", "teacher_video_renders",
            params={
                "resource_id": f"eq.{resource_id}", "user_id": f"eq.{user_id}",
                "status": "in.(queued,processing)", "select": "*",
                "order": "created_at.desc", "limit": "1",
            },
        )
        return rows[0] if rows else None

    def latest_teacher_video_render(
        self, resource_id: str, user_id: str
    ) -> dict[str, Any] | None:
        rows = self._request(
            "GET", "teacher_video_renders",
            params={
                "resource_id": f"eq.{resource_id}", "user_id": f"eq.{user_id}",
                "status": "not.eq.cancelled", "select": "*",
                "order": "created_at.desc", "limit": "1",
            },
        )
        return rows[0] if rows else None

    def update_teacher_video_render(
        self,
        render_id: str,
        user_id: str,
        changes: dict[str, Any],
        *,
        active_only: bool = False,
    ) -> dict[str, Any] | None:
        params = {"id": f"eq.{render_id}", "user_id": f"eq.{user_id}"}
        if active_only:
            params["status"] = "in.(queued,processing)"
        rows = self._request(
            "PATCH", "teacher_video_renders", params=params, payload=changes,
            prefer="return=representation",
        )
        return rows[0] if rows else None

    def list_active_teacher_video_renders(self, user_id: str) -> list[dict[str, Any]]:
        return self._request(
            "GET", "teacher_video_renders",
            params={
                "user_id": f"eq.{user_id}",
                "status": "in.(queued,processing)", "select": "id",
            },
        )

    def cancel_active_teacher_video_renders(
        self, user_id: str
    ) -> list[dict[str, Any]]:
        return (
            self._request(
                "PATCH", "teacher_video_renders",
                params={
                    "user_id": f"eq.{user_id}",
                    "status": "in.(queued,processing)", "select": "id",
                },
                payload={
                    "status": "cancelled", "progress": 0,
                    "stage": "cancelled",
                    "message": "Rendering stopped because the account is being deleted.",
                    "error": "account_deletion",
                },
                prefer="return=representation",
            ) or []
        )

    def invalidate_teacher_video_renders(
        self, resource_id: str, user_id: str, current_revision: int
    ) -> int:
        return self._cancel_teacher_video_renders(
            resource_id,
            user_id,
            resource_revision_filter=f"lt.{current_revision}",
            message="The video script changed. Render the saved script again.",
            error="resource_revision_changed",
        )

    def cancel_all_teacher_video_renders_for_resource(
        self, resource_id: str, user_id: str
    ) -> int:
        return self._cancel_teacher_video_renders(
            resource_id,
            user_id,
            resource_revision_filter=None,
            message="The video resource was removed.",
            error="resource_removed",
        )

    def _cancel_teacher_video_renders(
        self,
        resource_id: str,
        user_id: str,
        *,
        resource_revision_filter: str | None,
        message: str,
        error: str,
    ) -> int:
        params = {
            "resource_id": f"eq.{resource_id}",
            "user_id": f"eq.{user_id}",
            "status": "not.eq.cancelled",
        }
        if resource_revision_filter is not None:
            params["resource_revision"] = resource_revision_filter
        rows = self._request(
            "PATCH",
            "teacher_video_renders",
            params=params,
            payload={
                "status": "cancelled",
                "stage": "cancelled",
                "message": message,
                "error": error,
            },
            prefer="return=representation",
        ) or []
        owner_prefix = f"{user_id}/"
        for row in rows:
            object_path = row.get("video_object")
            if object_path:
                if object_path.startswith(owner_prefix):
                    self.delete_asset(object_path)
                self._request(
                    "PATCH",
                    "teacher_video_renders",
                    params={
                        "id": f"eq.{row['id']}",
                        "user_id": f"eq.{user_id}",
                        "status": "eq.cancelled",
                    },
                    payload={"video_object": None},
                    prefer="return=minimal",
                )
        return len(rows)

    def get_draft(self, draft_id: str, user_id: str) -> dict[str, Any] | None:
        rows = self._request(
            "GET",
            "story_drafts",
            params={
                "id": f"eq.{draft_id}",
                "user_id": f"eq.{user_id}",
                "select": "*",
                "limit": "1",
            },
        )
        return rows[0] if rows else None

    def update_draft(
        self, draft_id: str, user_id: str, changes: dict[str, Any]
    ) -> None:
        self._request(
            "PATCH",
            "story_drafts",
            params={"id": f"eq.{draft_id}", "user_id": f"eq.{user_id}"},
            payload=changes,
            prefer="return=minimal",
        )

    def update_draft_if_editable(
        self, draft_id: str, user_id: str, changes: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Update an owned draft only if it has not been claimed for rendering."""
        rows = self._request(
            "PATCH",
            "story_drafts",
            params={
                "id": f"eq.{draft_id}",
                "user_id": f"eq.{user_id}",
                "status": "eq.draft",
            },
            payload=changes,
            prefer="return=representation",
        )
        return rows[0] if rows else None

    def delete_draft_if_editable(
        self, draft_id: str, user_id: str
    ) -> dict[str, Any] | None:
        """Delete an owned draft only while it remains editable."""
        rows = self._request(
            "DELETE",
            "story_drafts",
            params={
                "id": f"eq.{draft_id}",
                "user_id": f"eq.{user_id}",
                "status": "eq.draft",
            },
            prefer="return=representation",
        )
        return rows[0] if rows else None

    def claim_render_job(
        self, draft_id: str, user_id: str, task_id: str
    ) -> dict[str, Any] | None:
        return self._request(
            "POST",
            "rpc/claim_story_render",
            payload={
                "p_draft_id": draft_id,
                "p_user_id": user_id,
                "p_task_id": task_id,
            },
        )

    def recover_render(self, draft_id: str, user_id: str) -> None:
        self._request(
            "POST",
            "rpc/recover_story_render",
            payload={
                "p_draft_id": draft_id,
                "p_user_id": user_id,
            },
        )

    def update_story_by_task(self, task_id: str, changes: dict[str, Any]) -> None:
        self._request(
            "PATCH",
            "stories",
            params={"task_id": f"eq.{task_id}"},
            payload=changes,
            prefer="return=minimal",
        )

    def update_story_progress_if_active(
        self, task_id: str, changes: dict[str, Any]
    ) -> bool:
        rows = self._request(
            "PATCH",
            "stories",
            params={
                "task_id": f"eq.{task_id}",
                "status": "in.(PENDING,PROGRESS)",
            },
            payload=changes,
            prefer="return=representation",
        )
        return bool(rows)

    def get_story_job(self, task_id: str, user_id: str) -> dict[str, Any] | None:
        rows = self._request(
            "GET",
            "stories",
            params={
                "task_id": f"eq.{task_id}",
                "user_id": f"eq.{user_id}",
                "select": "*",
                "limit": "1",
            },
        )
        return rows[0] if rows else None

    def get_story_by_id(self, story_id: str, user_id: str) -> dict[str, Any] | None:
        rows = self._request(
            "GET",
            "stories",
            params={
                "id": f"eq.{story_id}",
                "user_id": f"eq.{user_id}",
                "select": "*",
                "limit": "1",
            },
        )
        return rows[0] if rows else None

    def list_stories(
        self, user_id: str, *, limit: int = 25, offset: int = 0
    ) -> list[dict[str, Any]]:
        page_size = min(max(int(limit), 1), 50)
        page_offset = max(int(offset), 0)
        return self._request(
            "GET",
            "stories",
            params={
                "user_id": f"eq.{user_id}",
                "status": "eq.SUCCESS",
                "select": "*",
                "order": "created_at.desc",
                "limit": str(page_size),
                "offset": str(page_offset),
            },
        )

    def save_quiz_result(self, record: dict[str, Any]) -> dict[str, Any]:
        rows = self._request(
            "POST",
            "quiz_results",
            params={"on_conflict": "story_id,user_id"},
            payload=record,
            prefer="resolution=ignore-duplicates,return=representation",
        )
        if rows:
            return rows[0]
        existing = self.get_quiz_result(record["story_id"], record["user_id"])
        if not existing:
            raise RuntimeError("Quiz result was not saved")
        return existing

    def get_quiz_result(self, story_id: str, user_id: str) -> dict[str, Any] | None:
        rows = self._request(
            "GET",
            "quiz_results",
            params={
                "story_id": f"eq.{story_id}",
                "user_id": f"eq.{user_id}",
                "select": "*",
                "limit": "1",
            },
        )
        return rows[0] if rows else None

    def upload_asset(
        self, *, object_path: str, local_path: str, content_type: str
    ) -> str:
        if settings.MEDIA_STORAGE_PROVIDER.lower() == "r2":
            return r2_media_storage.upload(
                object_path=object_path,
                local_path=local_path,
                content_type=content_type,
            )
        if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
            raise RuntimeError("Supabase story storage is not configured")
        path = "/".join(part for part in object_path.split("/") if part)
        headers = {
            "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": content_type,
            "x-upsert": "true",
        }
        with Path(local_path).open("rb") as asset:
            response = self.session.post(
                f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1/object/{settings.SUPABASE_VIDEO_BUCKET}/{path}",
                data=asset,
                headers=headers,
                timeout=120,
            )
        response.raise_for_status()
        return path

    def create_signed_asset_url(
        self, object_path: str, expires_in: int | None = None
    ) -> str:
        if settings.MEDIA_STORAGE_PROVIDER.lower() == "r2":
            return r2_media_storage.signed_url(object_path, expires_in)
        headers = {
            "apikey": settings.SUPABASE_SERVICE_ROLE_KEY or "",
            "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY or ''}",
            "Content-Type": "application/json",
        }
        response = self.session.post(
            f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1/object/sign/{settings.SUPABASE_VIDEO_BUCKET}/{object_path}",
            json={"expiresIn": expires_in or settings.MEDIA_SIGNED_URL_TTL_SECONDS},
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()
        signed_path = response.json().get("signedURL") or response.json().get(
            "signedUrl"
        )
        if not signed_path:
            raise RuntimeError("Supabase did not return a signed media URL")
        if signed_path.startswith("http"):
            return signed_path
        return f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1{signed_path}"

    def delete_user_assets(self, user_id: str) -> int:
        """Recursively remove one user's media from the configured private bucket."""
        if not user_id or "/" in user_id or user_id in {".", ".."}:
            raise ValueError("Invalid user ID for media cleanup")
        if settings.MEDIA_STORAGE_PROVIDER.lower() == "r2":
            return r2_media_storage.delete_user_assets(user_id)
        if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
            raise RuntimeError("Supabase story storage is not configured")

        base_url = f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1"
        bucket = quote(settings.SUPABASE_VIDEO_BUCKET, safe="")
        headers = {
            "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": "application/json",
        }
        deleted = 0

        def list_folder(prefix: str) -> list[str]:
            files: list[str] = []
            offset = 0
            while True:
                response = self.session.post(
                    f"{base_url}/object/list/{bucket}",
                    json={
                        "prefix": prefix,
                        "limit": 1000,
                        "offset": offset,
                        "sortBy": {"column": "name", "order": "asc"},
                    },
                    headers=headers,
                    timeout=30,
                )
                response.raise_for_status()
                entries = response.json()
                if not isinstance(entries, list):
                    raise RuntimeError("Supabase returned an invalid storage listing")
                for entry in entries:
                    name = entry.get("name") if isinstance(entry, dict) else None
                    if not name or name in {".", ".."} or "/" in name:
                        continue
                    path = f"{prefix}{name}"
                    if entry.get("id") is None:
                        files.extend(list_folder(f"{path}/"))
                    else:
                        files.append(path)
                if len(entries) < 1000:
                    break
                offset += len(entries)
            return files

        object_paths = list_folder(f"{user_id}/")
        for start in range(0, len(object_paths), 1000):
            batch = object_paths[start : start + 1000]
            response = self.session.delete(
                f"{base_url}/object/{bucket}",
                json={"prefixes": batch},
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()
            result = response.json() if response.content else []
            if isinstance(result, list) and any(
                isinstance(item, dict) and item.get("error") for item in result
            ):
                raise RuntimeError("Supabase could not delete all user media")
            deleted += len(batch)
        return deleted

    def delete_asset(self, object_path: str) -> None:
        """Delete one server-owned private object; callers supply stored paths."""
        if not object_path or any(part in {'', '.', '..'} for part in object_path.split('/')):
            raise ValueError('Invalid media object path')
        if settings.MEDIA_STORAGE_PROVIDER.lower() == 'r2':
            return r2_media_storage.delete_asset(object_path)
        response = self.session.delete(
            f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1/object/{quote(settings.SUPABASE_VIDEO_BUCKET, safe='')}",
            json={'prefixes': [object_path]},
            headers={'apikey': settings.SUPABASE_SERVICE_ROLE_KEY or '', 'Authorization': f'Bearer {settings.SUPABASE_SERVICE_ROLE_KEY or ""}', 'Content-Type': 'application/json'},
            timeout=30,
        )
        response.raise_for_status()
        result = response.json() if response.content else []
        if isinstance(result, list) and any(isinstance(item, dict) and item.get('error') for item in result):
            raise RuntimeError('Could not remove private presentation media')

    def invalidate_presentation_renders(self, resource_id, user_id):
        rows = self._request('GET', 'teacher_presentation_renders', params={
            'resource_id': f'eq.{resource_id}', 'user_id': f'eq.{user_id}',
            'status': 'in.(queued,processing,ready)', 'select': 'id,video_object',
        }) or []
        self._request('PATCH', 'teacher_presentation_renders', params={
            'resource_id': f'eq.{resource_id}', 'user_id': f'eq.{user_id}',
            'status': 'in.(queued,processing,ready)',
        }, payload={'status': 'cancelled', 'stage': 'cancelled', 'video_object': None,
                    'message': 'Slide visuals changed. Render a new presentation video.', 'error': 'visuals_changed'})
        for row in rows:
            if row.get('video_object') and row['video_object'].startswith(f'{user_id}/'):
                self.delete_asset(row['video_object'])

    def list_active_presentation_visuals(self, user_id):
        return self._request('GET', 'presentation_slide_visuals', params={'user_id': f'eq.{user_id}', 'status': 'in.(pending,processing)', 'select': 'id'})

    def cancel_active_presentation_visuals(self, user_id):
        self._request('PATCH', 'presentation_slide_visuals', params={'user_id': f'eq.{user_id}', 'status': 'in.(pending,processing)'}, payload={'status': 'failed'})

    def delete_job_assets(self, user_id: str, job_id: str) -> int:
        """Remove only a cancelled generation's media, without touching history."""
        for value, label in ((user_id, "user"), (job_id, "job")):
            if not value or "/" in value or value in {".", ".."}:
                raise ValueError(f"Invalid {label} ID for media cleanup")
        if settings.MEDIA_STORAGE_PROVIDER.lower() == "r2":
            return r2_media_storage.delete_job_assets(user_id, job_id)
        if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
            raise RuntimeError("Supabase story storage is not configured")
        bucket = quote(settings.SUPABASE_VIDEO_BUCKET, safe="")
        object_paths = [
            f"{user_id}/{job_id}/video.mp4",
            f"{user_id}/{job_id}/audio.mp3",
        ]
        response = self.session.delete(
            f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1/object/{bucket}",
            json={"prefixes": object_paths},
            headers={
                "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
                "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
                "Content-Type": "application/json",
            },
            timeout=30,
        )
        response.raise_for_status()
        result = response.json() if response.content else []
        if isinstance(result, list) and any(
            isinstance(item, dict) and item.get("error") for item in result
        ):
            raise RuntimeError("Could not remove media from the cancelled generation")
        return len(object_paths)


story_repository = SupabaseStoryRepository()
