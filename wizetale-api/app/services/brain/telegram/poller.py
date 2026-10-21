"""Long-polling loop for local and demo use: `python -m app.services.brain.telegram.poller`."""
from __future__ import annotations

import logging
import signal
import time

import redis

from app.core.config import settings
from app.services.brain.telegram.bot import handle_update
from app.services.brain.telegram.client import TelegramClient, TelegramError

logger = logging.getLogger("brain.telegram.poller")
OFFSET_KEY = "brain:telegram:offset"
running = True


def _stop(*_args) -> None:
    global running
    running = False


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    if settings.TELEGRAM_MODE != "polling" or not settings.TELEGRAM_BOT_TOKEN:
        logger.info("telegram poller disabled (mode=%s, token=%s)", settings.TELEGRAM_MODE, bool(settings.TELEGRAM_BOT_TOKEN))
        while running:  # stay up so the container is healthy; nothing to do
            time.sleep(30)
        return
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    client = TelegramClient()
    store = redis.Redis.from_url(settings.REDIS_URL, socket_timeout=40)
    try:
        client.call("deleteWebhook", {"drop_pending_updates": False})
    except TelegramError as error:
        logger.warning("deleteWebhook failed: %s", type(error).__name__)
    logger.info("telegram poller started as @%s", client.username())
    backoff = 1.0
    while running:
        try:
            raw = store.get(OFFSET_KEY)
            offset = int(raw) if raw else None
            updates = client.updates(offset)
            backoff = 1.0
            for update in updates:
                try:
                    handle_update(update, client=client)
                except Exception as error:  # noqa: BLE001 — one bad update never stops the loop
                    logger.warning("update=%s error_type=%s", update.get("update_id"), type(error).__name__)
                store.set(OFFSET_KEY, int(update["update_id"]) + 1)
        except Exception as error:  # noqa: BLE001
            logger.warning("poll error_type=%s; retry in %.0fs", type(error).__name__, backoff)
            time.sleep(backoff)
            backoff = min(backoff * 2, 30)


if __name__ == "__main__":
    main()
