import asyncio
import importlib.util
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError


def modules():
    assert importlib.util.find_spec('app.domain.teacher') is not None, 'Teacher prep contracts are missing'
    from app.domain import teacher as models
    from app.api.v1 import teacher as routes
    return models, routes


def sample_content(kind):
    count = {'quiz': 10, 'exit_ticket': 3, 'homework': 5, 'test_paper': 10}.get(kind, 0)
    data = {
        'title': 'Fractions', 'instructions': 'Complete the tasks.',
        'objectives': ['Recognize fractions', 'Compare fractions', 'Explain a fraction'],
        'sections': [{'heading': 'Explore', 'body': 'Compare parts of a whole.'}],
        'questions': [{'prompt': f'Question {n}', 'choices': [], 'points': 2 if kind == 'test_paper' else 1} for n in range(count)],
        'answer_key': [{'question_number': n+1, 'answer': 'One half', 'explanation': 'One of two equal parts.'} for n in range(count)],
        'flashcards': [{'front': f'Fraction {n}', 'back': 'A part of a whole'} for n in range(12)] if kind == 'flashcards' else [],
        'teacher_notes': [{'heading': 'Review', 'body': 'Check the learner’s explanation.'}],
        'duration_minutes': 45,
    }
    if kind == 'presentation':
        data['slides'] = [{'title': f'Fractions {n}', 'key_points': ['A fraction names equal parts.'], 'speaker_notes': 'Explain the idea with an example.'} for n in range(8)]
    return data


@pytest.mark.parametrize('kind', ['objectives','lesson_plan','quiz','test_paper','flashcards','worksheet','exit_ticket','homework','presentation'])
def test_each_resource_preset_is_valid(kind):
    models, _ = modules()
    content = models.ResourceContent.model_validate(sample_content(kind))
    models.validate_content(kind, content, generated=True)


def test_presentation_resource_requires_ordered_slides_with_narration():
    models, _ = modules()
    resource = models.ResourceGenerate(kind='presentation', request_id=uuid4())
    content = models.ResourceContent.model_validate(sample_content('presentation'))
    models.validate_content(resource.kind, content, generated=True)
    assert len(content.slides) == 8
    assert content.slides[0].speaker_notes

    content.slides = []
    with pytest.raises(ValueError, match='slide'):
        models.validate_content('presentation', content, generated=True)


def test_edits_can_change_question_count_but_cannot_lose_answer_key():
    models, _ = modules()
    data = sample_content('quiz')
    data['questions'] = data['questions'][:2]
    data['answer_key'] = data['answer_key'][:2]
    content = models.ResourceContent.model_validate(data)
    models.validate_content('quiz', content)
    with pytest.raises(ValueError):
        models.validate_content('quiz', content, generated=True)
    data['answer_key'] = []
    with pytest.raises(ValueError):
        models.validate_content('quiz', models.ResourceContent.model_validate(data))


@pytest.mark.parametrize('grade', ['K','1','6','12'])
@pytest.mark.parametrize('language', ['en-US','ru-RU','kk-KZ'])
def test_lesson_accepts_school_grades_and_output_languages(grade, language):
    models, _ = modules()
    lesson = models.LessonInput(subject='math', grade=grade, language=language, topic=' Fractions ')
    assert lesson.topic == 'Fractions'
    with pytest.raises(ValidationError):
        models.LessonInput(subject='math', grade='13', topic='Fractions')
    with pytest.raises(ValidationError):
        models.LessonInput(subject='math', grade='6', topic='  ')


class MemoryRepository:
    def __init__(self):
        self.profiles = {'teacher': {'user_id': 'teacher'}}
        self.lessons = {'lesson': {'id': 'lesson', 'user_id': 'teacher', 'subject': 'math', 'grade': '6', 'language': 'kk-KZ', 'topic': 'Fractions', 'objectives': '', 'source_material': '', 'revision': 1}}
        self.resources = {}

    def profile(self, uid):
        return self.profiles.get(uid)

    def lesson(self, lid, uid):
        row = self.lessons.get(lid)
        return row if row and row['user_id'] == uid else None

    def resource(self, rid, uid):
        row = self.resources.get(rid)
        return row if row and row['user_id'] == uid else None

    def claim_resource(self, record):
        if record['id'] in self.resources:
            return None
        self.resources[record['id']] = record
        return record

    def finish_resource(self, rid, uid, changes):
        record = self.resource(rid, uid)
        if record is None:
            return None
        record.update(changes)
        return record

    def update_resource(self, rid, uid, revision, content):
        record = self.resource(rid, uid)
        if not record or record['revision'] != revision:
            return None
        record.update(content=content, revision=revision+1)
        return record

    def delete_resource(self, rid, uid):
        self.resources.pop(rid, None)

    def delete_lesson(self, lid, uid):
        self.lessons.pop(lid, None)


@pytest.fixture
def setup_routes(monkeypatch):
    models, routes = modules()
    repo = MemoryRepository()
    monkeypatch.setattr(routes, 'teacher_repository', repo)
    monkeypatch.setattr(routes.story_repository, 'is_user_deleting', lambda uid: False)
    async def inline(fn, *args, **kwargs):
        return fn(*args, **kwargs)
    monkeypatch.setattr(routes, 'run_in_threadpool', inline)
    monkeypatch.setattr(routes.teacher_generation_service, 'generate', lambda lesson, kind: models.ResourceContent.model_validate(sample_content(kind)))
    return models, routes, repo


def test_other_accounts_cannot_read_teacher_lessons(setup_routes):
    _, routes, _ = setup_routes
    with pytest.raises(HTTPException) as error:
        asyncio.run(routes.get_lesson('lesson', {'uid': 'other'}))
    assert error.value.status_code in (403, 404)


def test_generation_saves_original_context_and_duplicate_request_reuses_result(setup_routes):
    models, routes, repo = setup_routes
    request = models.ResourceGenerate(kind='quiz', request_id=uuid4())
    result = asyncio.run(routes.generate_resource('lesson', request, {'uid': 'teacher'}))
    assert result['status'] == 'ready'
    assert result['lesson_snapshot']['language'] == 'kk-KZ'
    assert len(result['content']['questions']) == 10
    repo.lessons['lesson']['topic'] = 'Decimals'
    again = asyncio.run(routes.generate_resource('lesson', request, {'uid': 'teacher'}))
    assert again['id'] == result['id']
    assert again['lesson_snapshot']['topic'] == 'Fractions'
    assert len(repo.resources) == 1


def test_stale_resource_edit_returns_conflict(setup_routes):
    models, routes, repo = setup_routes
    request = models.ResourceGenerate(kind='quiz', request_id=uuid4())
    record = asyncio.run(routes.generate_resource('lesson', request, {'uid': 'teacher'}))
    update = models.ResourceUpdate(revision=1, content=record['content'])
    assert asyncio.run(routes.edit_resource('lesson', record['id'], update, {'uid':'teacher'}))['revision'] == 2
    with pytest.raises(HTTPException) as error:
        asyncio.run(routes.edit_resource('lesson', record['id'], update, {'uid':'teacher'}))
    assert error.value.status_code == 409


def test_deleted_account_cannot_generate(setup_routes, monkeypatch):
    models, routes, repo = setup_routes
    monkeypatch.setattr(routes.story_repository, 'is_user_deleting', lambda uid: True)
    with pytest.raises(HTTPException) as error:
        asyncio.run(routes.generate_resource('lesson', models.ResourceGenerate(kind='quiz', request_id=uuid4()), {'uid':'teacher'}))
    assert error.value.status_code == 409
    assert not repo.resources


def test_provider_failure_leaves_retryable_failed_item(setup_routes, monkeypatch):
    models, routes, repo = setup_routes
    def fail(*_):
        raise RuntimeError('secret provider error')
    monkeypatch.setattr(routes.teacher_generation_service, 'generate', fail)
    with pytest.raises(HTTPException) as error:
        asyncio.run(routes.generate_resource('lesson', models.ResourceGenerate(kind='quiz', request_id=uuid4()), {'uid':'teacher'}))
    assert error.value.status_code == 503
    assert 'secret' not in error.value.detail
    assert next(iter(repo.resources.values()))['status'] == 'failed'


def test_generated_test_paper_requires_scoring_rubric():
    models, _ = modules()
    data = sample_content("test_paper")
    data["teacher_notes"] = []
    with pytest.raises(ValueError, match="rubric"):
        models.validate_content("test_paper", models.ResourceContent.model_validate(data), generated=True)


def video_resource_content():
    return {
        'script': {
            'title': 'Fractions in a Pizza',
            'hook': 'How can one pizza show many fractions?',
            'sections': [{'heading': 'Equal parts', 'summary': 'Fractions name equal parts.'}],
            'full_narration': 'Imagine a pizza divided into equal slices.',
            'estimated_duration_sec': 180,
        },
        'target_duration_sec': 180,
        'voice': 'female',
    }


def test_video_resource_model_accepts_supported_options():
    models, _ = modules()
    request = models.ResourceGenerate(kind='video', request_id=uuid4())
    content = models.VideoResourceContent.model_validate(video_resource_content())
    assert request.target_duration_sec == 180
    assert request.voice == 'female'
    assert content.script.title == 'Fractions in a Pizza'
    for duration in (180, 240, 300):
        assert models.VideoResourceContent.model_validate({
            **video_resource_content(), 'target_duration_sec': duration, 'voice': 'male'
        }).target_duration_sec == duration


def test_video_resource_model_rejects_invalid_options():
    models, _ = modules()
    with pytest.raises(ValidationError):
        models.ResourceGenerate(kind='video', request_id=uuid4(), target_duration_sec=200)
    with pytest.raises(ValidationError):
        models.VideoResourceContent.model_validate({**video_resource_content(), 'voice': 'robot'})


def test_resource_update_accepts_video_content():
    models, _ = modules()
    content = models.VideoResourceContent.model_validate(video_resource_content())
    update = models.ResourceUpdate(content=content, revision=1)
    assert update.content.script.title == 'Fractions in a Pizza'


def test_video_resource_generation_ignores_attached_documents(setup_routes, monkeypatch):
    models, routes, repo = setup_routes
    repo.lessons['lesson']['source_document_ids'] = ['source-1']
    repo.lessons['lesson']['objectives'] = 'Ignored objective.'
    repo.lessons['lesson']['source_material'] = 'Ignored pasted source.'
    generated = {}

    def generate(lesson, *, target_duration_sec, voice, user_id):
        generated.update(
            lesson=lesson, target_duration_sec=target_duration_sec,
            voice=voice, user_id=user_id,
        )
        return models.VideoResourceContent.model_validate(video_resource_content())

    monkeypatch.setattr(routes, 'teacher_video_generation_service', type('VideoService', (), {'generate': staticmethod(generate)})())
    monkeypatch.setattr(routes, 'build_context', lambda *_args: (_ for _ in ()).throw(AssertionError('documents must not be read')))
    monkeypatch.setattr(routes.teacher_generation_service, 'generate', lambda *_args: (_ for _ in ()).throw(AssertionError('generic resource generator must not run')))
    request = models.ResourceGenerate(
        kind='video', request_id=uuid4(), target_duration_sec=240, voice='male',
    )

    result = asyncio.run(routes.generate_resource('lesson', request, {'uid': 'teacher'}))

    assert result['status'] == 'ready'
    assert result['kind'] == 'video'
    assert result['content']['script']['title'] == 'Fractions in a Pizza'
    assert generated['target_duration_sec'] == 240
    assert generated['voice'] == 'male'
    assert generated['user_id'] == 'teacher'
    assert 'source_document_ids' not in result['lesson_snapshot']


def test_editing_video_script_invalidates_older_render_revision(setup_routes, monkeypatch):
    models, routes, _repo = setup_routes
    monkeypatch.setattr(routes.teacher_video_generation_service, 'generate', lambda *_args, **_kwargs: models.VideoResourceContent.model_validate(video_resource_content()))
    record = asyncio.run(routes.generate_resource(
        'lesson', models.ResourceGenerate(kind='video', request_id=uuid4()), {'uid': 'teacher'},
    ))
    invalidated = []
    monkeypatch.setattr(routes.story_repository, 'invalidate_teacher_video_renders', lambda *args: invalidated.append(args))
    update = models.ResourceUpdate(revision=1, content=record['content'])

    saved = asyncio.run(routes.edit_resource('lesson', record['id'], update, {'uid': 'teacher'}))

    assert saved['revision'] == 2
    assert invalidated == [(record['id'], 'teacher', 2)]


def test_deleting_video_resource_cancels_and_cleans_renders_first(setup_routes, monkeypatch):
    models, routes, repo = setup_routes
    monkeypatch.setattr(routes.teacher_video_generation_service, 'generate', lambda *_args, **_kwargs: models.VideoResourceContent.model_validate(video_resource_content()))
    record = asyncio.run(routes.generate_resource(
        'lesson', models.ResourceGenerate(kind='video', request_id=uuid4()), {'uid': 'teacher'},
    ))
    events = []
    monkeypatch.setattr(routes.story_repository, 'cancel_all_teacher_video_renders_for_resource', lambda *args: events.append(('cancel-all', args)))
    monkeypatch.setattr(routes.teacher_repository, 'delete_resource', lambda *args: events.append(('delete', args)))

    asyncio.run(routes.delete_resource('lesson', record['id'], {'uid': 'teacher'}))

    assert events[0] == ('cancel-all', (record['id'], 'teacher'))
    assert events[1][0] == 'delete'


def test_deleting_lesson_cancels_each_video_resource_render_first(setup_routes, monkeypatch):
    models, routes, repo = setup_routes
    monkeypatch.setattr(routes.teacher_video_generation_service, 'generate', lambda *_args, **_kwargs: models.VideoResourceContent.model_validate(video_resource_content()))
    record = asyncio.run(routes.generate_resource(
        'lesson', models.ResourceGenerate(kind='video', request_id=uuid4()), {'uid': 'teacher'},
    ))
    events = []
    monkeypatch.setattr(routes.teacher_repository, 'resources', lambda *_args: [record])
    monkeypatch.setattr(routes.story_repository, 'cancel_all_teacher_video_renders_for_resource', lambda *args: events.append(('cancel-all', args)))
    monkeypatch.setattr(routes.teacher_repository, 'delete_lesson', lambda *args: events.append(('delete', args)))

    asyncio.run(routes.delete_lesson('lesson', {'uid': 'teacher'}))

    assert events[0] == ('cancel-all', (record['id'], 'teacher'))
    assert events[1][0] == 'delete'

def test_stalled_resource_is_failed_on_read(monkeypatch):
    _, routes=modules()
    async def inline(fn, *args):
        return fn(*args)
    monkeypatch.setattr(routes, 'run_in_threadpool', inline)
    from datetime import datetime, timedelta, timezone
    row={'id':'r','lesson_id':'lesson','user_id':'teacher','status':'generating','updated_at':(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat()}
    monkeypatch.setattr(routes.teacher_repository,'resource',lambda *_args:row.copy())
    calls=[]
    monkeypatch.setattr(routes.teacher_repository,'expire_stalled_resource',lambda *args:calls.append(args) or {**row,'status':'failed'},raising=False)
    monkeypatch.setattr(routes.document_repository,'decorate',lambda row,_uid:row)
    result=asyncio.run(routes._resource('lesson','r','teacher'))
    assert result['status']=='failed'
    assert calls[0][:2]==('r','teacher')
