"""DOCX and UTF-8 text files → paragraph-anchored passages."""
from __future__ import annotations

import io
import zipfile

from app.domain.brain.pipeline import Extraction, ExtractInput, ExtractionError
from app.services.brain.ai.client import BrainAI
from app.services.brain.extract.chunking import group_paragraphs, paragraphs

MAX_EXPANDED = 30 * 1024 * 1024


def _docx_paragraphs(data: bytes) -> list[str]:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if sum(info.file_size for info in archive.infolist()) > MAX_EXPANDED:
                raise ExtractionError("too_large", "Expanded document is too large")
        from docx import Document

        document = Document(io.BytesIO(data))
        blocks = [p.text.strip() for p in document.paragraphs if p.text.strip()]
        for table in document.tables:
            for row in table.rows:
                line = " | ".join(cell.text.strip() for cell in row.cells)
                if line.strip(" |"):
                    blocks.append(line)
        return blocks
    except ExtractionError:
        raise
    except Exception as error:  # noqa: BLE001
        raise ExtractionError("unreadable", "DOCX could not be read") from error


def extract(inp: ExtractInput, ai: BrainAI) -> Extraction:
    data = inp.data or b""
    if (inp.mime_type or "").startswith("text/") or (inp.filename or "").lower().endswith(".txt"):
        try:
            blocks = paragraphs(data.decode("utf-8-sig"))
        except UnicodeDecodeError as error:
            raise ExtractionError("unreadable", "Text file is not UTF-8") from error
    else:
        blocks = _docx_paragraphs(data)
    chunks = group_paragraphs(blocks)
    if not chunks:
        raise ExtractionError("unreadable", "No readable text")
    return Extraction(title=blocks[0][:300] if blocks and len(blocks[0]) <= 120 else None, chunks=chunks[:1500])
