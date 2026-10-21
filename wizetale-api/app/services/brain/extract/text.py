"""Pasted or messaged text → paragraph-anchored passages."""
from __future__ import annotations

from app.domain.brain.pipeline import Extraction, ExtractInput, ExtractionError
from app.services.brain.ai.client import BrainAI
from app.services.brain.extract.chunking import group_paragraphs, paragraphs


def extract(inp: ExtractInput, ai: BrainAI) -> Extraction:
    raw = inp.text if inp.text is not None else (inp.data or b"").decode("utf-8", errors="replace")
    blocks = paragraphs(raw)
    chunks = group_paragraphs(blocks)
    if not chunks:
        raise ExtractionError("unreadable", "Text is empty")
    first = blocks[0]
    title = first if len(first) <= 100 and len(blocks) > 1 else None
    return Extraction(title=title, chunks=chunks[:1500])
