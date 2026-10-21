"""Cloudflare Workers AI adapter for FLUX image generation."""

import base64
import binascii
import logging
import re
import time
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image

from app.core.config import settings
from app.core.usage_context import generation_id

logger = logging.getLogger(__name__)


class CloudflareImageService:
    def __init__(self):
        self.account_id = settings.CLOUDFLARE_ACCOUNT_ID
        self.api_token = settings.CLOUDFLARE_API_TOKEN
        self.model_name = settings.CLOUDFLARE_IMAGE_MODEL
        self.timeout_seconds = settings.CLOUDFLARE_IMAGE_TIMEOUT_SECONDS

    def healthcheck(self) -> dict[str, str | bool]:
        configured = bool(self.account_id and self.api_token)
        return {
            "provider": "cloudflare",
            "configured": configured,
            "enabled": configured,
            "model": self.model_name,
            "transport": "rest",
        }

    def generate_image(
        self,
        *,
        prompt: str,
        output_path: str,
        aspect_ratio: str = "16:9",
        style: str | None = None,
    ) -> str | None:
        if not self.account_id or not self.api_token:
            return None
        if not re.fullmatch(r"[0-9a-fA-F]{32}", self.account_id):
            logger.warning("cloudflare image generation skipped: invalid account id")
            return None
        if not re.fullmatch(r"@cf/[a-zA-Z0-9._/-]+", self.model_name):
            logger.warning("cloudflare image generation skipped: invalid model id")
            return None

        dimensions = {
            "16:9": (1280, 720),
            "9:16": (720, 1280),
            "4:3": (1024, 768),
            "3:4": (768, 1024),
            "1:1": (1024, 1024),
        }
        size = dimensions.get(aspect_ratio)
        if size is None:
            return None

        started_at = time.perf_counter()
        url = (
            "https://api.cloudflare.com/client/v4/accounts/"
            f"{self.account_id}/ai/run/{self.model_name}"
        )
        final_prompt = f"{prompt}\nStyle guidance: {style}" if style else prompt
        try:
            headers = {
                "Authorization": f"Bearer {self.api_token}",
                "Accept": "application/json",
            }
            if self.model_name == "@cf/black-forest-labs/flux-1-schnell":
                # FLUX.1 Schnell accepts JSON and has a fixed low-cost 4-step default.
                response = requests.post(
                    url,
                    headers=headers,
                    json={"prompt": final_prompt, "steps": 4},
                    timeout=self.timeout_seconds,
                )
            else:
                # FLUX.2 Dev expects multipart form data, including prompt-only requests.
                response = requests.post(
                    url,
                    headers=headers,
                    files=[
                        ("prompt", (None, final_prompt)),
                        ("width", (None, str(size[0]))),
                        ("height", (None, str(size[1]))),
                        ("steps", (None, "25")),
                    ],
                    timeout=self.timeout_seconds,
                )
            response.raise_for_status()
            payload = response.json()
            if not payload.get("success", True) or payload.get("errors"):
                raise ValueError("Cloudflare image request failed")
            result = payload.get("result", payload)
            encoded_image = result.get("image") if isinstance(result, dict) else None
            if not encoded_image:
                raise ValueError("Cloudflare returned no image")
            if encoded_image.startswith("data:"):
                encoded_image = encoded_image.split(",", 1)[-1]
            image_bytes = base64.b64decode(encoded_image, validate=True)

            path = Path(output_path).with_suffix(".png")
            with Image.open(BytesIO(image_bytes)) as image:
                image.load()
                image.convert("RGB").save(path, "PNG")
            logger.info(
                "ai_usage generation_id=%s provider=cloudflare model=%s operation=image_generation image_count=1 latency_ms=%.0f",
                generation_id.get(),
                self.model_name,
                (time.perf_counter() - started_at) * 1000,
            )
            return str(path)
        except (
            requests.RequestException,
            ValueError,
            KeyError,
            binascii.Error,
            OSError,
        ) as error:
            # Keep response bodies and exception messages out of logs; they may include prompts.
            logger.warning(
                "ai_failure generation_id=%s provider=cloudflare model=%s operation=image_generation error_type=%s",
                generation_id.get(),
                self.model_name,
                type(error).__name__,
            )
            return None


cloudflare_image_service = CloudflareImageService()
