import asyncio
from uuid import uuid4

import pytest
from fastapi import HTTPException


class MemoryRepository:
    def __init__(self):
        self.lesson = {'id': 'lesson', 'user_id': 'teacher'}
        self.resource = {
            'id': 'resource', 'lesson_id': 'lesson', 'user_id': 'teacher',
            'kind': 'video', 'status': 'ready', 'revision': 4,
            'lesson_snapshot': {'subject': 'science', 'grade': '4', 'topic': 'Rain', 'language': 'en-US'},
            'content': {
                'script': {
                    'title': 'Rain', 'hook': 'Clouds gather.', 'sections': [],
                    'full_narration': 'Rain falls.', 'estimated_duration_sec': 180,
                },
                'target_duration_sec': 180, 'voice': 'female',
            },
        }
        self.renders = {}

    def teacher_video_render(self, render_id, user_id):
        row = self.renders.get(render_id)
        return row if row and row['user_id'] == user_id else None

    def active_teacher_video_render(self, resource_id, user_id):
        return next((row for row in self.renders.values()
                     if row['resource_id'] == resource_id and row['user_id'] == user_id
                     and row['status'] in {'queued', 'processing'}), None)

    def latest_teacher_video_render(self, resource_id, user_id):
        rows = [row for row in self.renders.values()
                if row['resource_id'] == resource_id and row['user_id'] == user_id
                and row['status'] != 'cancelled']
        return rows[-1] if rows else None

    def create_teacher_video_render(self, row):
        self.renders[row['id']] = row
        return row

    def update_teacher_video_render(self, render_id, user_id, changes, *, active_only=False):
        row = self.teacher_video_render(render_id, user_id)
        if active_only and (not row or row['status'] not in {'queued', 'processing'}):
            return None
        if row:
            row.update(changes)
        return row


@pytest.fixture
def setup_routes(monkeypatch):
    from app.api.v1 import teacher_video_renders as routes

    repo = MemoryRepository()
    monkeypatch.setattr(routes, 'teacher_video_render_repository', repo)
    monkeypatch.setattr(routes.teacher.teacher_repository, 'profile', lambda uid: {'user_id': uid} if uid == 'teacher' else None)
    monkeypatch.setattr(routes.teacher.teacher_repository, 'lesson', lambda lid, uid: repo.lesson if lid == 'lesson' and uid == 'teacher' else None)
    monkeypatch.setattr(routes.teacher.teacher_repository, 'resource', lambda rid, uid: repo.resource if rid == 'resource' and uid == 'teacher' else None)
    monkeypatch.setattr(routes.teacher.document_repository, 'decorate', lambda row, _uid: row)
    monkeypatch.setattr(routes.story_repository, 'is_user_deleting', lambda _uid: False)
    monkeypatch.setattr(routes.story_repository, 'create_signed_asset_url', lambda path: f'https://media.example/{path}')

    async def inline(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    monkeypatch.setattr(routes, 'run_in_threadpool', inline)
    monkeypatch.setattr(routes.teacher, 'run_in_threadpool', inline)

    class Task:
        def __init__(self):
            self.calls = []

        def apply_async(self, **kwargs):
            self.calls.append(kwargs)

    task = Task()
    monkeypatch.setattr(routes, 'render_teacher_video_task', task)
    return routes, repo, task


def test_start_teacher_video_render_returns_active_job(setup_routes):
    routes, repo, task = setup_routes
    render_id = str(uuid4())
    repo.renders[render_id] = {
        'id': render_id, 'user_id': 'teacher', 'resource_id': 'resource',
        'resource_revision': 4, 'status': 'processing', 'progress': 46,
        'stage': 'images', 'message': 'Drawing scenes.', 'video_object': None,
    }

    result = asyncio.run(routes.start_teacher_video_render('lesson', 'resource', {'uid': 'teacher'}))

    assert result['id'] == render_id
    assert result['status'] == 'processing'
    assert result['progress'] == 46
    assert not task.calls


def test_start_teacher_video_render_retries_after_failure(setup_routes):
    routes, repo, task = setup_routes
    repo.renders[str(uuid4())] = {
        'id': str(uuid4()), 'user_id': 'teacher', 'resource_id': 'resource',
        'resource_revision': 4, 'status': 'failed', 'progress': 0,
        'stage': 'failed', 'message': 'Retry available.', 'video_object': None,
    }

    result = asyncio.run(routes.start_teacher_video_render('lesson', 'resource', {'uid': 'teacher'}))

    assert result['status'] == 'queued'
    assert result['resource_revision'] == 4
    assert task.calls[0]['args'][1:4] == ['teacher', 'resource', 4]


def test_start_teacher_video_render_recovers_unique_index_race(setup_routes, monkeypatch):
    import requests

    routes, repo, task = setup_routes
    render_id = str(uuid4())
    active = {
        'id': render_id, 'user_id': 'teacher', 'resource_id': 'resource',
        'resource_revision': 4, 'status': 'processing', 'progress': 52,
        'stage': 'images', 'message': 'Making scenes.', 'video_object': None,
    }
    checks = iter([None, active])
    def find_active(*_args):
        found = next(checks)
        if found:
            repo.renders[found['id']] = found
        return found
    monkeypatch.setattr(repo, 'active_teacher_video_render', find_active)
    monkeypatch.setattr(repo, 'create_teacher_video_render', lambda *_args: (_ for _ in ()).throw(requests.HTTPError('unique index')))

    result = asyncio.run(routes.start_teacher_video_render('lesson', 'resource', {'uid': 'teacher'}))

    assert result['id'] == render_id
    assert result['status'] == 'processing'
    assert result['progress'] == 52
    assert not task.calls


def test_teacher_video_render_routes_enforce_teacher_and_resource_ownership(setup_routes):
    routes, repo, task = setup_routes
    render_id = str(uuid4())
    repo.renders[render_id] = {
        'id': render_id, 'user_id': 'teacher', 'resource_id': 'resource',
        'resource_revision': 4, 'status': 'queued', 'progress': 0,
        'stage': 'queued', 'message': 'Waiting.', 'video_object': None,
    }

    with pytest.raises(HTTPException) as error:
        asyncio.run(routes.start_teacher_video_render('lesson', 'resource', {'uid': 'other'}))
    assert error.value.status_code in (403, 404)
    with pytest.raises(HTTPException) as error:
        asyncio.run(routes.get_teacher_video_render(render_id, {'uid': 'other'}))
    assert error.value.status_code in (403, 404)
    with pytest.raises(HTTPException) as error:
        asyncio.run(routes.download_teacher_video(render_id, {'uid': 'other'}))
    assert error.value.status_code in (403, 404)
    repo.resource['lesson_id'] = 'deleted-lesson'
    with pytest.raises(HTTPException) as error:
        asyncio.run(routes.get_teacher_video_render(render_id, {'uid': 'teacher'}))
    assert error.value.status_code == 404
    assert not task.calls


def test_video_download_rejects_stale_resource_revision(setup_routes):
    routes, repo, _task = setup_routes
    render_id = str(uuid4())
    repo.resource['revision'] = 5
    repo.renders[render_id] = {
        'id': render_id, 'user_id': 'teacher', 'resource_id': 'resource',
        'resource_revision': 4, 'status': 'ready', 'progress': 100,
        'stage': 'complete', 'message': 'Ready.',
        'video_object': f'teacher/{render_id}/video.mp4', 'duration_sec': 180,
    }

    with pytest.raises(HTTPException) as error:
        asyncio.run(routes.download_teacher_video(render_id, {'uid': 'teacher'}))

    assert error.value.status_code == 409


def test_ready_teacher_video_render_returns_signed_playback_and_download(monkeypatch, setup_routes):
    routes, repo, _task = setup_routes
    render_id = str(uuid4())
    repo.renders[render_id] = {
        'id': render_id, 'user_id': 'teacher', 'resource_id': 'resource',
        'resource_revision': 4, 'status': 'ready', 'progress': 100,
        'stage': 'complete', 'message': 'Ready.',
        'video_object': f'teacher/{render_id}/video.mp4', 'duration_sec': 180,
    }

    playback = asyncio.run(routes.get_teacher_video_render(render_id, {'uid': 'teacher'}))

    assert playback['video_url'] == f'https://media.example/teacher/{render_id}/video.mp4'
    assert playback['duration_sec'] == 180

    class Response:
        ok = True
        headers = {'Content-Length': '3'}

        def iter_content(self, chunk_size):
            assert chunk_size == 1024 * 1024
            yield b'mp4'

        def close(self):
            return None

    monkeypatch.setattr(routes.requests, 'get', lambda *_args, **_kwargs: Response())
    download = asyncio.run(routes.download_teacher_video(render_id, {'uid': 'teacher'}))
    assert download.headers['content-disposition'].startswith('attachment;')
    assert download.media_type == 'video/mp4'
    assert download.headers['cache-control'] == 'private, no-store'


def test_teacher_video_render_suppresses_stale_playback_url(setup_routes):
    routes, repo, _task = setup_routes
    render_id = str(uuid4())
    repo.resource['revision'] = 5
    repo.renders[render_id] = {
        'id': render_id, 'user_id': 'teacher', 'resource_id': 'resource',
        'resource_revision': 4, 'status': 'ready', 'progress': 100,
        'stage': 'complete', 'message': 'Ready.',
        'video_object': f'teacher/{render_id}/video.mp4', 'duration_sec': 180,
    }

    playback = asyncio.run(routes.get_teacher_video_render(render_id, {'uid': 'teacher'}))

    assert playback['status'] == 'cancelled'
    assert playback['video_url'] is None
