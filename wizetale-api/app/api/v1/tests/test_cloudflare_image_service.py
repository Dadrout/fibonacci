import base64
from io import BytesIO
from unittest.mock import Mock

from PIL import Image

from app.core.config import Settings, settings
from app.services.ai.cloudflare_image_service import CloudflareImageService


def test_cloudflare_image_model_defaults_to_flux1_schnell():
    assert (
        Settings.model_fields["CLOUDFLARE_IMAGE_MODEL"].default
        == "@cf/black-forest-labs/flux-1-schnell"
    )


def test_flux2_dev_request_uses_multipart_form_fields(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "CLOUDFLARE_ACCOUNT_ID", "a" * 32)
    monkeypatch.setattr(settings, "CLOUDFLARE_API_TOKEN", "test-token")
    monkeypatch.setattr(
        settings, "CLOUDFLARE_IMAGE_MODEL", "@cf/black-forest-labs/flux-2-dev"
    )

    image_bytes = BytesIO()
    Image.new("RGB", (1, 1), color="red").save(image_bytes, format="PNG")
    encoded_image = base64.b64encode(image_bytes.getvalue()).decode("ascii")
    response = Mock()
    response.json.return_value = {"success": True, "result": {"image": encoded_image}}
    post = Mock(return_value=response)
    monkeypatch.setattr(
        "app.services.ai.cloudflare_image_service.requests.post", post
    )

    service = CloudflareImageService()
    output_path = service.generate_image(
        prompt="A historical Silk Road market",
        output_path=str(tmp_path / "market.jpg"),
        aspect_ratio="16:9",
    )

    assert output_path == str(tmp_path / "market.png")
    assert Image.open(output_path).size == (1, 1)
    kwargs = post.call_args.kwargs
    assert "data" not in kwargs
    assert dict(kwargs["files"]) == {
        "prompt": (None, "A historical Silk Road market"),
        "width": (None, "1280"),
        "height": (None, "720"),
        "steps": (None, "25"),
    }


def test_flux1_schnell_request_uses_json_and_four_steps(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "CLOUDFLARE_ACCOUNT_ID", "a" * 32)
    monkeypatch.setattr(settings, "CLOUDFLARE_API_TOKEN", "test-token")
    monkeypatch.setattr(
        settings, "CLOUDFLARE_IMAGE_MODEL", "@cf/black-forest-labs/flux-1-schnell"
    )

    image_bytes = BytesIO()
    Image.new("RGB", (1, 1), color="red").save(image_bytes, format="PNG")
    encoded_image = base64.b64encode(image_bytes.getvalue()).decode("ascii")
    response = Mock()
    response.json.return_value = {"success": True, "result": {"image": encoded_image}}
    post = Mock(return_value=response)
    monkeypatch.setattr(
        "app.services.ai.cloudflare_image_service.requests.post", post
    )

    service = CloudflareImageService()
    output_path = service.generate_image(
        prompt="A historical Silk Road market",
        output_path=str(tmp_path / "market.jpg"),
        aspect_ratio="16:9",
    )

    assert output_path == str(tmp_path / "market.png")
    kwargs = post.call_args.kwargs
    assert kwargs["json"] == {
        "prompt": "A historical Silk Road market",
        "steps": 4,
    }
    assert "files" not in kwargs
