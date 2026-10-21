"""Server-side fal queue adapter for FLUX.2 Turbo image generation."""

import logging
import time
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit

import requests
from PIL import Image

from app.core.config import settings
from app.core.usage_context import generation_id

logger = logging.getLogger(__name__)


class FalImageService:
    def __init__(self):
        self.api_key = settings.FAL_KEY
        self.model_name = settings.FAL_IMAGE_MODEL
        self.timeout_seconds = settings.FAL_IMAGE_TIMEOUT_SECONDS
        self.poll_interval_seconds = 1.0

    def healthcheck(self) -> dict[str, str | bool]:
        return {
            "provider": "fal",
            "configured": bool(self.api_key),
            "enabled": bool(self.api_key),
            "model": self.model_name,
            "transport": "queue-rest",
        }

    @staticmethod
    def _queue_url(value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme != "https" or parsed.netloc != "queue.fal.run":
            raise ValueError("Invalid fal queue URL")
        return value

    def generate_image(
        self,
        *,
        prompt: str,
        output_path: str,
        aspect_ratio: str = "16:9",
        style: str | None = None,
    ) -> str | None:
        if not self.api_key:
            return None
        started_at = time.monotonic()
        deadline = started_at + self.timeout_seconds
        headers = {"Authorization": f"Key {self.api_key}"}
        cancel_url = None
        completed = False

        def remaining():
            seconds = deadline - time.monotonic()
            if seconds <= 0:
                raise TimeoutError("fal generation deadline exceeded")
            return min(30, seconds)

        try:
            image_size = {
                "16:9": "landscape_16_9",
                "9:16": "portrait_16_9",
                "4:3": "landscape_4_3",
                "3:4": "portrait_4_3",
                "1:1": "square_hd",
            }[aspect_ratio]
            response = requests.post(
                f"https://queue.fal.run/{self.model_name}",
                headers={**headers, "X-Fal-Request-Timeout": str(self.timeout_seconds)},
                json={
                    "prompt": f"{prompt}\nStyle guidance: {style}" if style else prompt,
                    "image_size": image_size,
                    "num_images": 1,
                    "output_format": "png",
                    "enable_safety_checker": True,
                },
                timeout=remaining(),
                allow_redirects=False,
            )
            response.raise_for_status()
            queued = response.json()
            cancel_url = self._queue_url(queued["cancel_url"])
            status_url = self._queue_url(queued["status_url"])
            result_url = self._queue_url(queued["response_url"])
            while True:
                response = requests.get(
                    status_url,
                    headers=headers,
                    timeout=remaining(),
                    allow_redirects=False,
                )
                response.raise_for_status()
                status = response.json()
                if status.get("status") == "COMPLETED":
                    completed = True
                    if status.get("error"):
                        raise ValueError("fal generation failed")
                    break
                if status.get("status") not in {"IN_QUEUE", "IN_PROGRESS"}:
                    raise ValueError("Unexpected fal queue status")
                time.sleep(min(self.poll_interval_seconds, remaining()))
            response = requests.get(
                result_url, headers=headers, timeout=remaining(), allow_redirects=False
            )
            response.raise_for_status()
            result = response.json()
            if (
                result.get("error")
                or any(result.get("has_nsfw_concepts", []))
                or not result.get("images")
            ):
                raise ValueError("No usable image returned")
            media_url = result["images"][0]["url"]
            parsed = urlsplit(media_url)
            hostname = parsed.hostname or ""
            if parsed.scheme != "https" or not (
                hostname == "fal.media"
                or hostname.endswith(".fal.media")
                or hostname == "storage.googleapis.com"
            ):
                raise ValueError("Invalid fal media URL")
            # Never forward the fal API credential to the media CDN.
            response = requests.get(media_url, timeout=remaining())
            response.raise_for_status()
            path = Path(output_path).with_suffix(".png")
            with Image.open(BytesIO(response.content)) as image:
                image.load()
                image.convert("RGB").save(path, "PNG")
            logger.info(
                "ai_usage generation_id=%s provider=fal model=%s operation=image_generation image_count=1 latency_ms=%.0f",
                generation_id.get(),
                self.model_name,
                (time.monotonic() - started_at) * 1000,
            )
            return str(path)
        except Exception as error:
            # Exception messages and response bodies can contain credentials or prompts.
            logger.warning(
                "ai_failure generation_id=%s provider=fal model=%s operation=image_generation error_type=%s",
                generation_id.get(),
                self.model_name,
                type(error).__name__,
            )
            if cancel_url and not completed:
                try:
                    requests.put(
                        cancel_url, headers=headers, timeout=5, allow_redirects=False
                    )
                except requests.RequestException:
                    pass
            return None


fal_image_service = FalImageService()
