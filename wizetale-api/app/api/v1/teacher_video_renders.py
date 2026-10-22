"""Private asynchronous topic-video rendering for teacher lesson resources."""

import logging
from uuid import UUID, uuid4

import requests
from fastapi import APIRouter, Depends, HTTPException
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool
from starlette.responses import StreamingResponse

from app.api.dependencies import get_current_user, rate_limit_user_action
from app.api.v1 import teacher
from app.services.story_repository import story_repository
from app.services.teacher_repository import teacher_repository
from app.services.teacher_video_render import render_teacher_video_task

router = APIRouter(prefix="/teacher", tags=["teacher videos"])
logger = logging.getLogger(__name__)
teacher_video_render_repository = story_repository


def _public(row: dict) -> dict:
    return {
        key: row[key]
        for key in (
            "id", "status", "progress", "stage", "message",
            "resource_revision", "duration_sec",
        )
        if key in row
    }


async def _render_row(render_id: UUID, user_id: str) -> dict:
    row = await run_in_threadpool(
        teacher_video_render_repository.teacher_video_render,
        str(render_id), user_id,
    )
    if not row:
        raise HTTPException(404, "Teacher video not found.")

    visible = _public(row)
    visible["video_url"] = None
    resource = await run_in_threadpool(
        teacher_repository.resource, row["resource_id"], user_id,
    )
    if not resource:
        raise HTTPException(404, "Teacher video not found.")
    await teacher._lesson(resource["lesson_id"], user_id)
    is_current = bool(
        resource
        and resource.get("kind") == "video"
        and resource.get("status") == "ready"
        and resource.get("revision") == row.get("resource_revision")
    )
    object_path = row.get("video_object")
    if row.get("status") == "ready" and is_current and object_path:
        if not object_path.startswith(f"{user_id}/"):
            raise HTTPException(404, "Teacher video not found.")
        visible["video_url"] = await run_in_threadpool(
            story_repository.create_signed_asset_url, object_path,
        )
    elif row.get("status") == "ready" and not is_current:
        visible.update(
            status="cancelled", stage="cancelled",
            message="The saved script changed. Render the current version again.",
        )
    return visible


@router.post(
    "/lessons/{lesson_id}/resources/{resource_id}/video-renders",
    status_code=202,
    dependencies=[
        Depends(rate_limit_user_action("teacher-video-render", 3, window_seconds=3600))
    ],
)
async def start_teacher_video_render(
    lesson_id: UUID, resource_id: UUID, user=Depends(get_current_user)
):
    user_id = await teacher._uid(user)
    await teacher._lesson(lesson_id, user_id)
    resource = await teacher._resource(lesson_id, resource_id, user_id)
    if (
        resource.get("kind") != "video"
        or resource.get("status") != "ready"
        or not resource.get("content")
    ):
        raise HTTPException(409, "Save a ready video script before rendering.")

    active = await run_in_threadpool(
        teacher_video_render_repository.active_teacher_video_render,
        str(resource_id), user_id,
    )
    if active:
        return await _render_row(UUID(active["id"]), user_id)

    latest = await run_in_threadpool(
        teacher_video_render_repository.latest_teacher_video_render,
        str(resource_id), user_id,
    )
    if (
        latest and latest.get("status") == "ready"
        and latest.get("resource_revision") == resource["revision"]
    ):
        return await _render_row(UUID(latest["id"]), user_id)

    render_id = uuid4()
    record = {
        "id": str(render_id),
        "user_id": user_id,
        "resource_id": str(resource_id),
        "resource_revision": resource["revision"],
        "status": "queued",
        "progress": 0,
        "stage": "queued",
        "message": "Waiting to render your topic video.",
        "video_object": None,
        "duration_sec": None,
        "error": None,
    }
    try:
        saved = await run_in_threadpool(
            teacher_video_render_repository.create_teacher_video_render, record,
        )
    except requests.HTTPError as error:
        # A concurrent request can win the partial unique index after our read.
        active = await run_in_threadpool(
            teacher_video_render_repository.active_teacher_video_render,
            str(resource_id), user_id,
        )
        if active:
            return await _render_row(UUID(active["id"]), user_id)
        logger.warning("Could not create teacher video render (%s)", type(error).__name__)
        raise HTTPException(503, "The video render could not be queued. Please try again.") from error
    if not saved:
        active = await run_in_threadpool(
            teacher_video_render_repository.active_teacher_video_render,
            str(resource_id), user_id,
        )
        if active:
            return await _render_row(UUID(active["id"]), user_id)
        raise HTTPException(503, "The video render could not be queued. Please try again.")

    try:
        render_teacher_video_task.apply_async(
            args=[
                str(render_id), user_id, str(resource_id), resource["revision"],
                resource["content"], resource["lesson_snapshot"],
            ],
            task_id=str(render_id),
        )
    except Exception as error:
        await run_in_threadpool(
            teacher_video_render_repository.update_teacher_video_render,
            str(render_id), user_id,
            {
                "status": "failed", "stage": "failed",
                "message": "The video could not be queued. Please retry.",
                "error": "queue_failed",
            },
            active_only=True,
        )
        logger.warning("Could not queue teacher video render (%s)", type(error).__name__)
        raise HTTPException(503, "The video render could not be queued. Please try again.") from error
    return _public(saved)


@router.get("/lessons/{lesson_id}/resources/{resource_id}/video-renders")
async def latest_teacher_video_render(
    lesson_id: UUID, resource_id: UUID, user=Depends(get_current_user)
):
    user_id = await teacher._uid(user)
    await teacher._lesson(lesson_id, user_id)
    resource = await teacher._resource(lesson_id, resource_id, user_id)
    if resource.get("kind") != "video":
        raise HTTPException(404, "Video resource not found.")
    row = await run_in_threadpool(
        teacher_video_render_repository.latest_teacher_video_render,
        str(resource_id), user_id,
    )
    if not row:
        raise HTTPException(404, "The topic video has not been rendered yet.")
    return await _render_row(UUID(row["id"]), user_id)


@router.get("/video-renders/{render_id}")
async def get_teacher_video_render(render_id: UUID, user=Depends(get_current_user)):
    user_id = await teacher._uid(user)
    return await _render_row(render_id, user_id)


@router.get("/video-renders/{render_id}/video")
async def download_teacher_video(render_id: UUID, user=Depends(get_current_user)):
    user_id = await teacher._uid(user)
    row = await run_in_threadpool(
        teacher_video_render_repository.teacher_video_render,
        str(render_id), user_id,
    )
    if not row:
        raise HTTPException(404, "Teacher video not found.")
    resource = await run_in_threadpool(
        teacher_repository.resource, row["resource_id"], user_id,
    )
    if not resource:
        raise HTTPException(404, "Teacher video not found.")
    await teacher._lesson(resource["lesson_id"], user_id)
    object_path = row.get("video_object")
    if (
        row.get("status") != "ready"
        or not object_path
        or not object_path.startswith(f"{user_id}/")
    ):
        raise HTTPException(409, "The topic video is not ready to download.")
    if (
        not resource or resource.get("kind") != "video"
        or resource.get("status") != "ready"
        or resource.get("revision") != row.get("resource_revision")
    ):
        raise HTTPException(409, "The saved script changed. Render the current version again.")

    signed_url = await run_in_threadpool(
        story_repository.create_signed_asset_url, object_path,
    )
    upstream = await run_in_threadpool(requests.get, signed_url, stream=True, timeout=60)
    if not upstream.ok:
        upstream.close()
        raise HTTPException(503, "The topic video could not be downloaded.")

    def stream_video():
        for chunk in upstream.iter_content(chunk_size=1024 * 1024):
            if chunk:
                yield chunk

    headers = {
        "Content-Disposition": 'attachment; filename="fibonacci-topic-video.mp4"',
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
    }
    if upstream.headers.get("Content-Length"):
        headers["Content-Length"] = upstream.headers["Content-Length"]
    return StreamingResponse(
        stream_video(), media_type="video/mp4", headers=headers,
        background=BackgroundTask(upstream.close),
    )
