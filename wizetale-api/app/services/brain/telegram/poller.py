"""Long-polling loop for local and demo use: `python -m app.services.brain.telegram.poller`.

`run_once` handles one getUpdates batch and is what tests drive; `poll` adds backoff; `main`
wires settings, Redis (offset persistence), and signals.
"""
from __future__ import annotations

import logging
import signal
import time
from typing import Any, Callable, Optional

import redis

from app.core.config import settings
from app.services.brain.telegram.bot import handle_update
from app.services.brain.telegram.client import TelegramClient, TelegramError

logger = logging.getLogger("brain.telegram.poller")
OFFSET_KEY = "brain:telegram:offset"
MAX_BACKOFF = 30.0
running = True


def _stop(*_args) -> None:
    global running
    running = False


def load_offset(store: Any) -> Optional[int]:
    try:
        raw = store.get(OFFSET_KEY)
        return int(raw) if raw else None
    except Exception as error:  # noqa: BLE001 — Redis down: start from Telegram's own pending queue
        logger.warning("offset load failed error_type=%s", type(error).__name__)
        return None


def save_offset(store: Any, offset: int) -> None:
    try:
        store.set(OFFSET_KEY, offset)
    except Exception as error:  # noqa: BLE001 — the in-memory offset still moves on
        logger.warning("offset save failed error_type=%s", type(error).__name__)


def run_once(client: TelegramClient, store: Any, offset: Optional[int] = None, *,
             handler: Optional[Callable[[dict], None]] = None, timeout: int = 25) -> Optional[int]:
    """Fetch one batch, handle each update, persist the next offset after each one. Returns the next offset.

    `store` is the offset store (Redis-like `get`/`set`). Telegram raises on network errors.
    """
    if offset is None:
        offset = load_offset(store)
    handle = handler or (lambda update: handle_update(update, client=client))
    for update in client.updates(offset, timeout=timeout) or []:
        update_id = update.get("update_id") if isinstance(update, dict) else None
        if not isinstance(update_id, int):
            continue
        try:
            handle(update)
        except Exception as error:  # noqa: BLE001 — one bad update never stops the loop
            logger.warning("update=%s error_type=%s", update_id, type(error).__name__)
        offset = max(offset or 0, update_id + 1)
        save_offset(store, offset)
    return offset


def poll(client: TelegramClient, store: Any, *, keep_running: Callable[[], bool] = lambda: running,
         sleep: Callable[[float], None] = time.sleep, handler: Optional[Callable[[dict], None]] = None) -> None:
    offset = load_offset(store)
    backoff = 1.0
    while keep_running():
        try:
            offset = run_once(client, store, offset, handler=handler)
            backoff = 1.0
        except Exception as error:  # noqa: BLE001 — never log the URL: it contains the token
            status = getattr(error, "status", None)
            if status == 409:
                logger.warning("poll conflict: another copy of this bot is polling with the same token "
                               "(stop it, or revoke the token in BotFather); retry in %.0fs", backoff)
            else:
                logger.warning("poll error_type=%s status=%s description=%s; retry in %.0fs", type(error).__name__,
                               status, getattr(error, "description", "")[:120], backoff)
            sleep(backoff)
            backoff = min(backoff * 2, MAX_BACKOFF)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    logging.getLogger("urllib3").setLevel(logging.WARNING)  # its debug lines contain the token URL
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    if settings.TELEGRAM_MODE != "polling" or not settings.TELEGRAM_BOT_TOKEN:
        logger.info("telegram poller disabled (mode=%s, token=%s)", settings.TELEGRAM_MODE, bool(settings.TELEGRAM_BOT_TOKEN))
        while running:  # stay up so the container is healthy; nothing to do
            time.sleep(5)
        return
    client = TelegramClient()
    store = redis.Redis.from_url(settings.REDIS_URL, socket_timeout=40)
    try:
        client.call("deleteWebhook", {"drop_pending_updates": False})
    except TelegramError as error:
        logger.warning("deleteWebhook failed: %s", type(error).__name__)
    logger.info("telegram poller started as @%s", client.username())
    poll(client, store)


if __name__ == "__main__":
    main()
