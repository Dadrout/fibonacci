"""Prepare compact source-backed facts for story generation."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.services.knowledge_repository import knowledge_repository


KnowledgeStatus = Literal["grounded", "partial", "none"]


class KnowledgeContext(BaseModel):
    status: KnowledgeStatus = "none"
    prompt_context: str = ""
    sources: list[dict[str, Any]] = Field(default_factory=list)


class KnowledgeService:
    def __init__(self, repository=knowledge_repository):
        self.repository = repository

    def retrieve(self, topic: str, subject: str, grade_band: str) -> KnowledgeContext:
        entries = self.repository.search(topic, subject, grade_band)
        if not entries:
            return KnowledgeContext()

        status: KnowledgeStatus = (
            "grounded" if any(entry.get("match_type") == "exact" for entry in entries) else "partial"
        )
        context_sections = []
        sources: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        for entry in entries[:3]:
            facts = [str(fact).strip() for fact in entry.get("facts", []) if str(fact).strip()]
            if facts:
                context_sections.append(
                    f"{entry.get('canonical_topic', 'Related topic')}:\n"
                    + "\n".join(f"- {fact}" for fact in facts[:5])
                )
            for source in entry.get("sources", []):
                url = source.get("url")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    sources.append(source)

        prompt_context = "\n\n".join(context_sections)
        return KnowledgeContext(status=status, prompt_context=prompt_context, sources=sources)


knowledge_service = KnowledgeService()
