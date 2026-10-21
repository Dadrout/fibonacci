import logging
import base64
from pathlib import Path
import time
from typing import Any

import requests

from app.core.config import settings
from app.core.usage_context import generation_id

logger = logging.getLogger(__name__)


class GeminiImageService:
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.model_name = settings.GEMINI_IMAGE_MODEL
        self.enabled = settings.ENABLE_GEMINI_IMAGE
        self.timeout_seconds = 120
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"

    def _endpoint(self) -> str:
        return f"{self.base_url}/{self.model_name}:generateContent"

    def _build_payload(
        self,
        *,
        prompt: str,
        aspect_ratio: str,
        style: str | None = None,
    ) -> dict[str, Any]:
        final_prompt = prompt
        if style:
            final_prompt = f"{prompt}\nStyle guidance: {style}"

        return {
            "contents": [{"parts": [{"text": final_prompt}]}],
            "generationConfig": {
                "responseModalities": ["TEXT", "IMAGE"],
            },
        }

    def _extract_inline_image(self, response_data: dict[str, Any]) -> tuple[bytes, str] | None:
        candidates = response_data.get("candidates", [])
        for candidate in candidates:
            content = candidate.get("content", {})
            for part in content.get("parts", []):
                inline_data = part.get("inlineData") or part.get("inline_data")
                if not inline_data:
                    continue

                encoded = inline_data.get("data")
                mime_type = inline_data.get("mimeType") or inline_data.get("mime_type") or "image/png"
                if not encoded:
                    continue
                return base64.b64decode(encoded), mime_type
        return None

    def generate_image(
        self,
        *,
        prompt: str,
        output_path: str,
        aspect_ratio: str = "16:9",
        style: str | None = None,
    ) -> str | None:
        if not self.enabled or not self.api_key:
            return None

        started_at = time.perf_counter()
        try:
            response = requests.post(
                self._endpoint(),
                headers={"Content-Type": "application/json", "x-goog-api-key": self.api_key},
                json=self._build_payload(prompt=prompt, aspect_ratio=aspect_ratio, style=style),
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            extracted = self._extract_inline_image(response.json())
            if extracted:
                image_bytes, mime_type = extracted
                path = Path(output_path)
                if mime_type == "image/png" and path.suffix.lower() not in {".png"}:
                    path = path.with_suffix(".png")
                path.write_bytes(image_bytes)
                logger.info(
                    "ai_usage generation_id=%s provider=gemini model=%s operation=image_generation image_count=1 latency_ms=%.0f estimated_cost_usd=%.4f",
                    generation_id.get(),
                    self.model_name,
                    (time.perf_counter() - started_at) * 1000,
                    settings.GEMINI_IMAGE_USD_PER_IMAGE,
                )
                return str(path)
            logger.warning(
                "ai_failure generation_id=%s provider=gemini model=%s operation=image_generation error_type=no_image_returned latency_ms=%.0f",
                generation_id.get(),
                self.model_name,
                (time.perf_counter() - started_at) * 1000,
            )
        except Exception as error:
            logger.warning(
                "ai_failure generation_id=%s provider=gemini operation=image_generation model=%s error_type=%s latency_ms=%.0f",
                generation_id.get(),
                self.model_name,
                type(error).__name__,
                (time.perf_counter() - started_at) * 1000,
            )
        return None

    def healthcheck(self) -> dict[str, str | bool]:
        return {
            "provider": "gemini",
            "configured": bool(self.api_key),
            "enabled": self.enabled,
            "model": self.model_name,
            "transport": "rest",
        }


gemini_image_service = GeminiImageService()
