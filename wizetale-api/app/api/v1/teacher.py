"""Private teacher preparation API; teacher onboarding is self-service."""
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from starlette.concurrency import run_in_threadpool

from app.api.dependencies import get_current_user, rate_limit_user_action
from app.core.usage_context import generation_id
from app.domain.teacher import LessonInput, LessonUpdate, ResourceGenerate, ResourceUpdate, validate_content
from app.services.story_repository import story_repository
from app.services.presentation_visuals import presentation_visual_service, text_content
from app.services.teacher_repository import teacher_repository
from app.services.teacher_generation import teacher_generation_service
from app.services.document_repository import document_repository
from app.services.teacher_retrieval import build_context, InsufficientSources
from app.services.teacher_video_generation import (
    InvalidTeacherVideoTopic,
    teacher_video_generation_service,
)

router = APIRouter(prefix='/teacher', tags=['teacher'])
logger = logging.getLogger(__name__)


async def _uid(user, *, teacher=True):
    uid = user.get('uid')
    if not uid:
        raise HTTPException(401, 'Sign in to continue.')
    if await run_in_threadpool(story_repository.is_user_deleting, uid):
        raise HTTPException(409, 'Account deletion is in progress.')
    if teacher and not await run_in_threadpool(teacher_repository.profile, uid):
        raise HTTPException(403, 'Enable teacher mode to prepare lessons.')
    return uid


async def _lesson(lid, uid):
    lesson = await run_in_threadpool(teacher_repository.lesson, str(lid), uid)
    if not lesson:
        raise HTTPException(404, 'Lesson not found.')
    return lesson


async def _resource(lid, rid, uid):
    row = await run_in_threadpool(teacher_repository.resource, str(rid), uid)
    if not row or row['lesson_id'] != str(lid):
        raise HTTPException(404, 'Resource not found.')
    row = await _recover_resource(row, uid)
    row = await run_in_threadpool(document_repository.decorate, row, uid)
    return await run_in_threadpool(presentation_visual_service.decorate, row, 'teacher')


async def _recover_resource(row, uid):
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
    updated = row.get('updated_at')
    if row['status'] == 'generating' and updated and datetime.fromisoformat(updated.replace('Z', '+00:00')) < cutoff:
        expired = await run_in_threadpool(teacher_repository.expire_stalled_resource, row['id'], uid, cutoff.isoformat())
        if expired:
            return expired
        latest = await run_in_threadpool(teacher_repository.resource, row['id'], uid)
        if not latest:
            raise HTTPException(404, 'Resource not found.')
        return latest
    return row


@router.get('/profile')
async def get_profile(user=Depends(get_current_user)):
    uid = await _uid(user, teacher=False)
    profile = await run_in_threadpool(teacher_repository.profile, uid)
    return {'teacher_enabled': bool(profile)}


@router.post('/profile', dependencies=[Depends(rate_limit_user_action('teacher-onboarding', 10))])
async def enable_teacher(user=Depends(get_current_user)):
    uid = await _uid(user, teacher=False)
    await run_in_threadpool(teacher_repository.enable_teacher, uid)
    return {'teacher_enabled': True}


@router.get('/lessons')
async def list_lessons(limit: int = Query(25, ge=1, le=50), offset: int = Query(0, ge=0), user=Depends(get_current_user)):
    uid = await _uid(user)
    return await run_in_threadpool(teacher_repository.lessons, uid, limit, offset)


@router.post('/lessons', status_code=201, dependencies=[Depends(rate_limit_user_action('teacher-lesson-create', 20))])
async def create_lesson(lesson: LessonInput, user=Depends(get_current_user)):
    uid = await _uid(user)
    return await run_in_threadpool(teacher_repository.create_lesson, {'id': str(uuid4()), 'user_id': uid, **lesson.model_dump(), 'revision': 1})


@router.get('/lessons/{lesson_id}')
async def get_lesson(lesson_id: UUID, user=Depends(get_current_user)):
    return await _lesson(lesson_id, await _uid(user))


@router.patch('/lessons/{lesson_id}')
async def edit_lesson(lesson_id: UUID, update: LessonUpdate, user=Depends(get_current_user)):
    uid = await _uid(user)
    await _lesson(lesson_id, uid)
    saved = await run_in_threadpool(teacher_repository.update_lesson, str(lesson_id), uid, update.revision, update.lesson.model_dump())
    if not saved:
        raise HTTPException(409, 'This lesson changed. Reload before saving.')
    return saved


@router.delete('/lessons/{lesson_id}', status_code=204)
async def delete_lesson(lesson_id: UUID, user=Depends(get_current_user)):
    uid = await _uid(user)
    await _lesson(lesson_id, uid)
    resources = await run_in_threadpool(teacher_repository.resources, str(lesson_id), uid, 1000, 0)
    for row in resources:
        if row.get('kind') == 'video':
            await run_in_threadpool(
                story_repository.cancel_all_teacher_video_renders_for_resource,
                row['id'], uid,
            )
        await run_in_threadpool(presentation_visual_service.cleanup, row, 'teacher')
    await run_in_threadpool(teacher_repository.delete_lesson, str(lesson_id), uid)
    return Response(status_code=204)


@router.get('/lessons/{lesson_id}/resources')
async def list_resources(lesson_id: UUID, limit: int = Query(25, ge=1, le=50), offset: int = Query(0, ge=0), user=Depends(get_current_user)):
    uid = await _uid(user)
    await _lesson(lesson_id, uid)
    rows = await run_in_threadpool(teacher_repository.resources, str(lesson_id), uid, limit, offset)
    return [await run_in_threadpool(presentation_visual_service.decorate, await run_in_threadpool(document_repository.decorate, await _recover_resource(row, uid), uid), 'teacher') for row in rows]


@router.post('/lessons/{lesson_id}/resources', dependencies=[Depends(rate_limit_user_action('teacher-resource-generate', 5))])
async def generate_resource(lesson_id: UUID, request: ResourceGenerate, user=Depends(get_current_user)):
    uid = await _uid(user)
    lesson = await _lesson(lesson_id, uid)
    rid = str(request.request_id)
    record = {'id': rid, 'user_id': uid, 'lesson_id': str(lesson_id), 'kind': request.kind, 'status': 'generating', 'content': None, 'revision': 1, 'lesson_snapshot': LessonInput.model_validate({key: lesson[key] for key in LessonInput.model_fields}).model_dump()}
    source_ids = lesson.get('source_document_ids', []) if request.kind != 'video' else []
    if source_ids:
        record['lesson_snapshot']['source_document_ids'] = source_ids
    claim = await run_in_threadpool(teacher_repository.claim_resource, record)
    if not claim:
        prior = await _resource(lesson_id, rid, uid)
        if prior['kind'] != request.kind:
            raise HTTPException(409, 'This request belongs to a different resource.')
        if prior['status'] == 'ready':
            return prior
        raise HTTPException(409, 'This request is in progress or failed. Open the lesson or generate a new resource.')
    token = generation_id.set(rid)
    try:
        if request.kind == 'video':
            content = await run_in_threadpool(
                teacher_video_generation_service.generate,
                record['lesson_snapshot'],
                target_duration_sec=request.target_duration_sec,
                voice=request.voice,
                user_id=uid,
            )
            await _uid(user)
            saved = await run_in_threadpool(
                teacher_repository.finish_resource,
                rid, uid, {
                    'content': text_content(content.model_dump(mode='json')),
                    'status': 'ready',
                },
            )
        elif source_ids:
            passages = await run_in_threadpool(build_context, record['lesson_snapshot'], uid, document_repository)
            content, provenance = await run_in_threadpool(teacher_generation_service.generate, record['lesson_snapshot'], request.kind, passages)
            await _uid(user)
            saved = await run_in_threadpool(document_repository.finish_resource, rid, uid, source_ids, text_content(content.model_dump()), provenance)
        else:
            content = await run_in_threadpool(teacher_generation_service.generate, record['lesson_snapshot'], request.kind)
            await _uid(user)
            saved = await run_in_threadpool(teacher_repository.finish_resource, rid, uid, {'content': text_content(content.model_dump()), 'status': 'ready'})
        if not saved:
            raise HTTPException(409, 'The lesson or resource was removed during generation.')
        await run_in_threadpool(presentation_visual_service.queue, saved, 'teacher')
        return await run_in_threadpool(presentation_visual_service.decorate, saved, 'teacher')
    except Exception as error:
        try:
            await run_in_threadpool(teacher_repository.finish_resource, rid, uid, {'status': 'failed'})
        except Exception:
            logger.warning('Could not save teacher generation failure (%s)', type(error).__name__)
        if isinstance(error, InsufficientSources):
            raise HTTPException(422, str(error)) from error
        if isinstance(error, InvalidTeacherVideoTopic):
            raise HTTPException(422, str(error)) from error
        if isinstance(error, HTTPException):
            raise
        logger.warning('Teacher resource generation failed (%s)', type(error).__name__)
        raise HTTPException(503, 'Resource generation is temporarily unavailable. Please try again.') from error
    finally:
        generation_id.reset(token)


@router.get('/lessons/{lesson_id}/resources/{resource_id}')
async def get_resource(lesson_id: UUID, resource_id: UUID, user=Depends(get_current_user)):
    return await _resource(lesson_id, resource_id, await _uid(user))


@router.patch('/lessons/{lesson_id}/resources/{resource_id}')
async def edit_resource(lesson_id: UUID, resource_id: UUID, update: ResourceUpdate, user=Depends(get_current_user)):
    uid = await _uid(user)
    row = await _resource(lesson_id, resource_id, uid)
    try:
        validate_content(row['kind'], update.content)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    saved = await run_in_threadpool(teacher_repository.update_resource, str(resource_id), uid, update.revision, text_content(update.content.model_dump()))
    if not saved:
        raise HTTPException(409, 'This resource changed. Reload before saving.')
    if row.get('kind') == 'video':
        await run_in_threadpool(
            story_repository.invalidate_teacher_video_renders,
            str(resource_id), uid, saved['revision'],
        )
    return await run_in_threadpool(presentation_visual_service.decorate, saved, 'teacher')


@router.delete('/lessons/{lesson_id}/resources/{resource_id}', status_code=204)
async def delete_resource(lesson_id: UUID, resource_id: UUID, user=Depends(get_current_user)):
    uid = await _uid(user)
    row = await _resource(lesson_id, resource_id, uid)
    if row.get('kind') == 'video':
        await run_in_threadpool(
            story_repository.cancel_all_teacher_video_renders_for_resource,
            str(resource_id), uid,
        )
    await run_in_threadpool(presentation_visual_service.cleanup, row, 'teacher')
    await run_in_threadpool(teacher_repository.delete_resource, str(resource_id), uid)
    return Response(status_code=204)


@router.post('/lessons/{lesson_id}/resources/{resource_id}/slides/{slide_number}/visual', dependencies=[Depends(rate_limit_user_action('teacher-visual-retry', 5))])
async def retry_teacher_visual(lesson_id: UUID, resource_id: UUID, slide_number: int, user=Depends(get_current_user)):
    row = await _resource(lesson_id, resource_id, await _uid(user))
    try:
        await run_in_threadpool(presentation_visual_service.retry, row, 'teacher', slide_number - 1)
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
    return await run_in_threadpool(presentation_visual_service.decorate, row, 'teacher')


@router.delete('/lessons/{lesson_id}/resources/{resource_id}/slides/{slide_number}/visual')
async def remove_teacher_visual(lesson_id: UUID, resource_id: UUID, slide_number: int, user=Depends(get_current_user)):
    row = await _resource(lesson_id, resource_id, await _uid(user))
    try:
        await run_in_threadpool(presentation_visual_service.remove, row, 'teacher', slide_number - 1)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    return await run_in_threadpool(presentation_visual_service.decorate, row, 'teacher')
