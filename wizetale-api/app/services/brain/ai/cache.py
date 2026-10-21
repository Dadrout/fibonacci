"""Cache for Brain AI outputs.

Two layers, both keyed by a hash of the exact operation inputs:
- fast: Redis (30 days) — avoids paying twice for the same input;
- recorded: JSON files under ./recorded/ — real model outputs saved while rehearsing
  (BRAIN_AI_RECORD=true), committed with the repo so DEMO_MODE works without a network.
Failures in either layer are logged and ignored; the cache never blocks a request.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any, Optional, Sequence

import redis

from app.core.config import settings

logger = logging.getLogger(__name__)
RECORDED_DIR = Path(__file__).parent / "recorded"
FAST_TTL_SECONDS = 30 * 86400


class RecordedCache:
    def __init__(self, directory: Path = RECORDED_DIR):
        self.directory = directory
        self._redis: Optional[redis.Redis] = None

    @staticmethod
    def key(operation: str, *parts: Any) -> str:
        blob = json.dumps([operation, *parts], ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def _client(self) -> Optional[redis.Redis]:
        if self._redis is None:
            try:
                self._redis = redis.Redis.from_url(settings.REDIS_URL, socket_timeout=1, socket_connect_timeout=1)
            except Exception:  # noqa: BLE001
                return None
        return self._redis

    def _path(self, operation: str, key: str) -> Path:
        safe = "".join(ch for ch in operation if ch.isalnum() or ch in "_-") or "op"
        return self.directory / safe / f"{key}.json"

    def get_fast(self, operation: str, key: str) -> Optional[Any]:
        client = self._client()
        if client is None:
            return None
        try:
            raw = client.get(f"brain:ai:{operation}:{key}")
            return json.loads(raw) if raw else None
        except Exception as error:  # noqa: BLE001
            logger.debug("brain_ai_cache redis_get_failed error_type=%s", type(error).__name__)
            return None

    def get_recorded(self, operation: str, key: str) -> Optional[Any]:
        path = self._path(operation, key)
        try:
            return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
        except (OSError, ValueError):
            return None

    def get(self, operation: str, key: str) -> Optional[Any]:
        """Recorded file first (stable for demos), then Redis."""
        value = self.get_recorded(operation, key)
        return value if value is not None else self.get_fast(operation, key)

    def put(self, operation: str, key: str, value: Any) -> None:
        client = self._client()
        if client is not None:
            try:
                client.set(f"brain:ai:{operation}:{key}", json.dumps(value, ensure_ascii=False), ex=FAST_TTL_SECONDS)
            except Exception as error:  # noqa: BLE001
                logger.debug("brain_ai_cache redis_put_failed error_type=%s", type(error).__name__)
        if settings.BRAIN_AI_RECORD:
            path = self._path(operation, key)
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                tmp = path.with_suffix(".tmp")
                tmp.write_text(json.dumps(value, ensure_ascii=False, indent=1), encoding="utf-8")
                os.replace(tmp, path)
            except OSError as error:
                logger.warning("brain_ai_cache record_failed error_type=%s", type(error).__name__)


recorded_cache = RecordedCache()
