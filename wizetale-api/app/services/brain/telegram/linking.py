"""One-time codes that link a Telegram chat to a Fibonacci account."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.services.brain.store import BrainStore, brain_store
from app.services.brain.telegram.client import TelegramClient, telegram_client

CODE_TTL = timedelta(minutes=10)


def code_hash(code: str) -> str:
    return hashlib.sha256(code.strip().encode()).hexdigest()


def create_link_code(uid: str, *, store: BrainStore = brain_store, client: TelegramClient = telegram_client) -> dict:
    code = f"{secrets.randbelow(1_000_000):06d}"
    expires = datetime.now(timezone.utc) + CODE_TTL
    store.save_telegram_code(uid, code_hash(code), expires)
    bot = client.username() or "FibonacciBrainBot"
    return {"code": code, "deep_link": f"https://t.me/{bot}?start={code}", "expires_at": expires.isoformat(), "bot_username": bot}


def status(uid: str, *, store: BrainStore = brain_store, client: TelegramClient = telegram_client) -> dict:
    link = store.telegram_link(uid)
    configured = bool(settings.TELEGRAM_BOT_TOKEN)
    return {"bot_configured": configured, "bot_username": client.username() if configured else None, "linked": bool(link),
            "telegram_username": link.get("telegram_username") if link else None, "linked_at": link.get("linked_at") if link else None}
