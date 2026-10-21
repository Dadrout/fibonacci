"""Bounded, local text extraction; no document content is sent to a parser service."""
import io
import logging
import re
import zipfile

# Parser warnings can include fragments of malformed private documents.
# Application workers report sanitized failure types instead.
_parser_log = logging.getLogger('pypdf')
_parser_log.addHandler(logging.NullHandler())
_parser_log.propagate = False

MAX_BYTES = 10 * 1024 * 1024
MAX_CHARACTERS = 200000


def extract_document(data: bytes, kind: str) -> list[dict]:
    if not data or len(data) > MAX_BYTES:
        raise ValueError('Choose a nonempty document up to 10 MB.')
    sections = []
    total = 0

    def append(text, location):
        nonlocal total
        text = text.replace('\x00', '').strip()
        total += len(text)
        if total > MAX_CHARACTERS:
            raise ValueError('Document exceeds 200,000 extracted characters.')
        if text:
            sections.append({'text': text, 'location': location})

    try:
        if kind == 'pdf':
            # Celery/logging configuration may reset logger propagation after
            # this module is imported. Keep parser fragments private per call.
            _parser_log.propagate = False
            if not _parser_log.handlers:
                _parser_log.addHandler(logging.NullHandler())
            from pypdf import PdfReader
            # Some logging setups attach handlers directly to parser children.
            # Suppress those too; parser diagnostics can contain private bytes.
            for name, logger in list(logging.Logger.manager.loggerDict.items()):
                if name == 'pypdf' or name.startswith('pypdf.'):
                    if isinstance(logger, logging.Logger):
                        logger.disabled = True
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted:
                raise ValueError('Remove encryption from this encrypted PDF before uploading.')
            if len(reader.pages) > 200:
                raise ValueError('PDF exceeds 200 pages.')
            for number, page in enumerate(reader.pages, 1):
                append(page.extract_text() or '', f'Page {number}')
            if not sections:
                raise ValueError('Upload a searchable PDF or a text version; scanned PDFs need OCR.')
        elif kind == 'docx':
            from docx import Document
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                if sum(info.file_size for info in archive.infolist()) > 30*1024*1024:
                    raise ValueError('Expanded document is too large.')
            doc = Document(io.BytesIO(data))
            # iter_inner_content preserves paragraph/table order in the body.
            from docx.text.paragraph import Paragraph
            paragraph = table = 0
            for block in doc.iter_inner_content():
                if isinstance(block, Paragraph):
                    paragraph += 1
                    append(block.text, f'Paragraph {paragraph}')
                else:
                    table += 1
                    for row_index, row in enumerate(block.rows, 1):
                        append(' | '.join(cell.text for cell in row.cells), f'Table {table}, row {row_index}')
        elif kind == 'txt':
            text = data.decode('utf-8-sig')
            if len(text) > MAX_CHARACTERS:
                raise ValueError('Document exceeds 200,000 extracted characters.')
            for number, paragraph in enumerate(re.split(r'\n\s*\n', text), 1):
                append(paragraph, f'Paragraph {number}')
        else:
            raise ValueError('Choose a PDF, DOCX, or UTF-8 text document.')
    except ValueError:
        raise
    except Exception as error:
        raise ValueError('This document is malformed or is not valid UTF-8 text.') from error
    if not sections:
        raise ValueError('Document contains no readable text.')
    return sections


def chunk_sections(sections: list[dict]) -> list[dict]:
    chunks = []
    for section in sections:
        words = section['text'].split()
        for start in range(0, len(words), 450):
            text = ' '.join(words[start:start+500])
            # Limit pathological long words so retrieval always admits a passage.
            for offset in range(0, len(text), 8000):
                chunks.append({'ordinal': len(chunks), 'text': text[offset:offset+8000], 'location': section['location']})
            if start+500 >= len(words):
                break
    return chunks
