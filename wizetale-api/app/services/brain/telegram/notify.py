"""Replies to the original Telegram message once the pipeline files (or fails) an item."""
from __future__ import annotations

import logging
from typing import Optional

from app.services.brain.telegram.client import TelegramClient, TelegramError, telegram_client
from app.services.brain.telegram.texts import TEXTS, t

logger = logging.getLogger(__name__)


def _target(item: dict) -> Optional[tuple[int, Optional[int], str]]:
    meta = (item.get("metadata") or {}).get("telegram") or {}
    try:
        chat = int(meta.get("chat_id") or 0)
    except (TypeError, ValueError):
        return None
    if not chat:
        return None
    language = meta.get("language") if meta.get("language") in TEXTS else "en"
    return chat, meta.get("message_id"), language


def notify_filed(item: dict, course_title: str, topic_title: Optional[str], cross_link: Optional[str] = None,
                 client: TelegramClient = telegram_client) -> None:
    target = _target(item)
    if not target or not client.configured:
        return
    chat, message_id, language = target
    where = " → ".join(part.strip() for part in (course_title, topic_title) if part and part.strip()) or "Brain"
    text = t(language, "filed", where=where)
    if cross_link:
        text += "\n" + t(language, "new_link", link=cross_link)
    try:
        client.send(chat, text, message_id)
    except TelegramError as error:
        logger.warning("brain_telegram notify_filed_failed error_type=%s", type(error).__name__)


def notify_failed(item: dict, failure_code: str, client: TelegramClient = telegram_client) -> None:
    target = _target(item)
    if not target or not client.configured:
        return
    chat, message_id, language = target
    key = f"reason.{failure_code}" if f"reason.{failure_code}" in TEXTS["en"] else "reason.internal"
    try:
        client.send(chat, t(language, "failed", reason=t(language, key)), message_id)
    except TelegramError as error:
        logger.warning("brain_telegram notify_failed_failed error_type=%s", type(error).__name__)
