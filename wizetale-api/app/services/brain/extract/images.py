"""Image helpers shared by extractors (decode, orient, resize, thumbnail)."""
from __future__ import annotations

import io

from PIL import Image, ImageOps, UnidentifiedImageError

from app.domain.brain.pipeline import ExtractionError

Image.MAX_IMAGE_PIXELS = 60_000_000  # refuse decompression bombs


def load(data: bytes) -> Image.Image:
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise ExtractionError("unreadable", "Image could not be decoded") from error
    image = ImageOps.exif_transpose(image)
    return image.convert("RGB")


def jpeg(image: Image.Image, max_side: int, quality: int = 85) -> bytes:
    copy = image.copy()
    copy.thumbnail((max_side, max_side))
    out = io.BytesIO()
    copy.save(out, format="JPEG", quality=quality, optimize=True)
    return out.getvalue()
