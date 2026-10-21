"""Audio files and Telegram voice notes → timestamped transcript."""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from typing import Optional

from app.core.config import settings
from app.domain.brain.pipeline import Extraction, ExtractInput, ExtractionError
from app.services.brain.ai.client import AIUnavailable, BrainAI, Part
from app.services.brain.extract.segments import Transcript, windows


def _duration(data: bytes) -> Optional[float]:
    binary = shutil.which("ffprobe")
    if not binary:
        return None
    with tempfile.NamedTemporaryFile() as handle:
        handle.write(data)
        handle.flush()
        try:
            result = subprocess.run([binary, "-v", "error", "-show_entries", "format=duration", "-of", "json", handle.name],
                                    capture_output=True, text=True, timeout=15)
            return float(json.loads(result.stdout)["format"]["duration"])
        except Exception:  # noqa: BLE001
            return None


def extract(inp: ExtractInput, ai: BrainAI) -> Extraction:
    data = inp.data or b""
    duration = _duration(data)
    if duration is not None and duration > 7200:
        raise ExtractionError("too_large", "Audio longer than 2 hours")
    try:
        transcript = ai.generate(operation="brain_transcribe_audio", prompt="transcribe_media", schema=Transcript,
                                 parts=[Part(mime_type=inp.mime_type or "audio/ogg", data=data)],
                                 model=settings.BRAIN_TRANSCRIBE_MODEL, max_output_tokens=32768, timeout=90)
    except AIUnavailable as error:
        raise ExtractionError("ai_unavailable", "Transcription unavailable") from error
    chunks = windows(transcript.segments)
    if not chunks:
        raise ExtractionError("unreadable", "No speech found")
    end = max(c.anchor.end_sec or 0 for c in chunks)
    return Extraction(title=transcript.title, language=transcript.language, chunks=chunks,
                      duration_sec=duration or end, metadata={"transcript": "ai"})
