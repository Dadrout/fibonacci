from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


LanguageCode = Literal["en-US", "ru-RU", "kk-KZ"]
VoiceCode = Literal["female", "male"]


class GenerationRequest(BaseModel):
    subject: str
    topic: str
    language: LanguageCode = "en-US"
    voice: VoiceCode = "female"
    user_id: str
    grade_band: Literal["10-12", "13-15", "16-18"] = "13-15"
    school_grade: str | None = Field(
        default=None, pattern=r"^(K|[1-9]|1[0-2])$",
        exclude_if=lambda value: value is None,
    )
    target_duration_sec: int = Field(default=180, ge=60, le=300)


class StoryDraftRequest(BaseModel):
    subject: Literal["history", "history_social_studies", "language_arts", "math", "science", "geography", "philosophy"]
    topic: str = Field(min_length=1, max_length=200)
    grade_band: Literal["10-12", "13-15", "16-18"] = "13-15"
    target_duration_sec: int = Field(default=180, ge=60, le=300)
    language: LanguageCode = "en-US"
    voice: VoiceCode = "female"
    source_text: str = Field(default="", max_length=20000)

    @field_validator("topic")
    @classmethod
    def normalize_topic(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Topic cannot be blank")
        return value


class ValidatedTopic(BaseModel):
    subject: str
    original_topic: str
    normalized_topic: str
    language: LanguageCode
    valid: bool = True
    pedagogical_framing: str
    rejection_reason: str | None = None


class ScriptSection(BaseModel):
    heading: str
    summary: str


class VideoScript(BaseModel):
    title: str
    hook: str
    sections: list[ScriptSection] = Field(default_factory=list)
    full_narration: str
    estimated_duration_sec: int


class QuizOption(BaseModel):
    id: Literal["a", "b", "c", "d"]
    text: str


class QuizQuestion(BaseModel):
    question: str
    options: list[QuizOption] = Field(min_length=3, max_length=4)
    correct_option: Literal["a", "b", "c", "d"]
    explanation: str

    @model_validator(mode="after")
    def validate_answer_options(self):
        ids = [option.id for option in self.options]
        if len(set(ids)) != len(ids):
            raise ValueError("Quiz option identifiers must be distinct.")
        if self.correct_option not in ids:
            raise ValueError("The correct answer must be one of the supplied options.")
        return self


class LearningOutcomes(BaseModel):
    recap: str
    quiz: list[QuizQuestion] = Field(min_length=3, max_length=3)


class DraftGeneration(BaseModel):
    script: VideoScript
    learning_outcomes: LearningOutcomes


class QuizSubmission(BaseModel):
    answers: dict[str, Literal["a", "b", "c", "d"]]


class Scene(BaseModel):
    scene_index: int
    start_hint_sec: float
    end_hint_sec: float
    narration_text: str
    visual_goal: str
    on_screen_subtitle_text: str

    @property
    def duration_hint_sec(self) -> float:
        return max(1.0, self.end_hint_sec - self.start_hint_sec)


class SceneImageSpec(BaseModel):
    scene_index: int
    prompt: str
    negative_constraints: list[str] = Field(default_factory=list)
    style_tags: list[str] = Field(default_factory=list)
    consistency_anchor: str = "historical documentary illustration, cinematic realism"


class ImageArtifact(BaseModel):
    scene_index: int
    image_path: str
    source: str
    fallback_used: bool = False
    prompt: str


class NarrationAudio(BaseModel):
    audio_path: str
    duration_sec: float
    provider: str
    voice: VoiceCode
    language: LanguageCode


class SubtitleCue(BaseModel):
    index: int
    start_sec: float
    end_sec: float
    text: str


class RenderManifest(BaseModel):
    request: GenerationRequest
    validated_topic: ValidatedTopic
    script: VideoScript
    scenes: list[Scene]
    recap: str = ""
    quiz: list[QuizQuestion] = Field(default_factory=list)
    image_artifacts: list[ImageArtifact]
    audio: NarrationAudio
    subtitles_path: str
    video_path: str
    provider_summary: dict[str, str]
    fallbacks_used: list[str] = Field(default_factory=list)
    artifacts: dict[str, str] = Field(default_factory=dict)


class RenderJobResult(BaseModel):
    job_id: str
    status: str
    video_url: str
    audio_url: str
    script: str
    duration_sec: float
    scene_count: int
    scenes: list[Scene]
    recap: str = ""
    quiz: list[QuizQuestion] = Field(default_factory=list)
    fallbacks_used: list[str] = Field(default_factory=list)
    provider_summary: dict[str, str] = Field(default_factory=dict)
    artifacts: dict[str, str] = Field(default_factory=dict)


class JobPaths(BaseModel):
    temp_dir: Path
    output_dir: Path
    audio_path: Path
    video_path: Path
    subtitles_path: Path
    manifest_path: Path
