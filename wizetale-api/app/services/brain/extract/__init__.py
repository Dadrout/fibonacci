"""Extractors: turn one capture into clean, anchored passages (`Extraction`).

Contract (app/domain/brain/pipeline.py):
    extract(inp: ExtractInput, ai: BrainAI) -> Extraction
Raise `ExtractionError(code)` for unreadable input; never return empty text.
One module per kind; `extract()` dispatches on `inp.kind`.
"""
from __future__ import annotations

from app.domain.brain.pipeline import Extraction, ExtractInput, ExtractionError
from app.services.brain.ai.client import BrainAI


def extract(inp: ExtractInput, ai: BrainAI) -> Extraction:
    from app.services.brain.extract import audio, document, pdf, photo, text, web, youtube

    handlers = {
        "photo": photo.extract, "pdf": pdf.extract, "document": document.extract, "text": text.extract,
        "youtube": youtube.extract, "web": web.extract, "audio": audio.extract,
    }
    handler = handlers.get(inp.kind)
    if handler is None:
        raise ExtractionError("unsupported_type", f"No extractor for {inp.kind}")
    return handler(inp, ai)
