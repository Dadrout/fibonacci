"""'Exam in N days': plan, notes, flashcards, and quiz grounded in the student's material.

Every generated claim must cite passages (P1, P2, …) that we sent; claims without valid
citations are dropped. Quiz answers and the best "source moment" per question are kept
server-side (brain_plan_secrets), so answering is instant and works offline.
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from app.celery_utils import celery_app
from app.core.config import settings
from app.services.brain import events
from app.services.brain.ai.client import AIUnavailable, BrainAI, brain_ai
from app.services.brain.store import BrainStore, brain_store
from app.services.brain.views import Catalog, gap_alerts, media_url, source_ref, thumbnail_url, youtube_watch_url

logger = logging.getLogger(__name__)
LANGUAGE_NAMES = {"en-US": "English", "ru-RU": "Russian", "kk-KZ": "Kazakh"}
PASSAGE_BUDGET = 26000
PER_ITEM = 4
OPTION_IDS = ("a", "b", "c", "d")


class NotEnoughMaterial(Exception):
    pass


# ---------------------------------------------------------------- model output

class DraftTask(BaseModel):
    kind: Literal["read", "watch", "review", "flashcards", "quiz", "practice"] = "review"
    title: str = Field(min_length=1, max_length=300)
    minutes: int = Field(default=20, ge=5, le=240)
    topic_id: Optional[str] = None
    passage_ids: list[str] = Field(default_factory=list)


class DraftDay(BaseModel):
    day: int = Field(ge=1)
    focus: str = Field(min_length=1, max_length=300)
    tasks: list[DraftTask] = Field(default_factory=list)


class DraftBullet(BaseModel):
    text: str = Field(min_length=1, max_length=600)
    passage_ids: list[str] = Field(default_factory=list)


class DraftNote(BaseModel):
    heading: str = Field(min_length=1, max_length=200)
    topic_id: Optional[str] = None
    bullets: list[DraftBullet] = Field(default_factory=list)


class DraftCard(BaseModel):
    front: str = Field(min_length=1, max_length=400)
    back: str = Field(min_length=1, max_length=600)
    passage_ids: list[str] = Field(default_factory=list)


class DraftQuestion(BaseModel):
    prompt: str = Field(min_length=1, max_length=600)
    options: list[str] = Field(min_length=4, max_length=4)
    correct_index: int = Field(ge=0, le=3)
    explanation: str = Field(min_length=1, max_length=800)
    passage_ids: list[str] = Field(default_factory=list)
    explain_passage: str = ""
    explain_reason: str = Field(default="", max_length=300)
    concepts: list[str] = Field(default_factory=list)


class PlanDraft(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    days: list[DraftDay] = Field(default_factory=list)
    notes: list[DraftNote] = Field(default_factory=list)
    flashcards: list[DraftCard] = Field(default_factory=list)
    quiz: list[DraftQuestion] = Field(default_factory=list)


# ---------------------------------------------------------------- material

def gather(store: BrainStore, uid: str, catalog: Catalog, course_id: str) -> tuple[list[dict], dict[str, dict]]:
    """Choose passages: every filed item contributes, concept-bearing passages first, plus cross-course passages."""
    items = [i for i in store.items(uid, status="filed", course_id=course_id, limit=200)]
    if not items:
        raise NotEnoughMaterial()
    item_by_id = {i["id"]: i for i in items}
    chunks = store.chunks_for_items(uid, list(item_by_id), limit=3000)
    mentions = store.chunk_concepts(uid, chunk_ids=[c["id"] for c in chunks], limit=5000)
    with_concepts = {m["chunk_id"] for m in mentions}
    per_item: dict[str, list[dict]] = defaultdict(list)
    for chunk in chunks:
        per_item[chunk["item_id"]].append(chunk)
    selected: list[dict] = []
    for item in sorted(items, key=lambda i: i["captured_at"]):
        ranked = sorted(per_item[item["id"]], key=lambda c: (c["id"] not in with_concepts, c["ordinal"]))
        selected.extend(sorted(ranked[:PER_ITEM], key=lambda c: c["ordinal"]))
    # Cross-course pull: passages of concepts linked to this course from other courses.
    foreign_ids = set()
    for link in catalog.graph["links"]:
        a, b = catalog.concepts.get(link["source_concept_id"]), catalog.concepts.get(link["target_concept_id"])
        if a and b and link["cross_course"]:
            if a["course_id"] == course_id:
                foreign_ids.add(b["id"])
            elif b["course_id"] == course_id:
                foreign_ids.add(a["id"])
    foreign: list[dict] = []
    if foreign_ids:
        rows = store.chunk_concepts(uid, concept_ids=list(foreign_ids)[:8], limit=40)
        foreign_chunks = store.chunks_by_ids(uid, [r["chunk_id"] for r in rows][:8])
        foreign_items = {i["id"]: i for i in store.items_by_ids(uid, [c["item_id"] for c in foreign_chunks])}
        item_by_id.update(foreign_items)
        foreign = [c for c in foreign_chunks if c["item_id"] in foreign_items][:6]
    passages, used = [], 0
    for chunk in selected + foreign:
        if used + len(chunk["body"]) > PASSAGE_BUDGET:
            continue
        used += len(chunk["body"])
        passages.append(chunk)
    if not passages:
        raise NotEnoughMaterial()
    return passages, item_by_id


def _label(chunk: dict, item: dict) -> str:
    kind = chunk["anchor_kind"]
    if kind == "timestamp":
        start, end = int(chunk["start_sec"]), int(chunk["end_sec"])
        where = f"video {start // 60}:{start % 60:02d}–{end // 60}:{end % 60:02d}"
    elif kind == "page":
        where = f"page {chunk['page']}"
    elif kind == "slide":
        where = f"slide {chunk['slide']}" if chunk.get("slide") else "slide photo"
    elif kind == "paragraph":
        where = f"paragraph {chunk['paragraph']}"
    else:
        where = chunk.get("heading") or "web page"
    return f"{item['title']} — {where}"


def material_text(passages: list[dict], items: dict[str, dict], courses: dict[str, dict], course_id: str) -> tuple[str, dict[str, dict]]:
    lines, ids = [], {}
    for index, chunk in enumerate(passages, start=1):
        pid = f"P{index}"
        ids[pid] = chunk
        item = items[chunk["item_id"]]
        origin = "" if item.get("course_id") == course_id else f" [from: {courses.get(item.get('course_id') or '', {}).get('title', 'another course')}]"
        lines.append(f"{pid} ({_label(chunk, item)}){origin}: {chunk['body']}")
    return "\n".join(lines), ids


# ---------------------------------------------------------------- assembly

def _refs(uid: str, pids: list[str], ids: dict[str, dict], items: dict[str, dict]) -> list[dict]:
    refs, seen = [], set()
    for pid in pids:
        chunk = ids.get(pid.strip().upper())
        if chunk and chunk["id"] not in seen:
            seen.add(chunk["id"])
            refs.append(source_ref(uid, chunk, items[chunk["item_id"]]))
    return refs


def assemble(uid: str, draft: PlanDraft, ids: dict[str, dict], items: dict[str, dict], catalog: Catalog, course_id: str,
             days: int, exam_date: date) -> tuple[dict, dict]:
    topics = {t["id"] for t in catalog.topics.values() if t["course_id"] == course_id}
    names = {k["name"].lower(): k["id"] for k in catalog.concepts.values()}
    plan_days = []
    for index, day in enumerate(draft.days[:days], start=1):
        tasks = []
        for t_index, task in enumerate(day.tasks, start=1):
            sources = _refs(uid, task.passage_ids, ids, items)
            if sources:
                tasks.append({"id": f"d{index}t{t_index}", "kind": task.kind, "title": task.title, "minutes": task.minutes,
                              "topic_id": task.topic_id if task.topic_id in topics else None, "sources": sources})
        plan_days.append({"day": index, "date": (exam_date - timedelta(days=days - index + 1)).isoformat(),
                          "focus": day.focus, "tasks": tasks})
    notes = []
    for n_index, note in enumerate(draft.notes, start=1):
        bullets = [{"text": b.text, "sources": s} for b in note.bullets if (s := _refs(uid, b.passage_ids, ids, items))]
        if bullets:
            notes.append({"id": f"n{n_index}", "heading": note.heading,
                          "topic_id": note.topic_id if note.topic_id in topics else None, "bullets": bullets})
    flashcards = [{"id": f"f{i}", "front": c.front, "back": c.back, "sources": s}
                  for i, c in enumerate(draft.flashcards, start=1) if (s := _refs(uid, c.passage_ids, ids, items))]
    quiz, answer_key = [], {}
    for q in draft.quiz:
        sources = _refs(uid, q.passage_ids, ids, items)
        options = [o.strip() for o in q.options]
        if not sources or len({o.lower() for o in options}) != 4:
            continue
        qid = f"q{len(quiz) + 1}"
        moment_refs = _refs(uid, [q.explain_passage], ids, items) or sources[:1]
        quiz.append({"id": qid, "prompt": q.prompt, "options": [{"id": OPTION_IDS[i], "text": o} for i, o in enumerate(options)],
                     "concept_ids": [names[n.lower()] for n in q.concepts if n.lower() in names], "sources": sources})
        answer_key[qid] = {"correct": OPTION_IDS[q.correct_index], "explanation": {"text": q.explanation, "sources": sources},
                           "moment": {"source": moment_refs[0], "reason": q.explain_reason or q.explanation[:200],
                                      "confidence": 0.85 if q.explain_passage else 0.6}}
    content = {"title": draft.title, "days": plan_days, "notes": notes, "flashcards": flashcards, "quiz": quiz}
    return content, answer_key


def refresh_refs(uid: str, value: Any, store: BrainStore) -> Any:
    """Re-sign media URLs inside stored SourceRefs (signed URLs expire after 15 minutes)."""
    refs: list[dict] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if "chunk_id" in node and "item_id" in node and "anchor" in node:
                refs.append(node)
            for child in node.values():
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(value)
    items = {i["id"]: i for i in store.items_by_ids(uid, list({r["item_id"] for r in refs}))}
    for ref in refs:
        item = items.get(ref["item_id"])
        if not item:
            ref["thumbnail_url"] = ref["media_url"] = None
            continue
        ref["thumbnail_url"], ref["media_url"] = thumbnail_url(uid, item), media_url(uid, item)
        if item.get("youtube_id") and ref["anchor"].get("kind") == "timestamp":
            ref["open_url"] = youtube_watch_url(item["youtube_id"], ref["anchor"]["start_sec"])
    return value


# ---------------------------------------------------------------- generation and answers

def generate(uid: str, plan_id: str, *, store: BrainStore = brain_store, ai: BrainAI = brain_ai) -> bool:
    plan = store.plan(uid, plan_id)
    if not plan or plan["status"] != "generating":
        return False
    course_id, days = plan["course_id"], int(plan["days"])
    try:
        events.publish(uid, "plan.progress", plan_id=plan_id, stage="gathering")
        catalog = Catalog(store, uid)
        passages, items = gather(store, uid, catalog, course_id)
        text, ids = material_text(passages, items, catalog.courses, course_id)
        topics = [{"id": t["id"], "title": t["title"], "sequence": t.get("sequence")} for t in catalog.graph["topics"]
                  if t["course_id"] == course_id]
        events.publish(uid, "plan.progress", plan_id=plan_id, stage="planning")
        draft = ai.generate(operation="brain_exam_plan", prompt="exam_plan", schema=PlanDraft, model=settings.BRAIN_PLAN_MODEL,
                            max_output_tokens=12000, temperature=0.3, timeout=90, variables={
                                "language_name": LANGUAGE_NAMES[plan["language"]], "days": str(days),
                                "quiz_count": "6" if days <= 3 else "8", "course_title": catalog.courses[course_id]["title"],
                                "exam_date": plan["exam_date"], "topics": json.dumps(topics, ensure_ascii=False),
                                "passages": text})
        events.publish(uid, "plan.progress", plan_id=plan_id, stage="citing")
        content, answer_key = assemble(uid, draft, ids, items, catalog, course_id, days, date.fromisoformat(plan["exam_date"]))
        if not content["quiz"] and not any(d["tasks"] for d in content["days"]):
            raise NotEnoughMaterial()
        cited = {r["item_id"] for r in _all_refs(content)}
        course_items = {i for i, row in items.items() if row.get("course_id") == course_id}
        coverage = {"item_count": len(course_items), "cited_item_count": len(cited & course_items),
                    "missing": gap_alerts(catalog.graph, course_id)}
        store.save_plan_secrets(uid, plan_id, answer_key)
        saved = store.finish_plan(uid, plan_id, {"status": "ready", "content": content, "coverage": coverage})
        if saved:
            events.publish(uid, "plan.ready", plan=plan_view(saved))
        return bool(saved)
    except NotEnoughMaterial:
        code = "not_enough_material"
    except AIUnavailable:
        code = "ai_unavailable"
    except Exception:  # noqa: BLE001
        logger.exception("brain_plan failed plan=%s", plan_id)
        code = "internal"
    store.finish_plan(uid, plan_id, {"status": "failed", "failure_code": code})
    events.publish(uid, "plan.failed", plan_id=plan_id, failure_code=code)
    return False


def _all_refs(content: dict) -> list[dict]:
    refs = []
    for day in content["days"]:
        for task in day["tasks"]:
            refs.extend(task["sources"])
    for note in content["notes"]:
        for bullet in note["bullets"]:
            refs.extend(bullet["sources"])
    for card in content["flashcards"]:
        refs.extend(card["sources"])
    for question in content["quiz"]:
        refs.extend(question["sources"])
    return refs


def plan_view(row: dict) -> dict:
    return {key: row.get(key) for key in ("id", "course_id", "days", "exam_date", "language", "status", "failure_code",
                                          "content", "coverage", "created_at")}


def answer(uid: str, plan_id: str, question_id: str, option_id: str, *, store: BrainStore = brain_store) -> Optional[dict]:
    plan = store.plan(uid, plan_id)
    if not plan or plan["status"] != "ready":
        return None
    key = (store.plan_secrets(uid, plan_id) or {}).get(question_id)
    if not key:
        return None
    correct = option_id == key["correct"]
    explanation = refresh_refs(uid, key["explanation"], store)
    moment = refresh_refs(uid, key.get("moment"), store) if key.get("moment") else None
    attempt = store.add_attempt({"user_id": uid, "plan_id": plan_id, "question_id": question_id, "chosen_option": option_id,
                                 "correct": correct, "moment": moment})
    return {"question_id": question_id, "correct": correct, "correct_option_id": key["correct"], "explanation": explanation,
            "moment": moment, "attempt_id": attempt["id"]}


@celery_app.task(name="brain.generate_plan", soft_time_limit=150, time_limit=180)
def generate_plan(uid: str, plan_id: str) -> bool:
    return generate(uid, plan_id)
