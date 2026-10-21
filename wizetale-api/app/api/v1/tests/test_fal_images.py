import importlib.util
from io import BytesIO
from pathlib import Path
from threading import Barrier
from unittest.mock import Mock

import pytest
import requests
from PIL import Image

from app.core.config import Settings, settings
from app.services.ai.provider_factory import get_image_provider
from app.services.pipeline.image_service import ImagePipelineService
from app.api.v1.tests.test_image_pipeline_costs import _specs


def _service(monkeypatch):
    assert importlib.util.find_spec(
        "app.services.ai.fal_image_service"
    ), "fal provider is missing"
    from app.services.ai.fal_image_service import FalImageService

    monkeypatch.setattr(settings, "FAL_KEY", "test-key", raising=False)
    return FalImageService()


def _response(data=None, content=b""):
    return Mock(json=Mock(return_value=data), content=content, raise_for_status=Mock())


def _queue(monkeypatch, result):
    import app.services.ai.fal_image_service as module

    monkeypatch.setattr(
        module.requests,
        "post",
        lambda url, **kw: _response(
            {
                "request_id": "request-1",
                "status_url": "https://queue.fal.run/fal-ai/flux-2/requests/request-1/status",
                "response_url": "https://queue.fal.run/fal-ai/flux-2/requests/request-1",
                "cancel_url": "https://queue.fal.run/fal-ai/flux-2/requests/request-1/cancel",
            }
        ),
    )
    pixels = BytesIO()
    Image.new("RGB", (1280, 720)).save(pixels, "PNG")

    def get(url, **kw):
        if url.endswith("/status"):
            return _response({"status": "COMPLETED"})
        if url.endswith("/request-1"):
            return _response(result)
        assert url == "https://v3.fal.media/test.png"
        assert "headers" not in kw, "API key must not be sent to media CDN"
        return _response(content=pixels.getvalue())

    monkeypatch.setattr(module.requests, "get", get)


def test_fal_factory_selects_configured_provider(monkeypatch):
    monkeypatch.setattr(settings, "IMAGE_PROVIDER", "fal")
    assert get_image_provider().healthcheck()["provider"] == "fal"


def test_fal_downloads_queued_image(monkeypatch, tmp_path):
    service = _service(monkeypatch)
    _queue(
        monkeypatch,
        {
            "images": [{"url": "https://v3.fal.media/test.png"}],
            "has_nsfw_concepts": [False],
        },
    )
    path = tmp_path / "scene.png"
    assert service.generate_image(prompt="Ancient Rome", output_path=str(path)) == str(
        path
    )
    with Image.open(path) as image:
        assert image.size == (1280, 720)


@pytest.mark.parametrize(
    "result",
    [
        {"images": []},
        {
            "images": [{"url": "https://v3.fal.media/test.png"}],
            "has_nsfw_concepts": [True],
        },
        {"error": "generation failed"},
    ],
)
def test_fal_failed_or_flagged_result_returns_no_image(monkeypatch, tmp_path, result):
    service = _service(monkeypatch)
    _queue(monkeypatch, result)
    path = tmp_path / "scene.png"
    assert service.generate_image(prompt="test", output_path=str(path)) is None
    assert not path.exists()


def test_fal_transport_failure_does_not_log_credentials(monkeypatch, tmp_path, caplog):
    service = _service(monkeypatch)
    import app.services.ai.fal_image_service as module

    def fail(*args, **kwargs):
        raise requests.HTTPError("test-key: secret")

    monkeypatch.setattr(module.requests, "post", fail)
    assert (
        service.generate_image(prompt="test", output_path=str(tmp_path / "scene.png"))
        is None
    )
    assert "test-key" not in caplog.text


def test_fal_production_requires_key():
    config = Settings(ENVIRONMENT="production", IMAGE_PROVIDER="fal", FAL_KEY=None)
    errors = config.production_configuration_errors()
    assert "FAL_KEY" in errors
    assert "IMAGE_PROVIDER must be gemini" not in errors


def test_fal_scene_generation_is_concurrent_and_ordered(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "IMAGE_PROVIDER", "fal")
    monkeypatch.setattr(settings, "GENERATION_MAX_IMAGES_PER_STORY", 3)
    barrier = Barrier(3)

    class Provider:
        def generate_image(self, *, output_path, **kwargs):
            barrier.wait(timeout=2)
            return output_path

    service = ImagePipelineService(image_provider=Provider())
    artifacts, fallbacks = service.generate_images(
        topic="Rome", image_specs=_specs(3), temp_dir=tmp_path
    )
    assert [Path(item.image_path).name for item in artifacts] == [
        "scene_001.png",
        "scene_002.png",
        "scene_003.png",
    ]
    assert not fallbacks


def test_fal_submission_uses_server_auth_and_landscape_png(monkeypatch, tmp_path):
    service = _service(monkeypatch)
    _queue(monkeypatch, {"images": [{"url": "https://v3.fal.media/test.png"}]})
    import app.services.ai.fal_image_service as module

    original = module.requests.post

    def post(url, **kwargs):
        assert url == "https://queue.fal.run/fal-ai/flux-2/turbo"
        assert kwargs["headers"]["Authorization"] == "Key test-key"
        assert kwargs["json"] == {
            "prompt": "Ancient Rome\nStyle guidance: watercolor",
            "image_size": "landscape_16_9",
            "num_images": 1,
            "output_format": "png",
            "enable_safety_checker": True,
        }
        return original(url, **kwargs)

    monkeypatch.setattr(module.requests, "post", post)
    assert service.generate_image(
        prompt="Ancient Rome",
        style="watercolor",
        output_path=str(tmp_path / "scene.png"),
    )


def test_fal_without_key_skips_network(monkeypatch, tmp_path):
    service = _service(monkeypatch)
    service.api_key = None
    import app.services.ai.fal_image_service as module

    def unexpected(*args, **kwargs):
        pytest.fail("network request without a key")

    monkeypatch.setattr(module.requests, "post", unexpected)
    assert (
        service.generate_image(prompt="test", output_path=str(tmp_path / "scene.png"))
        is None
    )


def test_fal_timeout_cancels_queued_request(monkeypatch, tmp_path):
    service = _service(monkeypatch)
    _queue(monkeypatch, {})
    import app.services.ai.fal_image_service as module

    times = iter([0, 0, 181])
    monkeypatch.setattr(module.time, "monotonic", lambda: next(times))
    cancelled = []
    monkeypatch.setattr(module.requests, "put", lambda url, **kw: cancelled.append(url))
    assert (
        service.generate_image(prompt="test", output_path=str(tmp_path / "scene.png"))
        is None
    )
    assert cancelled == [
        "https://queue.fal.run/fal-ai/flux-2/requests/request-1/cancel"
    ]


def test_fal_rejects_queue_url_that_would_leak_key(monkeypatch, tmp_path):
    service = _service(monkeypatch)
    import app.services.ai.fal_image_service as module

    monkeypatch.setattr(
        module.requests,
        "post",
        lambda *a, **kw: _response(
            {
                "cancel_url": "https://untrusted.test/cancel",
                "status_url": "https://untrusted.test/status",
                "response_url": "https://untrusted.test/result",
            }
        ),
    )

    def unexpected(*args, **kwargs):
        pytest.fail("credential sent to untrusted URL")

    monkeypatch.setattr(module.requests, "get", unexpected)
    assert (
        service.generate_image(prompt="test", output_path=str(tmp_path / "scene.png"))
        is None
    )
