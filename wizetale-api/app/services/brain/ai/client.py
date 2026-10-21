"""Gemini access for the Brain: structured JSON, multimodal parts, embeddings.

Every call: prompt from its own file, JSON validated against a Pydantic schema, a hard
timeout, one retry (then the fallback model), and the recorded cache as the last resort.
In DEMO_MODE the recorded cache is consulted first, so rehearsed inputs work offline.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import math
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Sequence, TypeVar

import requests
from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.services.brain.ai.cache import RecordedCache, recorded_cache

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

PROMPT_DIR = Path(__file__).parent / "prompts"
API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
EMBED_DIMENSIONS = 768
USER_MARKER = "=== USER ==="


class AIUnavailable(Exception):
    """The provider failed and no recorded output exists for this exact input."""


@dataclass(frozen=True)
class Part:
    """A non-text input: inline bytes (image/PDF/audio) or a file URI (YouTube link)."""

    mime_type: Optional[str] = None
    data: Optional[bytes] = None
    file_uri: Optional[str] = None

    def digest(self) -> str:
        if self.data is not None:
            return "sha256:" + hashlib.sha256(self.data).hexdigest()
        return "uri:" + (self.file_uri or "")

    def to_api(self) -> dict[str, Any]:
        if self.data is not None:
            return {"inline_data": {"mime_type": self.mime_type or "application/octet-stream",
                                    "data": base64.b64encode(self.data).decode()}}
        payload: dict[str, Any] = {"file_uri": self.file_uri}
        if self.mime_type:
            payload["mime_type"] = self.mime_type
        return {"file_data": payload}


def load_prompt(name: str) -> tuple[str, str]:
    """Return (system, user_template) from prompts/<name>.md."""
    text = (PROMPT_DIR / f"{name}.md").read_text(encoding="utf-8")
    if USER_MARKER in text:
        system, user = text.split(USER_MARKER, 1)
        return system.strip(), user.strip()
    return "", text.strip()


def render(template: str, variables: dict[str, Any]) -> str:
    def value(match: re.Match) -> str:
        key = match.group(1)
        if key not in variables:
            raise KeyError(f"Prompt variable {key!r} is missing")
        item = variables[key]
        return item if isinstance(item, str) else json.dumps(item, ensure_ascii=False)

    return re.sub(r"\{\{\s*([a-z_][a-z0-9_]*)\s*\}\}", value, template)


def _json_candidate(text: str) -> str:
    stripped = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", stripped, re.DOTALL)
    if fenced:
        return fenced.group(1).strip()
    start, end = stripped.find("{"), stripped.rfind("}")
    return stripped[start : end + 1] if 0 <= start < end else stripped


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [round(v / norm, 7) for v in vector]


class BrainAI:
    def __init__(self, cache: RecordedCache = recorded_cache, session: Optional[requests.Session] = None):
        self.cache = cache
        self.session = session or requests.Session()

    # ------------------------------------------------------------------ public

    def generate(
        self,
        *,
        operation: str,
        prompt: str,
        variables: Optional[dict[str, Any]] = None,
        schema: type[T],
        parts: Sequence[Part] = (),
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_output_tokens: int = 4096,
        timeout: Optional[float] = None,
        cache_key: Optional[Sequence[Any]] = None,
    ) -> T:
        """Run prompt file `prompt` with `variables` and return a validated `schema` instance.

        `cache_key`: stable inputs that define the answer (e.g. the material, not volatile ids or
        dates), so a recorded output replays across re-seeds and days. Defaults to the full prompt.
        """
        system, template = load_prompt(prompt)
        system = render(system, variables or {})
        user = render(template, variables or {})
        material = list(cache_key) if cache_key is not None else [system, user]
        # The prompt file's fingerprint is always part of the key: editing a prompt retires old recordings.
        fingerprint = hashlib.sha256(f"{system}\n{template}".encode()).hexdigest()[:16]
        key = self.cache.key(operation, fingerprint, *material, [p.digest() for p in parts], schema.__name__)
        demo = settings.DEMO_MODE

        if demo:
            cached = self.cache.get(operation, key)
            if cached is not None:
                return schema.model_validate(cached)

        models: list[str] = []
        for candidate in (model, settings.BRAIN_TEXT_MODEL, settings.BRAIN_FALLBACK_MODEL):
            if candidate and candidate not in models:
                models.append(candidate)
        last_error: Optional[Exception] = None
        if not demo or settings.GEMINI_API_KEY:
            cached = None if demo else self.cache.get_fast(operation, key)
            if cached is not None:
                return schema.model_validate(cached)
            for attempt, model_name in enumerate(models):
                try:
                    result = self._generate_once(operation, model_name, system, user, schema, parts,
                                                 temperature, max_output_tokens, timeout)
                    self.cache.put(operation, key, result.model_dump(mode="json"))
                    return result
                except Exception as error:  # noqa: BLE001 — every failure falls through to the next option
                    last_error = error
                    status = getattr(getattr(error, "response", None), "status_code", None)
                    detail = str(error)[:200] if isinstance(error, ValueError) else ""
                    logger.warning("brain_ai_failure operation=%s model=%s attempt=%d error_type=%s status=%s %s",
                                   operation, model_name, attempt + 1, type(error).__name__, status, detail)
        cached = self.cache.get(operation, key)
        if cached is not None:
            logger.info("brain_ai_recorded_fallback operation=%s", operation)
            return schema.model_validate(cached)
        raise AIUnavailable(f"{operation} failed: {type(last_error).__name__ if last_error else 'no provider'}")

    def embed(self, texts: Sequence[str], *, task_type: str = "SEMANTIC_SIMILARITY") -> list[Optional[list[float]]]:
        """768-dim unit vectors, or None for texts that could not be embedded (never a fake vector)."""
        results: list[Optional[list[float]]] = [None] * len(texts)
        missing: list[int] = []
        keys = [self.cache.key("embed", task_type, text[:8000], [], str(EMBED_DIMENSIONS)) for text in texts]
        for index, key in enumerate(keys):
            cached = self.cache.get("embed", key) if settings.DEMO_MODE else self.cache.get_fast("embed", key)
            if cached is not None:
                results[index] = cached["vector"]
            else:
                missing.append(index)
        if missing and settings.GEMINI_API_KEY:
            for start in range(0, len(missing), 64):
                batch = missing[start : start + 64]
                try:
                    vectors = self._embed_batch([texts[i] for i in batch], task_type)
                except Exception as error:  # noqa: BLE001
                    logger.warning("brain_embed_failure count=%d error_type=%s", len(batch), type(error).__name__)
                    vectors = [None] * len(batch)
                for index, vector in zip(batch, vectors):
                    if vector is not None:
                        results[index] = vector
                        self.cache.put("embed", keys[index], {"vector": vector})
        for index in range(len(texts)):
            if results[index] is None:
                cached = self.cache.get("embed", keys[index])
                if cached is not None:
                    results[index] = cached["vector"]
        return results

    # ------------------------------------------------------------------ provider

    def _post(self, url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        if not settings.GEMINI_API_KEY:
            raise AIUnavailable("GEMINI_API_KEY is not configured")
        response = self.session.post(
            url, json=payload, timeout=(5, timeout),
            headers={"Content-Type": "application/json", "x-goog-api-key": settings.GEMINI_API_KEY},
        )
        if response.status_code >= 400:
            # Never log the response body: it can echo private material.
            raise requests.HTTPError(f"Gemini HTTP {response.status_code}", response=response)
        return response.json()

    def _generate_once(self, operation, model_name, system, user, schema, parts, temperature, max_tokens, timeout):
        # Native structured output constrains the reply to the schema; models that reject a
        # schema (HTTP 400) get it embedded in the prompt instead.
        json_schema = schema.model_json_schema()
        payload: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [*(p.to_api() for p in parts), {"text": user}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
                "responseMimeType": "application/json",
                "responseJsonSchema": json_schema,
            },
        }
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        started = time.perf_counter()
        deadline = timeout or settings.BRAIN_AI_TIMEOUT_SECONDS
        url = f"{API_BASE}/{model_name}:generateContent"
        try:
            data = self._post(url, payload, deadline)
        except requests.HTTPError as error:
            if getattr(error.response, "status_code", None) != 400:
                raise
            del payload["generationConfig"]["responseJsonSchema"]
            schema_text = json.dumps(json_schema, ensure_ascii=False, separators=(",", ":"))
            payload["contents"][0]["parts"][-1] = {"text": f"{user}\n\nReturn only JSON matching this JSON Schema:\n{schema_text}"}
            data = self._post(url, payload, deadline)
        raw = "".join(
            part.get("text", "")
            for candidate in data.get("candidates", [])[:1]
            for part in candidate.get("content", {}).get("parts", [])
            if not part.get("thought")
        )
        usage = data.get("usageMetadata", {})
        logger.info(
            "brain_ai operation=%s model=%s input_tokens=%s output_tokens=%s latency_ms=%d",
            operation, model_name, usage.get("promptTokenCount"), usage.get("candidatesTokenCount"),
            (time.perf_counter() - started) * 1000,
        )
        try:
            return schema.model_validate_json(_json_candidate(raw))
        except ValidationError as error:
            where = "; ".join(f"{'.'.join(str(p) for p in e['loc'])}:{e['type']}" for e in error.errors()[:3])
            raise ValueError(f"{operation} returned JSON that failed {schema.__name__} validation at {where} "
                             f"(finish={self._finish(data)}, thoughts={usage.get('thoughtsTokenCount')}, "
                             f"output={usage.get('candidatesTokenCount')}, chars={len(raw)})") from error
        except json.JSONDecodeError as error:
            raise ValueError(f"{operation} returned invalid JSON (finish={self._finish(data)})") from error

    @staticmethod
    def _finish(data: dict[str, Any]) -> str:
        candidates = data.get("candidates") or [{}]
        return str(candidates[0].get("finishReason", "unknown"))

    def _embed_batch(self, texts: list[str], task_type: str) -> list[Optional[list[float]]]:
        model = settings.BRAIN_EMBED_MODEL
        payload = {"requests": [
            {"model": f"models/{model}", "content": {"parts": [{"text": text[:8000]}]},
             "taskType": task_type, "outputDimensionality": EMBED_DIMENSIONS}
            for text in texts
        ]}
        started = time.perf_counter()
        data = self._post(f"{API_BASE}/{model}:batchEmbedContents", payload, min(settings.BRAIN_AI_TIMEOUT_SECONDS, 20))
        vectors = [e.get("values") for e in data.get("embeddings", [])]
        logger.info("brain_embed count=%d latency_ms=%d", len(texts), (time.perf_counter() - started) * 1000)
        return [_normalize(v) if v and len(v) == EMBED_DIMENSIONS else None for v in vectors] + [None] * (len(texts) - len(vectors))


brain_ai = BrainAI()
