import os
import asyncio

os.environ.setdefault("GEMINI_API_KEY", "test-gemini-key")

import pytest
from pydantic import ValidationError

from app.domain.models import StoryDraftRequest
from starlette.requests import Request
from fastapi import HTTPException
from app.api.dependencies import get_current_user


def test_story_draft_accepts_supported_subject_and_grade_band():
    request = StoryDraftRequest(
        subject="history",
        topic="Ancient Rome",
        grade_band="10-12",
        target_duration_sec=180,
        language="en-US",
    )

    assert request.topic == "Ancient Rome"
    assert request.target_duration_sec == 180


def test_story_draft_rejects_out_of_range_duration():
    with pytest.raises(ValidationError):
        StoryDraftRequest(
            subject="history",
            topic="Ancient Rome",
            grade_band="10-12",
            target_duration_sec=900,
        )


def test_story_draft_rejects_blank_topic():
    with pytest.raises(ValidationError):
        StoryDraftRequest(
            subject="history",
            topic="   ",
            grade_band="10-12",
        )


def test_story_history_requires_authenticated_session():
    request = Request({"type": "http", "headers": [], "method": "GET", "path": "/"})

    with pytest.raises(HTTPException) as error:
        asyncio.run(get_current_user(request))

    assert error.value.status_code == 401
