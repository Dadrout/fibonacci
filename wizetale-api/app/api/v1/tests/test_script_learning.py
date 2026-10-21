from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from app.domain.models import (
    DraftGeneration,
    GenerationRequest,
    LearningOutcomes,
    ValidatedTopic,
    VideoScript,
)
from app.services.pipeline.script_service import ScriptGenerationService


def test_topic_validation_requires_an_explicit_safety_verdict():
    from app.services.pipeline.script_service import TopicValidationPayload

    with pytest.raises(ValidationError):
        TopicValidationPayload.model_validate({
            "normalized_topic": "Ancient Rome",
            "pedagogical_framing": "How the republic grew",
        })


def test_script_generation_uses_grade_band_and_requested_duration():
    text = Mock()
    text.generate_structured.return_value = VideoScript(
        title="Rome",
        hook="A story about Rome.",
        full_narration="Rome grew through strong alliances. " * 61,
        estimated_duration_sec=120,
    )
    service = ScriptGenerationService(text_service=text)
    request = GenerationRequest(
        subject="history",
        topic="Ancient Rome",
        user_id="user-1",
        grade_band="10-12",
        target_duration_sec=120,
    )
    topic = ValidatedTopic(
        subject="history",
        original_topic="Ancient Rome",
        normalized_topic="Ancient Rome",
        language="en-US",
        pedagogical_framing="How Rome grew",
    )

    service.generate_script(request=request, validated_topic=topic)

    prompt = text.generate_structured.call_args.kwargs["prompt"]
    assert "10-12" in prompt
    assert "120" in prompt


def test_script_generation_includes_reviewed_facts_as_grounding_context():
    text = Mock()
    text.generate_structured.return_value = VideoScript(
        title="Silk Road", hook="A story about connected routes.",
        full_narration="Merchants traded goods along connected routes. " * 76, estimated_duration_sec=120,
    )
    service = ScriptGenerationService(text_service=text)
    request = GenerationRequest(
        subject="history", topic="The Silk Road", user_id="user-1", grade_band="13-15",
    )
    topic = ValidatedTopic(
        subject="history", original_topic="The Silk Road", normalized_topic="The Silk Road",
        language="en-US", pedagogical_framing="Trade and cultural exchange",
    )

    service.generate_script(
        request=request,
        validated_topic=topic,
        knowledge_context="- Merchants traded goods and ideas across regions.",
    )

    prompt = text.generate_structured.call_args.kwargs["prompt"]
    assert "Reviewed source notes" in prompt
    assert "Merchants traded goods and ideas across regions." in prompt
    assert "do not add unsupported details" in prompt


def test_learning_outcomes_are_generated_as_three_questions():
    text = Mock()
    expected = LearningOutcomes(
        recap="Rome expanded through alliances and conquest.",
        quiz=[
            {
                "question": f"Question {index}?",
                "options": [
                    {"id": "a", "text": "One"},
                    {"id": "b", "text": "Two"},
                    {"id": "c", "text": "Three"},
                ],
                "correct_option": "a",
                "explanation": "The story explains this.",
            }
            for index in range(1, 4)
        ],
    )
    text.generate_structured.return_value = expected
    service = ScriptGenerationService(text_service=text)

    result = service.generate_learning_outcomes(
        topic="Ancient Rome",
        narration="Rome expanded through alliances and conquest.",
        language="en-US",
        grade_band="10-12",
    )

    assert len(result.quiz) == 3
    assert result.recap.startswith("Rome expanded")


def test_draft_generation_combines_script_and_learning_outcomes_in_one_ai_call():
    text = Mock()
    outcomes = LearningOutcomes(
        recap="Trade connected distant regions.",
        quiz=[
            {
                "question": f"Question {index}?",
                "options": [
                    {"id": "a", "text": "One"},
                    {"id": "b", "text": "Two"},
                    {"id": "c", "text": "Three"},
                ],
                "correct_option": "a",
                "explanation": "The story explains this.",
            }
            for index in range(1, 4)
        ],
    )
    expected = DraftGeneration(
        script=VideoScript(
            title="Trade Routes",
            hook="A caravan carries more than goods.",
            full_narration="Merchants shared goods and ideas. " * 61,
            estimated_duration_sec=120,
        ),
        learning_outcomes=outcomes,
    )
    text.generate_structured.return_value = expected
    service = ScriptGenerationService(text_service=text)
    request = GenerationRequest(
        subject="history",
        topic="The Silk Road",
        user_id="user-1",
        grade_band="13-15",
        target_duration_sec=120,
    )
    topic = ValidatedTopic(
        subject="history",
        original_topic="The Silk Road",
        normalized_topic="The Silk Road",
        language="en-US",
        pedagogical_framing="Trade and cultural exchange",
    )

    result = service.generate_draft(
        request=request,
        validated_topic=topic,
        knowledge_context="Reviewed fact: merchants exchanged goods and ideas.",
    )

    assert text.generate_structured.call_count == 1
    assert result.script.title == "Trade Routes"
    assert len(result.learning_outcomes.quiz) == 3
    prompt = text.generate_structured.call_args.kwargs["prompt"]
    assert "Reviewed fact: merchants exchanged goods and ideas." in prompt


def _draft_with_narration(narration: str, estimated_duration_sec: int = 180):
    outcomes = LearningOutcomes(
        recap="A concise recap.",
        quiz=[
            {
                "question": f"Question {index}?",
                "options": [
                    {"id": "a", "text": "One"},
                    {"id": "b", "text": "Two"},
                    {"id": "c", "text": "Three"},
                ],
                "correct_option": "a",
                "explanation": "The story explains this.",
            }
            for index in range(1, 4)
        ],
    )
    return DraftGeneration(
        script=VideoScript(
            title="Trade Routes",
            hook="A story about connected routes.",
            full_narration=narration,
            estimated_duration_sec=estimated_duration_sec,
        ),
        learning_outcomes=outcomes,
    )


def test_short_draft_is_revised_to_the_requested_runtime_word_count():
    text = Mock()
    text.generate_structured.side_effect = [
        _draft_with_narration("A short opening. " * 20, estimated_duration_sec=53),
        _draft_with_narration("lesson " * 456, estimated_duration_sec=53),
    ]
    service = ScriptGenerationService(text_service=text)
    request = GenerationRequest(
        subject="history",
        topic="The Silk Road",
        user_id="user-1",
        target_duration_sec=180,
    )
    topic = ValidatedTopic(
        subject="history",
        original_topic="The Silk Road",
        normalized_topic="The Silk Road",
        language="en-US",
        pedagogical_framing="Trade and cultural exchange",
    )

    result = service.generate_draft(request=request, validated_topic=topic)

    word_count = len(result.script.full_narration.split())
    assert 388 <= word_count <= 524
    assert result.script.estimated_duration_sec == 180
    assert text.generate_structured.call_count == 2
    correction_prompt = text.generate_structured.call_args_list[1].kwargs["prompt"]
    assert "388–524 words" in correction_prompt


def test_draft_gets_a_second_length_correction_when_the_first_is_still_short():
    text = Mock()
    text.generate_structured.side_effect = [
        _draft_with_narration("lesson " * 300),
        _draft_with_narration("lesson " * 350),
        _draft_with_narration("lesson " * 464),
    ]
    service = ScriptGenerationService(text_service=text)
    request = GenerationRequest(
        subject="history",
        topic="The Silk Road",
        user_id="user-1",
        target_duration_sec=180,
    )
    topic = ValidatedTopic(
        subject="history",
        original_topic="The Silk Road",
        normalized_topic="The Silk Road",
        language="en-US",
        pedagogical_framing="Trade and cultural exchange",
    )

    result = service.generate_draft(request=request, validated_topic=topic)

    assert len(result.script.full_narration.split()) == 464
    assert text.generate_structured.call_count == 3

@pytest.mark.parametrize('words', [409, 428, 435, 500])
def test_approximate_three_minute_draft_is_accepted_without_regeneration(words):
    text = Mock()
    text.generate_structured.return_value = _draft_with_narration('lesson ' * words)
    service = ScriptGenerationService(text_service=text)
    request = GenerationRequest(subject='history', topic='Trade', user_id='learner', target_duration_sec=180)
    topic = ValidatedTopic(subject='history', original_topic='Trade', normalized_topic='Trade', language='en-US', pedagogical_framing='Exchange')
    result = service.generate_draft(request=request, validated_topic=topic)
    assert len(result.script.full_narration.split()) == words
    assert text.generate_structured.call_count == 1

@pytest.mark.parametrize('words', [20, 300, 600, 1000])
def test_three_minute_narration_still_rejects_materially_wrong_lengths(words):
    assert not ScriptGenerationService(text_service=Mock()).narration_length_is_valid('lesson ' * words, 180)
