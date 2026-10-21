from unittest.mock import Mock

from app.core.config import settings
from app.domain.models import SceneImageSpec, VideoScript
from app.services.pipeline.scene_service import (
    RenderPlan,
    SceneAssignment,
    SceneService,
)


def _long_script() -> VideoScript:
    return VideoScript(
        title="The Silk Road",
        hook="Trade carried ideas as well as goods.",
        full_narration=" ".join(["Silk Road trade connected distant cities."] * 120),
        estimated_duration_sec=240,
    )


def test_render_plan_requests_topic_driven_sections_between_five_and_ten(monkeypatch):
    monkeypatch.setattr(settings, "GENERATION_MAX_SCENES", 10)
    text = Mock()
    text.generate_structured.side_effect = RuntimeError("planner unavailable")
    service = SceneService(text_service=text)

    scenes, image_specs = service.build_render_plan(_long_script(), "en-US")

    prompt = text.generate_structured.call_args.kwargs["prompt"]
    assert "5 to 10 topic-driven sections" in prompt
    assert 5 <= len(scenes) <= 10
    assert len(image_specs) == len(scenes)


def test_short_model_scene_plan_falls_back_to_at_least_five_sections(monkeypatch):
    monkeypatch.setattr(settings, "GENERATION_MAX_SCENES", 10)
    text = Mock()
    text.generate_structured.return_value = RenderPlan(
        scenes=[
            SceneAssignment(
                scene_index=1,
                start_segment_index=1,
                end_segment_index=12,
                visual_goal="A caravan crosses the desert.",
                on_screen_subtitle_text="Across the desert",
            )
        ],
        images=[
            SceneImageSpec(
                scene_index=1,
                prompt="A caravan crosses the desert.",
            )
        ],
    )
    service = SceneService(text_service=text)

    scenes, image_specs = service.build_render_plan(_long_script(), "en-US")

    assert 5 <= len(scenes) <= 10
    assert len(image_specs) == len(scenes)

