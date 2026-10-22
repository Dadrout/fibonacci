"""Asynchronous narrated video rendering for teacher slide decks."""

import logging
from uuid import UUID, uuid4

import requests
from fastapi import APIRouter, Depends, HTTPException
from starlette.background import BackgroundTask
from starlette.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from app.api.dependencies import get_current_user, rate_limit_user_action
from app.api.v1 import teacher
from app.celery_utils import celery_app
from app.services.story_repository import story_repository

router = APIRouter(prefix="/teacher", tags=["teacher presentations"])
logger = logging.getLogger(__name__)
teacher_presentation_repository = story_repository


def _public(row: dict) -> dict:
    return {key: value for key, value in row.items() if key != "user_id"}


async def _render_row(render_id: UUID, user_id: str) -> dict:
    row = await run_in_threadpool(
        teacher_presentation_repository.presentation_render, str(render_id), user_id
    )
    if not row:
        raise HTTPException(404, "Presentation video not found.")
    visible = _public(row)
    visible["video_url"] = None
    if row.get("status") == "ready" and row.get("video_object"):
        visible["video_url"] = await run_in_threadpool(
            story_repository.create_signed_asset_url, row["video_object"]
        )
    return visible


@router.post(
    "/lessons/{lesson_id}/resources/{resource_id}/render",
    status_code=202,
    dependencies=[
        Depends(
            rate_limit_user_action(
                "teacher-presentation-render", 3, window_seconds=3600
            )
        )
    ],
)
async def start_presentation_render(
    lesson_id: UUID, resource_id: UUID, user=Depends(get_current_user)
):
    user_id = await teacher._uid(user)
    await teacher._lesson(lesson_id, user_id)
    resource = await teacher._resource(lesson_id, resource_id, user_id)
    if (
        resource.get("kind") != "presentation"
        or resource.get("status") != "ready"
        or not resource.get("content")
    ):
        raise HTTPException(
            409, "Save a ready presentation before rendering its video."
        )

    active = await run_in_threadpool(
        teacher_presentation_repository.active_presentation_render,
        str(resource_id),
        user_id,
    )
    if active:
        return await _render_row(UUID(active["id"]), user_id)

    render_id = uuid4()
    record = {
        "id": str(render_id),
        "user_id": user_id,
        "resource_id": str(resource_id),
        "resource_revision": resource["revision"],
        "status": "queued",
        "progress": 0,
        "stage": "queued",
        "message": "Waiting to render your presentation.",
        "video_object": None,
        "duration_sec": None,
        "error": None,
    }
    saved = await run_in_threadpool(
        teacher_presentation_repository.create_presentation_render, record
    )
    if not saved:
        raise HTTPException(
            503, "The video render could not be queued. Please try again."
        )
    try:
        render_teacher_presentation_task.apply_async(
            args=[
                str(render_id),
                user_id,
                resource["content"],
                resource["lesson_snapshot"],
            ],
            task_id=str(render_id),
        )
    except Exception as error:
        await run_in_threadpool(
            teacher_presentation_repository.update_presentation_render,
            str(render_id),
            user_id,
            {
                "status": "failed",
                "stage": "failed",
                "message": "The video could not be queued. Please retry.",
                "error": "queue_failed",
            },
        )
        logger.warning(
            "Could not queue presentation video render (%s)", type(error).__name__
        )
        raise HTTPException(
            503, "The video render could not be queued. Please try again."
        ) from error
    return _public(saved)


@router.get("/lessons/{lesson_id}/resources/{resource_id}/render")
async def latest_presentation_render(
    lesson_id: UUID, resource_id: UUID, user=Depends(get_current_user)
):
    user_id = await teacher._uid(user)
    await teacher._lesson(lesson_id, user_id)
    resource = await teacher._resource(lesson_id, resource_id, user_id)
    if resource.get("kind") != "presentation":
        raise HTTPException(404, "Presentation not found.")
    row = await run_in_threadpool(
        teacher_presentation_repository.latest_presentation_render,
        str(resource_id),
        user_id,
    )
    if not row:
        raise HTTPException(404, "Presentation video has not been rendered yet.")
    return await _render_row(UUID(row["id"]), user_id)


@router.get("/presentation-renders/{render_id}")
async def get_presentation_render(render_id: UUID, user=Depends(get_current_user)):
    user_id = await teacher._uid(user)
    return await _render_row(render_id, user_id)


@router.get("/presentation-renders/{render_id}/video")
async def download_presentation_video(render_id: UUID, user=Depends(get_current_user)):
    user_id = await teacher._uid(user)
    row = await run_in_threadpool(
        teacher_presentation_repository.presentation_render, str(render_id), user_id
    )
    if not row:
        raise HTTPException(404, "Presentation video not found.")
    if row.get("status") != "ready" or not row.get("video_object"):
        raise HTTPException(409, "The presentation video is not ready to download.")
    signed_url = await run_in_threadpool(
        story_repository.create_signed_asset_url, row["video_object"]
    )
    upstream = await run_in_threadpool(
        requests.get, signed_url, stream=True, timeout=60
    )
    if not upstream.ok:
        upstream.close()
        raise HTTPException(503, "The presentation video could not be downloaded.")

    def stream_video():
        for chunk in upstream.iter_content(chunk_size=1024 * 1024):
            if chunk:
                yield chunk

    headers = {
        "Content-Disposition": 'attachment; filename="fibonacci-presentation.mp4"',
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
    }
    if upstream.headers.get("Content-Length"):
        headers["Content-Length"] = upstream.headers["Content-Length"]
    return StreamingResponse(
        stream_video(),
        media_type="video/mp4",
        headers=headers,
        background=BackgroundTask(upstream.close),
    )


from app.services.teacher_presentation_video import render_teacher_presentation_task
