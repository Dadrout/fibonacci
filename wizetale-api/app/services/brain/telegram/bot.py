"""Handle one Telegram update: link a chat, or capture whatever the student sent.

`handle_update` never raises: the webhook would answer 500 and Telegram would redeliver the
same update forever. Captures use a request id derived from (chat, message, index), so a
redelivered update never files the same item twice.
"""
from __future__ import annotations

import logging
import re
import threading
import time
from collections import OrderedDict
from typing import Any, Callable, Optional
from uuid import NAMESPACE_URL, uuid5

from app.services.brain import events
from app.services.brain.capture import CaptureRejected, CaptureService, capture_service
from app.services.brain.store import BrainStore, brain_store
from app.services.brain.telegram import linking
from app.services.brain.telegram.client import TelegramClient, TelegramError, TooLarge, telegram_client
from app.services.brain.telegram.texts import lang, t

logger = logging.getLogger(__name__)
URL = re.compile(r"https?://[^\s<>\"'«»]+", re.IGNORECASE)
CODE = re.compile(r"^(?:/start(?:@\w+)?\s+)?([0-9]{3})[\s-]?([0-9]{3})$")
MAX_LINKS = 5
MAX_CODE_FAILURES = 5  # per chat per window: a 6-digit code must not be brute-forced
CODE_FAILURE_WINDOW = 600.0

_lock = threading.Lock()
_code_failures: dict[int, list[float]] = {}
_acked_albums: "OrderedDict[str, None]" = OrderedDict()


def _file(message: dict) -> Optional[tuple[str, str, Optional[str], Optional[int]]]:
    """(file_id, filename, mime, size) for photos, documents, voice notes, and audio."""
    if message.get("photo"):
        # Sizes come smallest first; pick by pixels (file_size is optional and not comparable to pixels).
        best = max(message["photo"], key=lambda p: ((p.get("width") or 0) * (p.get("height") or 0), p.get("file_size") or 0))
        return best["file_id"], f"photo_{message.get('message_id')}.jpg", "image/jpeg", best.get("file_size")
    for key, default_name, default_mime in (("document", "file", None), ("voice", "voice.ogg", "audio/ogg"),
                                             ("audio", "audio.mp3", "audio/mpeg")):
        media = message.get(key)
        if media and media.get("file_id"):
            return media["file_id"], media.get("file_name") or default_name, media.get("mime_type") or default_mime, media.get("file_size")
    return None


def _entity_text(text: str, entity: dict) -> str:
    """Entity offsets count UTF-16 code units, not Python characters."""
    encoded = text.encode("utf-16-le")
    start, length = int(entity.get("offset") or 0) * 2, int(entity.get("length") or 0) * 2
    return encoded[start:start + length].decode("utf-16-le", errors="ignore")


def _clean_url(url: str) -> Optional[str]:
    url = url.strip().rstrip(".,;:!?…")
    while url.endswith(")") and url.count("(") < url.count(")"):
        url = url[:-1].rstrip(".,;:!?…")
    if not url:
        return None
    if "://" not in url:
        url = "https://" + url
    return url if url.lower().startswith(("http://", "https://")) else None


def _urls(message: dict) -> list[str]:
    """Links in the text or caption: visible URLs and hidden `text_link`s, in order, at most MAX_LINKS."""
    found: list[str] = []
    for text_key, entities_key in (("text", "entities"), ("caption", "caption_entities")):
        body = message.get(text_key) or ""
        from_entities = False
        for entity in message.get(entities_key) or []:
            if entity.get("type") == "text_link" and entity.get("url"):
                found.append(entity["url"])
                from_entities = True
            elif entity.get("type") == "url":
                found.append(_entity_text(body, entity))
                from_entities = True
        if not from_entities:
            found.extend(URL.findall(body))
    unique: list[str] = []
    for raw in found:
        url = _clean_url(raw)
        if url and url not in unique:
            unique.append(url)
    return unique[:MAX_LINKS]


def _request_id(chat: int, message_id: Any, index: int) -> str:
    return str(uuid5(NAMESPACE_URL, f"telegram:{chat}:{message_id}:{index}"))


def _send(client: TelegramClient, chat: int, text: str, reply_to: Optional[int]) -> None:
    try:
        client.send(chat, text, reply_to)
    except TelegramError as error:
        logger.warning("brain_telegram send_failed error_type=%s", type(error).__name__)


def _throttled(chat: int) -> bool:
    now = time.monotonic()
    with _lock:
        recent = [at for at in _code_failures.get(chat, []) if now - at < CODE_FAILURE_WINDOW]
        _code_failures[chat] = recent
        return len(recent) >= MAX_CODE_FAILURES


def _code_failed(chat: int) -> None:
    with _lock:
        if len(_code_failures) > 10_000:
            _code_failures.clear()
        _code_failures.setdefault(chat, []).append(time.monotonic())


def _first_of_album(chat: int, message: dict) -> bool:
    """Albums arrive as one message per photo; acknowledge the album once."""
    group = message.get("media_group_id")
    if not group:
        return True
    key = f"{chat}:{group}"
    with _lock:
        if key in _acked_albums:
            return False
        _acked_albums[key] = None
        while len(_acked_albums) > 1000:
            _acked_albums.popitem(last=False)
    return True


def _link(code: str, chat: int, sender: dict, language: str, message_id: Optional[int], client: TelegramClient,
          store: BrainStore) -> None:
    if _throttled(chat):
        _send(client, chat, t(language, "link_failed"), message_id)
        return
    uid = store.redeem_telegram_code(linking.code_hash(code), chat, sender.get("id"), sender.get("username"))
    if not uid:
        _code_failed(chat)
        _send(client, chat, t(language, "link_failed"), message_id)
        return
    _send(client, chat, t(language, "linked"), message_id)
    try:
        events.publish(uid, "telegram.linked", telegram=linking.status(uid, store=store, client=client))
    except Exception as error:  # noqa: BLE001 — the link is saved; the web app also polls status
        logger.warning("brain_telegram linked_event_failed error_type=%s", type(error).__name__)


def _reply_for(code: str) -> str:
    return "too_large" if code == "too_large" else "unsupported" if code == "unsupported_type" else "error"


def _handle(message: dict, chat: int, language: str, client: TelegramClient, capture: CaptureService,
            store: BrainStore) -> None:
    sender = message.get("from") or {}
    message_id = message.get("message_id")
    text = (message.get("text") or "").strip()
    # A forwarded message is content to file, never a command or a link code.
    forwarded = bool(message.get("forward_origin") or message.get("forward_date") or message.get("forward_from_chat"))

    if text and not forwarded:
        code = CODE.match(text)
        if code:
            _link(code.group(1) + code.group(2), chat, sender, language, message_id, client, store)
            return

    link = store.telegram_link_for_chat(chat)
    if not link:
        _send(client, chat, t(language, "how_to_link"), message_id)
        return
    if text.startswith("/") and not forwarded:
        command = text.split()[0].split("@")[0].lower()
        _send(client, chat, t(language, "ready" if command in ("/start", "/help") else "unsupported"), message_id)
        return

    uid = link["user_id"]
    metadata = {"telegram": {"chat_id": chat, "message_id": message_id, "language": language}}
    jobs: list[Callable[[str], dict]] = []
    file = _file(message)
    if file:
        file_id, name, mime, size = file

        def upload(request_id: str) -> dict:
            data = client.download(file_id, size)
            return capture.from_upload(uid, None, data, name, mime, channel="telegram", request_id=request_id,
                                       metadata=metadata)
        jobs.append(upload)
    for url in _urls(message):
        jobs.append(lambda request_id, url=url: capture.from_link(uid, None, url, channel="telegram",
                                                                  request_id=request_id, metadata=metadata))
    if not jobs and text:
        jobs.append(lambda request_id: capture.from_text(uid, None, text, channel="telegram", request_id=request_id,
                                                         metadata=metadata))
    if not jobs:
        _send(client, chat, t(language, "unsupported"), message_id)
        return

    client.typing(chat)
    rows: list[dict] = []
    rejection: Optional[str] = None
    for index, job in enumerate(jobs):
        try:
            rows.append(job(_request_id(chat, message_id, index)) or {})
        except TooLarge:
            rejection = rejection or "too_large"
        except CaptureRejected as error:
            rejection = rejection or error.code
    if not rows:
        _send(client, chat, t(language, _reply_for(rejection or "internal")), message_id)
    elif all(row.get("status") == "failed" for row in rows):  # stored but could not be queued
        _send(client, chat, t(language, "failed", reason=t(language, "reason.internal")), message_id)
    elif _first_of_album(chat, message):
        _send(client, chat, t(language, "got_it"), message_id)


def handle_update(update: dict, *, client: TelegramClient = telegram_client, capture: CaptureService = capture_service,
                  store: BrainStore = brain_store) -> None:
    message = update.get("message") if isinstance(update, dict) else None
    if not isinstance(message, dict):
        return
    chat_info = message.get("chat") or {}
    chat = chat_info.get("id")
    if not chat or chat_info.get("type") != "private":  # groups and channels are ignored
        return
    language = lang((message.get("from") or {}).get("language_code"))
    try:
        _handle(message, chat, language, client, capture, store)
    except Exception as error:  # noqa: BLE001 — log the type only: exception text can carry URLs
        logger.warning("brain_telegram update=%s error_type=%s", update.get("update_id"), type(error).__name__)
        _send(client, chat, t(language, "error"), message.get("message_id"))
