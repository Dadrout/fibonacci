"""Presentation: a slide deck built from one course's own material.

Uses the same passage selection and citation rules as the exam plan (plans.py): every bullet
must cite passages we sent, bullets without valid citations are dropped, and a slide with no
cited bullets is dropped. Decks are generated on request and not stored; the AI cache makes
a repeat request for the same material instant (and offline in DEMO_MODE).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.brain.ai.client import BrainAI, brain_ai
from app.services.brain.plans import LANGUAGE_NAMES, DraftBullet, NotEnoughMaterial, _refs, clean, gather, material_text
from app.services.brain.store import BrainStore, brain_store
from app.services.brain.views import Catalog

MIN_SLIDES, MAX_SLIDES = 5, 12


class DraftSlide(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    bullets: list[DraftBullet] = Field(default_factory=list)
    notes: str = Field(default="", max_length=2000)
    topic_id: Optional[str] = None


class DeckDraft(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    slides: list[DraftSlide] = Field(default_factory=list)


def slide_count(topic_count: int) -> str:
    """Overview + one per topic + takeaways, kept between 5 and 12."""
    return str(max(MIN_SLIDES, min(MAX_SLIDES, topic_count + 2)))


def assemble(uid: str, draft: DeckDraft, ids: dict[str, dict], items: dict[str, dict], topics: set[str]) -> list[dict]:
    slides = []
    for slide in draft.slides[:MAX_SLIDES]:
        bullets = [{"text": clean(b.text), "sources": refs} for b in slide.bullets[:5] if (refs := _refs(uid, b.passage_ids, ids, items))]
        if bullets:
            slides.append({"id": f"s{len(slides) + 1}", "title": clean(slide.title)[:200], "bullets": bullets,
                           "notes": clean(slide.notes)[:1200], "topic_id": slide.topic_id if slide.topic_id in topics else None})
    return slides


def build(uid: str, course_id: str, language: str, *, store: BrainStore = brain_store, ai: BrainAI = brain_ai) -> dict:
    """Generate the deck. Raises KeyError for an unknown course, NotEnoughMaterial, or AIUnavailable."""
    catalog = Catalog(store, uid)
    course = catalog.courses[course_id]
    passages, items = gather(store, uid, catalog, course_id)
    text, ids = material_text(passages, items, catalog.courses, course_id)
    topics = [{"id": t["id"], "title": t["title"], "sequence": t.get("sequence")} for t in catalog.graph["topics"]
              if t["course_id"] == course_id]
    count = slide_count(len(topics))
    draft = ai.generate(operation="brain_deck", prompt="deck", schema=DeckDraft, model=settings.BRAIN_PLAN_MODEL,
                        max_output_tokens=8000, temperature=0.3, timeout=75, variables={
                            "language_name": LANGUAGE_NAMES[language], "slide_count": count, "course_title": course["title"],
                            "topics": json.dumps(topics, ensure_ascii=False), "passages": text},
                        cache_key=["v1", course["title"], language, count, [t["title"] for t in topics], text])
    slides = assemble(uid, draft, ids, items, {t["id"] for t in topics})
    if not slides:
        raise NotEnoughMaterial()
    return {"course_id": course_id, "language": language, "title": clean(draft.title)[:200], "slides": slides,
            "generated_at": datetime.now(timezone.utc).isoformat()}
