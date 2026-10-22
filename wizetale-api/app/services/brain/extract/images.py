"""Image helpers shared by extractors (decode, orient, resize, thumbnail)."""
from __future__ import annotations

import io

from celery.exceptions import SoftTimeLimitExceeded
from PIL import Image, ImageOps

from app.domain.brain.pipeline import ExtractionError

Image.MAX_IMAGE_PIXELS = 60_000_000  # refuse decompression bombs


def load(data: bytes) -> Image.Image:
    try:
        image = Image.open(io.BytesIO(data))
        # Pillow only warns between MAX_IMAGE_PIXELS and twice that; refuse before decoding.
        if image.width * image.height > Image.MAX_IMAGE_PIXELS:
            raise ExtractionError("too_large", "Image has too many pixels")
        image.load()
        # EXIF orientation and mode conversion can fail on malformed files too (struct/Key/Type errors).
        image = ImageOps.exif_transpose(image)
        return image.convert("RGB")
    except (ExtractionError, SoftTimeLimitExceeded):
        raise
    except Image.DecompressionBombError as error:
        raise ExtractionError("too_large", "Image has too many pixels") from error
    except Exception as error:  # noqa: BLE001 — any decoder failure means the file is unreadable
        raise ExtractionError("unreadable", "Image could not be decoded") from error


def jpeg(image: Image.Image, max_side: int, quality: int = 85) -> bytes:
    copy = image.copy()
    copy.thumbnail((max_side, max_side))
    out = io.BytesIO()
    copy.save(out, format="JPEG", quality=quality, optimize=True)
    return out.getvalue()
