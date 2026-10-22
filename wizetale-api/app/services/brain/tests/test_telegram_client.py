"""Telegram Bot API client, offline: payload shapes, file URLs, retry/backoff, and no token in errors."""
import pytest
import requests

from app.services.brain.telegram.client import MAX_DOWNLOAD, TelegramClient, TelegramError, TooLarge
from app.services.brain.tests.test_telegram_bot import FILES, TOKEN, FakeResponse, FakeSession, ok


@pytest.fixture
def setup():
    session, sleeps = FakeSession(), []
    return TelegramClient(token=TOKEN, session=session, sleep=sleeps.append), session, sleeps


def assert_no_token(error):
    assert TOKEN not in str(error) and "SECRET" not in repr(error)
    assert error.__cause__ is None and error.__context__ is None  # no chained requests error (its text has the URL)


def test_send_uses_reply_parameters_and_link_preview_options(setup):
    client, session, _ = setup
    client.send(1, "x" * 5000, reply_to=7)
    client.send(1, "plain")
    first, second = session.calls("sendMessage")
    assert first == {"chat_id": 1, "text": "x" * 4000, "link_preview_options": {"is_disabled": True},
                     "reply_parameters": {"message_id": 7, "allow_sending_without_reply": True}}
    assert "reply_parameters" not in second and "reply_to_message_id" not in first and "disable_web_page_preview" not in first


def test_get_updates_payload_and_http_timeout_outlasts_long_poll(setup):
    client, session, _ = setup
    session.queue("getUpdates", ok([{"update_id": 3}]))
    assert client.updates(3, timeout=25) == [{"update_id": 3}]
    method, payload, timeout = session.posts[0]
    assert payload == {"timeout": 25, "allowed_updates": ["message"], "offset": 3} and timeout > 25


def test_download_uses_the_file_endpoint(setup):
    client, session, _ = setup
    session.files["abc"] = b"%PDF-1.4 hello"
    assert client.download("abc", 14) == b"%PDF-1.4 hello"
    assert session.calls("getFile") == [{"file_id": "abc"}] and session.gets == [f"{FILES}documents/abc"]


def test_download_refuses_files_over_twenty_megabytes(setup):
    client, session, _ = setup
    with pytest.raises(TooLarge):
        client.download("x", MAX_DOWNLOAD + 1)
    session.queue("getFile", ok({"file_id": "y", "file_path": "documents/y", "file_size": MAX_DOWNLOAD + 1}))
    with pytest.raises(TooLarge):
        client.download("y")
    session.files["z"] = b"0" * (MAX_DOWNLOAD + 1)  # size unknown up front: the stream is capped
    session.queue("getFile", ok({"file_id": "z", "file_path": "documents/z"}))
    with pytest.raises(TooLarge):
        client.download("z")
    assert session.gets == [f"{FILES}documents/z"]


def test_rate_limit_and_server_errors_are_retried_with_backoff(setup):
    client, session, sleeps = setup
    session.queue("sendMessage", FakeResponse(429, {"ok": False, "error_code": 429, "description": "Too Many Requests",
                                                    "parameters": {"retry_after": 3}}),
                  FakeResponse(502, None), ok({"message_id": 1}))
    client.send(1, "hi")
    assert len(session.calls("sendMessage")) == 3 and sleeps == [3.0, 2.0]


def test_client_errors_are_not_retried(setup):
    client, session, sleeps = setup
    session.queue("sendMessage", FakeResponse(400, {"ok": False, "error_code": 400, "description": "Bad Request: chat not found"}))
    with pytest.raises(TelegramError) as raised:
        client.send(1, "hi")
    assert raised.value.status == 400 and "chat not found" in str(raised.value) and sleeps == []
    assert_no_token(raised.value)


def test_network_errors_never_leak_the_token(setup):
    client, session, sleeps = setup
    leak = f"HTTPSConnectionPool(host='api.telegram.org'): Max retries exceeded with url: /bot{TOKEN}/getUpdates"
    session.queue("getUpdates", *[requests.ConnectionError(leak)] * 3)
    with pytest.raises(TelegramError) as raised:
        client.updates(None)
    assert "ConnectionError" in str(raised.value) and sleeps == [1, 2]
    assert_no_token(raised.value)


def test_file_download_errors_never_leak_the_token(setup):
    client, session, _ = setup
    session.files["gone"] = b""

    def missing(url, timeout=None, stream=False):
        session.gets.append(url)
        return FakeResponse(404, content=b"")
    session.get = missing
    with pytest.raises(TelegramError) as raised:
        client.download("gone")
    assert "HTTP 404" in str(raised.value) and len(session.gets) == 1
    assert_no_token(raised.value)

    def offline(url, timeout=None, stream=False):
        raise requests.ConnectionError(f"Max retries exceeded with url: /file/bot{TOKEN}/documents/gone")
    session.get = offline
    with pytest.raises(TelegramError) as raised:
        client.download("gone")
    assert_no_token(raised.value)


def test_unconfigured_client_never_calls_the_api():
    session = FakeSession()
    client = TelegramClient(session=session)
    assert client.configured is False and client.username() is None
    with pytest.raises(TelegramError):
        client.send(1, "hi")
    assert session.posts == []


def test_username_lookup_is_quick_and_failure_is_cached(setup, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "TELEGRAM_BOT_USERNAME", None)
    client, session, sleeps = setup
    session.queue("getMe", requests.Timeout("slow"))
    assert client.username() is None and client.username() is None
    assert len(session.calls("getMe")) == 1 and sleeps == []
    monkeypatch.setattr(settings, "TELEGRAM_BOT_USERNAME", "@FibonacciBrainBot")
    assert client.username() == "FibonacciBrainBot"
