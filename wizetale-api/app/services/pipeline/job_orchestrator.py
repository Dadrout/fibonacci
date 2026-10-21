import json
import logging
import time
from pathlib import Path

from pydantic import BaseModel

from app.core.config import settings
from app.domain.models import (
    GenerationRequest,
    JobPaths,
    LearningOutcomes,
    RenderJobResult,
    RenderManifest,
    VideoScript,
)
from app.services.pipeline.image_service import image_pipeline_service
from app.services.pipeline.scene_service import scene_service
from app.services.pipeline.script_service import script_generation_service
from app.services.tts.provider_factory import get_tts_provider
from app.services.video.ffmpeg_service import ffmpeg_service
from app.services.video.subtitle_service import subtitle_service

logger = logging.getLogger(__name__)


class AIHealthStatus(BaseModel):
    text: dict[str, str | bool]
    image: dict[str, str | bool]
    tts: dict[str, str | bool]


class JobOrchestrator:
    def __init__(
        self,
        *,
        script_service=script_generation_service,
        scene_service_instance=scene_service,
        image_service=image_pipeline_service,
        tts_provider=None,
        subtitle_service_instance=subtitle_service,
        ffmpeg_service_instance=ffmpeg_service,
    ):
        self.script_service = script_service
        self.scene_service = scene_service_instance
        self.image_service = image_service
        self.tts_provider = tts_provider or get_tts_provider()
        self.subtitle_service = subtitle_service_instance
        self.ffmpeg_service = ffmpeg_service_instance

    def build_paths(self, *, user_id: str, job_id: str) -> JobPaths:
        temp_dir = Path(settings.WORKDIR_ROOT) / f"wizetale_task_{job_id}"
        output_dir = Path("static") / user_id / job_id
        temp_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        return JobPaths(
            temp_dir=temp_dir,
            output_dir=output_dir,
            audio_path=output_dir / "audio.mp3",
            video_path=output_dir / "video.mp4",
            subtitles_path=output_dir / "subtitles.srt",
            manifest_path=output_dir / "manifest.json",
        )

    def _log_event(
        self,
        *,
        task_id: str,
        user_id: str,
        step: str,
        provider: str,
        started_at: float,
        fallback_used: bool = False,
    ) -> None:
        logger.info(
            "event=%s task_id=%s user_id=%s provider=%s latency_ms=%.0f fallback_used=%s",
            step,
            task_id,
            user_id,
            provider,
            (time.perf_counter() - started_at) * 1000,
            fallback_used,
        )

    def run(
        self,
        *,
        request: GenerationRequest,
        job_id: str,
        task_instance=None,
        script_override: VideoScript | None = None,
        learning_outcomes: LearningOutcomes | None = None,
        generate_learning_outcomes: bool = True,
    ) -> RenderJobResult:
        paths = self.build_paths(user_id=request.user_id, job_id=job_id)
        fallbacks_used: list[str] = []

        if task_instance:
            task_instance.update_state(
                state="PROGRESS",
                meta={"progress": 5, "message": "Validating topic...", "step": "topic_validation"},
            )
        started_at = time.perf_counter()
        validated_topic = self.script_service.validate_topic(request)
        if not validated_topic.valid:
            raise ValueError(validated_topic.rejection_reason or "Topic validation failed.")
        self._log_event(
            task_id=job_id,
            user_id=request.user_id,
            step="topic_validated",
            provider="gemini",
            started_at=started_at,
        )

        if task_instance:
            task_instance.update_state(
                state="PROGRESS",
                meta={"progress": 18, "message": "Generating script...", "step": "script_generation"},
            )
        started_at = time.perf_counter()
        script = script_override or self.script_service.generate_script(
            request=request,
            validated_topic=validated_topic,
        )
        if generate_learning_outcomes:
            learning_outcomes = learning_outcomes or self.script_service.generate_learning_outcomes(
                topic=validated_topic.normalized_topic,
                narration=script.full_narration,
                language=request.language,
                grade_band=request.grade_band,
            )
        else:
            learning_outcomes = None
        self._log_event(
            task_id=job_id,
            user_id=request.user_id,
            step="script_generated",
            provider="gemini",
            started_at=started_at,
        )

        if task_instance:
            task_instance.update_state(
                state="PROGRESS",
                meta={"progress": 35, "message": "Planning scenes...", "step": "scene_generation"},
            )
        started_at = time.perf_counter()
        try:
            scenes, image_specs = self.scene_service.build_render_plan(
                script, request.language, school_grade=request.school_grade,
            )
        except Exception:
            scenes = self._build_fallback_scenes(script.full_narration, script.estimated_duration_sec)
            image_specs = self._build_fallback_image_specs(scenes)
            fallbacks_used.append("render_plan")
        self._log_event(
            task_id=job_id,
            user_id=request.user_id,
            step="scenes_generated",
            provider="gemini",
            started_at=started_at,
        )

        if task_instance:
            task_instance.update_state(
                state="PROGRESS",
                meta={"progress": 50, "message": "Generating narration...", "step": "audio_generation"},
            )
        started_at = time.perf_counter()
        audio = self.tts_provider.synthesize(
            text=script.full_narration,
            language=request.language,
            voice=request.voice,
            output_path=str(paths.audio_path),
        )
        self._log_event(
            task_id=job_id,
            user_id=request.user_id,
            step="audio_generated",
            provider=audio.provider,
            started_at=started_at,
        )

        if task_instance:
            task_instance.update_state(
                state="PROGRESS",
                meta={"progress": 65, "message": "Generating visuals...", "step": "image_generation"},
            )
        started_at = time.perf_counter()
        image_artifacts, image_fallbacks = self.image_service.generate_images(
            topic=validated_topic.normalized_topic,
            image_specs=image_specs,
            temp_dir=paths.temp_dir,
        )
        fallbacks_used.extend(image_fallbacks)
        self._log_event(
            task_id=job_id,
            user_id=request.user_id,
            step="scene_image_generated",
            provider=settings.IMAGE_PROVIDER,
            started_at=started_at,
            fallback_used=bool(image_fallbacks),
        )

        if task_instance:
            task_instance.update_state(
                state="PROGRESS",
                meta={"progress": 78, "message": "Building subtitles...", "step": "subtitle_generation"},
            )
        started_at = time.perf_counter()
        cues = self.subtitle_service.build_cues(scenes, audio.duration_sec)
        self.subtitle_service.write_srt(cues, paths.subtitles_path)
        self._log_event(
            task_id=job_id,
            user_id=request.user_id,
            step="subtitles_generated",
            provider="local",
            started_at=started_at,
        )

        scene_word_counts = [max(1, len(scene.narration_text.split())) for scene in scenes]
        total_words = sum(scene_word_counts) or 1
        scene_durations = [audio.duration_sec * (count / total_words) for count in scene_word_counts]
        image_paths = [artifact.image_path for artifact in image_artifacts]

        if task_instance:
            task_instance.update_state(
                state="PROGRESS",
                meta={"progress": 85, "message": "Rendering video...", "step": "video_creation"},
            )
        started_at = time.perf_counter()
        self.ffmpeg_service.render(
            image_paths=image_paths,
            scene_durations=scene_durations,
            audio_path=audio.audio_path,
            audio_duration=audio.duration_sec,
            subtitles_path=str(paths.subtitles_path),
            output_path=str(paths.video_path),
            task_instance=task_instance,
        )
        self._log_event(
            task_id=job_id,
            user_id=request.user_id,
            step="render_completed",
            provider="ffmpeg",
            started_at=started_at,
        )

        manifest = RenderManifest(
            request=request,
            validated_topic=validated_topic,
            script=script,
            scenes=scenes,
            recap=learning_outcomes.recap if learning_outcomes else "",
            quiz=learning_outcomes.quiz if learning_outcomes else [],
            image_artifacts=image_artifacts,
            audio=audio,
            subtitles_path=str(paths.subtitles_path),
            video_path=str(paths.video_path),
            provider_summary={
                "text": settings.AI_PROVIDER,
                "image": settings.IMAGE_PROVIDER,
                "tts": audio.provider,
            },
            fallbacks_used=fallbacks_used,
            artifacts={
                "video": str(paths.video_path),
                "audio": str(paths.audio_path),
                "subtitles": str(paths.subtitles_path),
            },
        )
        paths.manifest_path.write_text(
            json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return RenderJobResult(
            job_id=job_id,
            status="SUCCESS",
            video_url=f"/static/{request.user_id}/{job_id}/video.mp4",
            audio_url=f"/static/{request.user_id}/{job_id}/audio.mp3",
            script=script.full_narration,
            duration_sec=audio.duration_sec,
            scene_count=len(scenes),
            scenes=scenes,
            recap=learning_outcomes.recap if learning_outcomes else "",
            quiz=learning_outcomes.quiz if learning_outcomes else [],
            fallbacks_used=fallbacks_used,
            provider_summary=manifest.provider_summary,
            artifacts={
                "video": manifest.video_path,
                "audio": manifest.audio.audio_path,
                "subtitles": manifest.subtitles_path,
                "manifest": str(paths.manifest_path),
            },
        )

    def _build_fallback_image_specs(self, scenes):
        from app.domain.models import SceneImageSpec

        return [
            SceneImageSpec(
                scene_index=scene.scene_index,
                prompt=scene.visual_goal or scene.on_screen_subtitle_text or scene.narration_text[:180],
                negative_constraints=["low quality", "modern clothing", "text overlays"],
                style_tags=["cinematic", "documentary", "historical illustration"],
            )
            for scene in scenes
        ]

    def _build_fallback_scenes(self, narration: str, estimated_duration_sec: int):
        from app.domain.models import Scene

        paragraphs = [part.strip() for part in narration.split("\n\n") if part.strip()]
        if not paragraphs:
            words = narration.split()
            chunk_size = max(1, len(words) // max(1, settings.GENERATION_MAX_SCENES))
            paragraphs = [
                " ".join(words[index : index + chunk_size])
                for index in range(0, len(words), chunk_size)
            ]

        max_scenes = max(1, settings.GENERATION_MAX_SCENES)
        if len(paragraphs) > max_scenes:
            paragraphs = paragraphs[:max_scenes - 1] + ["\n\n".join(paragraphs[max_scenes - 1:])]
        duration = max(1, estimated_duration_sec // max(1, len(paragraphs)))
        scenes = []
        current_start = 0.0
        for index, paragraph in enumerate(paragraphs, start=1):
            end = current_start + duration
            scenes.append(
                Scene(
                    scene_index=index,
                    start_hint_sec=current_start,
                    end_hint_sec=end,
                    narration_text=paragraph,
                    visual_goal=paragraph[:180],
                    on_screen_subtitle_text=paragraph[:120],
                )
            )
            current_start = end
        return scenes

    def ai_health(self) -> AIHealthStatus:
        return AIHealthStatus(
            text=self.script_service.text_service.healthcheck(),
            image=self.image_service.image_provider.healthcheck(),
            tts=self.tts_provider.healthcheck(),
        )


job_orchestrator = JobOrchestrator()
