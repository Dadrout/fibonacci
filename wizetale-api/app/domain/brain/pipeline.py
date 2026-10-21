"""Internal types passed between Brain pipeline stages (extract → classify → link).

Owner: Claude. Extractors (app/services/brain/extract/) return `Extraction`; the
classifier and linker consume it. AI output schemas live here so prompts, code, and
tests share one definition.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.brain.models import BrainLanguage, CaptureFailureCode, CaptureKind, LinkRelation, SequenceKind


class Strict(BaseModel):
    model_config = ConfigDict(extra="ignore")


# ---------------------------------------------------------------- extraction

class Anchor(Strict):
    """Where a passage sits in its source. Mirrors the brain_chunks anchor columns."""

    kind: Literal["page", "slide", "timestamp", "paragraph", "section"]
    page: Optional[int] = Field(default=None, ge=1)
    slide: Optional[int] = Field(default=None, ge=1)
    start_sec: Optional[float] = Field(default=None, ge=0)
    end_sec: Optional[float] = Field(default=None, ge=0)
    paragraph: Optional[int] = Field(default=None, ge=1)
    heading: Optional[str] = Field(default=None, max_length=200)


class ExtractedChunk(Strict):
    anchor: Anchor
    text: str = Field(min_length=1, max_length=8000)


class Extraction(Strict):
    """Clean text of one capture, split into anchored passages in reading/playback order."""

    title: Optional[str] = Field(default=None, max_length=300)
    language: Optional[BrainLanguage] = None
    chunks: list[ExtractedChunk] = Field(min_length=1)
    page_count: Optional[int] = None
    duration_sec: Optional[float] = None
    #: Values copied into brain_items.metadata (e.g. {"slide_detected": true, "transcript": "captions"}).
    metadata: dict = Field(default_factory=dict)
    #: Small preview image (JPEG/PNG/WebP, ≤ 200 KB): photo, first PDF page, or video still. Not serialized.
    thumbnail: Optional[bytes] = Field(default=None, exclude=True)
    thumbnail_mime: Optional[str] = Field(default=None, exclude=True)


@dataclass
class ExtractInput:
    """Everything an extractor may need. Exactly one of data/url/text is set."""

    kind: CaptureKind
    data: Optional[bytes] = None
    mime_type: Optional[str] = None
    filename: Optional[str] = None
    url: Optional[str] = None
    youtube_id: Optional[str] = None
    text: Optional[str] = None
    title_hint: Optional[str] = None


class ExtractionError(Exception):
    """A capture cannot be read. `code` is shown to the user (localized in the UI)."""

    def __init__(self, code: CaptureFailureCode, detail: str = ""):
        super().__init__(detail or code)
        self.code = code


# ---------------------------------------------------------------- classification (AI output)

class ConceptDraft(Strict):
    name: str = Field(min_length=1, max_length=120)
    summary: str = Field(default="", max_length=600)
    #: Ordinals of the passages that explain this concept.
    chunk_ordinals: list[int] = Field(default_factory=list, max_length=50)


class Placement(Strict):
    #: Existing course id from the catalog, or null to create `course_title`.
    course_id: Optional[str] = None
    course_title: str = Field(min_length=1, max_length=120)
    course_code: Optional[str] = Field(default=None, max_length=32)
    topic_id: Optional[str] = None
    topic_title: str = Field(min_length=1, max_length=160)
    sequence: Optional[int] = Field(default=None, ge=0, le=400)
    sequence_kind: Optional[SequenceKind] = None
    confidence: float = Field(ge=0, le=1)


class Classification(Strict):
    title: str = Field(min_length=1, max_length=300)
    summary: str = Field(min_length=1, max_length=1000)
    language: BrainLanguage
    placement: Placement
    alternatives: list[Placement] = Field(default_factory=list, max_length=3)
    concepts: list[ConceptDraft] = Field(min_length=1, max_length=8)

    @field_validator("concepts")
    @classmethod
    def distinct(cls, value: list[ConceptDraft]) -> list[ConceptDraft]:
        seen: set[str] = set()
        unique = []
        for concept in value:
            key = concept.name.strip().lower()
            if key not in seen:
                seen.add(key)
                unique.append(concept)
        return unique


# ---------------------------------------------------------------- link verification (AI output)

class LinkVerdict(Strict):
    pair: int = Field(ge=0)
    related: bool
    relation: Optional[LinkRelation] = None
    #: Direction for builds_on/applies: "a_to_b" means A builds on / applies B.
    direction: Literal["a_to_b", "b_to_a"] = "a_to_b"
    strength: float = Field(ge=0, le=1)
    rationale: str = Field(default="", max_length=400)


class LinkVerdicts(Strict):
    verdicts: list[LinkVerdict] = Field(default_factory=list, max_length=40)
