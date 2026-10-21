import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.api.dependencies import get_current_user, rate_limit_user_action
from app.core.config import settings
from app.core.usage_context import generation_id
from app.domain.models import (
    GenerationRequest,
    LearningOutcomes,
    QuizSubmission,
    StoryDraftRequest,
    VideoScript,
)
from app.services.knowledge_service import KnowledgeContext, knowledge_service
from app.services.learner_source import source_prompt_block
from app.services.pipeline.script_service import (
    ScriptLengthUnavailable,
    TopicValidationUnavailable,
    script_generation_service,
)
from app.services.story_repository import story_repository

logger = logging.getLogger(__name__)
router = APIRouter(tags=["stories"])


class DraftUpdate(BaseModel):
    script: VideoScript


class DraftResponse(BaseModel):
    id: str
    status: str
    subject: str
    topic: str
    grade_band: str
    target_duration_sec: int
    language: str
    voice: str
    script: VideoScript
    recap: str
    quiz: LearningOutcomes
    sources: list[dict[str, Any]] = Field(default_factory=list)
    knowledge_status: Literal["grounded", "partial", "none"] = "none"


class RenderResponse(BaseModel):
    job_id: str


def _user_id(user: dict[str, Any]) -> str:
    uid = user.get("uid")
    if not uid:
        raise HTTPException(status_code=401, detail="Authenticated user ID is missing")
    return str(uid)


def _repo_error(error: Exception) -> HTTPException:
    logger.warning("TaleSpark story service request failed (%s)", type(error).__name__)
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        return HTTPException(status_code=503, detail="Story storage is not configured.")
    return HTTPException(status_code=503, detail="Story storage is temporarily unavailable.")


def _draft_response(record: dict[str, Any]) -> dict[str, Any]:
    outcomes = LearningOutcomes(recap=record["recap"], quiz=record["quiz"])
    return {
        "id": record["id"],
        "status": record["status"],
        "subject": record["subject"],
        "topic": record["topic"],
        "grade_band": record["grade_band"],
        "target_duration_sec": record["target_duration_sec"],
        "language": record["language"],
        "voice": record["voice"],
        "script": record["script"],
        "recap": outcomes.recap,
        "quiz": outcomes,
        "sources": record.get("sources", []),
        "knowledge_status": record.get("knowledge_status", "none"),
    }


async def _ensure_account_can_generate(user_id: str) -> None:
    if await run_in_threadpool(story_repository.is_user_deleting, user_id):
        raise HTTPException(status_code=409, detail="Account deletion is in progress")


@router.post(
    "/story-drafts",
    response_model=DraftResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit_user_action("story-draft", limit=5))],
)
async def create_story_draft(
    request: StoryDraftRequest,
    user: dict = Depends(get_current_user),
):
    user_id = _user_id(user)
    draft_id = str(uuid4())
    usage_token = generation_id.set(draft_id)
    generation = GenerationRequest(
        subject=request.subject,
        topic=request.topic,
        language=request.language,
        voice=request.voice,
        user_id=user_id,
        grade_band=request.grade_band,
        target_duration_sec=request.target_duration_sec,
    )
    try:
        await _ensure_account_can_generate(user_id)
        validated_topic = await run_in_threadpool(script_generation_service.validate_topic, generation)
        if not validated_topic.valid:
            raise HTTPException(status_code=422, detail=validated_topic.rejection_reason or "Choose a suitable learning topic.")
        try:
            knowledge = await run_in_threadpool(
                knowledge_service.retrieve,
                request.topic,
                request.subject,
                request.grade_band,
            )
        except Exception:
            logger.warning("Reviewed source lookup failed for topic '%s'.", request.topic, exc_info=True)
            knowledge = KnowledgeContext()
        generated_draft = await run_in_threadpool(
            script_generation_service.generate_draft,
            request=generation,
            validated_topic=validated_topic,
            knowledge_context="\n".join(
                part for part in (source_prompt_block(request.source_text), knowledge.prompt_context) if part
            ),
        )
        script = generated_draft.script
        outcomes = generated_draft.learning_outcomes
        record = await run_in_threadpool(
            story_repository.create_draft,
            {
                "id": draft_id,
                "user_id": user_id,
                "subject": request.subject,
                "topic": validated_topic.normalized_topic,
                "grade_band": request.grade_band,
                "target_duration_sec": request.target_duration_sec,
                "language": request.language,
                "voice": request.voice,
                "script": script.model_dump(mode="json"),
                "recap": outcomes.recap,
                "quiz": [question.model_dump(mode="json") for question in outcomes.quiz],
                "sources": knowledge.sources,
                "knowledge_status": knowledge.status,
                "status": "draft",
            },
        )
        return _draft_response(record)
    except HTTPException:
        raise
    except TopicValidationUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail="Topic validation is temporarily unavailable. Please try again shortly.",
        ) from error
    except ScriptLengthUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail="Could not create a script that fits the selected video length. Please try again.",
        ) from error
    except Exception as error:
        raise _repo_error(error) from error
    finally:
        generation_id.reset(usage_token)


@router.patch(
    "/story-drafts/{draft_id}",
    response_model=DraftResponse,
    dependencies=[Depends(rate_limit_user_action("story-draft-edit", limit=10))],
)
async def update_story_draft(
    draft_id: str,
    update: DraftUpdate,
    user: dict = Depends(get_current_user),
):
    user_id = _user_id(user)
    try:
        await _ensure_account_can_generate(user_id)
        draft = await run_in_threadpool(story_repository.get_draft, draft_id, user_id)
        if not draft:
            raise HTTPException(status_code=404, detail="Draft not found")
        if draft["status"] != "draft":
            raise HTTPException(status_code=409, detail="This draft can no longer be edited")
        if update.script.full_narration == draft["script"].get("full_narration"):
            outcomes = LearningOutcomes(recap=draft["recap"], quiz=draft["quiz"])
        else:
            if not script_generation_service.narration_length_is_valid(
                update.script.full_narration,
                draft["target_duration_sec"],
            ):
                minimum_words, maximum_words = script_generation_service.narration_word_range(
                    draft["target_duration_sec"]
                )
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "Narration must be "
                        f"{minimum_words}–{maximum_words} words for the selected video length."
                    ),
                )
            outcomes = await run_in_threadpool(
                script_generation_service.generate_learning_outcomes,
                topic=draft["topic"],
                narration=update.script.full_narration,
                language=draft["language"],
                grade_band=draft["grade_band"],
            )
        updated_draft = await run_in_threadpool(
            story_repository.update_draft_if_editable,
            draft_id,
            user_id,
            {
                "script": update.script.model_dump(mode="json"),
                "recap": outcomes.recap,
                "quiz": [question.model_dump(mode="json") for question in outcomes.quiz],
            },
        )
        if not updated_draft:
            raise HTTPException(status_code=409, detail="This draft can no longer be edited")
        return _draft_response(updated_draft)
    except HTTPException:
        raise
    except Exception as error:
        raise _repo_error(error) from error


@router.delete(
    "/story-drafts/{draft_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_story_draft(draft_id: str, user: dict = Depends(get_current_user)):
    user_id = _user_id(user)
    try:
        deleted = await run_in_threadpool(
            story_repository.delete_draft_if_editable, draft_id, user_id
        )
        if deleted:
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        existing = await run_in_threadpool(story_repository.get_draft, draft_id, user_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Draft not found")
        raise HTTPException(
            status_code=409,
            detail="This draft can no longer be discarded",
        )
    except HTTPException:
        raise
    except Exception as error:
        raise _repo_error(error) from error


@router.get("/story-drafts/{draft_id}", response_model=DraftResponse)
async def get_story_draft(draft_id: str, user: dict = Depends(get_current_user)):
    try:
        draft = await run_in_threadpool(story_repository.get_draft, draft_id, _user_id(user))
        if not draft:
            raise HTTPException(status_code=404, detail="Draft not found")
        if draft["status"] == "rendering":
            await run_in_threadpool(story_repository.recover_render, draft_id, _user_id(user))
            draft = await run_in_threadpool(story_repository.get_draft, draft_id, _user_id(user))
            if not draft:
                raise HTTPException(status_code=404, detail="Draft not found")
        return _draft_response(draft)
    except HTTPException:
        raise
    except Exception as error:
        raise _repo_error(error) from error


@router.post(
    "/story-drafts/{draft_id}/render",
    response_model=RenderResponse,
    status_code=202,
    dependencies=[Depends(rate_limit_user_action("story-render", limit=3))],
)
async def render_story_draft(draft_id: str, user: dict = Depends(get_current_user)):
    from app.api.v1.generate import generate_story_video_task

    user_id = _user_id(user)
    story = None
    try:
        await _ensure_account_can_generate(user_id)
        draft = await run_in_threadpool(story_repository.get_draft, draft_id, user_id)
        if not draft:
            raise HTTPException(status_code=404, detail="Draft not found")
        if draft["status"] == "rendering":
            await run_in_threadpool(story_repository.recover_render, draft_id, user_id)
            draft = await run_in_threadpool(story_repository.get_draft, draft_id, user_id)
            if not draft:
                raise HTTPException(status_code=404, detail="Draft not found")
        if draft["status"] != "draft":
            raise HTTPException(status_code=409, detail="This draft has already been submitted for rendering")
        task_id = str(uuid4())
        claimed = await run_in_threadpool(story_repository.claim_render_job, draft_id, user_id, task_id)
        if not claimed:
            raise HTTPException(status_code=409, detail="This draft has already been submitted for rendering")
        draft = claimed["draft"]
        story = claimed["story"]
        task_request = {
            "subject": draft["subject"],
            "topic": draft["topic"],
            "language": draft["language"],
            "voice": draft["voice"],
            "grade_band": draft["grade_band"],
            "target_duration_sec": draft["target_duration_sec"],
        }
        generate_story_video_task.apply_async(
            args=[
                task_request,
                user_id,
                draft["script"],
                {"recap": draft["recap"], "quiz": draft["quiz"]},
                story["id"],
                draft_id,
            ],
            task_id=task_id,
        )
        return RenderResponse(job_id=task_id)
    except HTTPException:
        raise
    except Exception as error:
        if story:
            try:
                if story:
                    await run_in_threadpool(
                        story_repository.update_story_progress_if_active,
                        story["task_id"],
                        {
                            "status": "FAILURE",
                            "stage": "failed",
                            "message": "Could not queue video generation.",
                            "error": "The video service could not start. Please retry.",
                        },
                    )
            except Exception:
                logger.warning("Could not roll back a failed queue request")
        raise _repo_error(error) from error


@router.get("/jobs/{job_id}")
async def get_story_job(job_id: str, user: dict = Depends(get_current_user)):
    try:
        record = await run_in_threadpool(story_repository.get_story_job, job_id, _user_id(user))
        if not record:
            raise HTTPException(status_code=404, detail="Story job not found")
        updated_at = record.get("updated_at")
        if updated_at and record["status"] in {"PENDING", "PROGRESS"}:
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(updated_at.replace("Z", "+00:00"))).total_seconds()
            if age > (600 if record["status"] == "PENDING" else 1800):
                await run_in_threadpool(story_repository.recover_render, record["draft_id"], _user_id(user))
                record = await run_in_threadpool(story_repository.get_story_job, job_id, _user_id(user))
                if not record:
                    raise HTTPException(status_code=404, detail="Story job not found")
        result = record.get("result")
        if result:
            result["sources"] = record.get("sources", [])
            result["knowledge_status"] = record.get("knowledge_status", "none")
            artifacts = result.get("artifacts", {})
            if artifacts.get("video_object"):
                result["video_url"] = await run_in_threadpool(story_repository.create_signed_asset_url, artifacts["video_object"])
            if artifacts.get("audio_object"):
                result["audio_url"] = await run_in_threadpool(story_repository.create_signed_asset_url, artifacts["audio_object"])
        return {
            "job_id": record["task_id"],
            "story_id": record["id"],
            "draft_id": record["draft_id"],
            "status": record["status"],
            "progress": record["progress"],
            "stage": record["stage"],
            "message": record["message"],
            "error": record.get("error"),
            "result": result,
        }
    except HTTPException:
        raise
    except Exception as error:
        raise _repo_error(error) from error


@router.get(
    "/stories",
    dependencies=[Depends(rate_limit_user_action("story-history", limit=30))],
)
async def list_stories(
    user: dict = Depends(get_current_user),
    limit: int = Query(default=25, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
):
    try:
        records = await run_in_threadpool(
            story_repository.list_stories,
            _user_id(user),
            limit=limit,
            offset=offset,
        )
        signing_slots = asyncio.Semaphore(8)

        async def signed_url(object_path: str) -> str:
            async with signing_slots:
                return await run_in_threadpool(
                    story_repository.create_signed_asset_url, object_path
                )

        async def enrich(record: dict[str, Any]) -> None:
            result = record.get("result") or {}
            result["sources"] = record.get("sources", [])
            result["knowledge_status"] = record.get("knowledge_status", "none")
            artifacts = result.get("artifacts", {})
            paths = {
                key: artifacts[object_key]
                for key, object_key in (
                    ("video_url", "video_object"),
                    ("audio_url", "audio_object"),
                )
                if artifacts.get(object_key)
            }
            if paths:
                urls = await asyncio.gather(
                    *(signed_url(path) for path in paths.values())
                )
                result.update(zip(paths, urls))
            record["result"] = result

        await asyncio.gather(*(enrich(record) for record in records))
        return records
    except Exception as error:
        raise _repo_error(error) from error


@router.get("/stories/{story_id}/quiz-results")
async def get_quiz_result(story_id: str, user: dict = Depends(get_current_user)):
    user_id = _user_id(user)
    try:
        record = await run_in_threadpool(story_repository.get_story_job, story_id, user_id)
        if not record:
            record = await run_in_threadpool(story_repository.get_story_by_id, story_id, user_id)
        if not record or record["status"] != "SUCCESS":
            raise HTTPException(status_code=404, detail="Completed story not found")
        if not (record.get("result") or {}).get("quiz"):
            raise HTTPException(status_code=404, detail="Completed story not found")
        saved = await run_in_threadpool(story_repository.get_quiz_result, record["id"], user_id)
        if not saved:
            return {"result": None}
        return {
            "result": {
                "answers": saved["answers"],
                "score": saved["score"],
                "total": saved["total"],
            }
        }
    except HTTPException:
        raise
    except Exception as error:
        raise _repo_error(error) from error


@router.post("/stories/{story_id}/quiz-results")
async def submit_quiz_result(
    story_id: str,
    submission: QuizSubmission,
    user: dict = Depends(get_current_user),
):
    user_id = _user_id(user)
    try:
        record = await run_in_threadpool(story_repository.get_story_job, story_id, user_id)
        if not record:
            # Story history IDs are UUIDs; task IDs remain accepted for direct result routes.
            record = await run_in_threadpool(story_repository.get_story_by_id, story_id, user_id)
        if not record or record["status"] != "SUCCESS":
            raise HTTPException(status_code=404, detail="Completed story not found")
        questions = (record.get("result") or {}).get("quiz", [])
        if not questions:
            raise HTTPException(status_code=404, detail="Completed story not found")
        if set(submission.answers) != {str(index) for index in range(1, len(questions) + 1)}:
            raise HTTPException(status_code=422, detail="Answer every quiz question")
        for index, question in enumerate(questions, start=1):
            option_ids = {option.get("id") for option in question.get("options", []) if isinstance(option, dict)}
            if not option_ids or submission.answers[str(index)] not in option_ids:
                raise HTTPException(status_code=422, detail="Choose a valid option for every quiz question")
        score = sum(
            submission.answers[str(index)] == question["correct_option"]
            for index, question in enumerate(questions, start=1)
        )
        saved = await run_in_threadpool(
            story_repository.save_quiz_result,
            {
                "story_id": record["id"],
                "user_id": user_id,
                "answers": submission.answers,
                "score": score,
                "total": len(questions),
            },
        )
        return {
            "answers": saved["answers"],
            "score": saved["score"],
            "total": saved["total"],
        }
    except HTTPException:
        raise
    except Exception as error:
        raise _repo_error(error) from error
