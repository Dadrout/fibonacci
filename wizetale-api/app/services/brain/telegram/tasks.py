"""Plain-text messages to the bot: a one-line summary and a checklist of the tasks they contain.

Only for text the student sends (notes, homework, a teacher's message). The text is still filed
into the Brain as a source; this adds an immediate, useful reply. Never invents tasks or dates:
the prompt and schema allow only what the message states. Falls back to None (the caller sends
the ordinary "got it") when the AI is unavailable.
"""
from __future__ import annotations

import logging
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.brain.ai.client import BrainAI, brain_ai

logger = logging.getLogger(__name__)
MIN_LENGTH = 12
MAX_TASKS = 12
LABELS = {
    "en": {"tasks": "To do:", "checklist": "Checklist:", "due": "due", "saved": "Saved to your Brain."},
    "ru": {"tasks": "Задачи:", "checklist": "Чек-лист:", "due": "срок", "saved": "Сохранено в ваш Brain."},
    "kk": {"tasks": "Тапсырмалар:", "checklist": "Тексеру тізімі:", "due": "мерзімі", "saved": "Brain-ге сақталды."},
}


class TaskItem(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    due: str = Field(default="", max_length=60)


class TextAnalysis(BaseModel):
    summary: str = Field(default="", max_length=400)
    kind: Literal["tasks", "checklist", "note"] = "note"
    tasks: list[TaskItem] = Field(default_factory=list)


def format_reply(analysis: TextAnalysis, language: str) -> str:
    labels = LABELS.get(language, LABELS["en"])
    lines = [analysis.summary.strip()] if analysis.summary.strip() else []
    tasks = [task for task in analysis.tasks if task.title.strip()][:MAX_TASKS]
    if tasks:
        lines.append("")
        lines.append(labels["checklist" if analysis.kind == "checklist" else "tasks"])
        for task in tasks:
            due = f" — {labels['due']}: {task.due.strip()}" if task.due.strip() else ""
            lines.append(f"☐ {task.title.strip()}{due}")
    lines.append("")
    lines.append(labels["saved"])
    return "\n".join(lines).strip()


def analyze(text: str, language: str, *, ai: BrainAI = brain_ai) -> Optional[str]:
    """Reply text for a plain-text message, or None when it is too short or the AI is unavailable."""
    text = text.strip()
    if len(text) < MIN_LENGTH:
        return None
    try:
        analysis = ai.generate(operation="brain_text_tasks", prompt="text_tasks", schema=TextAnalysis,
                               model=settings.BRAIN_TEXT_MODEL, max_output_tokens=1500, temperature=0.2, timeout=20,
                               variables={"text": text[:6000]}, cache_key=["v1", text[:6000]])
    except Exception as error:  # noqa: BLE001 — the capture already succeeded; fall back to "got it"
        logger.warning("brain_text_tasks failed error_type=%s", type(error).__name__)
        return None
    return format_reply(analysis, language)
