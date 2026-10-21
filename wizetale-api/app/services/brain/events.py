"""Per-user live events over Redis Streams.

Workers append events with `publish()` (sync). The SSE endpoint reads them with
`stream()` (async), resuming from the client's Last-Event-ID, so a reconnecting
browser never misses a step of the capture choreography. Payloads follow the
BrainEvent union in wizetale-app/lib/brain-types.ts; `id` and `at` are added here.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Optional

import redis
import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)
STREAM_MAXLEN = 500
STREAM_TTL_SECONDS = 7 * 86400
HEARTBEAT_SECONDS = 15
_ID = re.compile(r"^\d{1,20}-\d{1,10}$")

_sync_client: Optional[redis.Redis] = None


def _key(uid: str) -> str:
    return f"brain:events:{uid}"


def _client() -> redis.Redis:
    global _sync_client
    if _sync_client is None:
        _sync_client = redis.Redis.from_url(settings.REDIS_URL, socket_timeout=3, socket_connect_timeout=3)
    return _sync_client


def publish(uid: str, event_type: str, **payload: Any) -> Optional[str]:
    """Append one event; failures are logged, never raised (events are best-effort)."""
    body = json.dumps({"type": event_type, **payload}, ensure_ascii=False, default=str)
    try:
        client = _client()
        event_id = client.xadd(_key(uid), {"data": body}, maxlen=STREAM_MAXLEN, approximate=True)
        client.expire(_key(uid), STREAM_TTL_SECONDS)
        return event_id.decode() if isinstance(event_id, bytes) else str(event_id)
    except Exception as error:  # noqa: BLE001
        logger.warning("brain_event_publish_failed type=%s error_type=%s", event_type, type(error).__name__)
        return None


def frame(event_id: str, data: dict[str, Any]) -> str:
    """Encode one SSE frame with `id` and `at` folded into the JSON payload."""
    millis = int(event_id.split("-", 1)[0]) if _ID.match(event_id) else 0
    at = datetime.fromtimestamp(millis / 1000, tz=timezone.utc).isoformat() if millis else datetime.now(timezone.utc).isoformat()
    payload = json.dumps({**data, "id": event_id, "at": at}, ensure_ascii=False, default=str)
    return f"id: {event_id}\nevent: message\ndata: {payload}\n\n"


async def stream(uid: str, last_event_id: Optional[str], client: Optional[aioredis.Redis] = None) -> AsyncIterator[str]:
    """Yield SSE frames forever: missed events after `last_event_id`, then live ones, plus heartbeats."""
    own_client = client is None
    client = client or aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    cursor = last_event_id if last_event_id and _ID.match(last_event_id) else "$"
    try:
        yield "retry: 2000\n\n"
        while True:
            response = await client.xread({_key(uid): cursor}, block=HEARTBEAT_SECONDS * 1000, count=50)
            if not response:
                yield f": heartbeat {int(datetime.now(timezone.utc).timestamp())}\n\n"
                continue
            for _stream, entries in response:
                for event_id, fields in entries:
                    cursor = event_id
                    try:
                        data = json.loads(fields.get("data", "{}"))
                    except ValueError:
                        continue
                    yield frame(event_id, data)
    finally:
        if own_client:
            await client.aclose()
