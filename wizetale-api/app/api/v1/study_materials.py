"""Authenticated learner study-material API."""

from copy import deepcopy
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import Field
from starlette.concurrency import run_in_threadpool

from app.api.dependencies import get_current_user, rate_limit_user_action
from app.core.usage_context import generation_id
from app.domain.study_materials import (
    StudyMaterialContent,
    StudyMaterialGenerate,
    StudyMaterialUpdate,
    score_quiz,
    validate_study_content,
)
from app.domain.teacher import StrictModel
from app.services.story_repository import story_repository
from app.services.presentation_visuals import presentation_visual_service, text_content
from app.services.study_material_generation import study_generation_service
from app.services.study_material_repository import study_material_repository

router = APIRouter(prefix='/study-materials', tags=['study materials'])


class QuizCheck(StrictModel):
    answers: dict[str, str] = Field(min_length=1, max_length=10)


def _public_record(row: dict) -> dict:
    visible = presentation_visual_service.decorate(row, 'student')
    content = visible.get('content')
    if visible.get('kind') == 'quiz' and isinstance(content, dict):
        for question in content.get('questions', []):
            question.pop('correct_option', None)
    return visible


async def _uid(user: dict) -> str:
    user_id = user.get('uid')
    if not user_id:
        raise HTTPException(401, 'Sign in to continue.')
    if await run_in_threadpool(story_repository.is_user_deleting, user_id):
        raise HTTPException(409, 'Account deletion is in progress.')
    return user_id


async def _material(material_id: UUID, user_id: str) -> dict:
    row = await run_in_threadpool(study_material_repository.material, str(material_id), user_id)
    if not row:
        raise HTTPException(404, 'Study material not found.')
    return row


@router.get('')
async def list_study_materials(
    limit: int = Query(25, ge=1, le=50),
    offset: int = Query(0, ge=0),
    user=Depends(get_current_user),
):
    rows = await run_in_threadpool(study_material_repository.materials, await _uid(user), limit, offset)
    return [_public_record(row) for row in rows]


@router.post('', status_code=201, dependencies=[Depends(rate_limit_user_action('study-material-generate', 5))])
async def generate_study_material(request: StudyMaterialGenerate, user=Depends(get_current_user)):
    user_id = await _uid(user)
    material_id = str(request.request_id)
    record = {
        'id': material_id,
        'user_id': user_id,
        'kind': request.kind,
        'status': 'generating',
        'subject': request.context.subject,
        'grade': request.context.grade,
        'topic': request.context.topic,
        'language': request.context.language,
        'context': request.context.model_dump(),
        'content': None,
        'revision': 1,
    }
    claimed = await run_in_threadpool(study_material_repository.claim_material, record)
    if not claimed:
        previous = await run_in_threadpool(study_material_repository.material, material_id, user_id)
        if not previous or previous['kind'] != request.kind:
            raise HTTPException(409, 'This request cannot be reused. Start a new generation.')
        if previous['status'] == 'ready':
            return _public_record(previous)
        raise HTTPException(409, 'This request is already in progress or failed. Start a new generation.')

    token = generation_id.set(material_id)
    try:
        content = await run_in_threadpool(study_generation_service.generate, request.context, request.kind)
        await _uid(user)
        saved = await run_in_threadpool(
            study_material_repository.finish_material,
            material_id,
            user_id,
            {'content': text_content(content.model_dump(mode='json')), 'status': 'ready'},
        )
        if not saved:
            raise HTTPException(409, 'The study material was removed during generation.')
        await run_in_threadpool(presentation_visual_service.queue, saved, 'student')
        return _public_record(saved)
    except HTTPException:
        raise
    except Exception as error:
        try:
            await run_in_threadpool(study_material_repository.finish_material, material_id, user_id, {'status': 'failed'})
        except Exception:
            pass
        raise HTTPException(503, 'Study material generation is temporarily unavailable. Please try again.') from error
    finally:
        generation_id.reset(token)


@router.get('/{material_id}')
async def get_study_material(material_id: UUID, user=Depends(get_current_user)):
    return _public_record(await _material(material_id, await _uid(user)))


@router.patch('/{material_id}')
async def edit_study_material(
    material_id: UUID,
    update: StudyMaterialUpdate,
    user=Depends(get_current_user),
):
    user_id = await _uid(user)
    row = await _material(material_id, user_id)
    try:
        validate_study_content(row['kind'], update.content)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    saved = await run_in_threadpool(
        study_material_repository.update_material,
        str(material_id), user_id, update.revision, text_content(update.content.model_dump(mode='json')),
    )
    if not saved:
        raise HTTPException(409, 'This study material changed. Reload before saving.')
    return _public_record(saved)


@router.delete('/{material_id}', status_code=204)
async def delete_study_material(material_id: UUID, user=Depends(get_current_user)):
    user_id = await _uid(user)
    row = await _material(material_id, user_id)
    await run_in_threadpool(presentation_visual_service.cleanup, row, 'student')
    await run_in_threadpool(study_material_repository.delete_material, str(material_id), user_id)
    return Response(status_code=204)


@router.post('/{material_id}/check')
async def check_study_quiz(material_id: UUID, check: QuizCheck, user=Depends(get_current_user)):
    row = await _material(material_id, await _uid(user))
    if row['kind'] != 'quiz' or row.get('status') != 'ready':
        raise HTTPException(409, 'This study material is not a ready quiz.')
    content = StudyMaterialContent.model_validate(row['content'])
    try:
        return score_quiz(content, check.answers)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@router.post('/{material_id}/slides/{slide_number}/visual', dependencies=[Depends(rate_limit_user_action('study-visual-retry', 5))])
async def retry_study_visual(material_id: UUID, slide_number: int, user=Depends(get_current_user)):
    row = await _material(material_id, await _uid(user))
    try:
        await run_in_threadpool(presentation_visual_service.retry, row, 'student', slide_number - 1)
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
    return _public_record(row)


@router.delete('/{material_id}/slides/{slide_number}/visual')
async def remove_study_visual(material_id: UUID, slide_number: int, user=Depends(get_current_user)):
    row = await _material(material_id, await _uid(user))
    try:
        await run_in_threadpool(presentation_visual_service.remove, row, 'student', slide_number - 1)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    return _public_record(row)
