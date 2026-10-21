import math
import re
import json

from pydantic import BaseModel, Field

from app.core.config import settings
from app.domain.models import Scene, SceneImageSpec, VideoScript
from app.services.ai.provider_factory import get_text_provider


class ScenePlan(BaseModel):
    scenes: list[Scene] = Field(default_factory=list)


class SceneImagePlan(BaseModel):
    images: list[SceneImageSpec] = Field(default_factory=list)


class NarrationSegment(BaseModel):
    segment_index: int
    text: str
    word_count: int


class SceneAssignment(BaseModel):
    scene_index: int
    start_segment_index: int
    end_segment_index: int
    visual_goal: str
    on_screen_subtitle_text: str


class SceneAssignmentPlan(BaseModel):
    scenes: list[SceneAssignment] = Field(default_factory=list)


class RenderPlan(BaseModel):
    scenes: list[SceneAssignment] = Field(default_factory=list)
    images: list[SceneImageSpec] = Field(default_factory=list)


class SceneService:
    def __init__(self, text_service=None):
        self.text_service = text_service or get_text_provider()

    def _section_limit(self, segment_count: int) -> tuple[int, int]:
        maximum = max(1, min(10, settings.GENERATION_MAX_SCENES))
        minimum = min(5, maximum)
        return minimum, min(maximum, max(minimum, segment_count))

    def split_into_scenes(self, script: VideoScript, language: str) -> list[Scene]:
        segments = self._segment_narration(script.full_narration)
        minimum_scene_count, target_scene_count = self._section_limit(len(segments))

        prompt = (
            f"Create a chronological scene plan for an educational video in {language}.\n"
            f"Create between {minimum_scene_count} and {target_scene_count} topic-driven sections.\n"
            "Choose the section count based on the topic's natural story beats; do not force a fixed count.\n"
            "You are given ordered narration segments. Group contiguous segments into scenes.\n\n"
            "Rules:\n"
            "- Every segment must be covered exactly once.\n"
            "- Scene ranges must be contiguous and non-overlapping.\n"
            "- start_segment_index and end_segment_index are inclusive.\n"
            "- Keep scenes balanced in length.\n"
            "- visual_goal should describe one strong historical image concept.\n"
            "- on_screen_subtitle_text must be short, readable, and free of markdown.\n\n"
            f"Segments JSON:\n{self._segments_to_json(segments)}"
        )

        try:
            result = self.text_service.generate_structured(
                prompt=prompt,
                operation_name="scene splitting",
                schema=SceneAssignmentPlan,
                temperature=0.1,
                max_output_tokens=1800,
                system_prompt="You are a precise video editor who returns compact structured scene assignments.",
            )
            assignments = self._normalize_assignments(
                assignments=result.scenes,
                segment_count=len(segments),
                target_scene_count=target_scene_count,
            )
        except Exception:
            assignments = self._fallback_assignments(segments, target_scene_count)

        return self._assignments_to_scenes(assignments, segments, script.estimated_duration_sec)

    def build_render_plan(
        self,
        script: VideoScript,
        language: str,
        school_grade: str | None = None,
    ) -> tuple[list[Scene], list[SceneImageSpec]]:
        """Plan narration scenes and their illustrations with one model request."""
        segments = self._segment_narration(script.full_narration)
        minimum_scene_count, target_scene_count = self._section_limit(len(segments))
        grade_guidance = (
            f"School grade: {school_grade}. Adapt scene concepts and illustration details for this exact grade.\n"
            if school_grade is not None
            else "Preserve age appropriateness for the learner age band supplied by the script.\n"
        )
        prompt = (
            f"Create a chronological educational video render plan in {language}.\n"
            f"Group every ordered narration segment exactly once into {minimum_scene_count} to {target_scene_count} "
            "topic-driven sections. Choose the number based on the topic's natural story beats; do not force a fixed count.\n"
            "Each section becomes one video scene and must have its own distinct image.\n"
            "For each section return its inclusive start/end segment indexes, a short visual goal, "
            "readable subtitle, and one detailed English illustration prompt.\n"
            "Preserve chronology and subject accuracy. Avoid text in images.\n"
            f"{grade_guidance}"
            f"Video title: {script.title}\nSegments JSON:\n{self._segments_to_json(segments)}"
        )
        try:
            plan = self.text_service.generate_structured(
                prompt=prompt,
                operation_name="scene and image planning",
                schema=RenderPlan,
                temperature=0.2,
                max_output_tokens=3600,
                system_prompt="You are a precise educational video editor and visual development artist.",
            )
            assignments = self._normalize_assignments(
                assignments=plan.scenes,
                segment_count=len(segments),
                target_scene_count=target_scene_count,
            )
            scenes = self._assignments_to_scenes(assignments, segments, script.estimated_duration_sec)
            specs = self._normalize_image_specs(scenes=scenes, generated_specs=plan.images)
            return scenes, specs
        except Exception:
            assignments = self._fallback_assignments(segments, target_scene_count)
            scenes = self._assignments_to_scenes(assignments, segments, script.estimated_duration_sec)
            return scenes, self._normalize_image_specs(scenes=scenes, generated_specs=[])

    def build_image_specs(
        self,
        *,
        script: VideoScript,
        scenes: list[Scene],
    ) -> list[SceneImageSpec]:
        compact_scene_payload = [
            {
                "scene_index": scene.scene_index,
                "narration_excerpt": scene.narration_text[:320],
                "visual_goal": scene.visual_goal[:220],
                "subtitle": scene.on_screen_subtitle_text[:140],
            }
            for scene in scenes
        ]
        prompt = (
            "Create one English image-generation prompt for each scene. "
            "Preserve historical coherence and avoid modern artifacts.\n\n"
            f"Video title: {script.title}\n"
            f"Scenes JSON:\n{json.dumps(compact_scene_payload, ensure_ascii=False, indent=2)}"
        )
        try:
            result = self.text_service.generate_structured(
                prompt=prompt,
                operation_name="scene image prompts",
                schema=SceneImagePlan,
                temperature=0.4,
                max_output_tokens=1800,
                system_prompt="You are a visual development artist for educational videos across school subjects.",
            )
            return self._normalize_image_specs(scenes=scenes, generated_specs=result.images)
        except Exception:
            return self._normalize_image_specs(scenes=scenes, generated_specs=[])

    def _segment_narration(self, narration: str) -> list[NarrationSegment]:
        sentences = [
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?])\s+", narration.strip())
            if sentence.strip()
        ]
        if not sentences:
            sentences = [narration.strip() or "Educational narration."]

        grouped_segments: list[NarrationSegment] = []
        buffer: list[str] = []
        word_budget = 50
        segment_index = 1

        def flush_buffer() -> None:
            nonlocal segment_index, buffer
            if not buffer:
                return
            text = " ".join(buffer).strip()
            grouped_segments.append(
                NarrationSegment(
                    segment_index=segment_index,
                    text=text,
                    word_count=max(1, len(text.split())),
                )
            )
            segment_index += 1
            buffer = []

        for sentence in sentences:
            sentence_words = sentence.split()
            sentence_chunks = [
                " ".join(sentence_words[index : index + word_budget])
                for index in range(0, len(sentence_words), word_budget)
            ] or [sentence]
            for sentence_chunk in sentence_chunks:
                candidate = " ".join(buffer + [sentence_chunk]).strip()
                if buffer and len(candidate.split()) > word_budget:
                    flush_buffer()
                buffer.append(sentence_chunk)

        flush_buffer()

        return grouped_segments

    def _segments_to_json(self, segments: list[NarrationSegment]) -> str:
        payload = [
            {
                "segment_index": segment.segment_index,
                "word_count": segment.word_count,
                "text": segment.text[:260],
            }
            for segment in segments
        ]
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def _normalize_assignments(
        self,
        *,
        assignments: list[SceneAssignment],
        segment_count: int,
        target_scene_count: int,
    ) -> list[SceneAssignment]:
        valid_assignments = sorted(
            assignments,
            key=lambda item: (item.start_segment_index, item.scene_index),
        )
        if not valid_assignments:
            raise ValueError("No scene assignments returned.")

        normalized: list[SceneAssignment] = []
        cursor = 1
        for idx, assignment in enumerate(valid_assignments, start=1):
            if cursor > segment_count:
                break
            # Absorb model-created gaps so every spoken segment has a scene.
            start_index = cursor
            end_index = max(start_index, min(segment_count, assignment.end_segment_index))
            normalized.append(
                SceneAssignment(
                    scene_index=idx,
                    start_segment_index=start_index,
                    end_segment_index=end_index,
                    visual_goal=assignment.visual_goal.strip() or "Historical documentary scene",
                    on_screen_subtitle_text=assignment.on_screen_subtitle_text.strip()[:140] or "Key historical moment",
                )
            )
            cursor = end_index + 1

        while cursor <= segment_count:
            remaining = segment_count - cursor + 1
            remaining_slots = max(1, target_scene_count - len(normalized))
            chunk_size = max(1, math.ceil(remaining / remaining_slots))
            end_index = min(segment_count, cursor + chunk_size - 1)
            normalized.append(
                SceneAssignment(
                    scene_index=len(normalized) + 1,
                    start_segment_index=cursor,
                    end_segment_index=end_index,
                    visual_goal="Chronological historical documentary moment",
                    on_screen_subtitle_text="Key moment in the timeline",
                )
            )
            cursor = end_index + 1

        max_scenes = max(1, target_scene_count)
        minimum_scene_count = min(5, max_scenes)
        if len(normalized) < minimum_scene_count:
            fallback_count = min(minimum_scene_count, segment_count)
            fallback: list[SceneAssignment] = []
            cursor = 1
            for scene_index in range(1, fallback_count + 1):
                remaining_segments = segment_count - cursor + 1
                remaining_scenes = fallback_count - scene_index + 1
                chunk_size = max(1, math.ceil(remaining_segments / remaining_scenes))
                end_index = min(segment_count, cursor + chunk_size - 1)
                fallback.append(
                    SceneAssignment(
                        scene_index=scene_index,
                        start_segment_index=cursor,
                        end_segment_index=end_index,
                        visual_goal="Chronological historical documentary moment",
                        on_screen_subtitle_text="Key moment in the timeline",
                    )
                )
                cursor = end_index + 1
            return fallback
        if len(normalized) <= max_scenes:
            return normalized

        head = normalized[: max_scenes - 1]
        tail = normalized[max_scenes - 1 :]
        merged_tail = SceneAssignment(
            scene_index=max_scenes,
            start_segment_index=tail[0].start_segment_index,
            end_segment_index=tail[-1].end_segment_index,
            visual_goal=tail[0].visual_goal,
            on_screen_subtitle_text=tail[0].on_screen_subtitle_text,
        )
        return head + [merged_tail]

    def _fallback_assignments(
        self,
        segments: list[NarrationSegment],
        target_scene_count: int,
    ) -> list[SceneAssignment]:
        assignments: list[SceneAssignment] = []
        total_segments = len(segments)
        cursor = 1

        for scene_idx in range(1, min(target_scene_count, total_segments) + 1):
            remaining_segments = total_segments - cursor + 1
            remaining_scenes = min(target_scene_count, total_segments) - scene_idx + 1
            chunk_size = max(1, math.ceil(remaining_segments / remaining_scenes))
            end_index = min(total_segments, cursor + chunk_size - 1)
            excerpt = " ".join(
                segment.text for segment in segments[cursor - 1 : end_index]
            )[:160]
            assignments.append(
                SceneAssignment(
                    scene_index=scene_idx,
                    start_segment_index=cursor,
                    end_segment_index=end_index,
                    visual_goal=excerpt or "Historical documentary scene",
                    on_screen_subtitle_text=(excerpt or "Key historical moment")[:120],
                )
            )
            cursor = end_index + 1
            if cursor > total_segments:
                break

        return assignments

    def _assignments_to_scenes(
        self,
        assignments: list[SceneAssignment],
        segments: list[NarrationSegment],
        total_duration_sec: int,
    ) -> list[Scene]:
        total_words = sum(segment.word_count for segment in segments) or 1
        timeline_cursor = 0.0
        scenes: list[Scene] = []

        for scene_index, assignment in enumerate(assignments, start=1):
            scene_segments = segments[
                assignment.start_segment_index - 1 : assignment.end_segment_index
            ]
            narration_text = " ".join(segment.text for segment in scene_segments).strip()
            scene_words = sum(segment.word_count for segment in scene_segments) or 1
            duration = max(8.0, (scene_words / total_words) * total_duration_sec)
            start_hint_sec = timeline_cursor
            end_hint_sec = timeline_cursor + duration
            timeline_cursor = end_hint_sec

            scenes.append(
                Scene(
                    scene_index=scene_index,
                    start_hint_sec=round(start_hint_sec, 2),
                    end_hint_sec=round(end_hint_sec, 2),
                    narration_text=narration_text,
                    visual_goal=assignment.visual_goal[:220],
                    on_screen_subtitle_text=assignment.on_screen_subtitle_text[:140],
                )
            )

        if scenes:
            scenes[-1].end_hint_sec = float(total_duration_sec)
        return scenes

    def _normalize_image_specs(
        self,
        *,
        scenes: list[Scene],
        generated_specs: list[SceneImageSpec],
    ) -> list[SceneImageSpec]:
        specs_by_scene_index = {
            spec.scene_index: spec
            for spec in generated_specs
            if 1 <= spec.scene_index <= len(scenes)
        }

        normalized_specs: list[SceneImageSpec] = []
        for scene in scenes:
            spec = specs_by_scene_index.get(scene.scene_index)
            if spec is None:
                spec = self._fallback_image_spec(scene)
            normalized_specs.append(spec)
        return normalized_specs

    def _fallback_image_spec(self, scene: Scene) -> SceneImageSpec:
        return SceneImageSpec(
            scene_index=scene.scene_index,
            prompt=(scene.visual_goal or scene.on_screen_subtitle_text or scene.narration_text[:180])[:260],
            negative_constraints=["low quality", "modern clothing", "text overlays"],
            style_tags=["cinematic", "documentary", "historical illustration"],
        )


scene_service = SceneService()
