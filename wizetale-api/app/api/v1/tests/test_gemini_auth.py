import logging
from unittest.mock import Mock

from app.services.ai.gemini_image_service import GeminiImageService
from app.services.ai.gemini_text_service import GeminiTextService
from app.services.ai.gemini_text_service import GeminiGenerationError


def test_text_generation_sends_api_key_in_header_not_url(monkeypatch):
    service = GeminiTextService()
    service.api_key = "private-test-key"
    response = Mock()
    response.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": "ok"}]}}]
    }
    response.raise_for_status.return_value = None
    request = Mock(return_value=response)
    monkeypatch.setattr("app.services.ai.gemini_text_service.requests.post", request)

    result = service._call_model(
        model_name="gemini-test",
        prompt="hello",
        temperature=0.1,
        max_output_tokens=10,
    )

    assert result == "ok"
    assert "private-test-key" not in request.call_args.args[0]
    assert request.call_args.kwargs["headers"]["x-goog-api-key"] == "private-test-key"


def test_image_generation_sends_api_key_in_header_not_url(monkeypatch, tmp_path):
    monkeypatch.setattr("app.services.ai.gemini_image_service.settings.ENABLE_GEMINI_IMAGE", True)
    service = GeminiImageService()
    service.api_key = "private-test-key"
    response = Mock()
    response.json.return_value = {"candidates": []}
    response.raise_for_status.return_value = None
    request = Mock(return_value=response)
    monkeypatch.setattr("app.services.ai.gemini_image_service.requests.post", request)

    service.generate_image(prompt="a map", output_path=str(tmp_path / "map.png"))

    assert "private-test-key" not in request.call_args.args[0]
    assert request.call_args.kwargs["headers"]["x-goog-api-key"] == "private-test-key"


def test_production_generation_requires_paid_gemini_tier(monkeypatch):
    service = GeminiTextService()
    service.api_key = "private-test-key"
    monkeypatch.setattr("app.services.ai.gemini_text_service.settings.ENVIRONMENT", "production")
    monkeypatch.setattr("app.services.ai.gemini_text_service.settings.GEMINI_BILLING_TIER", "unknown")

    try:
        service._ensure_client()
    except GeminiGenerationError as error:
        assert "paid data tier" in error.debug_message
    else:
        raise AssertionError("Production learner generation must require paid-tier billing")


def test_usage_estimate_uses_the_selected_models_rate(monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    service = GeminiTextService()
    service.api_key = "private-test-key"
    service.fallback_model = "fallback-model"
    monkeypatch.setattr("app.services.ai.gemini_text_service.settings.GEMINI_FALLBACK_TEXT_MODEL", "fallback-model")
    response = Mock()
    response.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": "ok"}]}}],
        "usageMetadata": {"promptTokenCount": 1_000_000, "candidatesTokenCount": 1_000_000},
    }
    response.raise_for_status.return_value = None
    monkeypatch.setattr("app.services.ai.gemini_text_service.requests.post", Mock(return_value=response))

    service._call_model(
        model_name="fallback-model", prompt="synthetic", temperature=0.1, max_output_tokens=10
    )

    assert "estimated_cost_usd=3.500000" in caplog.text


def test_text_generation_recovers_from_temporary_provider_overload(monkeypatch):
    import requests
    from app.services.ai import gemini_text_service as module
    service = GeminiTextService()
    service.api_key = 'test-only-key'
    unavailable = requests.Response()
    unavailable.status_code = 503
    unavailable._content = b'{"error":{"status":"UNAVAILABLE"}}'
    unavailable._content_consumed = True
    available = requests.Response()
    available.status_code = 200
    available._content = b'{"candidates":[{"content":{"parts":[{"text":"Recovered narration"}]}}]}'
    responses = iter([unavailable, available])
    monkeypatch.setattr(module.requests, 'post', lambda *args, **kwargs: next(responses))
    monkeypatch.setattr(module.time, 'sleep', lambda *_: None)
    assert service._call_model(model_name='test-model', prompt='Fictional topic', temperature=0.1, max_output_tokens=20) == 'Recovered narration'
