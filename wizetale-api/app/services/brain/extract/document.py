"""DOCX and UTF-8 text files → paragraph-anchored passages."""
from __future__ import annotations

import io
import zipfile

from celery.exceptions import SoftTimeLimitExceeded

from app.domain.brain.pipeline import Extraction, ExtractInput, ExtractionError
from app.services.brain.ai.client import BrainAI
from app.services.brain.extract.chunking import group_paragraphs, paragraphs

MAX_EXPANDED = 30 * 1024 * 1024
MAX_MEMBERS = 2000
READ_STEP = 1 << 20


def _verified_zip(data: bytes) -> bytes:
    """Re-pack the DOCX archive uncompressed after bounded reads of every member.

    zipfile's one-shot read() inflates up to 1 GiB per call before trimming to the declared
    size, so a member that lies about its size could exhaust memory inside python-docx.
    Reading in 1 MiB steps caps each inflate call and stops at the declared size; the CRC
    is checked at the end of each member.
    """
    out = io.BytesIO()
    total = 0
    with zipfile.ZipFile(io.BytesIO(data)) as archive, zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as packed:
        infos = archive.infolist()
        if len(infos) > MAX_MEMBERS or sum(info.file_size for info in infos) > MAX_EXPANDED:
            raise ExtractionError("too_large", "Expanded document is too large")
        for info in infos:
            if info.is_dir():
                continue
            pieces = []
            with archive.open(info) as member:
                while piece := member.read(READ_STEP):
                    total += len(piece)
                    if total > MAX_EXPANDED:
                        raise ExtractionError("too_large", "Expanded document is too large")
                    pieces.append(piece)
            packed.writestr(info.filename, b"".join(pieces))
    return out.getvalue()


def _table_rows(table) -> list[str]:
    lines = []
    for row in table.rows:
        cells, seen = [], set()
        for cell in row.cells:
            if id(cell._tc) in seen:  # a horizontally merged cell repeats once per grid column
                continue
            seen.add(id(cell._tc))
            cells.append(cell.text.strip())
        line = " | ".join(cells)
        if line.strip(" |"):
            lines.append(line)
    return lines


def _docx_paragraphs(data: bytes) -> list[str]:
    try:
        safe = _verified_zip(data)
        from docx import Document
        from docx.table import Table

        document = Document(io.BytesIO(safe))
        blocks: list[str] = []
        # Body paragraphs and tables in reading order, so paragraph anchors match the document.
        for block in document.iter_inner_content():
            if isinstance(block, Table):
                blocks.extend(_table_rows(block))
            elif block.text.strip():
                blocks.append(block.text.strip())
        return blocks
    except (ExtractionError, SoftTimeLimitExceeded):
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
