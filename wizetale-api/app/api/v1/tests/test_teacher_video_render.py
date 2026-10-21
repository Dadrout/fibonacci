from app.services.story_repository import SupabaseStoryRepository


class Repository(SupabaseStoryRepository):
    def __init__(self):
        super().__init__()
        self.calls = []
        self.rows = []
        self.deleted = []

    def _request(self, method, table, *, params=None, payload=None, prefer=None):
        self.calls.append((method, table, params, payload, prefer))
        if method == 'GET':
            return self.rows
        return self.rows

    def delete_asset(self, path):
        self.deleted.append(path)


def test_teacher_video_render_queries_filter_by_owner():
    repo = Repository()

    repo.create_teacher_video_render({'id': 'render-1'})
    repo.teacher_video_render('render-1', 'teacher-1')
    repo.active_teacher_video_render('resource-1', 'teacher-1')
    repo.latest_teacher_video_render('resource-1', 'teacher-1')
    repo.update_teacher_video_render('render-1', 'teacher-1', {'progress': 50})
    repo.list_active_teacher_video_renders('teacher-1')

    assert all(call[1] == 'teacher_video_renders' for call in repo.calls)
    assert repo.calls[1][2]['id'] == 'eq.render-1'
    assert repo.calls[1][2]['user_id'] == 'eq.teacher-1'
    assert repo.calls[2][2]['resource_id'] == 'eq.resource-1'
    assert repo.calls[2][2]['user_id'] == 'eq.teacher-1'
    assert repo.calls[4][2]['id'] == 'eq.render-1'
    assert repo.calls[4][2]['user_id'] == 'eq.teacher-1'
    assert repo.calls[5][2]['user_id'] == 'eq.teacher-1'


def test_active_teacher_video_render_unique_index_rejects_duplicate():
    from pathlib import Path

    migration = (Path(__file__).parents[5] / 'supabase' / 'teacher_video_renders.sql').read_text()

    assert 'teacher_video_renders_one_active_resource' in migration
    assert "where status in ('queued','processing')" in migration
    assert "starts_with(video_object,user_id::text || '/')" in migration


def test_latest_teacher_video_render_is_owner_scoped():
    repo = Repository()

    repo.latest_teacher_video_render('resource-1', 'teacher-2')

    params = repo.calls[-1][2]
    assert params['resource_id'] == 'eq.resource-1'
    assert params['user_id'] == 'eq.teacher-2'
    assert params['status'] == 'not.eq.cancelled'


def test_invalidating_teacher_video_renders_cancels_and_deletes_assets():
    repo = Repository()
    repo.rows = [
        {'id': 'r1', 'video_object': 'teacher-1/r1/video.mp4'},
        {'id': 'r2', 'video_object': 'other-user/r2/video.mp4'},
        {'id': 'r3', 'video_object': None},
    ]

    result = repo.invalidate_teacher_video_renders('resource-1', 'teacher-1', 5)

    assert result == 3
    assert repo.deleted == ['teacher-1/r1/video.mp4']
    cancellation = next(
        call for call in repo.calls if call[3] and call[3].get('status') == 'cancelled'
    )
    assert cancellation[0] == 'PATCH'
    assert cancellation[2]['resource_id'] == 'eq.resource-1'
    assert cancellation[2]['user_id'] == 'eq.teacher-1'
    assert cancellation[2]['resource_revision'] == 'lt.5'
    assert cancellation[3]['status'] == 'cancelled'
    assert cancellation[4] == 'return=representation'
    assert not any(call[0] == 'GET' for call in repo.calls)


def test_invalidation_captures_video_published_during_atomic_cancel():
    class PublishingRepository(Repository):
        def _request(self, method, table, *, params=None, payload=None, prefer=None):
            self.calls.append((method, table, params, payload, prefer))
            if method == 'GET':
                return [{'id': 'r1', 'video_object': None}]
            if payload and payload.get('status') == 'cancelled':
                row = {'id': 'r1', 'video_object': 'teacher-1/r1/video.mp4'}
                self.rows = [row]
                return [row]
            return self.rows

    repo = PublishingRepository()

    repo.invalidate_teacher_video_renders('resource-1', 'teacher-1', 5)

    assert repo.deleted == ['teacher-1/r1/video.mp4']
    cancellation = next(call for call in repo.calls if call[3] and call[3].get('status') == 'cancelled')
    assert cancellation[0] == 'PATCH'
    assert cancellation[4] == 'return=representation'
    assert cancellation[2]['resource_revision'] == 'lt.5'


def test_invalidation_only_targets_older_resource_revisions():
    repo = Repository()

    repo.invalidate_teacher_video_renders('resource-1', 'teacher-1', 5)

    cancellation = next(call for call in repo.calls if call[3] and call[3].get('status') == 'cancelled')
    assert cancellation[2]['resource_revision'] == 'lt.5'


def test_resource_deletion_cancels_all_render_revisions():
    repo = Repository()

    repo.cancel_all_teacher_video_renders_for_resource('resource-1', 'teacher-1')

    cancellation = next(call for call in repo.calls if call[3] and call[3].get('status') == 'cancelled')
    assert cancellation[2]['resource_id'] == 'eq.resource-1'
    assert 'resource_revision' not in cancellation[2]


def _run_worker(monkeypatch, tmp_path, *, revision_after_render=None, fail=False):
    from types import SimpleNamespace
    from app.services import teacher_video_render as worker

    render_id = 'render-1'
    resource = {
        'id': 'resource-1', 'user_id': 'teacher-1', 'kind': 'video',
        'status': 'ready', 'revision': 4,
    }
    render_row = {
        'id': render_id, 'user_id': 'teacher-1', 'resource_id': 'resource-1',
        'resource_revision': 4, 'status': 'queued', 'progress': 0,
    }

    class MemoryRepository:
        def __init__(self):
            self.row = dict(render_row)
            self.updates = []
            self.uploads = []
            self.deleted = []

        def teacher_video_render(self, _render_id, _user_id):
            return self.row

        def update_teacher_video_render(self, _render_id, _user_id, changes, *, active_only=False):
            if active_only and self.row['status'] not in {'queued', 'processing'}:
                return None
            self.row.update(changes)
            self.updates.append(dict(changes))
            return self.row

        def is_user_deleting(self, _user_id):
            return False

        def upload_asset(self, **kwargs):
            self.uploads.append(kwargs)

        def delete_asset(self, path):
            self.deleted.append(path)

    class TeacherRepository:
        def resource(self, _resource_id, _user_id):
            return resource

    class Orchestrator:
        def __init__(self):
            self.kwargs = None

        def run(self, **kwargs):
            self.kwargs = kwargs
            kwargs['task_instance'].update_state(
                state='PROGRESS',
                meta={'progress': 64, 'step': 'scene_generation', 'message': 'Making scenes.'},
            )
            output = tmp_path / 'video.mp4'
            output.write_bytes(b'mp4')
            if revision_after_render is not None:
                resource['revision'] = revision_after_render
            if fail:
                raise RuntimeError('private provider failure')
            return SimpleNamespace(
                artifacts={'video': str(output)}, duration_sec=180,
            )

    repo = MemoryRepository()
    orchestrator = Orchestrator()
    service = worker.TeacherVideoRenderService(
        repository=repo, teacher_repo=TeacherRepository(), orchestrator=orchestrator,
    )
    monkeypatch.setattr(worker, 'teacher_video_render_service', service)
    payload = {
        'script': {
            'title': 'Rain', 'hook': 'Rain returns.', 'sections': [],
            'full_narration': 'Rain falls and returns to the clouds.',
            'estimated_duration_sec': 180,
        },
        'target_duration_sec': 180, 'voice': 'female',
    }
    result = worker.render_teacher_video_task.run(
        render_id, 'teacher-1', 'resource-1', 4, payload,
        {'subject': 'science', 'topic': 'Rain', 'grade': '4', 'language': 'en-US'},
    )
    return result, repo, orchestrator


def test_teacher_video_render_skips_story_history_and_outcomes(monkeypatch, tmp_path):
    result, repo, orchestrator = _run_worker(monkeypatch, tmp_path)

    assert result['status'] == 'ready'
    assert orchestrator.kwargs['generate_learning_outcomes'] is False
    assert orchestrator.kwargs['request'].school_grade == '4'
    assert orchestrator.kwargs['request'].voice == 'female'
    assert repo.uploads[0]['object_path'] == 'teacher-1/render-1/video.mp4'
    assert repo.row['status'] == 'ready'
    assert repo.row['video_object'] == 'teacher-1/render-1/video.mp4'
    assert any(update.get('progress') == 64 for update in repo.updates)
    assert any(update.get('stage') == 'scene_generation' for update in repo.updates)


def test_teacher_video_render_checks_revision_before_publish(monkeypatch, tmp_path):
    result, repo, _orchestrator = _run_worker(
        monkeypatch, tmp_path, revision_after_render=5,
    )

    assert result['status'] == 'cancelled'
    assert not repo.uploads
    assert repo.row['status'] == 'cancelled'


def test_teacher_video_render_marks_failure_retryable(monkeypatch, tmp_path):
    result, repo, _orchestrator = _run_worker(monkeypatch, tmp_path, fail=True)

    assert result['status'] == 'failed'
    assert repo.row['status'] == 'failed'
    assert repo.row['error'] == 'render_failed'
    assert not repo.uploads
