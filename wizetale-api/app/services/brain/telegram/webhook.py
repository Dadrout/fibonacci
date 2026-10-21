"""Webhook entry point (production). Telegram signs requests with our secret header."""
from __future__ import annotations

import hmac
from typing import Optional

from app.core.config import settings
from app.services.brain.telegram.bot import handle_update


def handle_webhook(body: dict, secret_header: Optional[str]) -> bool:
    secret = settings.TELEGRAM_WEBHOOK_SECRET
    if not secret or not secret_header or not hmac.compare_digest(secret, secret_header):
        return False
    handle_update(body)
    return True
