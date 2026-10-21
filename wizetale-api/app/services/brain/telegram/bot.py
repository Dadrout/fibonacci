"""Handle one Telegram update: link a chat, or capture whatever the student sent."""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

from app.services.brain import events
from app.services.brain.capture import CaptureRejected, CaptureService, capture_service
from app.services.brain.store import BrainStore, brain_store
from app.services.brain.telegram import linking
from app.services.brain.telegram.client import TelegramClient, TelegramError, TooLarge, telegram_client
from app.services.brain.telegram.texts import lang, t

logger = logging.getLogger(__name__)
URL = re.compile(r"https?://[^\s<>\"']+")
CODE = re.compile(r"^\s*(?:/start\s+)?(\d{6})\s*$")
MAX_LINKS = 5


def _file(message: dict) -> Optional[tuple[str, str, Optional[str], Optional[int]]]:
    """(file_id, filename, mime, size) for photos, documents, voice notes, and audio."""
    if message.get("photo"):
        best = max(message["photo"], key=lambda p: p.get("file_size") or p.get("width", 0) * p.get("height", 0))
        return best["file_id"], f"photo_{message.get('message_id')}.jpg", "image/jpeg", best.get("file_size")
    for key, default_name, default_mime in (("document", "file", None), ("voice", "voice.ogg", "audio/ogg"),
                                             ("audio", "audio.mp3", "audio/mpeg")):
        if message.get(key):
            media = message[key]
            return media["file_id"], media.get("file_name") or default_name, media.get("mime_type") or default_mime, media.get("file_size")
    return None


def handle_update(update: dict, *, client: TelegramClient = telegram_client, capture: CaptureService = capture_service,
                  store: BrainStore = brain_store) -> None:
    message = update.get("message") or {}
    chat = (message.get("chat") or {}).get("id")
    if not chat or (message.get("chat") or {}).get("type") != "private":
        return
    sender = message.get("from") or {}
    language = lang(sender.get("language_code"))
    message_id = message.get("message_id")
    text = (message.get("text") or "").strip()

    code = CODE.match(text) if text else None
    if code:
        uid = store.redeem_telegram_code(linking.code_hash(code.group(1)), chat, sender.get("id"), sender.get("username"))
        if uid:
            client.send(chat, t(language, "linked"), message_id)
            events.publish(uid, "telegram.linked", telegram=linking.status(uid, store=store, client=client))
        else:
            client.send(chat, t(language, "link_failed"), message_id)
        return

    link = store.telegram_link_for_chat(chat)
    if not link:
        client.send(chat, t(language, "how_to_link"), message_id)
        return
    uid = link["user_id"]
    metadata = {"telegram": {"chat_id": chat, "message_id": message_id, "language": language}}
    try:
        file = _file(message)
        if file:
            file_id, name, mime, size = file
            client.typing(chat)
            data = client.download(file_id, size)
            capture.from_upload(uid, None, data, name, mime, channel="telegram", request_id=None, metadata=metadata)
        elif text:
            urls = URL.findall(text)[:MAX_LINKS]
            if text.startswith("/"):
                client.send(chat, t(language, "how_to_link" if text.startswith("/start") else "unsupported"), message_id)
                return
            if urls:
                for url in urls:
                    capture.from_link(uid, None, url.rstrip(").,"), channel="telegram", request_id=None, metadata=metadata)
            else:
                capture.from_text(uid, None, text, channel="telegram", request_id=None, metadata=metadata)
        else:
            client.send(chat, t(language, "unsupported"), message_id)
            return
        client.send(chat, t(language, "got_it"), message_id)
    except TooLarge:
        client.send(chat, t(language, "too_large"), message_id)
    except CaptureRejected as error:
        key = "too_large" if error.code == "too_large" else "unsupported" if error.code == "unsupported_type" else "error"
        client.send(chat, t(language, key), message_id)
    except (TelegramError, Exception) as error:  # noqa: BLE001
        logger.warning("brain_telegram update=%s error_type=%s", update.get("update_id"), type(error).__name__)
        try:
            client.send(chat, t(language, "error"), message_id)
        except TelegramError:
            pass
