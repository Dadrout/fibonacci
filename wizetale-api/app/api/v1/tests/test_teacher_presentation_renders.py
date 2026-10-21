import asyncio
import importlib.util
from uuid import uuid4

import pytest
from fastapi import HTTPException


def modules():
    assert (
        importlib.util.find_spec("app.api.v1.teacher_presentation_renders") is not None
    ), "Teacher presentation render API is missing"
    from app.api.v1 import teacher_presentation_renders as routes

    return routes


class MemoryRepository:
    def __init__(self):
        self.lesson = {"id": "lesson", "user_id": "teacher"}
        self.resource = {
            "id": "resource",
            "lesson_id": "lesson",
            "user_id": "teacher",
            "kind": "presentation",
            "status": "ready",
            "revision": 3,
            "lesson_snapshot": {"topic": "Fractions", "language": "kk-KZ"},
            "content": {
                "title": "Fractions",
                "slides": [
                    {
                        "title": "One half",
                        "key_points": ["Equal parts"],
                        "speaker_notes": "Explain equal parts.",
                    }
                ],
            },
        }
        self.renders = {}

    def claim(self, row):
        self.renders[row["id"]] = row
        return row

    def render(self, render_id, user_id):
        row = self.renders.get(render_id)
        return row if row and row["user_id"] == user_id else None

    def active(self, resource_id, user_id):
        return next(
            (
                row
                for row in self.renders.values()
                if row["resource_id"] == resource_id
                and row["user_id"] == user_id
                and row["status"] in {"queued", "processing"}
            ),
            None,
        )

    def active_presentation_render(self, resource_id, user_id):
        return self.active(resource_id, user_id)

    def presentation_render(self, render_id, user_id):
        return self.render(render_id, user_id)

    def create_presentation_render(self, row):
        return self.claim(row)

    def update(self, render_id, user_id, changes):
        row = self.render(render_id, user_id)
        if row:
            row.update(changes)
        return row

    def update_presentation_render(
        self, render_id, user_id, changes, *, active_only=False
    ):
        row = self.render(render_id, user_id)
        if active_only and (not row or row["status"] not in {"queued", "processing"}):
            return None
        return self.update(render_id, user_id, changes)

    def is_user_deleting(self, _user_id):
        return False

    def upload_asset(self, **kwargs):
        self.uploaded = kwargs

    def delete_job_assets(self, _user_id, _render_id):
        self.deleted_asset = True


@pytest.fixture
def setup_routes(monkeypatch):
    routes = modules()
    repo = MemoryRepository()
    monkeypatch.setattr(routes, "teacher_presentation_repository", repo)
    monkeypatch.setattr(
        routes.teacher.teacher_repository, "profile", lambda uid: {"user_id": uid}
    )
    monkeypatch.setattr(
        routes.teacher.teacher_repository,
        "lesson",
        lambda lid, uid: repo.lesson if uid == "teacher" else None,
    )
    monkeypatch.setattr(
        routes.teacher.teacher_repository,
        "resource",
        lambda rid, uid: (
            repo.resource if rid == "resource" and uid == "teacher" else None
        ),
    )
    monkeypatch.setattr(
        routes.teacher.document_repository, "decorate", lambda row, _uid: row
    )
    monkeypatch.setattr(routes.story_repository, "is_user_deleting", lambda uid: False)

    async def inline(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    monkeypatch.setattr(routes, "run_in_threadpool", inline)
    monkeypatch.setattr(routes.teacher, "run_in_threadpool", inline)

    class Task:
        def __init__(self):
            self.calls = []

        def apply_async(self, **kwargs):
            self.calls.append(kwargs)

    task = Task()
    monkeypatch.setattr(routes, "render_teacher_presentation_task", task)
    return routes, repo, task


def test_teacher_can_queue_owned_ready_presentation(setup_routes):
    routes, repo, task = setup_routes
    result = asyncio.run(
        routes.start_presentation_render("lesson", "resource", {"uid": "teacher"})
    )
    assert result["status"] == "queued"
    assert result["resource_id"] == "resource"
    assert task.calls[0]["args"][1:] == [
        "teacher",
        repo.resource["content"],
        repo.resource["lesson_snapshot"],
    ]
    assert result["id"] in repo.renders


def test_other_account_cannot_queue_or_read_teacher_render(setup_routes):
    routes, repo, task = setup_routes
    with pytest.raises(HTTPException) as error:
        asyncio.run(
            routes.start_presentation_render("lesson", "resource", {"uid": "other"})
        )
    assert error.value.status_code in (403, 404)
    render_id = str(uuid4())
    repo.claim(
        {
            "id": render_id,
            "user_id": "teacher",
            "resource_id": "resource",
            "status": "queued",
        }
    )
    with pytest.raises(HTTPException) as error:
        asyncio.run(routes.get_presentation_render(render_id, {"uid": "other"}))
    assert error.value.status_code == 404
    with pytest.raises(HTTPException) as error:
        asyncio.run(routes.download_presentation_video(render_id, {"uid": "other"}))
    assert error.value.status_code == 404
    assert not task.calls


def test_ready_render_returns_playback_url_and_download_stream(monkeypatch, setup_routes):
    routes, repo, _ = setup_routes
    render_id = str(uuid4())
    repo.claim({
        "id": render_id, "user_id": "teacher", "resource_id": "resource",
        "status": "ready", "progress": 100, "stage": "complete",
        "message": "Ready", "video_object": f"teacher/{render_id}/video.mp4",
    })
    monkeypatch.setattr(routes.story_repository, "create_signed_asset_url", lambda _path: "https://media.example/video")
    playback = asyncio.run(routes.get_presentation_render(render_id, {"uid": "teacher"}))
    assert playback["video_url"] == "https://media.example/video"

    class Response:
        ok = True
        headers = {"Content-Length": "3"}

        def iter_content(self, chunk_size):
            assert chunk_size == 1024 * 1024
            yield b"mp4"

        def close(self):
            return None

    monkeypatch.setattr(routes.requests, "get", lambda *_args, **_kwargs: Response())
    download = asyncio.run(routes.download_presentation_video(render_id, {"uid": "teacher"}))
    assert download.headers["content-disposition"].startswith("attachment;")
    assert download.media_type == "video/mp4"
    assert download.status_code == 200


def test_only_ready_presentations_can_render(setup_routes):
    routes, repo, _ = setup_routes
    repo.resource["kind"] = "quiz"
    with pytest.raises(HTTPException) as error:
        asyncio.run(
            routes.start_presentation_render("lesson", "resource", {"uid": "teacher"})
        )
    assert error.value.status_code == 409


def test_failed_render_can_be_retried_as_a_new_job(setup_routes):
    routes, repo, task = setup_routes
    repo.claim(
        {
            "id": str(uuid4()),
            "user_id": "teacher",
            "resource_id": "resource",
            "status": "failed",
            "progress": 0,
            "stage": "failed",
            "message": "Retry me",
        }
    )
    result = asyncio.run(
        routes.start_presentation_render("lesson", "resource", {"uid": "teacher"})
    )
    assert result["status"] == "queued"
    assert len(repo.renders) == 2
    assert task.calls


def test_render_worker_publishes_completed_mp4(monkeypatch, setup_routes, tmp_path):
    import app.services.teacher_presentation_video as video

    routes, repo, _ = setup_routes
    monkeypatch.setattr(video, "story_repository", repo)
    monkeypatch.setattr(video.settings, "WORKDIR_ROOT", str(tmp_path / "work"))
    result = asyncio.run(
        routes.start_presentation_render("lesson", "resource", {"uid": "teacher"})
    )
    render_id = result["id"]
    output = tmp_path / "render.mp4"
    output.write_bytes(b"mp4")

    class Renderer:
        def render(self, **_kwargs):
            return {"video_path": str(output), "duration_sec": 14.5}

    monkeypatch.setattr(video, "presentation_video_renderer", Renderer())
    completed = video.render_teacher_presentation_task.run(
        render_id, "teacher", repo.resource["content"], repo.resource["lesson_snapshot"]
    )
    assert completed["status"] == "ready"
    assert repo.renders[render_id]["status"] == "ready"
    assert repo.renders[render_id]["video_object"] == f"teacher/{render_id}/video.mp4"
    assert repo.uploaded["content_type"] == "video/mp4"


def test_render_failure_is_saved_and_retryable(monkeypatch, setup_routes, tmp_path):
    import app.services.teacher_presentation_video as video

    _, repo, _ = setup_routes
    monkeypatch.setattr(video, "story_repository", repo)
    monkeypatch.setattr(video.settings, "WORKDIR_ROOT", str(tmp_path / "work"))
    render_id = str(uuid4())
    repo.claim(
        {
            "id": render_id,
            "user_id": "teacher",
            "resource_id": "resource",
            "status": "queued",
        }
    )

    class BrokenRenderer:
        def render(self, **_kwargs):
            raise RuntimeError("provider secret")

    monkeypatch.setattr(video, "presentation_video_renderer", BrokenRenderer())
    with pytest.raises(RuntimeError, match="provider secret"):
        video.render_teacher_presentation_task.run(
            render_id,
            "teacher",
            repo.resource["content"],
            repo.resource["lesson_snapshot"],
        )
    assert repo.renders[render_id]["status"] == "failed"
    assert repo.renders[render_id]["error"] == "render_failed"
