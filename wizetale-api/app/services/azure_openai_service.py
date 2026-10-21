import logging
import time
from typing import Any

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)

AI_QUOTA_USER_MESSAGE = (
    "Content generation quota was exceeded. Please retry in a few minutes."
)
AI_GENERIC_USER_MESSAGE = (
    "Content generation is temporarily unavailable. Please try again shortly."
)


class AITextGenerationError(Exception):
    def __init__(self, user_message: str, debug_message: str | None = None):
        super().__init__(user_message)
        self.user_message = user_message
        self.debug_message = debug_message or user_message


def _extract_retry_seconds(error_text: str) -> float | None:
    lowered = error_text.lower()

    if "retry-after" in lowered:
        fragments = lowered.replace("=", ":").split(":")
        for fragment in reversed(fragments):
            try:
                return float(fragment.strip().split()[0])
            except (ValueError, IndexError):
                continue

    return None


def _is_quota_error(error_text: str) -> bool:
    lowered = error_text.lower()
    markers = [
        "quota",
        "rate limit",
        "429",
        "too many requests",
        "token rate limit",
        "request rate limit",
    ]
    return any(marker in lowered for marker in markers)


def _user_facing_error_message(error_text: str) -> str:
    if _is_quota_error(error_text):
        return AI_QUOTA_USER_MESSAGE
    return AI_GENERIC_USER_MESSAGE


def _normalize_content(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text = str(item.get("text", "")).strip()
                if text:
                    parts.append(text)
        return "\n".join(parts).strip()

    return ""


class AzureOpenAIService:
    def __init__(self):
        self.endpoint = settings.AZURE_OPENAI_ENDPOINT
        self.api_key = settings.AZURE_OPENAI_API_KEY
        self.api_version = settings.AZURE_OPENAI_API_VERSION or "2024-11-20"
        self.deployment = settings.AZURE_OPENAI_DEPLOYMENT_NAME

    def _chat_completions_url(self) -> str:
        base_url = (self.endpoint or "").rstrip("/")
        deployment = (self.deployment or "").strip()
        return (
            f"{base_url}/openai/deployments/{deployment}/chat/completions"
            f"?api-version={self.api_version}"
        )

    def generate_text(
        self,
        *,
        prompt: str,
        operation_name: str,
        temperature: float,
        max_output_tokens: int,
        system_prompt: str | None = None,
    ) -> str:
        if not self.endpoint or not self.api_key or not self.deployment:
            raise AITextGenerationError(
                AI_GENERIC_USER_MESSAGE,
                "Azure OpenAI configuration is incomplete.",
            )

        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_output_tokens,
        }
        headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json",
        }

        collected_errors: list[str] = []
        for attempt in range(2):
            try:
                response = requests.post(
                    self._chat_completions_url(),
                    headers=headers,
                    json=payload,
                    timeout=120,
                )
                response.raise_for_status()
                response_data = response.json()
                choices = response_data.get("choices", [])
                if not choices:
                    raise ValueError("Azure OpenAI returned no choices.")

                message = choices[0].get("message", {})
                text = _normalize_content(message.get("content"))
                if not text:
                    raise ValueError("Azure OpenAI returned an empty response.")

                logger.info(
                    "Azure OpenAI %s succeeded on attempt %s.",
                    operation_name,
                    attempt + 1,
                )
                return text
            except Exception as error:
                error_text = str(error)
                collected_errors.append(
                    f"attempt={attempt + 1}, error={error_text}"
                )
                logger.warning(
                    "Azure OpenAI %s failed on attempt %s: %s",
                    operation_name,
                    attempt + 1,
                    error_text,
                )
                retry_seconds = _extract_retry_seconds(error_text)
                if attempt == 0 and retry_seconds is not None and retry_seconds <= 10:
                    time.sleep(min(max(retry_seconds, 0.5), 8.0))
                    continue
                break

        debug_message = (
            f"Azure OpenAI {operation_name} failed. Details: {' | '.join(collected_errors)}"
        )
        raise AITextGenerationError(
            _user_facing_error_message(" ".join(collected_errors)),
            debug_message,
        )


azure_openai_service = AzureOpenAIService()
