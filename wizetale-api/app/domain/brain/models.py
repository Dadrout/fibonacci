"""Fibonacci Brain API contract. Mirrors wizetale-app/lib/brain-types.ts exactly.

Owner: Claude. Change both files together and note it in docs/brain/COLLAB.md.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any, Literal, Optional, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

BrainLanguage = Literal["en-US", "ru-RU", "kk-KZ"]
CaptureKind = Literal["photo", "pdf", "document", "youtube", "web", "audio", "text"]
CaptureChannel = Literal["web_drop", "web_paste", "web_picker", "telegram", "seed"]
WebChannel = Literal["web_drop", "web_paste", "web_picker"]
ItemStatus = Literal["queued", "extracting", "classifying", "linking", "filed", "failed"]
CaptureFailureCode = Literal[
    "unsupported_type", "too_large", "unreadable", "fetch_failed", "transcript_unavailable", "ai_unavailable", "internal"
]
SequenceKind = Literal["week", "lecture", "chapter", "module"]
LinkRelation = Literal["same_idea", "builds_on", "applies", "contrasts"]
PlanStatus = Literal["generating", "ready", "failed"]
PlanFailureCode = Literal["not_enough_material", "ai_unavailable", "internal"]
PlanTaskKind = Literal["read", "watch", "review", "flashcards", "quiz", "practice"]
QuizOptionId = Literal["a", "b", "c", "d"]
BrainErrorCode = Literal[
    "unauthorized", "not_found", "invalid_input", "unsupported_type", "too_large", "rate_limited",
    "conflict", "not_enough_material", "telegram_not_configured", "unavailable", "internal",
]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------- anchors and citations

class PageAnchor(Model):
    kind: Literal["page"] = "page"
    page: int = Field(ge=1)


class SlideAnchor(Model):
    kind: Literal["slide"] = "slide"
    slide: Optional[int] = Field(default=None, ge=1)


class TimestampAnchor(Model):
    kind: Literal["timestamp"] = "timestamp"
    start_sec: float = Field(ge=0)
    end_sec: float = Field(ge=0)

    @model_validator(mode="after")
    def ordered(self):
        if self.end_sec < self.start_sec:
            raise ValueError("end_sec must not precede start_sec")
        return self


class ParagraphAnchor(Model):
    kind: Literal["paragraph"] = "paragraph"
    paragraph: int = Field(ge=1)


class SectionAnchor(Model):
    kind: Literal["section"] = "section"
    heading: str = Field(min_length=1, max_length=200)


SourceAnchor = Annotated[
    Union[PageAnchor, SlideAnchor, TimestampAnchor, ParagraphAnchor, SectionAnchor], Field(discriminator="kind")
]


class SourceRef(Model):
    item_id: UUID
    chunk_id: UUID
    item_kind: CaptureKind
    item_title: str
    course_id: Optional[UUID]
    anchor: SourceAnchor
    quote: str = Field(max_length=280)
    captured_at: datetime
    thumbnail_url: Optional[str]
    open_url: Optional[str]
    youtube_id: Optional[str]
    media_url: Optional[str]


# ---------------------------------------------------------------- items

class FilingAlternative(Model):
    course_id: Optional[UUID]
    course_title: str
    topic_id: Optional[UUID]
    topic_title: str
    confidence: float = Field(ge=0, le=1)


class BrainItem(Model):
    id: UUID
    kind: CaptureKind
    channel: CaptureChannel
    status: ItemStatus
    progress: float = Field(ge=0, le=1)
    title: str
    summary: Optional[str]
    language: Optional[BrainLanguage]
    course_id: Optional[UUID]
    course_title: Optional[str]
    topic_id: Optional[UUID]
    topic_title: Optional[str]
    confidence: Optional[float]
    needs_review: bool
    alternatives: list[FilingAlternative]
    concept_ids: list[UUID]
    source_url: Optional[str]
    youtube_id: Optional[str]
    thumbnail_url: Optional[str]
    media_url: Optional[str]
    duration_sec: Optional[float]
    page_count: Optional[int]
    failure_code: Optional[CaptureFailureCode]
    captured_at: datetime
    filed_at: Optional[datetime]
    timings_ms: dict[Literal["extract", "classify", "link", "total"], int]


class BrainChunk(Model):
    id: UUID
    item_id: UUID
    ordinal: int
    anchor: SourceAnchor
    text: str


class BrainCourse(Model):
    id: UUID
    title: str
    code: Optional[str]
    color_index: int = Field(ge=0, le=7)
    created_by: Literal["auto", "user"]
    item_count: int
    topic_count: int
    concept_count: int
    created_at: datetime


class BrainTopic(Model):
    id: UUID
    course_id: UUID
    title: str
    sequence: Optional[int]
    sequence_kind: Optional[SequenceKind]
    item_count: int
    concept_count: int
    created_at: datetime


class BrainConcept(Model):
    id: UUID
    course_id: UUID
    topic_id: Optional[UUID]
    name: str
    summary: str
    mention_count: int
    created_at: datetime


class ConceptLink(Model):
    id: UUID
    source_concept_id: UUID
    target_concept_id: UUID
    cross_course: bool
    strength: float = Field(ge=0, le=1)
    relation: LinkRelation
    rationale: str
    method: Literal["embedding", "verified", "user"]
    created_at: datetime


class BrainItemDetail(Model):
    item: BrainItem
    chunks: list[BrainChunk]
    concepts: list[BrainConcept]


class BrainGraph(Model):
    courses: list[BrainCourse]
    topics: list[BrainTopic]
    concepts: list[BrainConcept]
    links: list[ConceptLink]
    generated_at: datetime


class LinkedConcept(Model):
    link: ConceptLink
    concept: BrainConcept
    course: BrainCourse


class ConceptDetail(Model):
    concept: BrainConcept
    course: BrainCourse
    topic: Optional[BrainTopic]
    sources: list[SourceRef]
    linked: list[LinkedConcept]


class GapAlert(Model):
    id: str
    course_id: UUID
    course_title: str
    sequence_kind: SequenceKind
    missing: int
    present: list[int]


class TopicWithItems(Model):
    topic: BrainTopic
    items: list[BrainItem]


class CourseDetail(Model):
    course: BrainCourse
    topics: list[TopicWithItems]
    loose_items: list[BrainItem]
    gaps: list[GapAlert]


class TelegramStatus(Model):
    bot_configured: bool
    bot_username: Optional[str]
    linked: bool
    telegram_username: Optional[str]
    linked_at: Optional[datetime]


class TelegramLinkCode(Model):
    code: str = Field(pattern=r"^\d{6}$")
    deep_link: str
    expires_at: datetime
    bot_username: str


class OverviewCounts(Model):
    items: int
    courses: int
    concepts: int
    cross_links: int
    processing: int


class BrainOverview(Model):
    counts: OverviewCounts
    recent_items: list[BrainItem]
    gaps: list[GapAlert]
    telegram: TelegramStatus
    demo_mode: bool


class ItemPage(Model):
    items: list[BrainItem]
    next_cursor: Optional[str]


# ---------------------------------------------------------------- exam mode

class CitedText(Model):
    text: str
    sources: list[SourceRef]


class PlanTask(Model):
    id: str
    kind: PlanTaskKind
    title: str
    minutes: int = Field(ge=1, le=240)
    topic_id: Optional[UUID]
    sources: list[SourceRef]


class PlanDay(Model):
    day: int = Field(ge=1)
    date: Optional[date]
    focus: str
    tasks: list[PlanTask]


class PlanNote(Model):
    id: str
    heading: str
    topic_id: Optional[UUID]
    bullets: list[CitedText]


class Flashcard(Model):
    id: str
    front: str
    back: str
    sources: list[SourceRef]


class QuizOption(Model):
    id: QuizOptionId
    text: str


class QuizQuestion(Model):
    id: str
    prompt: str
    options: list[QuizOption] = Field(min_length=2, max_length=4)
    concept_ids: list[UUID]
    sources: list[SourceRef]


class StudyPlanContent(Model):
    title: str
    days: list[PlanDay]
    notes: list[PlanNote]
    flashcards: list[Flashcard]
    quiz: list[QuizQuestion]


class PlanCoverage(Model):
    item_count: int
    cited_item_count: int
    missing: list[GapAlert]


class StudyPlan(Model):
    id: UUID
    course_id: UUID
    days: int
    exam_date: date
    language: BrainLanguage
    status: PlanStatus
    failure_code: Optional[PlanFailureCode]
    content: Optional[StudyPlanContent]
    coverage: Optional[PlanCoverage]
    created_at: datetime


class SourceMoment(Model):
    source: SourceRef
    reason: str
    confidence: float = Field(ge=0, le=1)


class QuizAnswerResult(Model):
    question_id: str
    correct: bool
    correct_option_id: QuizOptionId
    explanation: CitedText
    moment: Optional[SourceMoment]
    attempt_id: UUID


class RefileResult(Model):
    item: BrainItem
    course: BrainCourse
    topic: Optional[BrainTopic]
    learned: bool


class SearchHitConcept(Model):
    kind: Literal["concept"] = "concept"
    score: float
    concept: BrainConcept


class SearchHitPassage(Model):
    kind: Literal["passage"] = "passage"
    score: float
    source: SourceRef


class SearchResponse(Model):
    query: str
    hits: list[Annotated[Union[SearchHitConcept, SearchHitPassage], Field(discriminator="kind")]]


# ---------------------------------------------------------------- requests

class CaptureCreateRequest(Model):
    url: Optional[str] = Field(default=None, max_length=2048)
    text: Optional[str] = Field(default=None, max_length=100_000)
    title: Optional[str] = Field(default=None, max_length=200)
    channel: WebChannel
    request_id: UUID

    @model_validator(mode="after")
    def one_input(self):
        has_url = bool(self.url and self.url.strip())
        has_text = bool(self.text and self.text.strip())
        if has_url == has_text:
            raise ValueError("Send exactly one of url or text")
        if has_url:
            url = self.url.strip()
            if not url.lower().startswith(("http://", "https://")):
                raise ValueError("Links must start with http:// or https://")
            self.url = url
        return self


class RefileRequest(Model):
    course_id: Optional[UUID] = None
    new_course_title: Optional[str] = Field(default=None, min_length=1, max_length=120)
    topic_id: Optional[UUID] = None
    new_topic_title: Optional[str] = Field(default=None, min_length=1, max_length=160)

    @model_validator(mode="after")
    def course_choice(self):
        if bool(self.course_id) == bool(self.new_course_title and self.new_course_title.strip()):
            raise ValueError("Choose an existing course or name a new one")
        if self.topic_id and self.new_topic_title:
            raise ValueError("Choose an existing topic or name a new one, not both")
        return self


class RenameCourseRequest(Model):
    title: str = Field(min_length=1, max_length=120)

    @field_validator("title")
    @classmethod
    def strip(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Title is empty")
        return value


class ExamPlanRequest(Model):
    days: int = Field(ge=1, le=30)
    exam_date: Optional[date] = None
    language: BrainLanguage
    request_id: UUID


class PresentationRequest(Model):
    language: BrainLanguage


class QuizAnswerRequest(Model):
    option_id: QuizOptionId


def error_body(detail: str, code: BrainErrorCode) -> dict[str, Any]:
    return {"detail": detail, "code": code}
