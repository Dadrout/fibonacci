import pytest
import requests

from app.core.config import settings
from app.services.story_repository import SupabaseStoryRepository


def test_repository_requires_server_only_supabase_configuration(monkeypatch):
    monkeypatch.setattr(settings, "SUPABASE_URL", None)
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_ROLE_KEY", None)

    with pytest.raises(RuntimeError, match="Supabase story storage is not configured"):
        SupabaseStoryRepository().list_stories("user-1")


def test_repository_scopes_story_reads_by_owner(monkeypatch):
    monkeypatch.setattr(settings, "SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "server-only-test-key")
    response = requests.Response()
    response.status_code = 200
    response._content = b'[]'
    request_calls = []

    def fake_request(_session, method, url, **kwargs):
        request_calls.append((method, url, kwargs))
        return response

    monkeypatch.setattr(requests.Session, "request", fake_request)
    repo = SupabaseStoryRepository()

    repo.list_stories("user-1")

    method, url, kwargs = request_calls[0]
    assert method == "GET"
    assert url.endswith("/rest/v1/stories")
    assert kwargs["params"]["user_id"] == "eq.user-1"
    assert kwargs["headers"]["Authorization"] == "Bearer server-only-test-key"


def test_repository_retries_a_safe_read_after_a_stale_connection(monkeypatch):
    monkeypatch.setattr(settings, "SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "server-only-test-key")
    response = requests.Response()
    response.status_code = 200
    response._content = b"[]"
    attempts = 0

    def fake_request(_session, _method, _url, **_kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise requests.ConnectionError("stale keep-alive connection")
        return response

    monkeypatch.setattr(requests.Session, "request", fake_request)

    assert SupabaseStoryRepository().list_stories("learner-1") == []
    assert attempts == 2


def test_story_history_query_is_bounded_and_supports_offset_pagination(monkeypatch):
    monkeypatch.setattr(settings, "SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "server-only-test-key")
    response = requests.Response()
    response.status_code = 200
    response._content = b'[]'
    calls = []

    def fake_request(_session, method, url, **kwargs):
        calls.append((method, url, kwargs))
        return response

    monkeypatch.setattr(requests.Session, "request", fake_request)

    SupabaseStoryRepository().list_stories("learner-1", limit=25, offset=50)

    params = calls[0][2]["params"]
    assert params["limit"] == "25"
    assert params["offset"] == "50"
    assert params["order"] == "created_at.desc"


def test_deletion_lock_is_durable_and_worker_visible(monkeypatch):
    repository = SupabaseStoryRepository()
    calls = []

    def fake_request(method, table, **kwargs):
        calls.append((method, table, kwargs))
        return [{"user_id": "learner-1"}] if method == "GET" else None

    monkeypatch.setattr(repository, "_request", fake_request)

    repository.mark_user_deleting("learner-1")
    assert repository.is_user_deleting("learner-1") is True

    assert calls[0][0:2] == ("POST", "account_deletion_locks")
    assert calls[0][2]["payload"] == {"user_id": "learner-1"}
    assert calls[0][2]["params"] == {"on_conflict": "user_id"}
    assert calls[1][0:2] == ("GET", "account_deletion_locks")
    assert calls[1][2]["params"]["user_id"] == "eq.learner-1"


def test_account_deletion_lists_and_cancels_only_active_owned_jobs(monkeypatch):
    repository = SupabaseStoryRepository()
    calls = []

    def fake_request(method, table, **kwargs):
        calls.append((method, table, kwargs))
        if method == "GET":
            return [{"task_id": "job-1", "draft_id": "draft-1"}]
        if table == "stories":
            return [{"draft_id": "draft-1"}]
        return None

    monkeypatch.setattr(repository, "_request", fake_request)

    jobs = repository.list_active_story_jobs("learner-1")
    repository.cancel_story_job_for_deletion("job-1", "learner-1")

    assert jobs == [{"task_id": "job-1", "draft_id": "draft-1"}]
    assert calls[0][2]["params"]["status"] == "in.(PENDING,PROGRESS)"
    assert calls[1][2]["params"]["user_id"] == "eq.learner-1"
    assert calls[1][2]["payload"]["stage"] == "cancelled"
    assert calls[2][1] == "story_drafts"
    assert calls[2][2]["params"]["status"] == "eq.rendering"
    assert calls[2][2]["payload"] == {"status": "draft"}


def test_worker_progress_cannot_overwrite_a_terminally_cancelled_job(monkeypatch):
    repository = SupabaseStoryRepository()
    calls = []

    def fake_request(method, table, **kwargs):
        calls.append((method, table, kwargs))
        return []

    monkeypatch.setattr(repository, "_request", fake_request)

    assert repository.update_story_progress_if_active("job-1", {"status": "PROGRESS"}) is False
    assert calls[0][2]["params"]["status"] == "in.(PENDING,PROGRESS)"


def test_supabase_job_media_cleanup_deletes_only_the_cancelled_job(monkeypatch):
    monkeypatch.setattr(settings, "SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "server-only-test-key")
    monkeypatch.setattr(settings, "SUPABASE_VIDEO_BUCKET", "story-videos")
    monkeypatch.setattr(settings, "MEDIA_STORAGE_PROVIDER", "supabase")
    response = requests.Response()
    response.status_code = 200
    response._content = b'[]'
    calls = []

    def fake_delete(_session, url, **kwargs):
        calls.append((url, kwargs))
        return response

    monkeypatch.setattr(requests.Session, "delete", fake_delete)

    assert SupabaseStoryRepository().delete_job_assets("learner-1", "job-1") == 2
    assert calls[0][0].endswith("/storage/v1/object/story-videos")
    assert calls[0][1]["json"] == {
        "prefixes": ["learner-1/job-1/video.mp4", "learner-1/job-1/audio.mp3"]
    }


@pytest.mark.parametrize(
    ("method_name", "method_args", "table", "owner_key"),
    [
        ("get_draft", ("draft-1", "learner-1"), "story_drafts", "user_id"),
        ("get_story_job", ("job-1", "learner-1"), "stories", "user_id"),
        ("get_story_by_id", ("story-1", "learner-1"), "stories", "user_id"),
    ],
)
def test_repository_scopes_individual_records_by_owner(monkeypatch, method_name, method_args, table, owner_key):
    monkeypatch.setattr(settings, "SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "server-only-test-key")
    response = requests.Response()
    response.status_code = 200
    response._content = b'[]'
    request_calls = []

    def fake_request(_session, method, url, **kwargs):
        request_calls.append((method, url, kwargs))
        return response

    monkeypatch.setattr(requests.Session, "request", fake_request)
    repo = SupabaseStoryRepository()

    assert getattr(repo, method_name)(*method_args) is None

    method, url, kwargs = request_calls[0]
    assert method == "GET"
    assert url.endswith(f"/rest/v1/{table}")
    assert kwargs["params"][owner_key] == "eq.learner-1"


def test_repository_updates_a_draft_only_while_it_is_editable(monkeypatch):
    repository = SupabaseStoryRepository()
    updated = {"id": "draft-1", "status": "draft", "script": {"title": "New"}}
    calls = []

    def fake_request(method, table, **kwargs):
        calls.append((method, table, kwargs))
        return [updated]

    monkeypatch.setattr(repository, "_request", fake_request)

    result = repository.update_draft_if_editable(
        "draft-1", "learner-1", {"script": updated["script"]}
    )

    assert result == updated
    method, table, kwargs = calls[0]
    assert method == "PATCH"
    assert table == "story_drafts"
    assert kwargs["params"] == {
        "id": "eq.draft-1",
        "user_id": "eq.learner-1",
        "status": "eq.draft",
    }
    assert kwargs["prefer"] == "return=representation"


def test_delete_draft_if_editable_filters_by_owner_and_status(monkeypatch):
    repository = SupabaseStoryRepository()
    deleted = {"id": "draft-1", "user_id": "learner-1", "status": "draft"}
    calls = []

    def fake_request(method, table, **kwargs):
        calls.append((method, table, kwargs))
        return [deleted]

    monkeypatch.setattr(repository, "_request", fake_request)

    assert repository.delete_draft_if_editable("draft-1", "learner-1") == deleted

    assert calls == [(
        "DELETE",
        "story_drafts",
        {
            "params": {
                "id": "eq.draft-1",
                "user_id": "eq.learner-1",
                "status": "eq.draft",
            },
            "prefer": "return=representation",
        },
    )]


def test_delete_draft_if_editable_returns_none_when_state_no_longer_matches(monkeypatch):
    repository = SupabaseStoryRepository()
    monkeypatch.setattr(repository, "_request", lambda *_args, **_kwargs: [])

    assert repository.delete_draft_if_editable("draft-1", "learner-1") is None


def test_get_quiz_result_filters_by_story_and_user(monkeypatch):
    repository = SupabaseStoryRepository()
    expected = {"story_id": "story-1", "user_id": "learner-1", "answers": {"1": "a"}}
    calls = []
    monkeypatch.setattr(
        repository,
        "_request",
        lambda method, table, **kwargs: calls.append((method, table, kwargs)) or [expected],
    )

    assert repository.get_quiz_result("story-1", "learner-1") == expected
    assert calls == [(
        "GET",
        "quiz_results",
        {"params": {
            "story_id": "eq.story-1",
            "user_id": "eq.learner-1",
            "select": "*",
            "limit": "1",
        }},
    )]


def test_get_quiz_result_returns_none_without_a_saved_row(monkeypatch):
    repository = SupabaseStoryRepository()
    monkeypatch.setattr(repository, "_request", lambda *_args, **_kwargs: [])

    assert repository.get_quiz_result("story-1", "learner-1") is None


def test_save_quiz_result_keeps_the_first_result_on_conflict(monkeypatch):
    repository = SupabaseStoryRepository()
    original = {"story_id": "story-1", "user_id": "learner-1", "answers": {"1": "a"}, "score": 1, "total": 1}
    calls = []

    def fake_request(method, table, **kwargs):
        calls.append((method, table, kwargs))
        return [] if method == "POST" else [original]

    monkeypatch.setattr(repository, "_request", fake_request)
    replacement = {**original, "answers": {"1": "b"}, "score": 0}

    assert repository.save_quiz_result(replacement) == original
    assert calls[0][0:2] == ("POST", "quiz_results")
    assert calls[0][2]["prefer"] == "resolution=ignore-duplicates,return=representation"
    assert calls[1][0:2] == ("GET", "quiz_results")



def test_render_claim_and_story_creation_use_one_server_transaction(monkeypatch):
    repo = SupabaseStoryRepository()
    calls=[]
    snapshot={'draft':{'id':'draft-1'},'story':{'id':'story-1','task_id':'job-1'}}
    monkeypatch.setattr(repo,'_request',lambda method,table,**kwargs: calls.append((method,table,kwargs)) or snapshot)
    assert repo.claim_render_job('draft-1','owner-1','job-1') == snapshot
    assert calls == [('POST','rpc/claim_story_render',{'payload':{'p_draft_id':'draft-1','p_user_id':'owner-1','p_task_id':'job-1'}})]
