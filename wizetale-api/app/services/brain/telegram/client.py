"""Minimal Telegram Bot API client.

The token is part of every URL, so URLs are never logged and never end up in exception text:
errors are raised outside `except` blocks so no `requests` exception (whose message contains
the URL) is chained as `__cause__` or `__context__`.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Callable, Optional

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)
API = "https://api.telegram.org"
MAX_DOWNLOAD = 20 * 1024 * 1024  # Bot API getFile limit
USERNAME_RETRY_SECONDS = 60


class TelegramError(RuntimeError):
    def __init__(self, message: str, *, status: Optional[int] = None, description: str = ""):
        super().__init__(message)
        self.status = status
        self.description = description


class TooLarge(TelegramError):
    pass


class TelegramClient:
    def __init__(self, token: Optional[str] = None, session: Optional[requests.Session] = None,
                 sleep: Callable[[float], None] = time.sleep):
        self._token = token
        self.session = session or requests.Session()
        self.sleep = sleep
        self._username: Optional[str] = None
        self._username_retry_at = 0.0

    @property
    def token(self) -> Optional[str]:
        # Read settings lazily so the shared client follows configuration loaded after import.
        return self._token or settings.TELEGRAM_BOT_TOKEN

    @property
    def configured(self) -> bool:
        return bool(self.token)

    def call(self, method: str, payload: Optional[dict[str, Any]] = None, timeout: float = 15, retries: int = 3) -> Any:
        token = self.token
        if not token:
            raise TelegramError("Telegram bot is not configured")
        failure, status, description = "no attempt", None, ""
        for attempt in range(max(1, retries)):
            last = attempt >= retries - 1
            try:
                response = self.session.post(f"{API}/bot{token}/{method}", json=payload or {}, timeout=timeout)
            except requests.RequestException as error:
                failure, status, description = type(error).__name__, None, ""
                if last:
                    break
                self.sleep(1 + attempt)
                continue
            try:
                data = response.json()
            except ValueError:
                data = None
            if isinstance(data, dict) and data.get("ok"):
                return data.get("result")
            status = response.status_code
            description = str((data or {}).get("description", ""))[:120] if isinstance(data, dict) else ""
            failure = f"HTTP {status} {description}".strip()
            parameters = (data or {}).get("parameters") if isinstance(data, dict) else None
            retry_after = (parameters or {}).get("retry_after") if isinstance(parameters, dict) else None
            if last or not (status == 429 or status >= 500 or data is None):
                break
            self.sleep(min(float(retry_after), 10.0) if retry_after else float(1 + attempt))
        raise TelegramError(f"{method} failed: {failure}", status=status, description=description)

    def username(self) -> Optional[str]:
        if settings.TELEGRAM_BOT_USERNAME:
            return settings.TELEGRAM_BOT_USERNAME.lstrip("@")
        if self._username is None and self.token and time.monotonic() >= self._username_retry_at:
            try:  # one quick try: this runs inside web requests (status, overview)
                self._username = (self.call("getMe", timeout=5, retries=1) or {}).get("username")
            except TelegramError:
                self._username_retry_at = time.monotonic() + USERNAME_RETRY_SECONDS
                return None
        return self._username

    def send(self, chat_id: int, text: str, reply_to: Optional[int] = None) -> None:
        payload: dict[str, Any] = {"chat_id": chat_id, "text": text[:4000], "link_preview_options": {"is_disabled": True}}
        if reply_to:
            payload["reply_parameters"] = {"message_id": reply_to, "allow_sending_without_reply": True}
        self.call("sendMessage", payload)

    def typing(self, chat_id: int) -> None:
        try:
            self.call("sendChatAction", {"chat_id": chat_id, "action": "typing"}, timeout=5, retries=1)
        except TelegramError:
            pass

    def download(self, file_id: str, size_hint: Optional[int] = None) -> bytes:
        if size_hint and size_hint > MAX_DOWNLOAD:
            raise TooLarge("File larger than 20 MB")
        try:
            info = self.call("getFile", {"file_id": file_id})
        except TelegramError as error:
            too_big = "too big" in error.description.lower()
            if not too_big:
                raise
        else:
            too_big = False
        if too_big:  # Bot API refuses getFile above 20 MB
            raise TooLarge("File larger than 20 MB")
        path = (info or {}).get("file_path")
        if not path:
            raise TelegramError("getFile returned no file path")
        if ((info or {}).get("file_size") or 0) > MAX_DOWNLOAD:
            raise TooLarge("File larger than 20 MB")
        failure = "no attempt"
        for attempt in range(2):
            try:
                response = self.session.get(f"{API}/file/bot{self.token}/{path}", timeout=60, stream=True)
            except requests.RequestException as error:
                failure = type(error).__name__
            else:
                try:
                    if response.status_code == 200:
                        data = bytearray()
                        for piece in response.iter_content(65536):
                            data.extend(piece)
                            if len(data) > MAX_DOWNLOAD:
                                raise TooLarge("File larger than 20 MB")
                        return bytes(data)
                    failure = f"HTTP {response.status_code}"
                    if response.status_code < 500:
                        break
                except requests.RequestException as error:
                    failure = type(error).__name__
                finally:
                    response.close()
            if attempt == 0:
                self.sleep(1)
        raise TelegramError(f"download failed: {failure}")

    def updates(self, offset: Optional[int], timeout: int = 25) -> list[dict]:
        payload: dict[str, Any] = {"timeout": timeout, "allowed_updates": ["message"]}
        if offset is not None:
            payload["offset"] = offset
        return self.call("getUpdates", payload, timeout=timeout + 10) or []


telegram_client = TelegramClient()
