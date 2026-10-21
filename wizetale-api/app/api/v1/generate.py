import logging
import shutil
from pathlib import Path
from typing import Literal

import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from starlette.concurrency import run_in_threadpool

from app.api.dependencies import get_current_user, rate_limit_user_action
from app.celery_utils import celery_app
from app.core.config import settings
from app.core.usage_context import generation_id
from app.domain.models import GenerationRequest, LearningOutcomes, VideoScript
from app.services.ai.gemini_text_service import (
    GEMINI_GENERIC_USER_MESSAGE,
    GeminiGenerationError,
)
from app.services.pipeline.job_orchestrator import job_orchestrator
from app.services.pipeline.script_service import script_generation_service
from app.services.story_repository import story_repository

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

router = APIRouter(tags=["generate"])


class PromptEnhancementRequest(BaseModel):
    description: str = Field(min_length=1, max_length=2000)
    language: Literal["en-US", "ru-RU"] = "en-US"

    @field_validator("description")
    @classmethod
    def require_nonblank_description(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Description is required")
        return value


def _user_facing_error_message(error_text: str) -> str:
    lowered = error_text.lower()
    if any(marker in lowered for marker in ["quota", "429", "resource_exhausted"]):
        return "Content generation quota was exceeded. Please retry in a few minutes."
    return GEMINI_GENERIC_USER_MESSAGE


class PersistedTaskProgress:
    def __init__(
        self,
        celery_task,
        task_id: str,
        draft_id: str | None,
        user_id: str | None = None,
    ):
        self.celery_task = celery_task
        self.request = celery_task.request
        self.task_id = task_id
        self.user_id = user_id
        self.draft_id = draft_id

    def update_state(self, *, state: str, meta: dict):
        changes = {
            "status": state,
            "progress": int(meta.get("progress", 0)),
            "stage": meta.get("step", "processing"),
            "message": meta.get("message", "Processing"),
        }
        try:
            updated = story_repository.update_story_progress_if_active(self.task_id, changes)
        except requests.Timeout:
            if state != "PROGRESS" or not self.user_id:
                raise
            # A transient progress-write timeout should not discard a completed
            # render. Recheck the deletion lock and job state before continuing.
            _assert_generation_is_active(self.task_id, self.user_id)
            logger.warning(
                "Progress update timed out for story job %s; continuing while the job remains active.",
                self.task_id,
            )
            self.celery_task.update_state(state=state, meta=meta)
            return
        if not updated:
            raise GenerationCancelled("Generation was cancelled before account cleanup.")
        self.celery_task.update_state(state=state, meta=meta)


class GenerationCancelled(Exception):
    """Raised when a persisted story job is no longer eligible to render."""


def _assert_generation_is_active(task_id: str, user_id: str) -> None:
    if story_repository.is_user_deleting(user_id):
        raise GenerationCancelled("Account deletion is in progress.")
    record = story_repository.get_story_job(task_id, user_id)
    if not record or record.get("status") not in {"PENDING", "PROGRESS"}:
        raise GenerationCancelled("Generation was cancelled before account cleanup.")


def _assert_generation_active_or_cleanup(task_id: str, user_id: str) -> None:
    try:
        _assert_generation_is_active(task_id, user_id)
    except GenerationCancelled:
        # Account cleanup may have listed the prefix while an upload was already
        # in flight. Remove the prefix again before this worker exits.
        story_repository.delete_job_assets(user_id, task_id)
        raise


@celery_app.task(bind=True, name="generate_story_video_task", soft_time_limit=1100, time_limit=1200)
def generate_story_video_task(
    self,
    request_data: dict,
    user_id: str,
    script_override: dict | None = None,
    outcomes_data: dict | None = None,
    story_row_id: str | None = None,
    draft_id: str | None = None,
):
    temp_dir = None
    usage_token = generation_id.set(str(self.request.id))
    try:
        if story_row_id:
            _assert_generation_is_active(self.request.id, user_id)
        request = GenerationRequest(
            subject=request_data["subject"],
            topic=request_data["topic"],
            language=request_data.get("language", "en-US"),
            voice=request_data.get("voice", "female"),
            user_id=user_id,
            grade_band=request_data.get("grade_band", "13-15"),
            target_duration_sec=request_data.get("target_duration_sec", 180),
        )
        temp_dir = Path(settings.WORKDIR_ROOT) / f"wizetale_task_{self.request.id}"
        persisted_task = PersistedTaskProgress(self, self.request.id, draft_id, user_id) if story_row_id else self
        result = job_orchestrator.run(
            request=request,
            job_id=self.request.id,
            task_instance=persisted_task,
            script_override=VideoScript.model_validate(script_override) if script_override else None,
            learning_outcomes=LearningOutcomes.model_validate(outcomes_data) if outcomes_data else None,
        )
        video_path = result.artifacts["video"]
        audio_path = result.artifacts["audio"]
        if story_row_id:
            _assert_generation_is_active(self.request.id, user_id)
        video_object = f"{user_id}/{self.request.id}/video.mp4"
        audio_object = f"{user_id}/{self.request.id}/audio.mp3"
        story_repository.upload_asset(
            object_path=video_object,
            local_path=video_path,
            content_type="video/mp4",
        )
        story_repository.upload_asset(
            object_path=audio_object,
            local_path=audio_path,
            content_type="audio/mpeg",
        )
        if story_row_id:
            _assert_generation_active_or_cleanup(self.request.id, user_id)
        result = result.model_copy(
            update={
                "video_url": story_repository.create_signed_asset_url(video_object),
                "audio_url": story_repository.create_signed_asset_url(audio_object),
                "artifacts": {"video_object": video_object, "audio_object": audio_object},
            }
        )
        if story_row_id:
            published = story_repository.update_story_progress_if_active(
                self.request.id,
                {
                    "status": "SUCCESS",
                    "progress": 100,
                    "stage": "complete",
                    "message": "Your story video is ready.",
                    "result": result.model_dump(mode="json"),
                },
            )
            if not published:
                story_repository.delete_job_assets(user_id, self.request.id)
                raise GenerationCancelled("Generation was cancelled before publication.")
            if draft_id:
                try:
                    story_repository.update_draft(draft_id, user_id, {"status": "complete"})
                except Exception:
                    # Media publication is terminal; metadata failure must not
                    # hide a successful video or trigger another paid render.
                    logger.exception("Could not mark completed draft %s", draft_id)
        shutil.rmtree(Path(video_path).parent, ignore_errors=True)
        logger.info(
            "Task %s completed successfully with %s scenes.",
            self.request.id,
            result.scene_count,
        )
        return result.model_dump(mode="json")
    except GenerationCancelled as error:
        logger.info("Generation task %s stopped: %s", self.request.id, error)
        return {"status": "CANCELLED"}
    except Exception as error:
        if story_row_id:
            try:
                story_repository.update_story_progress_if_active(
                    self.request.id,
                    {
                        "status": "FAILURE",
                        "progress": 0,
                        "stage": "failed",
                        "message": "Story generation failed. You can retry this draft.",
                        "error": _user_facing_error_message(str(error)),
                    },
                )
            except Exception:
                logger.exception("Could not persist failed story job %s", self.request.id)
        raise
    finally:
        generation_id.reset(usage_token)
        if temp_dir and temp_dir.exists():
            try:
                shutil.rmtree(temp_dir)
            except Exception as error:
                logger.warning("Failed to remove temporary directory %s: %s", temp_dir, error)
        shutil.rmtree(Path("static") / user_id / self.request.id, ignore_errors=True)


@router.get("/health")
async def health_check():
    return {"status": "ok"}


@router.get(
    "/ai/health",
    dependencies=[Depends(rate_limit_user_action("ai-health", limit=10))],
)
async def ai_health(user: dict = Depends(get_current_user)):
    health = await run_in_threadpool(job_orchestrator.ai_health)
    public_fields = {"provider", "configured", "enabled", "model", "transport", "fallback_provider", "authenticated"}
    return {
        name: {key: value for key, value in status.items() if key in public_fields}
        for name, status in health.model_dump().items()
    }


@router.post(
    "/enhance-prompt",
    dependencies=[Depends(rate_limit_user_action("prompt-enhancement", limit=10))],
)
async def enhance_prompt(request: PromptEnhancementRequest, user: dict = Depends(get_current_user)):
    try:
        enhanced_description = await run_in_threadpool(
            script_generation_service.enhance_prompt,
            description=request.description,
            language=request.language,
        )
        return {"enhanced_description": enhanced_description}
    except GeminiGenerationError as error:
        logger.error("Failed to enhance prompt: %s", error.debug_message, exc_info=True)
        raise HTTPException(status_code=503, detail=error.user_message) from error
    except Exception as error:
        logger.error("Failed to enhance prompt: %s", error, exc_info=True)
        raise HTTPException(status_code=500, detail=GEMINI_GENERIC_USER_MESSAGE) from error


if not settings.GEMINI_API_KEY:
    logger.warning(
        "GEMINI_API_KEY is not configured. Text generation, topic validation, and scene generation will fail until it is set."
    )

if settings.TTS_PROVIDER == "azure" and (
    not settings.AZURE_SPEECH_KEY or not settings.AZURE_SPEECH_REGION
):
    logger.warning(
        "Azure Speech is not fully configured. Audio generation will fail until TTS is configured."
    )

if settings.TTS_PROVIDER == "google" and not settings.GOOGLE_APPLICATION_CREDENTIALS_PATH:
    logger.warning(
        "Google Cloud TTS is selected but GOOGLE_APPLICATION_CREDENTIALS_PATH is not configured."
    )
