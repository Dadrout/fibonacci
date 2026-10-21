import asyncio
from copy import deepcopy
import importlib.util
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError


def modules():
    assert (
        importlib.util.find_spec("app.domain.study_materials") is not None
    ), "Student study material contracts are missing"
    assert (
        importlib.util.find_spec("app.api.v1.study_materials") is not None
    ), "Student study material API is missing"
    from app.domain import study_materials as models
    from app.api.v1 import study_materials as routes

    return models, routes


def sample_content(kind):
    return {
        "title": "Fractions",
        "instructions": "Explore equal parts.",
        "flashcards": (
            [
                {"front": f"Question {index}", "back": f"Answer {index}"}
                for index in range(12)
            ]
            if kind == "flashcards"
            else []
        ),
        "questions": (
            [
                {
                    "prompt": f"Question {index}",
                    "options": [
                        {"id": choice, "text": f"Choice {choice}"}
                        for choice in ["a", "b", "c", "d"]
                    ],
                    "correct_option": "a",
                    "explanation": "One equal part out of two is one half.",
                }
                for index in range(10)
            ]
            if kind == "quiz"
            else []
        ),
        "slides": (
            [
                {
                    "title": f"Fractions {index}",
                    "key_points": ["A fraction describes equal parts."],
                    "speaker_notes": "Explain the idea with an example.",
                }
                for index in range(8)
            ]
            if kind == "presentation"
            else []
        ),
    }


@pytest.mark.parametrize("kind", ["flashcards", "quiz", "presentation"])
def test_student_material_presets_validate_complete_generated_content(kind):
    models, _ = modules()
    content = models.StudyMaterialContent.model_validate(sample_content(kind))
    models.validate_study_content(kind, content, generated=True)


def test_student_material_input_supports_k12_subjects_and_three_languages():
    models, _ = modules()
    for subject in [
        "language_arts",
        "math",
        "science",
        "history_social_studies",
        "geography",
        "philosophy",
    ]:
        for grade in ["K", "1", "12"]:
            for language in ["en-US", "ru-RU", "kk-KZ"]:
                value = models.StudyContext(
                    subject=subject, grade=grade, language=language, topic=" Fractions "
                )
                assert value.topic == "Fractions"
    with pytest.raises(ValidationError):
        models.StudyContext(subject="math", grade="13", topic="Fractions")


def test_all_six_student_subjects_are_supported_by_story_and_study_inputs():
    from app.domain.models import StoryDraftRequest

    subjects = [
        "language_arts",
        "math",
        "science",
        "history_social_studies",
        "geography",
        "philosophy",
    ]
    models, _ = modules()
    for subject in subjects:
        assert models.StudyContext(subject=subject, grade="6", topic="Atoms")
        assert StoryDraftRequest(subject=subject, topic="Atoms")


def test_quiz_scoring_returns_feedback_and_rejects_incomplete_answers():
    models, _ = modules()
    content = models.StudyMaterialContent.model_validate(sample_content("quiz"))
    result = models.score_quiz(
        content, {str(index + 1): ("a" if index == 0 else "b") for index in range(10)}
    )
    assert result["score"] == 1
    assert result["total"] == 10
    assert result["results"][0]["correct"] is True
    assert result["results"][1]["correct_option"] == "a"
    with pytest.raises(ValueError, match="every question"):
        models.score_quiz(content, {"1": "a"})


class MemoryStudyRepository:
    def __init__(self):
        self.rows = {}

    def claim_material(self, row):
        if row["id"] in self.rows:
            return None
        self.rows[row["id"]] = row
        return row

    def material(self, material_id, user_id):
        row = self.rows.get(str(material_id))
        return row if row and row["user_id"] == user_id else None

    def materials(self, user_id, limit, offset):
        rows = [row for row in self.rows.values() if row["user_id"] == user_id]
        return rows[offset : offset + limit]

    def finish_material(self, material_id, user_id, changes):
        row = self.material(material_id, user_id)
        if not row:
            return None
        row.update(changes)
        return row

    def update_material(self, material_id, user_id, revision, content):
        row = self.material(material_id, user_id)
        if not row or row["revision"] != revision:
            return None
        row.update(content=content, revision=revision + 1)
        return row

    def delete_material(self, material_id, user_id):
        if self.material(material_id, user_id):
            del self.rows[str(material_id)]


@pytest.fixture
def setup_routes(monkeypatch):
    models, routes = modules()
    repository = MemoryStudyRepository()
    monkeypatch.setattr(routes, "study_material_repository", repository)
    monkeypatch.setattr(routes.story_repository, "is_user_deleting", lambda _uid: False)

    class NoVisuals:
        @staticmethod
        def decorate(row, _kind):
            return deepcopy(row)

        @staticmethod
        def queue(_row, _kind):
            return None

        @staticmethod
        def cleanup(_row, _kind):
            return None

    monkeypatch.setattr(routes, "presentation_visual_service", NoVisuals())

    async def inline(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    monkeypatch.setattr(routes, "run_in_threadpool", inline)
    monkeypatch.setattr(
        routes.study_generation_service,
        "generate",
        lambda _context, kind: models.StudyMaterialContent.model_validate(
            sample_content(kind)
        ),
    )
    return models, routes, repository


def test_generated_quiz_hides_answer_key_until_server_check(setup_routes):
    models, routes, repository = setup_routes
    request = models.StudyMaterialGenerate(
        kind="quiz",
        request_id=uuid4(),
        context={
            "subject": "math",
            "grade": "6",
            "topic": "Fractions",
            "language": "en-US",
        },
    )
    created = asyncio.run(routes.generate_study_material(request, {"uid": "learner"}))
    assert created["status"] == "ready"
    assert "correct_option" not in created["content"]["questions"][0]
    full = repository.material(created["id"], "learner")
    checked = asyncio.run(
        routes.check_study_quiz(
            created["id"],
            routes.QuizCheck(answers={"1": "a", **{str(i): "b" for i in range(2, 11)}}),
            {"uid": "learner"},
        )
    )
    assert checked["score"] == 1
    assert checked["results"][1]["correct_option"] == "a"
    assert full["content"]["questions"][1]["correct_option"] == "a"


def test_student_materials_are_owner_scoped_and_revision_checked(setup_routes):
    models, routes, _ = setup_routes
    request = models.StudyMaterialGenerate(
        kind="presentation",
        request_id=uuid4(),
        context={
            "subject": "science",
            "grade": "7",
            "topic": "Water cycle",
            "language": "kk-KZ",
        },
    )
    created = asyncio.run(routes.generate_study_material(request, {"uid": "learner"}))
    assert len(created["content"]["slides"]) == 8
    with pytest.raises(HTTPException) as hidden:
        asyncio.run(routes.get_study_material(created["id"], {"uid": "another"}))
    assert hidden.value.status_code == 404
    update = models.StudyMaterialUpdate(
        revision=1,
        content=models.StudyMaterialContent.model_validate(
            {
                **sample_content("presentation"),
                "title": "Water cycle: revised",
            }
        ),
    )
    saved = asyncio.run(
        routes.edit_study_material(created["id"], update, {"uid": "learner"})
    )
    assert saved["revision"] == 2
    with pytest.raises(HTTPException) as stale:
        asyncio.run(
            routes.edit_study_material(created["id"], update, {"uid": "learner"})
        )
    assert stale.value.status_code == 409

    asyncio.run(routes.delete_study_material(created["id"], {"uid": "learner"}))
    with pytest.raises(HTTPException) as deleted:
        asyncio.run(routes.get_study_material(created["id"], {"uid": "learner"}))
    assert deleted.value.status_code == 404
