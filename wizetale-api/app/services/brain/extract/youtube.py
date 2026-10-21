"""YouTube link → transcript with timestamp windows (captions first, Gemini second)."""
from __future__ import annotations

import logging
from typing import Optional

import requests

from app.core.config import settings
from app.domain.brain.pipeline import Anchor, ExtractedChunk, Extraction, ExtractInput, ExtractionError
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


CLIP_SECONDS = 300
CLIPS_PER_BATCH = 3
MAX_SECONDS = 7200


def _clip(video_id: str, start: int, ai: BrainAI) -> Transcript:
    return ai.generate(operation="brain_transcribe_youtube", prompt="transcribe_youtube", schema=Transcript,
                       parts=[Part(file_uri=f"https://www.youtube.com/watch?v={video_id}", clip=(start, start + CLIP_SECONDS))],
                       model=settings.BRAIN_TRANSCRIBE_MODEL, max_output_tokens=8192, timeout=45)


def _transcribe_clips(video_id: str, ai: BrainAI) -> Transcript:
    """Transcribe 5-minute clips a few at a time (fast, accurate timestamps, gentle on rate limits).

    Stops when a batch yields no speech: past the end of the video Gemini returns errors or empty clips.
    """
    from concurrent.futures import ThreadPoolExecutor

    segments: list[Segment] = []
    title, language = None, "en-US"
    start = 0
    with ThreadPoolExecutor(max_workers=CLIPS_PER_BATCH) as pool:
        while start < MAX_SECONDS:
            starts = list(range(start, min(start + CLIP_SECONDS * CLIPS_PER_BATCH, MAX_SECONDS), CLIP_SECONDS))
            futures = {s: pool.submit(_clip, video_id, s, ai) for s in starts}
            found_any = False
            last_has_speech = False
            for s in starts:
                try:
                    result = futures[s].result()
                except Exception:  # noqa: BLE001 — past the end, rate-limited, or transient
                    last_has_speech = False
                    continue
                last_has_speech = bool(result.segments)
                if not result.segments:
                    continue
                found_any = True
                title = title or result.title
                language = result.language
                for seg in result.segments:
                    if seg.start_sec < CLIP_SECONDS + 5:
                        segments.append(Segment(start_sec=s + seg.start_sec,
                                                end_sec=s + min(max(seg.end_sec, seg.start_sec), CLIP_SECONDS), text=seg.text))
            if not found_any or not last_has_speech:
                break
            start = starts[-1] + CLIP_SECONDS
    if not segments:
        raise AIUnavailable("No clip could be transcribed")
    return Transcript(title=title, language=language, segments=sorted(segments, key=lambda seg: seg.start_sec))


def extract(inp: ExtractInput, ai: BrainAI) -> Extraction:
    video_id = inp.youtube_id
    if not video_id:
        raise ExtractionError("fetch_failed", "Missing YouTube id")
    # Captions and video metadata are recorded like AI outputs, so a rehearsed video works offline.
    cache_key = ai.cache.key("youtube_captions", "v1", video_id)
    recorded = ai.cache.get("youtube_captions", cache_key)
    if recorded:
        meta, segments = recorded.get("meta", {}), [Segment(**s) for s in recorded.get("segments", [])]
    else:
        meta, segments = _oembed(video_id), _captions(video_id)
        if segments:
            ai.cache.put("youtube_captions", cache_key, {"meta": meta, "segments": [s.model_dump() for s in segments]})
    method, language, title = "captions", None, meta.get("title")
    if not segments:
        try:
            transcript = _transcribe_clips(video_id, ai)
        except AIUnavailable as error:
            if not title:
                raise ExtractionError("transcript_unavailable", "No captions and transcription failed") from error
            # Degraded but honest: file the video by its public title; no timestamps to cite.
            logger.info("brain_youtube transcript_unavailable filing_by_title")
            text = title + (f" — {meta['author_name']}" if meta.get("author_name") else "")
            return Extraction(title=title, chunks=[ExtractedChunk(anchor=Anchor(kind="section", heading="YouTube"), text=text)],
                              thumbnail=_thumbnail(video_id), thumbnail_mime="image/jpeg",
                              metadata={"transcript": "title_only", "channel": (meta.get("author_name") or "")[:120]})
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
