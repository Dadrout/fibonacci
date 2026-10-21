from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
import logging
import re
from pathlib import Path
from uuid import uuid4

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover - dependency may be absent in tests
    Image = None
    ImageDraw = None
    ImageFont = None

from app.core.config import settings
from app.core.usage_context import generation_id
from app.domain.models import ImageArtifact, SceneImageSpec
from app.services.ai.provider_factory import get_image_provider

logger = logging.getLogger(__name__)


class ImagePipelineService:
    def __init__(self, image_provider=None):
        self.image_provider = image_provider or get_image_provider()

    def generate_images(
        self,
        *,
        topic: str,
        image_specs: list[SceneImageSpec],
        temp_dir: Path,
    ) -> tuple[list[ImageArtifact], list[str]]:
        fallbacks_used: list[str] = []
        max_images = settings.GENERATION_MAX_IMAGES_PER_STORY
        if len(image_specs) <= max_images:
            selected_specs = image_specs
        elif max_images == 0:
            selected_specs = []
        elif max_images == 1:
            selected_specs = [image_specs[len(image_specs) // 2]]
        else:
            selected_indices = {
                round(index * (len(image_specs) - 1) / (max_images - 1))
                for index in range(max_images)
            }
            selected_specs = [
                spec
                for index, spec in enumerate(image_specs)
                if index in selected_indices
            ]

        if settings.IMAGE_PROVIDER.lower() == "gemini":
            logger.info(
                "ai_usage generation_id=%s provider=gemini model=%s operation=image_generation image_limit=%d selected_images=%d estimated_cost_usd=%.4f",
                generation_id.get(),
                settings.GEMINI_IMAGE_MODEL,
                max_images,
                len(selected_specs),
                len(selected_specs) * settings.GEMINI_IMAGE_USD_PER_IMAGE,
            )

        def generate_scene(spec):
            output_path = temp_dir / f"scene_{spec.scene_index:03d}.png"
            full_prompt = self._compose_prompt(spec)
            sensitive_prompt = self._is_sensitive_historical_prompt(full_prompt)
            prompt = (
                self._compose_policy_safer_prompt(spec)
                if sensitive_prompt
                else full_prompt
            )
            generated_path = self.image_provider.generate_image(
                prompt=prompt,
                output_path=str(output_path),
                style=(
                    "historical editorial illustration"
                    if sensitive_prompt
                    else ", ".join(spec.style_tags) if spec.style_tags else None
                ),
            )

            fallback_used = False
            source = settings.IMAGE_PROVIDER
            if not generated_path:
                fallback_used = True
                source = "placeholder"
                generated_path = self._create_placeholder_image(
                    topic=topic,
                    spec=spec,
                    image_path=temp_dir
                    / f"scene_{uuid4().hex[:8]}_{spec.scene_index}.jpg",
                )

            return ImageArtifact(
                scene_index=spec.scene_index,
                image_path=str(generated_path),
                source=source,
                fallback_used=fallback_used,
                prompt=prompt,
            )

        if settings.IMAGE_PROVIDER.lower() in {"fal", "cloudflare"} and selected_specs:
            with ThreadPoolExecutor(
                max_workers=settings.IMAGE_GENERATION_CONCURRENCY
            ) as executor:
                futures = [
                    executor.submit(copy_context().run, generate_scene, spec)
                    for spec in selected_specs
                ]
                generated = [future.result() for future in futures]
        else:
            generated = [generate_scene(spec) for spec in selected_specs]
        generated_by_scene = {artifact.scene_index: artifact for artifact in generated}

        artifacts: list[ImageArtifact] = []
        selected_indices = sorted(generated_by_scene)
        for spec in image_specs:
            selected_scene = min(
                selected_indices,
                key=lambda scene_index: abs(scene_index - spec.scene_index),
                default=None,
            )
            if selected_scene is None:
                artifact = ImageArtifact(
                    scene_index=spec.scene_index,
                    image_path=self._create_placeholder_image(
                        topic=topic,
                        spec=spec,
                        image_path=temp_dir / f"scene_{spec.scene_index:03d}.jpg",
                    ),
                    source="placeholder",
                    fallback_used=True,
                    prompt=spec.prompt,
                )
                fallbacks_used.append(f"image_scene_{spec.scene_index}")
            else:
                artifact = generated_by_scene[selected_scene].model_copy(
                    update={"scene_index": spec.scene_index}
                )
                if artifact.fallback_used:
                    fallbacks_used.append(f"image_scene_{spec.scene_index}")
            artifacts.append(artifact)

        return artifacts, fallbacks_used

    def _compose_prompt(self, spec: SceneImageSpec) -> str:
        negatives = ", ".join(spec.negative_constraints) or "no text overlays"
        styles = ", ".join(spec.style_tags) or "cinematic, documentary"
        return (
            f"{spec.prompt}. Style: {styles}. Consistency anchor: {spec.consistency_anchor}. "
            f"Avoid: {negatives}."
        )

    def _compose_simplified_prompt(self, spec: SceneImageSpec) -> str:
        prompt = self._shrink_prompt(spec.prompt, max_words=45)
        return (
            f"{prompt}. Historical documentary illustration. "
            "16:9 composition, cinematic realism, no modern objects."
        )

    def _compose_policy_safer_prompt(self, spec: SceneImageSpec) -> str:
        prompt = self._shrink_prompt(spec.prompt, max_words=28)
        replacements = {
            r"\bAdolf Hitler\b": "Axis-era authoritarian leader",
            r"\bBenito Mussolini\b": "Axis-era Italian leader",
            r"\bHideki Tojo\b": "Axis-era Japanese military leader",
            r"\bHitler\b": "Axis-era authoritarian leader",
            r"\bMussolini\b": "Axis-era Italian leader",
            r"\bNazi Germany\b": "wartime Germany",
            r"\bFascist Italy\b": "wartime Italy",
            r"\bImperial Japan\b": "wartime Japan",
            r"\bflags?\b": "banners",
            r"\bparades?\b": "public gatherings",
            r"\brallies?\b": "public gatherings",
            r"\bportrait\b": "dramatic scene",
        }
        safer_prompt = prompt
        for pattern, replacement in replacements.items():
            safer_prompt = re.sub(
                pattern, replacement, safer_prompt, flags=re.IGNORECASE
            )

        return (
            f"{safer_prompt}. Historical 1940s documentary illustration, symbolic wartime leadership, "
            "map room atmosphere, subdued palette, no insignia, no propaganda symbols, no text."
        )

    def _shrink_prompt(self, prompt: str, *, max_words: int) -> str:
        words = prompt.split()
        if len(words) <= max_words:
            return prompt.strip()
        return " ".join(words[:max_words]).rstrip(",.;:") + "."

    def _is_sensitive_historical_prompt(self, prompt: str) -> bool:
        lowered = prompt.lower()
        markers = [
            "hitler",
            "mussolini",
            "tojo",
            "nazi",
            "fascist",
            "axis leaders",
            "military parades",
            "political rallies",
        ]
        return any(marker in lowered for marker in markers)

    def _create_placeholder_image(
        self,
        *,
        topic: str,
        spec: SceneImageSpec,
        image_path: Path,
    ) -> str:
        if not Image or not ImageDraw or not ImageFont:
            raise RuntimeError("Pillow is required for placeholder image generation.")

        image = Image.new("RGB", (1280, 720), "#102542")
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default()
        draw.rectangle([(72, 72), (1208, 648)], outline=(255, 255, 255), width=3)
        draw.text((110, 120), topic[:80], fill=(255, 255, 255), font=font)
        draw.text((110, 220), spec.prompt[:220], fill=(240, 240, 240), font=font)
        image.save(image_path, "JPEG", quality=92)
        logger.info("Created placeholder image for scene=%s", spec.scene_index)
        return str(image_path)


image_pipeline_service = ImagePipelineService()
