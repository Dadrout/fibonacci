"""Timestamped transcript segments shared by YouTube and audio extraction."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.domain.brain.pipeline import Anchor, ExtractedChunk

WINDOW = 60.0
MAX_WINDOW = 75.0


class Segment(BaseModel):
    start_sec: float = Field(ge=0)
    end_sec: float = Field(ge=0)
    text: str = ""


class Transcript(BaseModel):
    title: Optional[str] = Field(default=None, max_length=300)
    language: Literal["en-US", "ru-RU", "kk-KZ"] = "en-US"
    segments: list[Segment] = Field(default_factory=list)


def windows(segments: list[Segment], *, max_chunks: int = 400, max_seconds: float = 7200) -> list[ExtractedChunk]:
    """Merge short caption lines into ~45–75 s windows with timestamp anchors."""
    chunks: list[ExtractedChunk] = []
    start: Optional[float] = None
    end = 0.0
    words: list[str] = []
    for segment in sorted(segments, key=lambda s: s.start_sec):
        text = " ".join(segment.text.replace("\n", " ").split())
        if not text or segment.start_sec > max_seconds:
            continue
        if start is None:
            # Each window starts fresh: a stale `end` from an earlier (possibly bogus, over-long)
            # segment would otherwise stretch every later anchor to that end time.
            start, end = segment.start_sec, segment.start_sec
        words.append(text)
        end = max(end, segment.end_sec, segment.start_sec)
        if end - start >= WINDOW or (end - start >= 45 and text.endswith((".", "?", "!"))) or end - start >= MAX_WINDOW:
            chunks.append(ExtractedChunk(anchor=Anchor(kind="timestamp", start_sec=round(start, 1), end_sec=round(end, 1)),
                                         text=" ".join(words)[:8000]))
            start, words = None, []
            if len(chunks) >= max_chunks:
                return chunks
    if words and start is not None:
        chunks.append(ExtractedChunk(anchor=Anchor(kind="timestamp", start_sec=round(start, 1), end_sec=round(max(end, start), 1)),
                                     text=" ".join(words)[:8000]))
    return chunks
