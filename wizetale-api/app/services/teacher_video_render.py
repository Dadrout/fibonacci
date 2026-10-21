"""Celery worker for private teacher topic-video renders."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from app.celery_utils import celery_app
from app.core.config import settings
from app.domain.models import GenerationRequest, VideoScript
from app.domain.teacher import VideoResourceContent
from app.services.pipeline.job_orchestrator import job_orchestrator
from app.services.story_repository import story_repository
from app.services.teacher_repository import teacher_repository
from app.services.teacher_video_generation import grade_to_lookup_band

logger = logging.getLogger(__name__)


class GenerationCancelled(RuntimeError):
    """Raised when the resource changed or the owner began account deletion."""


class TeacherVideoRenderService:
    def __init__(self, *, repository=None, teacher_repo=None, orchestrator=None):
        self.repository = repository or story_repository
        self.teacher_repo = teacher_repo or teacher_repository
        self.orchestrator = orchestrator or job_orchestrator

    def _active(self, render_id: str, user_id: str, resource_id: str, revision: int) -> bool:
        if self.repository.is_user_deleting(user_id):
            return False
        render = self.repository.teacher_video_render(render_id, user_id)
        if (
            not render
            or render.get('status') not in {'queued', 'processing'}
            or render.get('resource_id') != resource_id
            or render.get('resource_revision') != revision
        ):
            return False
        resource = self.teacher_repo.resource(resource_id, user_id)
        return bool(
            resource
            and resource.get('kind') == 'video'
            and resource.get('status') == 'ready'
            and resource.get('revision') == revision
        )

    def _update_active(self, render_id: str, user_id: str, changes: dict):
        updated = self.repository.update_teacher_video_render(
            render_id, user_id, changes, active_only=True,
        )
        if not updated:
            raise GenerationCancelled('The video render is no longer active.')
        return updated

    def _cancel(self, render_id: str, user_id: str, message: str):
        self.repository.update_teacher_video_render(
            render_id, user_id,
            {
                'status': 'cancelled', 'stage': 'cancelled',
                'video_object': None, 'message': message,
                'error': 'resource_revision_changed',
            },
            active_only=True,
        )

    def render(
        self,
        render_id: str,
        user_id: str,
        resource_id: str,
        resource_revision: int,
        content: dict,
        lesson_snapshot: dict,
        *,
        task_instance=None,
    ) -> dict:
        if not self._active(render_id, user_id, resource_id, resource_revision):
            self._cancel(render_id, user_id, 'The saved script changed. Render the current version again.')
            return {'status': 'cancelled'}
        self._update_active(
            render_id, user_id,
            {'status': 'processing', 'progress': 1, 'stage': 'starting',
             'message': 'Starting your topic video.'},
        )
        object_path = f'{user_id}/{render_id}/video.mp4'
        uploaded = False
        try:
            if not user_id or '/' in user_id or user_id in {'.', '..'}:
                raise ValueError('Invalid video owner')
            video_content = VideoResourceContent.model_validate(content)
            school_grade = str(lesson_snapshot['grade'])
            request = GenerationRequest(
                subject=lesson_snapshot['subject'],
                topic=lesson_snapshot['topic'],
                language=lesson_snapshot['language'],
                voice=video_content.voice,
                user_id=user_id,
                grade_band=grade_to_lookup_band(school_grade),
                school_grade=school_grade,
                target_duration_sec=video_content.target_duration_sec,
            )
            progress = _RenderProgress(self, render_id, user_id)
            result = self.orchestrator.run(
                request=request,
                job_id=render_id,
                task_instance=progress if task_instance else None,
                script_override=video_content.script,
                generate_learning_outcomes=False,
            )
            if not self._active(render_id, user_id, resource_id, resource_revision):
                self._cancel(render_id, user_id, 'The saved script changed. Render the current version again.')
                return {'status': 'cancelled'}
            local_video = Path(result.artifacts.get('video') or '')
            if not local_video.is_file():
                raise RuntimeError('The video renderer did not produce a file')
            self._update_active(
                render_id, user_id,
                {'progress': 95, 'stage': 'uploading', 'message': 'Saving your video.'},
            )
            self.repository.upload_asset(
                object_path=object_path,
                local_path=str(local_video),
                content_type='video/mp4',
            )
            uploaded = True
            if not self._active(render_id, user_id, resource_id, resource_revision):
                self.repository.delete_asset(object_path)
                uploaded = False
                self._cancel(render_id, user_id, 'The saved script changed. Render the current version again.')
                return {'status': 'cancelled'}
            ready = self.repository.update_teacher_video_render(
                render_id, user_id,
                {
                    'status': 'ready', 'progress': 100, 'stage': 'complete',
                    'message': 'Your topic video is ready.',
                    'video_object': object_path,
                    'duration_sec': result.duration_sec,
                    'error': None,
                },
                active_only=True,
            )
            if not ready:
                self.repository.delete_asset(object_path)
                uploaded = False
                return {'status': 'cancelled'}
            uploaded = False
            return ready
        except GenerationCancelled:
            self._cancel(render_id, user_id, 'The video render was stopped because the saved script changed.')
            return {'status': 'cancelled'}
        except Exception as error:
            if uploaded:
                try:
                    self.repository.delete_asset(object_path)
                except Exception:
                    logger.warning('Could not remove incomplete teacher video asset')
            self.repository.update_teacher_video_render(
                render_id, user_id,
                {
                    'status': 'failed', 'stage': 'failed', 'progress': 0,
                    'video_object': None,
                    'message': 'The video could not be rendered. You can try again.',
                    'error': 'render_failed',
                },
                active_only=True,
            )
            logger.warning('Teacher video render failed (%s)', type(error).__name__)
            return {'status': 'failed'}
        finally:
            shutil.rmtree(Path('static') / user_id / render_id, ignore_errors=True)
            shutil.rmtree(Path(settings.WORKDIR_ROOT) / f'wizetale_task_{render_id}', ignore_errors=True)


class _RenderProgress:
    def __init__(self, service, render_id, user_id):
        self.service = service
        self.render_id = render_id
        self.user_id = user_id

    def update_state(self, *, state, meta=None):
        meta = meta or {}
        if state not in {'PROGRESS', 'STARTED'}:
            return
        self.service._update_active(
            self.render_id, self.user_id,
            {
                'status': 'processing',
                'progress': int(meta.get('progress', 1)),
                'stage': str(meta.get('step') or 'processing')[:80],
                'message': str(meta.get('message') or 'Rendering your topic video.')[:500],
            },
        )


teacher_video_render_service = TeacherVideoRenderService()


@celery_app.task(
    bind=True,
    name='render_teacher_video_task',
    soft_time_limit=600,
    time_limit=660,
)
def render_teacher_video_task(
    task,
    render_id: str,
    user_id: str,
    resource_id: str,
    resource_revision: int,
    content: dict,
    lesson_snapshot: dict,
):
    return teacher_video_render_service.render(
        render_id,
        user_id,
        resource_id,
        resource_revision,
        content,
        lesson_snapshot,
        task_instance=task,
    )
