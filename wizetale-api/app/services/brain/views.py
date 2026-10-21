"""Database rows → API JSON shapes (wizetale-app/lib/brain-types.ts).

Kept separate from routes so the pipeline, events, and Telegram replies all serialize
items, courses, and citations the same way.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Optional, Sequence

from app.services.brain.blobs import sign_media
from app.services.brain.store import BrainStore

REVIEW_THRESHOLD = 0.6
MEDIA_KINDS = {"photo", "pdf", "audio"}
TIMING_KEYS = ("extract", "classify", "link", "total")


def youtube_watch_url(youtube_id: str, start: float = 0) -> str:
    suffix = f"&t={int(start)}s" if start else ""
    return f"https://www.youtube.com/watch?v={youtube_id}{suffix}"


def anchor_of(chunk: dict) -> dict:
    kind = chunk["anchor_kind"]
    if kind == "page":
        return {"kind": "page", "page": chunk["page"]}
    if kind == "slide":
        return {"kind": "slide", "slide": chunk.get("slide")}
    if kind == "timestamp":
        return {"kind": "timestamp", "start_sec": float(chunk["start_sec"]), "end_sec": float(chunk["end_sec"])}
    if kind == "paragraph":
        return {"kind": "paragraph", "paragraph": chunk["paragraph"]}
    return {"kind": "section", "heading": chunk.get("heading") or ""}


def thumbnail_url(uid: str, item: dict) -> Optional[str]:
    if item.get("thumbnail_path"):
        return sign_media(uid, item["thumbnail_path"], "image/jpeg")
    if item.get("kind") == "photo" and item.get("object_path"):
        return sign_media(uid, item["object_path"], item.get("mime_type"))
    if item.get("youtube_id"):
        return f"https://i.ytimg.com/vi/{item['youtube_id']}/hqdefault.jpg"
    return None


def media_url(uid: str, item: dict) -> Optional[str]:
    if item.get("kind") in MEDIA_KINDS and item.get("object_path"):
        return sign_media(uid, item["object_path"], item.get("mime_type"))
    return None


def item_view(uid: str, item: dict, *, courses: dict[str, dict], topics: dict[str, dict],
              concept_ids: Sequence[str] = ()) -> dict[str, Any]:
    confidence = item.get("confidence")
    timings = {k: int(v) for k, v in (item.get("timings_ms") or {}).items() if k in TIMING_KEYS and v is not None}
    course = courses.get(item.get("course_id") or "")
    topic = topics.get(item.get("topic_id") or "")
    return {
        "id": item["id"],
        "kind": item["kind"],
        "channel": item["channel"],
        "status": item["status"],
        "progress": float(item.get("progress") or 0),
        "title": item["title"],
        "summary": item.get("summary"),
        "language": item.get("language"),
        "course_id": item.get("course_id"),
        "course_title": course["title"] if course else None,
        "topic_id": item.get("topic_id"),
        "topic_title": topic["title"] if topic else None,
        "confidence": float(confidence) if confidence is not None else None,
        "needs_review": item["status"] == "filed" and confidence is not None and float(confidence) < REVIEW_THRESHOLD,
        "alternatives": item.get("alternatives") or [],
        "concept_ids": list(concept_ids),
        "source_url": item.get("source_url"),
        "youtube_id": item.get("youtube_id"),
        "thumbnail_url": thumbnail_url(uid, item),
        "media_url": media_url(uid, item),
        "duration_sec": float(item["duration_sec"]) if item.get("duration_sec") is not None else None,
        "page_count": item.get("page_count"),
        "failure_code": item.get("failure_code"),
        "captured_at": item["captured_at"],
        "filed_at": item.get("filed_at"),
        "timings_ms": timings,
    }


def source_ref(uid: str, chunk: dict, item: dict) -> dict[str, Any]:
    anchor = anchor_of(chunk)
    start = anchor.get("start_sec", 0) if anchor["kind"] == "timestamp" else 0
    open_url = None
    if item.get("youtube_id"):
        open_url = youtube_watch_url(item["youtube_id"], start)
    elif item.get("kind") == "web":
        open_url = item.get("source_url")
    return {
        "item_id": item["id"],
        "chunk_id": chunk["id"],
        "item_kind": item["kind"],
        "item_title": item["title"],
        "course_id": item.get("course_id"),
        "anchor": anchor,
        "quote": " ".join(chunk["body"].split())[:280],
        "captured_at": item["captured_at"],
        "thumbnail_url": thumbnail_url(uid, item),
        "open_url": open_url,
        "youtube_id": item.get("youtube_id"),
        "media_url": media_url(uid, item),
    }


class Catalog:
    """Courses, topics, and concepts of one user, loaded once per request."""

    def __init__(self, store: BrainStore, uid: str, graph: Optional[dict] = None):
        self.store, self.uid = store, uid
        graph = graph or store.graph(uid)
        self.graph = graph
        self.courses = {c["id"]: c for c in graph["courses"]}
        self.topics = {t["id"]: t for t in graph["topics"]}
        self.concepts = {k["id"]: k for k in graph["concepts"]}

    def concept_ids_for_items(self, item_ids: Iterable[str]) -> dict[str, list[str]]:
        item_ids = [i for i in item_ids if i]
        chunks = self.store.chunks_for_items(self.uid, item_ids, limit=5000) if item_ids else []
        chunk_to_item = {c["id"]: c["item_id"] for c in chunks}
        result: dict[str, list[str]] = defaultdict(list)
        for row in self.store.chunk_concepts(self.uid, chunk_ids=list(chunk_to_item)):
            item_id = chunk_to_item[row["chunk_id"]]
            if row["concept_id"] not in result[item_id]:
                result[item_id].append(row["concept_id"])
        return result

    def items(self, rows: Sequence[dict]) -> list[dict]:
        concept_map = self.concept_ids_for_items(r["id"] for r in rows if r["status"] in ("linking", "filed"))
        return [item_view(self.uid, r, courses=self.courses, topics=self.topics, concept_ids=concept_map.get(r["id"], []))
                for r in rows]

    def item(self, row: dict) -> dict:
        return self.items([row])[0]

    def sources(self, chunk_rows: Sequence[dict]) -> list[dict]:
        items = {i["id"]: i for i in self.store.items_by_ids(self.uid, list({c["item_id"] for c in chunk_rows}))}
        return [source_ref(self.uid, c, items[c["item_id"]]) for c in chunk_rows if c["item_id"] in items]


def gap_alerts(graph: dict, course_id: Optional[str] = None) -> list[dict]:
    """Missing week/lecture numbers between the first and last one a course has material for."""
    alerts = []
    for course in graph["courses"]:
        if course_id and course["id"] != course_id:
            continue
        by_kind: dict[str, set[int]] = defaultdict(set)
        for topic in graph["topics"]:
            if topic["course_id"] == course["id"] and topic.get("sequence") is not None and topic.get("item_count", 0) > 0:
                by_kind[topic["sequence_kind"]].add(int(topic["sequence"]))
        for kind, numbers in by_kind.items():
            present = sorted(numbers)
            if len(present) < 2:
                continue
            for missing in range(present[0], present[-1] + 1):
                if missing not in numbers:
                    alerts.append({
                        "id": f"{course['id']}:{kind}:{missing}", "course_id": course["id"], "course_title": course["title"],
                        "sequence_kind": kind, "missing": missing, "present": present,
                    })
    return alerts
