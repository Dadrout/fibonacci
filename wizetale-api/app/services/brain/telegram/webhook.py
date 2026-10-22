"""Webhook entry point (production). Telegram sends our secret in `X-Telegram-Bot-Api-Secret-Token`."""
from __future__ import annotations

import hmac
import logging
from typing import Optional

from app.core.config import settings
from app.services.brain.telegram.bot import handle_update

logger = logging.getLogger(__name__)


def handle_webhook(body: dict, secret_header: Optional[str]) -> bool:
    """False (→ 401) unless the secret matches. Accepted updates always return True, so Telegram never redelivers."""
    secret = settings.TELEGRAM_WEBHOOK_SECRET
    if not secret or not secret_header:
        return False
    # Compare bytes: compare_digest raises TypeError for non-ASCII str.
    if not hmac.compare_digest(secret.encode("utf-8"), secret_header.encode("utf-8", "surrogateescape")):
        return False
    if isinstance(body, dict):
        try:
            handle_update(body)
        except Exception as error:  # noqa: BLE001
            logger.warning("brain_telegram webhook update=%s error_type=%s", body.get("update_id"), type(error).__name__)
    return True
