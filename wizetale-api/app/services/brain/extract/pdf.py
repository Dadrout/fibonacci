"""PDF → text by page (page anchors); scanned PDFs go through vision OCR."""
from __future__ import annotations

import io
import logging
import re
from typing import Optional

from celery.exceptions import SoftTimeLimitExceeded
from pydantic import BaseModel, Field

from app.core.config import settings
from app.domain.brain.pipeline import Anchor, Extraction, ExtractInput, ExtractionError
from app.services.brain.ai.client import AIUnavailable, BrainAI, Part
from app.services.brain.extract.chunking import anchored

logger = logging.getLogger(__name__)
MAX_PAGES = 200
THUMBNAIL_BYTES = 200_000


class OCRPage(BaseModel):
    page: int = Field(ge=1)
    text: str = ""


class PdfOCR(BaseModel):
    pages: list[OCRPage] = Field(default_factory=list)


def _thumbnail(data: bytes) -> Optional[bytes]:
    document = None
    try:
        import pypdfium2 as pdfium

        document = pdfium.PdfDocument(data)
        page = document[0]
        # Bound both sides: a scale from the width alone renders a very tall page into a huge bitmap.
        scale = min(480 / max(page.get_width(), 1), 960 / max(page.get_height(), 1))
        image = page.render(scale=scale).to_pil().convert("RGB")
        out = io.BytesIO()
        image.save(out, format="JPEG", quality=78)
        thumbnail = out.getvalue()
        return thumbnail if len(thumbnail) <= THUMBNAIL_BYTES else None
    except SoftTimeLimitExceeded:
        raise
    except Exception as error:  # noqa: BLE001 — a thumbnail is optional
        logger.info("brain_pdf thumbnail_failed error_type=%s", type(error).__name__)
        return None
    finally:
        if document is not None:
            document.close()


def _page_text(page) -> str:
    try:
        return (page.extract_text() or "").replace("\x00", "")
    except SoftTimeLimitExceeded:
        raise
    except Exception as error:  # noqa: BLE001 — one malformed page must not sink the document
        logger.info("brain_pdf page_text_failed error_type=%s", type(error).__name__)
        return ""


def _title(reader) -> Optional[str]:
    try:
        meta_title = reader.metadata.title if reader.metadata else None
    except Exception:  # noqa: BLE001 — broken metadata is not a broken document
        return None
    meta_title = meta_title.strip() if isinstance(meta_title, str) else ""
    # Ignore titles that are really file names or tool defaults ("week6.html", "Microsoft Word - x.docx").
    if len(meta_title) > 3 and not re.search(r"\.(html?|docx?|pptx?|pdf|txt|tex)$|^(untitled|microsoft word|document\d*$)", meta_title, re.I):
        return meta_title[:300]
    return None


def _pages(data: bytes) -> tuple[list[str], Optional[str]]:
    from pypdf import PdfReader

    for name in ("pypdf",):
        logging.getLogger(name).setLevel(logging.ERROR)
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            # Owner-password-only PDFs (print/copy restrictions) open with an empty user password.
            try:
                opened = reader.decrypt("")
            except Exception as error:  # noqa: BLE001 — unsupported cipher
                raise ExtractionError("unreadable", "Encrypted PDF") from error
            if not opened:
                raise ExtractionError("unreadable", "Encrypted PDF")
        if len(reader.pages) > MAX_PAGES:
            raise ExtractionError("too_large", "PDF has more than 200 pages")
        texts = [_page_text(page) for page in reader.pages]
        return texts, _title(reader)
    except (ExtractionError, SoftTimeLimitExceeded):
        raise
    except Exception as error:  # noqa: BLE001
        raise ExtractionError("unreadable", "PDF could not be parsed") from error


def extract(inp: ExtractInput, ai: BrainAI) -> Extraction:
    data = inp.data or b""
    texts, title = _pages(data)
    if not texts:
        raise ExtractionError("unreadable", "PDF has no pages")
    readable = sum(len(t.strip()) for t in texts)
    method = "text"
    if readable < 40 * max(len(texts), 1):
        try:
            ocr = ai.generate(operation="brain_ocr_pdf", prompt="ocr_pdf", schema=PdfOCR,
                              parts=[Part(mime_type="application/pdf", data=data)], model=settings.BRAIN_VISION_MODEL,
                              max_output_tokens=16384, timeout=60)
            by_page = {p.page: p.text for p in ocr.pages if 1 <= p.page <= len(texts)}
            # Keep the embedded text where OCR returned nothing for a page.
            texts = [by_page.get(i + 1) or texts[i] for i in range(len(texts))]
            method = "vision"
        except AIUnavailable:
            if readable == 0:
                raise ExtractionError("ai_unavailable", "Scanned PDF needs OCR")
    chunks = []
    for number, text in enumerate(texts, start=1):
        chunks.extend(anchored(Anchor(kind="page", page=number), text))
    if not chunks:
        raise ExtractionError("unreadable", "No readable text in PDF")
    return Extraction(title=title, chunks=chunks[:1500], page_count=len(texts), thumbnail=_thumbnail(data),
                      thumbnail_mime="image/jpeg", metadata={"pdf_text": method})
