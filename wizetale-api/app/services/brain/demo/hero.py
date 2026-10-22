"""Demo tools: send the three hero-demo inputs through the normal capture pipeline.

The presenter can press one button instead of forwarding the items from Telegram. Nothing
is faked: the real files go through the same capture → read → file → link steps as any
upload or link, and in DEMO_MODE the recorded AI outputs replay first.
Inputs live in `demo/hero/` (mounted read-only into the API at BRAIN_DEMO_HERO_DIR).
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional
from uuid import uuid4

from app.core.config import settings

HERO_YOUTUBE_URL = "https://youtu.be/2xcUup_-K6c"
HERO_PHOTO = ("slide7-heteroskedasticity.jpg", "image/jpeg")
HERO_PDF = ("ECON301_Week6_Heteroskedasticity.pdf", "application/pdf")


class HeroInputsMissing(RuntimeError):
    """The demo files are not available on this server."""


def _read(directory: Path, name: str) -> bytes:
    path = directory / name
    if not path.is_file():
        raise HeroInputsMissing(name)
    return path.read_bytes()


def send(capture, uid: str, email: Optional[str], directory: Optional[Path] = None) -> list[dict]:
    """Capture the slide photo, the lecture video and the PDF, in the order the demo tells them."""
    folder = Path(directory or settings.BRAIN_DEMO_HERO_DIR)
    photo, pdf = _read(folder, HERO_PHOTO[0]), _read(folder, HERO_PDF[0])  # check both before creating anything
    return [
        capture.from_upload(uid, email, photo, HERO_PHOTO[0], HERO_PHOTO[1], channel="web_drop", request_id=str(uuid4())),
        capture.from_link(uid, email, HERO_YOUTUBE_URL, channel="web_paste", request_id=str(uuid4())),
        capture.from_upload(uid, email, pdf, HERO_PDF[0], HERO_PDF[1], channel="web_drop", request_id=str(uuid4())),
    ]
