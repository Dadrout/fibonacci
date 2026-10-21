"""Auto-filing: decide Course → Topic → Concepts for an extracted item."""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

from app.core.config import settings
from app.domain.brain.pipeline import Classification, Extraction, Placement
from app.services.brain.ai.client import BrainAI
from app.services.brain.store import BrainStore

logger = logging.getLogger(__name__)
PASSAGE_BUDGET = 9000
ANCHOR_LABEL = {"page": "page {page}", "slide": "slide {slide}", "paragraph": "paragraph {paragraph}", "section": "{heading}"}


def catalog(graph: dict) -> list[dict[str, Any]]:
    """Compact view of the user's courses for the prompt (ids let the model reuse them)."""
    concepts_by_course: dict[str, list[str]] = {}
    for concept in graph["concepts"]:
        concepts_by_course.setdefault(concept["course_id"], []).append(concept["name"])
    result = []
    for course in graph["courses"]:
        topics = [
            {"id": t["id"], "title": t["title"], **({"sequence": t["sequence"], "kind": t["sequence_kind"]} if t.get("sequence") is not None else {})}
            for t in graph["topics"] if t["course_id"] == course["id"]
        ]
        result.append({"id": course["id"], "title": course["title"], "code": course.get("code"), "topics": topics,
                       "concepts": concepts_by_course.get(course["id"], [])[:40]})
    return result


def corrections(rows: list[dict]) -> list[dict[str, Any]]:
    return [{"item": r["item_title"], "summary": r.get("item_summary", "")[:200],
             "was": f"{r.get('from_course_title') or '—'} → {r.get('from_topic_title') or '—'}",
             "corrected_to": f"{r['to_course_title']} → {r.get('to_topic_title') or '—'}"} for r in rows]


def passages_text(extraction: Extraction) -> str:
    """Numbered passages with their anchors, trimmed to a budget that keeps latency low."""
    lines, used = [], 0
    for ordinal, chunk in enumerate(extraction.chunks):
        anchor = chunk.anchor
        if anchor.kind == "timestamp":
            label = f"{int(anchor.start_sec or 0) // 60}:{int(anchor.start_sec or 0) % 60:02d}"
        else:
            label = ANCHOR_LABEL[anchor.kind].format(**anchor.model_dump())
        line = f"[{ordinal}] ({label}) {chunk.text}"
        if used + len(line) > PASSAGE_BUDGET:
            line = line[: max(0, PASSAGE_BUDGET - used)]
        lines.append(line)
        used += len(line)
        if used >= PASSAGE_BUDGET:
            lines.append(f"[… {len(extraction.chunks) - ordinal - 1} more passages]")
            break
    return "\n".join(lines)


def _sanitize(placement: Placement, graph: dict) -> Placement:
    courses = {c["id"]: c for c in graph["courses"]}
    topics = {t["id"]: t for t in graph["topics"]}
    if placement.course_id and placement.course_id not in courses:
        placement.course_id = None
    if placement.course_id:
        placement.course_title = courses[placement.course_id]["title"]
    if placement.topic_id and (placement.topic_id not in topics or topics[placement.topic_id]["course_id"] != placement.course_id):
        placement.topic_id = None
    if placement.topic_id:
        placement.topic_title = topics[placement.topic_id]["title"]
    if placement.sequence is not None and placement.sequence_kind is None:
        placement.sequence_kind = "week"
    if placement.sequence is None:
        placement.sequence_kind = None
    return placement


def classify(store: BrainStore, uid: str, item: dict, extraction: Extraction, graph: dict, ai: BrainAI) -> Classification:
    result = ai.generate(
        operation="brain_classify", prompt="classify", schema=Classification, model=settings.BRAIN_TEXT_MODEL,
        max_output_tokens=3000, temperature=0.1,
        variables={
            "catalog": json.dumps(catalog(graph), ensure_ascii=False),
            "corrections": json.dumps(corrections(store.refile_events(uid, 8)), ensure_ascii=False),
            "kind": item["kind"], "name": extraction.title or item["title"], "passages": passages_text(extraction),
        },
    )
    result.placement = _sanitize(result.placement, graph)
    result.alternatives = [_sanitize(a, graph) for a in result.alternatives
                           if a.course_title.lower() != result.placement.course_title.lower()
                           or a.topic_title.lower() != result.placement.topic_title.lower()][:2]
    count = len(extraction.chunks)
    for concept in result.concepts:
        concept.chunk_ordinals = sorted({o for o in concept.chunk_ordinals if 0 <= o < count})[:20]
    return result


def alternatives_json(classification: Classification) -> list[dict[str, Any]]:
    return [{"course_id": a.course_id, "course_title": a.course_title, "topic_id": a.topic_id,
             "topic_title": a.topic_title, "confidence": round(a.confidence, 2)} for a in classification.alternatives]


def placement_payload(placement: Placement) -> tuple[dict, Optional[dict]]:
    course = {"id": placement.course_id, "title": placement.course_title, "code": placement.course_code}
    topic = {"id": placement.topic_id, "title": placement.topic_title, "sequence": placement.sequence,
             "sequence_kind": placement.sequence_kind}
    return course, topic
