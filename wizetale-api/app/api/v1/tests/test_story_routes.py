import asyncio

import pytest
from fastapi import HTTPException

from app.api.v1 import stories
from app.domain.models import QuizSubmission


async def direct_call(function, *args, **kwargs):
    return function(*args, **kwargs)


@pytest.fixture(autouse=True)
def default_account_is_not_deleting(monkeypatch):
    monkeypatch.setattr(stories.story_repository, "recover_render", lambda *_args: None)
    monkeypatch.setattr(stories.story_repository, "is_user_deleting", lambda _user_id: False)


def test_story_generation_is_rejected_after_account_deletion_lock(monkeypatch):
    monkeypatch.setattr(stories, "run_in_threadpool", direct_call)
    monkeypatch.setattr(stories.story_repository, "is_user_deleting", lambda _user_id: True)
    monkeypatch.setattr(
        stories.script_generation_service,
        "validate_topic",
        lambda *_args: pytest.fail("The AI provider must not run for a deleting account"),
    )

    with pytest.raises(HTTPException) as error:
        asyncio.run(stories.create_story_draft(
            stories.StoryDraftRequest(subject="history", topic="Silk Road"),
            {"uid": "learner-1"},
        ))

    assert error.value.status_code == 409


@pytest.mark.parametrize("route_id", ["story-owned-by-another-learner", "unknown-story"])
def test_job_read_returns_not_found_for_non_owned_story(monkeypatch, route_id):
    calls = []

    def get_job(job_id, user_id):
        calls.append((job_id, user_id))
        return None

    monkeypatch.setattr(stories.story_repository, "get_story_job", get_job)
    monkeypatch.setattr(stories, "run_in_threadpool", direct_call)
    with pytest.raises(HTTPException) as error:
        asyncio.run(stories.get_story_job(route_id, {"uid": "learner-1"}))

    assert error.value.status_code == 404
    assert calls == [(route_id, "learner-1")]


def test_quiz_answers_are_scored_and_saved_for_owner(monkeypatch):
    saved = []
    record = {
        "id": "story-1",
        "status": "SUCCESS",
        "result": {"quiz": [
            {"correct_option": "b", "options": [{"id": "a"}, {"id": "b"}, {"id": "c"}]},
            {"correct_option": "a", "options": [{"id": "a"}, {"id": "b"}, {"id": "c"}]},
            {"correct_option": "c", "options": [{"id": "a"}, {"id": "b"}, {"id": "c"}]},
        ]},
    }
    monkeypatch.setattr(stories.story_repository, "get_story_job", lambda *_: None)
    monkeypatch.setattr(stories.story_repository, "get_story_by_id", lambda story_id, user_id: record)
    monkeypatch.setattr(stories.story_repository, "save_quiz_result", lambda result: saved.append(result) or result)
    monkeypatch.setattr(stories, "run_in_threadpool", direct_call)

    response = asyncio.run(stories.submit_quiz_result(
        "story-1",
        QuizSubmission(answers={"1": "b", "2": "c", "3": "c"}),
        {"uid": "learner-1"},
    ))

    assert response == {"answers": {"1": "b", "2": "c", "3": "c"}, "score": 2, "total": 3}
    assert saved[0]["user_id"] == "learner-1"
    assert saved[0]["answers"] == {"1": "b", "2": "c", "3": "c"}


def test_get_quiz_result_returns_only_the_owned_completed_story_result(monkeypatch):
    story = {"id": "story-1", "status": "SUCCESS", "result": {"quiz": [{"correct_option": "a"}]}}
    saved = {"answers": {"1": "a"}, "score": 1, "total": 1, "private": "omit"}
    monkeypatch.setattr(stories.story_repository, "get_story_job", lambda *_: None)
    monkeypatch.setattr(stories.story_repository, "get_story_by_id", lambda *_: story)
    monkeypatch.setattr(stories.story_repository, "get_quiz_result", lambda *_: saved)
    monkeypatch.setattr(stories, "run_in_threadpool", direct_call)

    response = asyncio.run(stories.get_quiz_result("story-1", {"uid": "learner-1"}))

    assert response == {"result": {"answers": {"1": "a"}, "score": 1, "total": 1}}


def test_get_quiz_result_returns_null_when_not_submitted(monkeypatch):
    story = {"id": "story-1", "status": "SUCCESS", "result": {"quiz": [{"correct_option": "a"}]}}
    monkeypatch.setattr(stories.story_repository, "get_story_job", lambda *_: None)
    monkeypatch.setattr(stories.story_repository, "get_story_by_id", lambda *_: story)
    monkeypatch.setattr(stories.story_repository, "get_quiz_result", lambda *_: None)
    monkeypatch.setattr(stories, "run_in_threadpool", direct_call)

    assert asyncio.run(stories.get_quiz_result("story-1", {"uid": "learner-1"})) == {"result": None}


def test_get_quiz_result_hides_another_users_result(monkeypatch):
    monkeypatch.setattr(stories.story_repository, "get_story_job", lambda *_: None)
    monkeypatch.setattr(stories.story_repository, "get_story_by_id", lambda *_: None)
    monkeypatch.setattr(stories, "run_in_threadpool", direct_call)

    with pytest.raises(HTTPException) as error:
        asyncio.run(stories.get_quiz_result("story-1", {"uid": "learner-1"}))

    assert error.value.status_code == 404


def test_quiz_submission_returns_the_existing_result_on_repeat(monkeypatch):
    story = {"id": "story-1", "status": "SUCCESS", "result": {"quiz": [{"correct_option": "a", "options": [{"id": "a"}, {"id": "b"}]}]}}
    original = {"answers": {"1": "b"}, "score": 0, "total": 1}
    monkeypatch.setattr(stories.story_repository, "get_story_job", lambda *_: None)
    monkeypatch.setattr(stories.story_repository, "get_story_by_id", lambda *_: story)
    monkeypatch.setattr(stories.story_repository, "save_quiz_result", lambda _record: original)
    monkeypatch.setattr(stories, "run_in_threadpool", direct_call)

    response = asyncio.run(stories.submit_quiz_result(
        "story-1", QuizSubmission(answers={"1": "a"}), {"uid": "learner-1"}
    ))

    assert response == original


def test_quiz_requires_an_answer_for_every_question(monkeypatch):
    record = {"id": "story-1", "status": "SUCCESS", "result": {"quiz": [{"correct_option": "a"}]}}
    monkeypatch.setattr(stories.story_repository, "get_story_job", lambda *_: None)
    monkeypatch.setattr(stories.story_repository, "get_story_by_id", lambda *_: record)
    monkeypatch.setattr(stories, "run_in_threadpool", direct_call)

    with pytest.raises(HTTPException) as error:
        asyncio.run(stories.submit_quiz_result(
            "story-1", QuizSubmission(answers={}), {"uid": "learner-1"}
        ))

    assert error.value.status_code == 422


def test_quiz_rejects_answer_ids_that_are_not_options(monkeypatch):
    record = {
        "id": "story-1", "status": "SUCCESS",
        "result": {"quiz": [{"correct_option": "a", "options": [{"id": "a"}, {"id": "b"}]}]},
    }
    monkeypatch.setattr(stories.story_repository, "get_story_job", lambda *_: None)
    monkeypatch.setattr(stories.story_repository, "get_story_by_id", lambda *_: record)
    monkeypatch.setattr(stories, "run_in_threadpool", direct_call)

    with pytest.raises(HTTPException) as error:
        asyncio.run(stories.submit_quiz_result(
            "story-1", QuizSubmission(answers={"1": "d"}), {"uid": "learner-1"}
        ))

    assert error.value.status_code == 422


def test_draft_creation_generates_preview_without_queueing_video(monkeypatch):
    from types import SimpleNamespace
    from app.domain.models import LearningOutcomes, ValidatedTopic, VideoScript

    monkeypatch.setattr(stories, "run_in_threadpool", direct_call)
    validated = ValidatedTopic(
        subject="history", original_topic="Silk Road", normalized_topic="Silk Road",
        language="en-US", pedagogical_framing="How trade connected cultures",
    )
    script = VideoScript(title="Silk Road", hook="A route linked worlds.", full_narration="Trade connected people.", estimated_duration_sec=180)
    outcomes = LearningOutcomes(recap="Trade connected distant communities.", quiz=[
        {"question": f"Question {i}?", "options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}, {"id": "c", "text": "C"}], "correct_option": "a", "explanation": "From the story."}
        for i in range(1, 4)
    ])
    generated = SimpleNamespace(script=script, learning_outcomes=outcomes)
    monkeypatch.setattr(stories.script_generation_service, "validate_topic", lambda *_: validated)
    calls = []
    monkeypatch.setattr(
        stories.script_generation_service,
        "generate_draft",
        lambda **kwargs: calls.append(kwargs) or generated,
    )
    stored = {}
    def create_draft(record):
        stored.update(record)
        return {**record, "id": "draft-1"}
    monkeypatch.setattr(stories.story_repository, "create_draft", create_draft)

    response = asyncio.run(stories.create_story_draft(
        stories.StoryDraftRequest(subject="history", topic="Silk Road"),
        {"uid": "learner-1"},
    ))

    assert response["id"] == "draft-1"
    assert response["script"]["full_narration"] == script.full_narration
    assert len(response["quiz"].quiz) == 3
    assert response["knowledge_status"] == "none"
    assert response["sources"] == []
    assert stored["status"] == "draft"
    assert stored["user_id"] == "learner-1"
    assert len(calls) == 1


def test_draft_creation_reports_when_long_enough_script_cannot_be_generated(monkeypatch):
    from app.services.pipeline.script_service import ScriptLengthUnavailable
    from app.domain.models import ValidatedTopic

    monkeypatch.setattr(stories, "run_in_threadpool", direct_call)
    monkeypatch.setattr(stories.knowledge_service, "retrieve", lambda *_: stories.KnowledgeContext())
    monkeypatch.setattr(
        stories.script_generation_service,
        "validate_topic",
        lambda *_: ValidatedTopic(
            subject="history", original_topic="Silk Road", normalized_topic="Silk Road",
            language="en-US", pedagogical_framing="Trade connected cultures",
        ),
    )
    monkeypatch.setattr(
        stories.script_generation_service,
        "generate_draft",
        lambda **_: (_ for _ in ()).throw(ScriptLengthUnavailable("narration too short")),
    )

    with pytest.raises(HTTPException) as error:
        asyncio.run(stories.create_story_draft(
            stories.StoryDraftRequest(subject="history", topic="Silk Road"),
            {"uid": "learner-1"},
        ))

    assert error.value.status_code == 503
    assert "fits the selected video length" in error.value.detail


def test_draft_creation_uses_and_persists_reviewed_knowledge(monkeypatch):
    from types import SimpleNamespace
    from app.domain.models import LearningOutcomes, ValidatedTopic, VideoScript

    monkeypatch.setattr(stories, "run_in_threadpool", direct_call)
    source = {"title": "UNESCO Silk Roads", "url": "https://example.org/silk-roads"}
    context = SimpleNamespace(
        status="grounded", prompt_context="The routes carried goods and ideas.", sources=[source]
    )
    monkeypatch.setattr(stories.knowledge_service, "retrieve", lambda *args: context)
    validated = ValidatedTopic(
        subject="history", original_topic="The Silk Road", normalized_topic="The Silk Road",
        language="en-US", pedagogical_framing="Trade connected regions",
    )
    script = VideoScript(
        title="The Silk Road", hook="A path can connect worlds.",
        full_narration="The routes carried goods and ideas.", estimated_duration_sec=180,
    )
    outcomes = LearningOutcomes(recap="Routes connected people.", quiz=[
        {"question": f"Question {i}?", "options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}, {"id": "c", "text": "C"}], "correct_option": "a", "explanation": "From the story."}
        for i in range(1, 4)
    ])
    script_call = {}
    monkeypatch.setattr(stories.script_generation_service, "validate_topic", lambda *_: validated)
    def generate_draft(**kwargs):
        script_call.update(kwargs)
        from app.domain.models import DraftGeneration
        return DraftGeneration(script=script, learning_outcomes=outcomes)
    monkeypatch.setattr(stories.script_generation_service, "generate_draft", generate_draft)
    stored = {}
    monkeypatch.setattr(stories.story_repository, "create_draft", lambda record: stored.update(record) or {"id": "draft-1", **record})

    response = asyncio.run(stories.create_story_draft(
        stories.StoryDraftRequest(subject="history", topic="The Silk Road"), {"uid": "learner-1"}
    ))

    assert script_call["knowledge_context"] == context.prompt_context
    assert stored["sources"] == [source]
    assert stored["knowledge_status"] == "grounded"
    assert response["sources"] == [source]
    assert response["knowledge_status"] == "grounded"


def test_render_persists_knowledge_sources_for_completed_story(monkeypatch):
    from app.api.v1 import generate

    monkeypatch.setattr(stories, "run_in_threadpool", direct_call)
    source = {"title": "UNESCO Silk Roads", "url": "https://example.org/silk-roads"}
    draft = {
        "id": "draft-1", "user_id": "learner-1", "status": "draft", "subject": "history",
        "topic": "Silk Road", "grade_band": "13-15", "target_duration_sec": 180,
        "language": "en-US", "voice": "female", "script": {"title": "Silk Road", "full_narration": "Trade connected people."},
        "recap": "Trade connected people.", "quiz": [
            {"question": f"Question {i}?", "options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}, {"id": "c", "text": "C"}], "correct_option": "a", "explanation": "From the story."}
            for i in range(1, 4)
        ], "sources": [source], "knowledge_status": "grounded",
    }
    monkeypatch.setattr(stories.story_repository, "get_draft", lambda *_: draft)
    created = {}
    monkeypatch.setattr(
        stories.story_repository,
        "claim_render_job",
        lambda _draft, _owner, task_id: {"draft": {**draft, "status": "rendering"}, "story": created.update({**draft, "id":"story-row", "task_id":task_id}) or {"id":"story-row", "task_id":task_id}},
    )
    monkeypatch.setattr(
        stories.story_repository,
        "update_draft_if_editable",
        lambda _draft_id, _user_id, changes: draft.update(changes) or draft,
    )
    task = type("Task", (), {"apply_async": lambda self, **kwargs: None})()
    monkeypatch.setattr(generate, "generate_story_video_task", task)

    asyncio.run(stories.render_story_draft("draft-1", {"uid": "learner-1"}))

    assert created["sources"] == [source]
    assert created["knowledge_status"] == "grounded"


def test_render_claim_conflict_does_not_queue_duplicate_video(monkeypatch):
    monkeypatch.setattr(stories, "run_in_threadpool", direct_call)
    monkeypatch.setattr(
        stories.story_repository,
        "get_draft",
        lambda *_: {"id": "draft-1", "status": "draft"},
    )
    monkeypatch.setattr(stories.story_repository, "claim_render_job", lambda *_: False)

    with pytest.raises(HTTPException) as error:
        asyncio.run(stories.render_story_draft("draft-1", {"uid": "learner-1"}))

    assert error.value.status_code == 409


def test_render_uses_the_draft_snapshot_returned_by_the_atomic_claim(monkeypatch):
    from app.api.v1 import generate

    monkeypatch.setattr(stories, "run_in_threadpool", direct_call)
    stale_draft = {
        "id": "draft-1", "user_id": "learner-1", "status": "draft", "subject": "history",
        "topic": "Silk Road", "grade_band": "13-15", "target_duration_sec": 180,
        "language": "en-US", "voice": "female",
        "script": {"title": "Old title", "full_narration": "Old narration."},
        "recap": "Old recap.", "quiz": [{"question": "Old question?"}],
    }
    claimed_draft = {
        **stale_draft,
        "status": "rendering",
        "script": {"title": "Latest title", "full_narration": "Latest narration."},
        "recap": "Latest recap.",
        "quiz": [{"question": "Latest question?"}],
    }
    monkeypatch.setattr(stories.story_repository, "get_draft", lambda *_: stale_draft)
    monkeypatch.setattr(stories.story_repository, "claim_render_job", lambda _draft, _owner, task_id: {"draft": claimed_draft, "story": created.update({"title":claimed_draft["script"]["title"]}) or {"id":"story-row", "task_id":task_id}})
    created = {}
    queued = []
    task = type("Task", (), {"apply_async": lambda self, **kwargs: queued.append(kwargs)})()
    monkeypatch.setattr(generate, "generate_story_video_task", task)

    asyncio.run(stories.render_story_draft("draft-1", {"uid": "learner-1"}))

    assert created["title"] == "Latest title"
    assert queued[0]["args"][2] == claimed_draft["script"]
    assert queued[0]["args"][3] == {"recap": "Latest recap.", "quiz": claimed_draft["quiz"]}


def test_editing_a_draft_keeps_its_knowledge_sources(monkeypatch):
    from app.domain.models import VideoScript

    monkeypatch.setattr(stories, "run_in_threadpool", direct_call)
    source = {"title": "UNESCO Silk Roads", "url": "https://example.org/silk-roads"}
    draft = {
        "id": "draft-1", "user_id": "learner-1", "status": "draft", "subject": "history",
        "topic": "Silk Road", "grade_band": "13-15", "target_duration_sec": 180,
        "language": "en-US", "voice": "female", "script": {"title": "Silk Road", "full_narration": "Trade connected people."},
        "recap": "Trade connected people.", "quiz": [
            {"question": f"Question {i}?", "options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}, {"id": "c", "text": "C"}], "correct_option": "a", "explanation": "From the story."}
            for i in range(1, 4)
        ], "sources": [source], "knowledge_status": "grounded",
    }
    monkeypatch.setattr(stories.story_repository, "get_draft", lambda *_: draft)
    monkeypatch.setattr(
        stories.story_repository,
        "update_draft_if_editable",
        lambda _draft_id, _user_id, changes: draft.update(changes) or draft,
    )

    response = asyncio.run(stories.update_story_draft(
        "draft-1", stories.DraftUpdate(script=VideoScript(
            title="Silk Road", hook="Trade connected people.",
            full_narration="Trade connected people.", estimated_duration_sec=180,
        )), {"uid": "learner-1"},
    ))

    assert response["sources"] == [source]
    assert response["knowledge_status"] == "grounded"


def test_edit_cannot_shorten_narration_below_its_selected_runtime(monkeypatch):
    from app.domain.models import VideoScript

    monkeypatch.setattr(stories, "run_in_threadpool", direct_call)
    draft = {
        "id": "draft-1", "user_id": "learner-1", "status": "draft",
        "subject": "history", "topic": "Silk Road", "grade_band": "13-15",
        "target_duration_sec": 180, "language": "en-US", "voice": "female",
        "script": {"title": "Silk Road", "full_narration": "lesson " * 420},
        "recap": "Trade connected people.", "quiz": [], "sources": [],
        "knowledge_status": "none",
    }
    monkeypatch.setattr(stories.story_repository, "get_draft", lambda *_: draft)
    monkeypatch.setattr(
        stories.script_generation_service,
        "generate_learning_outcomes",
        lambda **_: pytest.fail("Too-short narration must be rejected before learning outcomes are regenerated"),
    )

    with pytest.raises(HTTPException) as error:
        asyncio.run(stories.update_story_draft(
            "draft-1",
            stories.DraftUpdate(script=VideoScript(
                title="Silk Road", hook="Trade connected people.",
                full_narration="This is too short.", estimated_duration_sec=180,
            )),
            {"uid": "learner-1"},
        ))

    assert error.value.status_code == 422
    assert "388–524 words" in error.value.detail


def test_edit_loses_conflict_if_render_claims_draft_during_ai_work(monkeypatch):
    from app.domain.models import LearningOutcomes, VideoScript

    monkeypatch.setattr(stories, "run_in_threadpool", direct_call)
    original_script = {
        "title": "Original",
        "hook": "The old hook.",
        "full_narration": "Original narration.",
        "estimated_duration_sec": 180,
    }
    draft = {
        "id": "draft-1", "user_id": "learner-1", "status": "draft", "subject": "history",
        "topic": "Silk Road", "grade_band": "13-15", "target_duration_sec": 180,
        "language": "en-US", "voice": "female", "script": original_script,
        "recap": "Original recap.", "quiz": [], "sources": [], "knowledge_status": "none",
    }

    def generate_outcomes(**_kwargs):
        draft["status"] = "rendering"
        quiz = [
            {
                "question": f"Question {index}?",
                "options": [
                    {"id": "a", "text": "A"},
                    {"id": "b", "text": "B"},
                    {"id": "c", "text": "C"},
                ],
                "correct_option": "a",
                "explanation": "From the story.",
            }
            for index in range(1, 4)
        ]
        return LearningOutcomes(recap="Updated recap.", quiz=quiz)

    def conditional_update(_draft_id, _user_id, changes):
        if draft["status"] != "draft":
            return None
        draft.update(changes)
        return draft.copy()

    monkeypatch.setattr(stories.story_repository, "get_draft", lambda *_: draft)
    monkeypatch.setattr(stories.script_generation_service, "generate_learning_outcomes", generate_outcomes)
    monkeypatch.setattr(
        stories.story_repository,
        "update_draft_if_editable",
        conditional_update,
        raising=False,
    )
    monkeypatch.setattr(
        stories.story_repository,
        "update_draft",
        lambda _draft_id, _user_id, changes: draft.update(changes),
    )

    with pytest.raises(HTTPException) as error:
        asyncio.run(stories.update_story_draft(
            "draft-1",
            stories.DraftUpdate(script=VideoScript(
                title="Revised", hook="A new hook.", full_narration="Revised narration is ready. " * 114,
                estimated_duration_sec=180,
            )),
            {"uid": "learner-1"},
        ))

    assert error.value.status_code == 409
    assert draft["script"] == original_script
    assert draft["recap"] == "Original recap."


def test_delete_story_draft_returns_no_content_to_owner(monkeypatch):
    monkeypatch.setattr(stories, "run_in_threadpool", direct_call)
    monkeypatch.setattr(
        stories.story_repository,
        "delete_draft_if_editable",
        lambda draft_id, user_id: {"id": draft_id, "user_id": user_id, "status": "draft"},
        raising=False,
    )

    response = asyncio.run(stories.delete_story_draft("draft-1", {"uid": "learner-1"}))

    assert response.status_code == 204


def test_delete_story_draft_hides_missing_or_foreign_drafts(monkeypatch):
    monkeypatch.setattr(stories, "run_in_threadpool", direct_call)
    monkeypatch.setattr(stories.story_repository, "delete_draft_if_editable", lambda *_: None, raising=False)
    monkeypatch.setattr(stories.story_repository, "get_draft", lambda *_: None)

    with pytest.raises(HTTPException) as error:
        asyncio.run(stories.delete_story_draft("draft-foreign", {"uid": "learner-1"}))

    assert error.value.status_code == 404


def test_delete_story_draft_returns_conflict_after_render_claim(monkeypatch):
    monkeypatch.setattr(stories, "run_in_threadpool", direct_call)
    monkeypatch.setattr(stories.story_repository, "delete_draft_if_editable", lambda *_: None, raising=False)
    monkeypatch.setattr(
        stories.story_repository,
        "get_draft",
        lambda *_: {"id": "draft-1", "user_id": "learner-1", "status": "rendering"},
    )

    with pytest.raises(HTTPException) as error:
        asyncio.run(stories.delete_story_draft("draft-1", {"uid": "learner-1"}))

    assert error.value.status_code == 409


def test_job_and_history_results_include_saved_knowledge_sources(monkeypatch):
    monkeypatch.setattr(stories, "run_in_threadpool", direct_call)
    source = {"title": "UNESCO Silk Roads", "url": "https://example.org/silk-roads"}
    record = {
        "id": "story-1", "task_id": "job-1", "draft_id": "draft-1", "status": "SUCCESS",
        "progress": 100, "stage": "complete", "message": "Ready", "result": {"recap": "A recap."},
        "sources": [source], "knowledge_status": "grounded",
    }
    monkeypatch.setattr(stories.story_repository, "get_story_job", lambda *_: record)
    job = asyncio.run(stories.get_story_job("job-1", {"uid": "learner-1"}))
    assert job["result"]["sources"] == [source]
    assert job["result"]["knowledge_status"] == "grounded"

    monkeypatch.setattr(stories.story_repository, "list_stories", lambda *_args, **_kwargs: [record])
    history = asyncio.run(stories.list_stories({"uid": "learner-1"}, limit=25, offset=0))
    assert history[0]["result"]["sources"] == [source]
    assert history[0]["result"]["knowledge_status"] == "grounded"


def test_story_history_signs_asset_urls_concurrently_with_a_bound(monkeypatch):
    records = [
        {
            "id": f"story-{index}",
            "result": {"artifacts": {"video_object": f"{index}/video", "audio_object": f"{index}/audio"}},
        }
        for index in range(25)
    ]
    monkeypatch.setattr(stories.story_repository, "list_stories", lambda *_args, **_kwargs: records)
    active = 0
    max_active = 0

    def sign_asset(path):
        return f"signed:{path}"

    async def run_concurrently(function, *args, **kwargs):
        nonlocal active, max_active
        if function is sign_asset:
            active += 1
            max_active = max(max_active, active)
            await asyncio.sleep(0)
            active -= 1
            return function(*args, **kwargs)
        return function(*args, **kwargs)

    monkeypatch.setattr(stories.story_repository, "create_signed_asset_url", sign_asset)
    monkeypatch.setattr(stories, "run_in_threadpool", run_concurrently)

    history = asyncio.run(stories.list_stories({"uid": "learner-1"}, limit=25, offset=0))

    assert len(history) == 25
    assert 1 < max_active <= 8
    assert history[0]["result"]["video_url"] == "signed:0/video"


def test_render_is_queued_only_for_an_owned_saved_draft(monkeypatch):
    from app.api.v1 import generate

    monkeypatch.setattr(stories, "run_in_threadpool", direct_call)
    draft = {
        "id": "draft-1", "user_id": "learner-1", "status": "draft", "subject": "history",
        "topic": "Silk Road", "grade_band": "13-15", "target_duration_sec": 180,
        "language": "en-US", "voice": "female", "script": {"title": "Silk Road", "full_narration": "Trade connected people."},
        "recap": "Trade connected people.", "quiz": [],
    }
    monkeypatch.setattr(stories.story_repository, "get_draft", lambda draft_id, user_id: draft if user_id == "learner-1" else None)
    claims = []
    monkeypatch.setattr(
        stories.story_repository,
        "claim_render_job",
        lambda *args: claims.append(args[:2]) or {"draft": {**draft, "status": "rendering"}, "story": {"id":"story-row", "task_id":args[2]}},
    )
    task = type("Task", (), {"apply_async": lambda self, **kwargs: queued.append(kwargs)})()
    queued = []
    monkeypatch.setattr(generate, "generate_story_video_task", task)

    response = asyncio.run(stories.render_story_draft("draft-1", {"uid": "learner-1"}))
    # A failed worker restores this saved draft to `draft`; a second explicit
    # confirmation queues a fresh job while keeping the reviewed script.
    draft["status"] = "draft"
    retry = asyncio.run(stories.render_story_draft("draft-1", {"uid": "learner-1"}))

    assert response.job_id == queued[0]["task_id"]
    assert retry.job_id == queued[1]["task_id"]
    assert retry.job_id != response.job_id
    assert queued[0]["args"][-1] == "draft-1"
    assert claims == [("draft-1", "learner-1"), ("draft-1", "learner-1")]


def test_provider_failure_does_not_create_a_draft(monkeypatch):
    from app.core.config import settings
    from app.domain.models import ValidatedTopic

    monkeypatch.setattr(settings, "SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "server-only-test-key")
    monkeypatch.setattr(stories, "run_in_threadpool", direct_call)
    monkeypatch.setattr(stories.script_generation_service, "validate_topic", lambda *_: ValidatedTopic(
        subject="history", original_topic="Silk Road", normalized_topic="Silk Road",
        language="en-US", pedagogical_framing="How trade connected cultures",
    ))
    monkeypatch.setattr(stories.script_generation_service, "generate_script", lambda **_: (_ for _ in ()).throw(RuntimeError("provider unavailable")))
    monkeypatch.setattr(stories.story_repository, "create_draft", lambda *_: pytest.fail("must not persist an incomplete draft"))

    with pytest.raises(HTTPException) as error:
        asyncio.run(stories.create_story_draft(
            stories.StoryDraftRequest(subject="history", topic="Silk Road"),
            {"uid": "learner-1"},
        ))

    assert error.value.status_code == 503
