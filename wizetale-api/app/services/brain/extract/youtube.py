"""YouTube link → transcript with timestamp windows (captions first, Gemini second)."""
from __future__ import annotations

import logging
from typing import Optional

import requests

from app.core.config import settings
from app.domain.brain.pipeline import Extraction, ExtractInput, ExtractionError
from app.services.brain.ai.client import AIUnavailable, BrainAI, Part
from app.services.brain.extract.segments import Segment, Transcript, windows

logger = logging.getLogger(__name__)
LANGUAGES = ["ru", "kk", "en", "en-US", "en-GB"]


def _captions(video_id: str) -> Optional[list[Segment]]:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        api = YouTubeTranscriptApi()
        listing = api.list(video_id)
        transcript = None
        for finder in (listing.find_manually_created_transcript, listing.find_generated_transcript):
            try:
                transcript = finder(LANGUAGES)
                break
            except Exception:  # noqa: BLE001
                continue
        if transcript is None:
            transcript = next(iter(listing), None)
        if transcript is None:
            return None
        fetched = transcript.fetch()
        return [Segment(start_sec=s.start, end_sec=s.start + s.duration, text=s.text) for s in fetched]
    except Exception as error:  # noqa: BLE001 — blocked IPs, no captions, network
        logger.info("brain_youtube captions_unavailable error_type=%s", type(error).__name__)
        return None


def _language(code: Optional[str]) -> Optional[str]:
    if not code:
        return None
    code = code.lower()
    return "ru-RU" if code.startswith("ru") else "kk-KZ" if code.startswith("kk") else "en-US" if code.startswith("en") else None


def _oembed(video_id: str) -> dict:
    try:
        response = requests.get("https://www.youtube.com/oembed",
                                params={"url": f"https://www.youtube.com/watch?v={video_id}", "format": "json"}, timeout=5)
        return response.json() if response.ok else {}
    except Exception:  # noqa: BLE001
        return {}


def _thumbnail(video_id: str) -> Optional[bytes]:
    try:
        response = requests.get(f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg", timeout=5)
        if response.ok and len(response.content) <= 300_000:
            return response.content
    except Exception:  # noqa: BLE001
        pass
    return None


def extract(inp: ExtractInput, ai: BrainAI) -> Extraction:
    video_id = inp.youtube_id
    if not video_id:
        raise ExtractionError("fetch_failed", "Missing YouTube id")
    meta = _oembed(video_id)
    segments = _captions(video_id)
    method, language, title = "captions", None, meta.get("title")
    if not segments:
        try:
            transcript = ai.generate(operation="brain_transcribe_youtube", prompt="transcribe_youtube", schema=Transcript,
                                     parts=[Part(file_uri=f"https://www.youtube.com/watch?v={video_id}")],
                                     model=settings.BRAIN_TRANSCRIBE_MODEL, max_output_tokens=32768, timeout=90)
        except AIUnavailable as error:
            raise ExtractionError("transcript_unavailable", "No captions and transcription failed") from error
        segments, method, language = transcript.segments, "ai", transcript.language
        title = title or transcript.title
    chunks = windows(segments)
    if not chunks:
        raise ExtractionError("transcript_unavailable", "Empty transcript")
    duration = max(c.anchor.end_sec or 0 for c in chunks)
    metadata = {"transcript": method}
    if meta.get("author_name"):
        metadata["channel"] = meta["author_name"][:120]
    return Extraction(title=title, language=language, chunks=chunks, duration_sec=duration,
                      thumbnail=_thumbnail(video_id), thumbnail_mime="image/jpeg", metadata=metadata)
