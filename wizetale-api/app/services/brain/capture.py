"""Turn anything a student sends (file, link, text) into a queued brain item.

Used by the web API and the Telegram bot. Steps: detect the kind, store the original,
create the `brain_items` row (idempotent per request id), emit `item.created`, and queue
the pipeline. No "choose a folder" step — filing happens in the pipeline.
"""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Callable, Optional
from urllib.parse import urlsplit
from uuid import uuid4

from app.core.config import settings
from app.services.brain import events
from app.services.brain.blobs import BlobStore, blob_store, object_path
from app.services.brain.store import BrainStore, brain_store
from app.services.brain.views import item_view

logger = logging.getLogger(__name__)

YOUTUBE_ID = re.compile(
    r"(?:youtube\.com/(?:watch\?(?:.*&)?v=|shorts/|live/|embed/)|youtu\.be/|youtube-nocookie\.com/embed/)([A-Za-z0-9_-]{11})"
)
AUDIO_EXTENSIONS = {".m4a", ".mp3", ".ogg", ".oga", ".opus", ".wav", ".webm", ".aac", ".flac"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".gif", ".bmp"}
EXTENSION_MIME = {
    ".pdf": "application/pdf", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp",
    ".heic": "image/heic", ".heif": "image/heif", ".gif": "image/gif", ".bmp": "image/bmp", ".m4a": "audio/mp4",
    ".mp3": "audio/mpeg", ".ogg": "audio/ogg", ".oga": "audio/ogg", ".opus": "audio/ogg", ".wav": "audio/wav",
    ".webm": "audio/webm", ".aac": "audio/aac", ".flac": "audio/flac",
}


class CaptureRejected(ValueError):
    """Input we will not accept. `code` is a BrainErrorCode."""

    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code


@dataclass
class Sniffed:
    kind: str
    mime: str
    extension: str


def youtube_id(url: str) -> Optional[str]:
    match = YOUTUBE_ID.search(url)
    return match.group(1) if match else None


def sniff_file(data: bytes, filename: str, declared_mime: Optional[str]) -> Sniffed:
    """Decide the capture kind from magic bytes first, then extension, then the declared type."""
    extension = PurePosixPath(filename.lower()).suffix
    head = data[:16]
    if head.startswith(b"%PDF"):
        return Sniffed("pdf", "application/pdf", ".pdf")
    if head.startswith(b"\xff\xd8\xff"):
        return Sniffed("photo", "image/jpeg", ".jpg")
    if head.startswith(b"\x89PNG"):
        return Sniffed("photo", "image/png", ".png")
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return Sniffed("photo", "image/webp", ".webp")
    if head[4:12] in (b"ftypheic", b"ftypheix", b"ftypmif1", b"ftyphevc"):
        return Sniffed("photo", "image/heic", ".heic")
    if head.startswith(b"PK") and extension == ".docx":
        return Sniffed("document", EXTENSION_MIME[".docx"], ".docx")
    mime = (declared_mime or "").split(";")[0].strip().lower()
    if extension in AUDIO_EXTENSIONS or mime.startswith("audio/") or head.startswith((b"OggS", b"ID3", b"fLaC")) \
            or head[4:8] == b"ftyp" and extension in (".m4a", ".aac"):
        ext = extension if extension in AUDIO_EXTENSIONS else ".ogg" if head.startswith(b"OggS") else ".m4a"
        return Sniffed("audio", mime if mime.startswith("audio/") else EXTENSION_MIME.get(ext, "audio/mpeg"), ext)
    if extension in IMAGE_EXTENSIONS and mime.startswith("image/"):
        return Sniffed("photo", mime, extension)
    if extension == ".txt" or mime == "text/plain":
        try:
            data.decode("utf-8")
        except UnicodeDecodeError as error:
            raise CaptureRejected("unsupported_type", "Text files must be UTF-8.") from error
        return Sniffed("document", "text/plain", ".txt")
    raise CaptureRejected("unsupported_type", "Send a photo, PDF, DOCX, text file, audio, or a link.")


def _title_from_url(url: str) -> str:
    parts = urlsplit(url)
    path = parts.path.strip("/")
    return (parts.netloc + ("/" + path if path else ""))[:200] or url[:200]


class CaptureService:
    def __init__(self, store: BrainStore = brain_store, blobs: BlobStore = blob_store,
                 enqueue: Optional[Callable[[str, str, str], None]] = None):
        self.store, self.blobs = store, blobs
        self._enqueue = enqueue

    def enqueue(self, uid: str, item_id: str, task_id: str) -> None:
        if self._enqueue:
            self._enqueue(uid, item_id, task_id)
            return
        from app.services.brain.pipeline import process_item  # late import: Celery app loads lazily

        process_item.apply_async(args=[uid, item_id, task_id], task_id=task_id)

    # ------------------------------------------------------------------ entry points

    def from_upload(self, uid: str, email: Optional[str], data: bytes, filename: str, mime: Optional[str], *,
                    channel: str, request_id: Optional[str] = None, metadata: Optional[dict] = None) -> dict:
        if not data:
            raise CaptureRejected("invalid_input", "This file is empty.")
        if len(data) > settings.BRAIN_MAX_UPLOAD_BYTES:
            raise CaptureRejected("too_large", "Choose a file up to 20 MB.")
        sniffed = sniff_file(data, filename or "file", mime)
        title = (PurePosixPath(filename).name if filename else f"{sniffed.kind}{sniffed.extension}")[:200] or "Untitled"
        return self._create(uid, email, kind=sniffed.kind, channel=channel, title=title, request_id=request_id,
                            data=data, mime=sniffed.mime, extension=sniffed.extension, metadata=metadata)

    def from_link(self, uid: str, email: Optional[str], url: str, *, channel: str,
                  request_id: Optional[str] = None, metadata: Optional[dict] = None) -> dict:
        url = url.strip()
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.netloc or len(url) > 2048:
            raise CaptureRejected("invalid_input", "Send a full http(s) link.")
        video = youtube_id(url)
        kind = "youtube" if video else "web"
        title = f"youtu.be/{video}" if video else _title_from_url(url)
        return self._create(uid, email, kind=kind, channel=channel, title=title, request_id=request_id,
                            source_url=url, youtube=video, metadata=metadata)

    def from_text(self, uid: str, email: Optional[str], text: str, *, title: Optional[str] = None, channel: str,
                  request_id: Optional[str] = None, metadata: Optional[dict] = None) -> dict:
        text = text.strip()
        if not text:
            raise CaptureRejected("invalid_input", "Text is empty.")
        if len(text) > 100_000:
            raise CaptureRejected("too_large", "Paste up to 100,000 characters.")
        # A message that is just a link is a link capture.
        if re.fullmatch(r"https?://\S+", text):
            return self.from_link(uid, email, text, channel=channel, request_id=request_id, metadata=metadata)
        heading = (title or text.splitlines()[0]).strip()[:200] or "Note"
        return self._create(uid, email, kind="text", channel=channel, title=heading, request_id=request_id,
                            data=text.encode("utf-8"), mime="text/plain", extension=".txt", metadata=metadata)

    # ------------------------------------------------------------------ core

    def _create(self, uid: str, email: Optional[str], *, kind: str, channel: str, title: str,
                request_id: Optional[str], data: Optional[bytes] = None, mime: Optional[str] = None,
                extension: str = "", source_url: Optional[str] = None, youtube: Optional[str] = None,
                metadata: Optional[dict] = None) -> dict:
        self.store.ensure_user(uid, email)
        if self.store.is_user_deleting(uid):
            raise CaptureRejected("conflict", "Account deletion is in progress.")
        item_id, task_id = str(uuid4()), str(uuid4())
        path = object_path(uid, item_id, f"original{extension}") if data is not None else None
        digest_source = data if data is not None else (youtube or source_url or "").encode()
        record: dict[str, Any] = {
            "id": item_id, "user_id": uid, "kind": kind, "channel": channel, "status": "queued", "progress": 0.02,
            "title": title, "source_url": source_url, "youtube_id": youtube, "object_path": path, "mime_type": mime,
            "byte_count": len(data) if data is not None else None,
            "content_hash": hashlib.sha256(digest_source).hexdigest(), "task_id": task_id,
            "request_id": request_id, "metadata": metadata or {},
        }
        row = self.store.create_item(record)
        if row["id"] != item_id:  # idempotent repeat of an earlier request
            return row
        if data is not None and path:
            try:
                self.blobs.put(path, data, mime or "application/octet-stream")
            except Exception:
                self.store.update_item(uid, item_id, {"status": "failed", "failure_code": "internal"}, task_id=task_id)
                raise
        view = item_view(uid, row, courses={}, topics={})
        events.publish(uid, "item.created", item=view)
        try:
            self.enqueue(uid, item_id, task_id)
        except Exception:
            logger.exception("brain_capture enqueue_failed item=%s", item_id)
            failed = self.store.update_item(uid, item_id, {"status": "failed", "failure_code": "internal"}, task_id=task_id)
            events.publish(uid, "item.failed", item_id=item_id, failure_code="internal")
            return failed or row
        logger.info("brain_capture item=%s kind=%s channel=%s bytes=%s", item_id, kind, channel, record["byte_count"])
        return row


capture_service = CaptureService()
