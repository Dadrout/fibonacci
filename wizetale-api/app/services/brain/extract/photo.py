"""Photo of a slide, whiteboard, or notes → OCR text with a slide anchor."""
from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.core.config import settings
from app.domain.brain.pipeline import Anchor, Extraction, ExtractInput, ExtractionError
from app.services.brain.ai.client import AIUnavailable, BrainAI, Part
from app.services.brain.extract import images
from app.services.brain.extract.chunking import anchored

logger = logging.getLogger(__name__)


class PhotoOCR(BaseModel):
    is_slide: bool = False
    slide_number: Optional[int] = Field(default=None, ge=1, le=999)
    title: Optional[str] = Field(default=None, max_length=300)
    language: Literal["en-US", "ru-RU", "kk-KZ"] = "en-US"
    text: str = ""
    legible: bool = True


def _tesseract(jpeg: bytes) -> str:
    binary = shutil.which("tesseract")
    if not binary:
        raise ExtractionError("ai_unavailable", "No OCR available offline")
    try:
        langs = subprocess.run([binary, "--list-langs"], capture_output=True, text=True, timeout=10).stdout.split()
        wanted = "+".join(l for l in ("eng", "rus", "kaz") if l in langs) or "eng"
        with tempfile.NamedTemporaryFile(suffix=".jpg") as handle:
            handle.write(jpeg)
            handle.flush()
            result = subprocess.run([binary, handle.name, "stdout", "-l", wanted], capture_output=True, text=True,
                                    timeout=40)
    except (OSError, subprocess.SubprocessError) as error:  # timeout, not executable, crashed
        raise ExtractionError("ai_unavailable", "Offline OCR failed") from error
    if result.returncode != 0:
        raise ExtractionError("ai_unavailable", "Offline OCR failed")
    return result.stdout


def extract(inp: ExtractInput, ai: BrainAI) -> Extraction:
    image = images.load(inp.data or b"")
    model_jpeg = images.jpeg(image, 2048)
    thumbnail = images.jpeg(image, 480, quality=78)
    try:
        ocr = ai.generate(operation="brain_ocr_photo", prompt="ocr_photo", variables={"filename": inp.filename or "photo"},
                          schema=PhotoOCR, parts=[Part(mime_type="image/jpeg", data=model_jpeg)],
                          model=settings.BRAIN_VISION_MODEL, max_output_tokens=4096)
        method = "vision"
    except AIUnavailable:
        text = _tesseract(model_jpeg)
        ocr = PhotoOCR(text=text, legible=bool(text.strip()))
        method = "tesseract"
    text = "\n".join(line.rstrip() for line in ocr.text.splitlines() if line.strip())
    if not ocr.legible or len(text) < 3:
        raise ExtractionError("unreadable", "No readable text on the photo")
    chunks = anchored(Anchor(kind="slide", slide=ocr.slide_number), text)
    return Extraction(title=ocr.title, language=ocr.language, chunks=chunks, thumbnail=thumbnail, thumbnail_mime="image/jpeg",
                      metadata={"slide_detected": ocr.is_slide, "ocr": method})
