import json
import logging
import re
import time
from typing import Any

import requests
from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.core.usage_context import generation_id
from app.services.ai.base import SchemaT

logger = logging.getLogger(__name__)

GEMINI_QUOTA_USER_MESSAGE = (
    "Content generation quota was exceeded. Please retry in a few minutes."
)
GEMINI_GENERIC_USER_MESSAGE = (
    "Content generation is temporarily unavailable. Please try again shortly."
)


class GeminiGenerationError(Exception):
    def __init__(self, user_message: str, debug_message: str | None = None):
        super().__init__(user_message)
        self.user_message = user_message
        self.debug_message = debug_message or user_message


def _is_quota_error(error_text: str) -> bool:
    lowered = error_text.lower()
    markers = [
        "quota",
        "429",
        "resource_exhausted",
        "rate limit",
        "too many requests",
        "retry later",
    ]
    return any(marker in lowered for marker in markers)


def _user_facing_error_message(error_text: str) -> str:
    if _is_quota_error(error_text):
        return GEMINI_QUOTA_USER_MESSAGE
    return GEMINI_GENERIC_USER_MESSAGE


def _extract_json_candidate(text: str) -> str:
    stripped = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", stripped, re.DOTALL)
    if fenced:
        return fenced.group(1).strip()

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        return stripped[start : end + 1]

    return stripped


class GeminiTextService:
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.primary_model = settings.GEMINI_TEXT_MODEL
        self.fallback_model = settings.GEMINI_FALLBACK_TEXT_MODEL
        self.timeout_seconds = 45
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"

    def _ensure_client(self) -> None:
        if not self.api_key:
            raise GeminiGenerationError(
                GEMINI_GENERIC_USER_MESSAGE,
                "GEMINI_API_KEY is not configured.",
            )
        if settings.ENVIRONMENT.lower() == "production" and settings.GEMINI_BILLING_TIER.lower() != "paid":
            raise GeminiGenerationError(
                GEMINI_GENERIC_USER_MESSAGE,
                "Production learner generation requires the Gemini paid data tier.",
            )

    def _endpoint(self, model_name: str) -> str:
        return f"{self.base_url}/{model_name}:generateContent"

    def _build_payload(
        self,
        *,
        prompt: str,
        temperature: float,
        max_output_tokens: int,
        system_prompt: str | None = None,
        response_mime_type: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_output_tokens,
            },
        }
        if response_mime_type:
            payload["generationConfig"]["responseMimeType"] = response_mime_type
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}
        return payload

    def _extract_text(self, response_data: dict[str, Any]) -> str:
        candidates = response_data.get("candidates", [])
        for candidate in candidates:
            content = candidate.get("content", {})
            for part in content.get("parts", []):
                text = part.get("text")
                if text:
                    return str(text).strip()
        raise ValueError(f"Gemini returned no text parts: {response_data}")

    def _call_model(
        self,
        *,
        model_name: str,
        prompt: str,
        temperature: float,
        max_output_tokens: int,
        response_mime_type: str | None = None,
        system_prompt: str | None = None,
        operation_name: str = "text_generation",
    ) -> str:
        payload = self._build_payload(
            prompt=prompt,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            system_prompt=system_prompt,
            response_mime_type=response_mime_type,
        )
        started_at = time.perf_counter()
        for attempt in range(3):
            response = requests.post(
                self._endpoint(model_name),
                headers={"Content-Type": "application/json", "x-goog-api-key": self.api_key},
                json=payload,
                timeout=self.timeout_seconds,
            )
            if response.status_code not in {502, 503, 504} or attempt == 2:
                break
            logger.warning(
                "Gemini temporarily unavailable: model=%s status=%s retry=%s",
                model_name, response.status_code, attempt + 1,
            )
            response.close()
            time.sleep(attempt + 1)
        response.raise_for_status()
        response_data = response.json()
        usage = response_data.get("usageMetadata", {})
        input_tokens = int(usage.get("promptTokenCount", 0) or 0)
        output_tokens = int(usage.get("candidatesTokenCount", 0) or 0)
        if model_name == settings.GEMINI_FALLBACK_TEXT_MODEL:
            input_rate = settings.GEMINI_FALLBACK_TEXT_INPUT_USD_PER_MILLION_TOKENS
            output_rate = settings.GEMINI_FALLBACK_TEXT_OUTPUT_USD_PER_MILLION_TOKENS
        else:
            input_rate = settings.GEMINI_TEXT_INPUT_USD_PER_MILLION_TOKENS
            output_rate = settings.GEMINI_TEXT_OUTPUT_USD_PER_MILLION_TOKENS
        estimated_cost = (
            input_tokens * input_rate
            + output_tokens * output_rate
        ) / 1_000_000
        logger.info(
            "ai_usage generation_id=%s provider=gemini model=%s operation=%s input_tokens=%d output_tokens=%d latency_ms=%.0f estimated_cost_usd=%.6f",
            generation_id.get(),
            model_name,
            operation_name,
            input_tokens,
            output_tokens,
            (time.perf_counter() - started_at) * 1000,
            estimated_cost,
        )
        return self._extract_text(response_data)

    def _generate_with_fallback(
        self,
        *,
        prompt: str,
        operation_name: str,
        temperature: float,
        max_output_tokens: int,
        system_prompt: str | None = None,
        response_mime_type: str | None = None,
    ) -> str:
        self._ensure_client()
        collected_errors: list[str] = []
        last_error: Exception | None = None

        for index, model_name in enumerate([self.primary_model, self.fallback_model]):
            try:
                started_at = time.perf_counter()
                text = self._call_model(
                    model_name=model_name,
                    prompt=prompt,
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                    response_mime_type=response_mime_type,
                    system_prompt=system_prompt,
                    operation_name=operation_name,
                )
                logger.info(
                    "Gemini %s succeeded with model=%s in %.0fms.",
                    operation_name,
                    model_name,
                    (time.perf_counter() - started_at) * 1000,
                )
                return text
            except Exception as error:
                last_error = error
                collected_errors.append(
                    f"attempt={index + 1}, model={model_name}, error={error}"
                )
                logger.warning(
                    "ai_failure generation_id=%s provider=gemini operation=%s model=%s error_type=%s",
                    generation_id.get(),
                    operation_name,
                    model_name,
                    type(error).__name__,
                )

        error_text = " | ".join(collected_errors) or str(last_error)
        raise GeminiGenerationError(
            _user_facing_error_message(error_text),
            f"Gemini {operation_name} failed. Details: {error_text}",
        )

    def generate_text(
        self,
        *,
        prompt: str,
        operation_name: str,
        temperature: float = 0.7,
        max_output_tokens: int = 1024,
        system_prompt: str | None = None,
    ) -> str:
        return self._generate_with_fallback(
            prompt=prompt,
            operation_name=operation_name,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            system_prompt=system_prompt,
        )

    def generate_structured(
        self,
        *,
        prompt: str,
        operation_name: str,
        schema: type[SchemaT],
        temperature: float = 0.3,
        max_output_tokens: int = 2048,
        system_prompt: str | None = None,
    ) -> SchemaT:
        structured_prompt = (
            f"{prompt}\n\n"
            "Return valid JSON only.\n"
            f"JSON schema:\n{json.dumps(schema.model_json_schema(), ensure_ascii=False)}"
        )
        raw = self._generate_with_fallback(
            prompt=structured_prompt,
            operation_name=operation_name,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            system_prompt=system_prompt,
            response_mime_type="application/json",
        )

        try:
            return schema.model_validate_json(_extract_json_candidate(raw))
        except (ValidationError, json.JSONDecodeError) as parse_error:
            raise GeminiGenerationError(
                GEMINI_GENERIC_USER_MESSAGE,
                f"{operation_name} schema validation failed: {parse_error}",
            ) from parse_error

    def healthcheck(self) -> dict[str, str | bool]:
        configured = bool(self.api_key)
        return {
            "provider": "gemini",
            "configured": configured,
            "primary_model": self.primary_model,
            "fallback_model": self.fallback_model,
            "transport": "rest",
        }


gemini_text_service = GeminiTextService()
