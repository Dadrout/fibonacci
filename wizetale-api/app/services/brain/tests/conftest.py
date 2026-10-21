"""Brain tests run offline: no real network, Redis, Supabase, or Gemini."""
import socket

import pytest

from app.core.config import settings


@pytest.fixture(autouse=True)
def brain_test_settings(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    monkeypatch.setattr(settings, "BRAIN_AI_RECORD", False)
    monkeypatch.setattr(settings, "BRAIN_BLOB_STORE", "local")
    monkeypatch.setattr(settings, "BRAIN_MEDIA_DIR", str(tmp_path / "media"))
    monkeypatch.setattr(settings, "BRAIN_MEDIA_SECRET", "test-media-secret")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", None)
    yield


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Fail loudly if a test tries to open a real connection."""
    def guard(*args, **kwargs):
        raise RuntimeError("Brain tests must not use the network; mock the client instead.")
    monkeypatch.setattr(socket, "create_connection", guard)
    monkeypatch.setattr(socket.socket, "connect", lambda self, *a, **k: guard())
    yield
