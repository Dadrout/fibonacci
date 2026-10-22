"""Split clean text into passages of a size that cites well (≈300–1500 characters)."""
from __future__ import annotations

import re
from typing import Iterable

from app.domain.brain.pipeline import Anchor, ExtractedChunk

TARGET = 1200
LIMIT = 1500


def split_long(text: str, limit: int = LIMIT) -> list[str]:
    """Split on sentence ends, then on spaces, so no passage exceeds `limit`."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return [text] if text else []
    target = min(TARGET, limit)
    parts, current = [], ""
    for sentence in re.split(r"(?<=[.!?;:])\s+", text):
        if len(sentence) > limit and current:
            # Flush first: joining `current` to a cut of an over-long sentence would exceed `limit`.
            parts.append(current)
            current = ""
        while len(sentence) > limit:
            cut = sentence.rfind(" ", 0, limit + 1)
            cut = cut if cut > 0 else limit
            parts.append(sentence[:cut].strip())
            sentence = sentence[cut:].strip()
        if len(current) + len(sentence) + 1 > target and current:
            parts.append(current.strip())
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        parts.append(current.strip())
    return [p for p in parts if p]


def paragraphs(text: str) -> list[str]:
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text.replace("\r\n", "\n"))]
    if len(blocks) == 1:  # single block: treat lines as paragraphs when they look like bullets/lines
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        blocks = lines if len(lines) > 1 else blocks
    return [b for b in blocks if b]


def group_paragraphs(blocks: Iterable[str]) -> list[ExtractedChunk]:
    """Group consecutive paragraphs; anchor = first paragraph number (1-based) of each group."""
    chunks: list[ExtractedChunk] = []
    buffer: list[str] = []
    first = 1
    for index, block in enumerate(blocks, start=1):
        if not buffer:
            first = index
        buffer.append(block)
        if sum(len(b) for b in buffer) >= TARGET:
            for piece in split_long("\n".join(buffer)):
                chunks.append(ExtractedChunk(anchor=Anchor(kind="paragraph", paragraph=first), text=piece))
            buffer = []
    if buffer:
        for piece in split_long("\n".join(buffer)):
            chunks.append(ExtractedChunk(anchor=Anchor(kind="paragraph", paragraph=first), text=piece))
    return chunks


def anchored(anchor: Anchor, text: str) -> list[ExtractedChunk]:
    return [ExtractedChunk(anchor=anchor, text=piece) for piece in split_long(text)]
