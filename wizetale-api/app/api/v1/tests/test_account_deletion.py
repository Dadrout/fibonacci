import pytest
from types import SimpleNamespace

from app.services.account_deletion import AccountDeletionError, AccountDeletionService


class Response:
    content = b"{}"

    def raise_for_status(self):
        return None


def test_deletion_revokes_sessions_removes_media_then_deletes_auth_user(monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.settings, "SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setattr(config.settings, "SUPABASE_PUBLISHABLE_KEY", "publishable")
    monkeypatch.setattr(config.settings, "SUPABASE_SERVICE_ROLE_KEY", "service")
    calls = []

    class Session:
        def post(self, url, **kwargs):
            calls.append(("logout", url, kwargs))
            return Response()

        def delete(self, url, **kwargs):
            calls.append(("delete-user", url, kwargs))
            return Response()

    class Repository:
        def mark_user_deleting(self, user_id):
            calls.append(("lock", user_id))

        def list_active_story_jobs(self, user_id):
            return []

        def cancel_story_job_for_deletion(self, task_id, user_id):
            calls.append(("cancel", task_id, user_id))

        def delete_user_assets(self, user_id):
            calls.append(("delete-media", user_id))
            return 2

    AccountDeletionService(Session(), Repository()).delete_account("learner-1", "access-token")

    assert [call[0] for call in calls if call[0] in {"logout", "delete-media", "delete-user"}] == [
        "logout", "delete-media", "delete-user"
    ]
    logout_call = next(call for call in calls if call[0] == "logout")
    delete_call = next(call for call in calls if call[0] == "delete-user")
    assert logout_call[2]["headers"]["Authorization"] == "Bearer access-token"
    assert delete_call[1].endswith("/auth/v1/admin/users/learner-1")
    assert delete_call[2]["headers"]["Authorization"] == "Bearer service"


def test_deletion_cancels_presentation_render_before_removing_private_video(monkeypatch):
    from app.core import config
    from app.services import account_deletion as deletion

    monkeypatch.setattr(config.settings, "SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setattr(config.settings, "SUPABASE_PUBLISHABLE_KEY", "publishable")
    monkeypatch.setattr(config.settings, "SUPABASE_SERVICE_ROLE_KEY", "service")
    events = []

    class Session:
        def post(self, *_args, **_kwargs):
            events.append("logout")
            return Response()

        def delete(self, *_args, **_kwargs):
            events.append("delete-user")
            return Response()

    class Repository:
        def mark_user_deleting(self, user_id):
            events.append("lock")

        def list_active_story_jobs(self, _user_id):
            return []

        def list_active_presentation_renders(self, _user_id):
            return [{"id": "render-1"}]

        def cancel_active_presentation_renders(self, _user_id):
            events.append("cancel-render")
            return [{"id": "render-1"}]

        def delete_user_assets(self, _user_id):
            events.append("delete-video-assets")

    class Documents:
        def active_jobs(self, _user_id):
            return []

        def cancel_jobs(self, _user_id):
            return None

        def delete_user_assets(self, _user_id):
            return None

    class Control:
        control = None

        def __init__(self):
            self.control = self

        def revoke(self, task_id, *, terminate, signal):
            events.append(("revoke", task_id, terminate, signal))

        def inspect(self, *, timeout):
            return SimpleNamespace(active=lambda: {})

    monkeypatch.setattr(deletion, "document_repository", Documents())
    deletion.AccountDeletionService(Session(), Repository(), task_control=Control()).delete_account("teacher-1", "token")

    assert events.index("lock") < events.index("cancel-render")
    assert events.index("cancel-render") < events.index(("revoke", "render-1", True, "SIGTERM"))
    assert events.index(("revoke", "render-1", True, "SIGTERM")) < events.index("delete-video-assets")
    assert events.index("delete-video-assets") < events.index("delete-user")


def test_account_deletion_cancels_teacher_video_renders(monkeypatch):
    from app.core import config
    from app.services import account_deletion as deletion

    monkeypatch.setattr(config.settings, "SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setattr(config.settings, "SUPABASE_PUBLISHABLE_KEY", "publishable")
    monkeypatch.setattr(config.settings, "SUPABASE_SERVICE_ROLE_KEY", "service")
    events = []

    class Session:
        def post(self, *_args, **_kwargs):
            events.append("logout")
            return Response()

        def delete(self, *_args, **_kwargs):
            events.append("delete-user")
            return Response()

    class Repository:
        def mark_user_deleting(self, _user_id):
            events.append("lock")

        def list_active_story_jobs(self, _user_id):
            return []

        def list_active_teacher_video_renders(self, _user_id):
            return [{'id': 'video-render-1'}]

        def cancel_active_teacher_video_renders(self, _user_id):
            events.append("cancel-video-render")
            return [{'id': 'video-render-1'}]

        def delete_user_assets(self, _user_id):
            events.append("delete-video-assets")

    class Documents:
        def active_jobs(self, _user_id):
            return []

        def cancel_jobs(self, _user_id):
            return None

        def delete_user_assets(self, _user_id):
            return None

    class Control:
        control = None

        def __init__(self):
            self.control = self

        def revoke(self, task_id, *, terminate, signal):
            events.append(('revoke', task_id, terminate, signal))

        def inspect(self, *, timeout):
            return SimpleNamespace(active=lambda: {})

    monkeypatch.setattr(deletion, 'document_repository', Documents())
    deletion.AccountDeletionService(Session(), Repository(), task_control=Control()).delete_account('teacher-1', 'token')

    assert events.index('lock') < events.index('cancel-video-render')
    assert events.index('cancel-video-render') < events.index(('revoke', 'video-render-1', True, 'SIGTERM'))
    assert events.index(('revoke', 'video-render-1', True, 'SIGTERM')) < events.index('delete-video-assets')
    assert events.index('delete-video-assets') < events.index('delete-user')


def test_deletion_locks_generation_and_waits_for_active_worker_before_media_cleanup(monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.settings, "SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setattr(config.settings, "SUPABASE_PUBLISHABLE_KEY", "publishable")
    monkeypatch.setattr(config.settings, "SUPABASE_SERVICE_ROLE_KEY", "service")
    events = []

    class Session:
        def post(self, url, **kwargs):
            events.append("logout")
            return Response()

        def delete(self, url, **kwargs):
            events.append("delete-user")
            return Response()

    class Repository:
        def mark_user_deleting(self, user_id):
            events.append(("lock", user_id))

        def list_active_story_jobs(self, user_id):
            events.append(("list-active", user_id))
            return [{"task_id": "job-1", "draft_id": "draft-1"}]

        def cancel_story_job_for_deletion(self, task_id, user_id):
            events.append(("cancel", task_id, user_id))

        def delete_user_assets(self, user_id):
            events.append(("delete-media", user_id))

    class Control:
        def __init__(self):
            self.polls = 0
            self.control = self

        def revoke(self, task_id, *, terminate, signal):
            events.append(("revoke", task_id, terminate, signal))

        def inspect(self, *, timeout):
            events.append("inspect")
            self.polls += 1
            active = {"worker-1": [{"id": "job-1"}]} if self.polls == 1 else {}
            return SimpleNamespace(active=lambda: active)

    from app.services.account_deletion import AccountDeletionService

    AccountDeletionService(
        Session(), Repository(), task_control=Control(), sleep=lambda _seconds: None
    ).delete_account("learner-1", "access-token")

    assert events.index(("lock", "learner-1")) < events.index("logout")
    revoke_index = events.index(("revoke", "job-1", True, "SIGTERM"))
    media_index = next(i for i, event in enumerate(events) if isinstance(event, tuple) and event[0] == "delete-media")
    delete_user_index = events.index("delete-user")
    assert revoke_index < media_index
    assert events.index("inspect") < media_index
    assert media_index < delete_user_index


def test_deletion_stops_safely_if_active_worker_does_not_exit(monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.settings, "SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setattr(config.settings, "SUPABASE_PUBLISHABLE_KEY", "publishable")
    monkeypatch.setattr(config.settings, "SUPABASE_SERVICE_ROLE_KEY", "service")
    calls = []

    class Session:
        def post(self, *_args, **_kwargs):
            calls.append("logout")
            return Response()

        def delete(self, *_args, **_kwargs):
            calls.append("delete-user")
            return Response()

    class Repository:
        def mark_user_deleting(self, _user_id):
            calls.append("lock")

        def list_active_story_jobs(self, _user_id):
            return [{"task_id": "job-1", "draft_id": "draft-1"}]

        def cancel_story_job_for_deletion(self, *_args):
            calls.append("cancel")

        def delete_user_assets(self, _user_id):
            calls.append("delete-media")

    class Control:
        control = None

        def __init__(self):
            self.control = self

        def revoke(self, *_args, **_kwargs):
            return None

        def inspect(self, *, timeout):
            return SimpleNamespace(active=lambda: {"worker-1": [{"id": "job-1"}]})

    from app.services.account_deletion import AccountDeletionService

    tick = iter([0, 0, 2, 2, 4, 4])
    service = AccountDeletionService(
        Session(), Repository(), task_control=Control(),
        sleep=lambda _seconds: None, monotonic=lambda: next(tick), worker_stop_timeout=1,
    )

    with pytest.raises(AccountDeletionError):
        service.delete_account("learner-1", "access-token")

    assert "delete-media" not in calls
    assert "delete-user" not in calls


def test_account_is_not_deleted_when_user_media_cleanup_fails(monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.settings, "SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setattr(config.settings, "SUPABASE_PUBLISHABLE_KEY", "publishable")
    monkeypatch.setattr(config.settings, "SUPABASE_SERVICE_ROLE_KEY", "service")
    calls = []

    class Session:
        def post(self, url, **kwargs):
            calls.append("logout")
            return Response()

        def delete(self, url, **kwargs):
            calls.append("delete-user")
            return Response()

    class Repository:
        def mark_user_deleting(self, _user_id):
            return None

        def list_active_story_jobs(self, _user_id):
            return []

        def cancel_story_job_for_deletion(self, *_args):
            return None

        def delete_user_assets(self, user_id):
            raise RuntimeError("storage unavailable")

    with pytest.raises(AccountDeletionError):
        AccountDeletionService(Session(), Repository()).delete_account("learner-1", "access-token")

    assert calls == ["logout"]


def test_supabase_storage_cleanup_recurses_and_batches_user_files(monkeypatch):
    from app.core import config
    from app.services.story_repository import SupabaseStoryRepository

    monkeypatch.setattr(config.settings, "SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setattr(config.settings, "SUPABASE_SERVICE_ROLE_KEY", "service")
    monkeypatch.setattr(config.settings, "SUPABASE_VIDEO_BUCKET", "story-videos")
    monkeypatch.setattr(config.settings, "MEDIA_STORAGE_PROVIDER", "supabase")
    calls = []

    class ListingResponse(Response):
        def __init__(self, entries):
            self.entries = entries

        def json(self):
            return self.entries

    class DeleteResponse(Response):
        def json(self):
            return []

    class Session:
        def post(self, url, **kwargs):
            calls.append(("list", url, kwargs["json"]))
            if kwargs["json"]["prefix"] == "learner-1/":
                return ListingResponse([{"name": "job", "id": None}])
            if kwargs["json"]["prefix"] == "learner-1/job/":
                return ListingResponse([{"name": "video.mp4", "id": "object-id"}])
            raise AssertionError(f"unexpected prefix: {kwargs['json']['prefix']}")

        def delete(self, url, **kwargs):
            calls.append(("delete", url, kwargs["json"]))
            return DeleteResponse()

    count = SupabaseStoryRepository(Session()).delete_user_assets("learner-1")

    assert count == 1
    assert calls[-1][2] == {"prefixes": ["learner-1/job/video.mp4"]}


def test_account_route_requires_auth_and_applies_daily_limit():
    from app.main import app

    from app.api.v1.account import router
    assert "delete" in app.openapi()["paths"]["/api/v1/account"]
    route = next(route for route in router.routes if route.path == "/account" and "DELETE" in route.methods)
    dependencies = route.dependant.dependencies

    assert any(dependency.call.__name__ == "get_current_user" for dependency in dependencies)
    assert any(
        getattr(dependency.call, "rate_limit_spec", None) == ("account-delete", 3, 86400)
        for dependency in dependencies
    )


@pytest.fixture(autouse=True)
def document_cleanup_stub(monkeypatch):
    from app.services.document_repository import document_repository
    monkeypatch.setattr(document_repository,'active_jobs',lambda uid: [])
    monkeypatch.setattr(document_repository,'cancel_jobs',lambda uid: None)
    monkeypatch.setattr(document_repository,'delete_user_assets',lambda uid: None)


def test_account_deletion_stops_document_tasks_before_original_cleanup(monkeypatch):
    from app.services.document_repository import document_repository
    from app.core.config import settings
    for key,value in [('SUPABASE_URL','https://project.supabase.co'),('SUPABASE_PUBLISHABLE_KEY','pub'),('SUPABASE_SERVICE_ROLE_KEY','secret')]: monkeypatch.setattr(settings,key,value)
    events=[]
    monkeypatch.setattr(document_repository,'active_jobs',lambda uid:[{'task_id':'document-task'}])
    monkeypatch.setattr(document_repository,'cancel_jobs',lambda uid: events.append('cancel-document'))
    monkeypatch.setattr(document_repository,'delete_user_assets',lambda uid: events.append('delete-original'))
    class Repo:
        def mark_user_deleting(self,*a): events.append('lock')
        def list_active_story_jobs(self,*a): return []
        def cancel_story_job_for_deletion(self,*a): pass
        def delete_user_assets(self,*a): events.append('delete-video')
    class Session:
        def post(self,*a,**k): events.append('logout'); return Response()
        def delete(self,*a,**k): events.append('delete-user'); return Response()
    class Control:
        def revoke(self,*a,**k): events.append('revoke-document')
        def inspect(self,**k): return SimpleNamespace(active=lambda:{})
    AccountDeletionService(Session(),Repo(),task_control=SimpleNamespace(control=Control())).delete_account('u','token')
    assert events.index('revoke-document')<events.index('delete-original')<events.index('delete-user')
