"""Minimal Telegram Bot API client. The token is part of every URL, so URLs are never logged."""
from __future__ import annotations

import logging
import time
from typing import Any, Optional

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)
API = "https://api.telegram.org"
MAX_DOWNLOAD = 20 * 1024 * 1024


class TelegramError(RuntimeError):
    pass


class TooLarge(TelegramError):
    pass


class TelegramClient:
    def __init__(self, token: Optional[str] = None, session: Optional[requests.Session] = None):
        self.token = token or settings.TELEGRAM_BOT_TOKEN
        self.session = session or requests.Session()
        self._username: Optional[str] = None

    @property
    def configured(self) -> bool:
        return bool(self.token)

    def call(self, method: str, payload: Optional[dict[str, Any]] = None, timeout: float = 15) -> Any:
        if not self.token:
            raise TelegramError("Telegram bot is not configured")
        for attempt in range(3):
            try:
                response = self.session.post(f"{API}/bot{self.token}/{method}", json=payload or {}, timeout=timeout)
                data = response.json()
            except (requests.RequestException, ValueError) as error:
                if attempt == 2:
                    raise TelegramError(f"{method} failed: {type(error).__name__}") from error
                time.sleep(1 + attempt)
                continue
            if data.get("ok"):
                return data.get("result")
            retry_after = (data.get("parameters") or {}).get("retry_after")
            if response.status_code == 429 and retry_after and attempt < 2:
                time.sleep(min(int(retry_after), 10))
                continue
            raise TelegramError(f"{method} failed: HTTP {response.status_code} {str(data.get('description', ''))[:80]}")
        raise TelegramError(f"{method} failed")

    def username(self) -> Optional[str]:
        if settings.TELEGRAM_BOT_USERNAME:
            return settings.TELEGRAM_BOT_USERNAME.lstrip("@")
        if self._username is None and self.token:
            try:
                self._username = (self.call("getMe") or {}).get("username")
            except TelegramError:
                return None
        return self._username

    def send(self, chat_id: int, text: str, reply_to: Optional[int] = None) -> None:
        payload: dict[str, Any] = {"chat_id": chat_id, "text": text[:4000], "link_preview_options": {"is_disabled": True}}
        if reply_to:
            payload["reply_parameters"] = {"message_id": reply_to, "allow_sending_without_reply": True}
        self.call("sendMessage", payload)

    def typing(self, chat_id: int) -> None:
        try:
            self.call("sendChatAction", {"chat_id": chat_id, "action": "typing"}, timeout=5)
        except TelegramError:
            pass

    def download(self, file_id: str, size_hint: Optional[int] = None) -> bytes:
        if size_hint and size_hint > MAX_DOWNLOAD:
            raise TooLarge("File larger than 20 MB")
        info = self.call("getFile", {"file_id": file_id})
        path = (info or {}).get("file_path")
        if not path:
            raise TelegramError("No file path")
        response = self.session.get(f"{API}/file/bot{self.token}/{path}", timeout=60, stream=True)
        response.raise_for_status()
        data = bytearray()
        for piece in response.iter_content(65536):
            data.extend(piece)
            if len(data) > MAX_DOWNLOAD:
                raise TooLarge("File larger than 20 MB")
        return bytes(data)

    def updates(self, offset: Optional[int], timeout: int = 25) -> list[dict]:
        payload: dict[str, Any] = {"timeout": timeout, "allowed_updates": ["message"]}
        if offset is not None:
            payload["offset"] = offset
        return self.call("getUpdates", payload, timeout=timeout + 10) or []


telegram_client = TelegramClient()
