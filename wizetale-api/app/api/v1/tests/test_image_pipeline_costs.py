from pathlib import Path
from unittest.mock import Mock

from app.domain.models import SceneImageSpec
from app.services.pipeline.image_service import ImagePipelineService


def _specs(count: int) -> list[SceneImageSpec]:
    return [
        SceneImageSpec(
            scene_index=index,
            prompt=f"Illustration {index}",
            style_tags=["educational illustration"],
        )
        for index in range(1, count + 1)
    ]


def test_image_generation_caps_unique_paid_illustrations_at_configured_limit(
    monkeypatch, tmp_path: Path
):
    from app.core.config import settings

    monkeypatch.setattr(settings, "GENERATION_MAX_IMAGES_PER_STORY", 3, raising=False)
    provider = Mock()
    provider.generate_image.side_effect = [
        "/tmp/key-image-1.png",
        "/tmp/key-image-2.png",
        "/tmp/key-image-3.png",
    ]
    service = ImagePipelineService(image_provider=provider)

    artifacts, fallbacks = service.generate_images(
        topic="Ancient Rome",
        image_specs=_specs(8),
        temp_dir=tmp_path,
    )

    assert provider.generate_image.call_count == 3
    assert len(artifacts) == 8
    assert len({artifact.image_path for artifact in artifacts}) == 3
    assert [artifact.scene_index for artifact in artifacts] == list(range(1, 9))
    assert not fallbacks


def test_failed_paid_image_attempt_uses_placeholder_without_retrying(
    monkeypatch, tmp_path: Path
):
    from app.core.config import settings
    monkeypatch.setattr(settings, "GENERATION_MAX_IMAGES_PER_STORY", 3)
    provider = Mock()
    provider.generate_image.return_value = None
    service = ImagePipelineService(image_provider=provider)
    monkeypatch.setattr(
        service,
        "_create_placeholder_image",
        lambda **kwargs: "/tmp/fallback.jpg",
    )

    artifacts, fallbacks = service.generate_images(
        topic="Ancient Rome",
        image_specs=_specs(1),
        temp_dir=tmp_path,
    )

    assert provider.generate_image.call_count == 1
    assert artifacts[0].source == "placeholder"
    assert artifacts[0].image_path == "/tmp/fallback.jpg"
    assert fallbacks == ["image_scene_1"]


def test_settings_allow_one_image_for_each_of_ten_sections():
    from app.core.config import Settings

    configured = Settings(
        GENERATION_MAX_SCENES=10,
        GENERATION_MAX_IMAGES_PER_STORY=10,
    )

    assert configured.GENERATION_MAX_SCENES == 10
    assert configured.GENERATION_MAX_IMAGES_PER_STORY == 10


def test_each_section_gets_a_unique_image_when_ten_are_allowed(
    monkeypatch, tmp_path: Path
):
    from app.core.config import settings

    monkeypatch.setattr(settings, "GENERATION_MAX_IMAGES_PER_STORY", 10)
    provider = Mock()
    provider.generate_image.side_effect = [f"/tmp/section-{index}.png" for index in range(1, 11)]
    service = ImagePipelineService(image_provider=provider)

    artifacts, fallbacks = service.generate_images(
        topic="The Silk Road",
        image_specs=_specs(10),
        temp_dir=tmp_path,
    )

    assert provider.generate_image.call_count == 10
    assert len({artifact.image_path for artifact in artifacts}) == 10
    assert not fallbacks
