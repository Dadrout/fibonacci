"""Capture pipeline: extract → classify → embed → file → link, with live events.

One Celery task per item. The item's task_id guards every write, so a retried or
deleted item can never be overwritten by a stale worker. Stage timings are logged
and stored on the item (the hero demo targets < 10 s from capture to filed).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from time import monotonic
from typing import Optional

from celery.exceptions import SoftTimeLimitExceeded

from app.celery_utils import celery_app
from app.domain.brain.pipeline import Classification, Extraction, ExtractInput, ExtractionError
from app.services.brain import events
from app.services.brain.ai.client import AIUnavailable, BrainAI, brain_ai
from app.services.brain.blobs import BlobStore, blob_store, object_path
from app.services.brain.classify import alternatives_json, classify, placement_payload
from app.services.brain.extract import extract
from app.services.brain.link import link_concepts
from app.services.brain.store import BrainStore, brain_store
from app.services.brain.views import Catalog, gap_alerts

logger = logging.getLogger(__name__)
ACTIVE = ("queued", "extracting", "classifying", "linking")


class Run:
    def __init__(self, uid: str, item_id: str, task_id: str, store: BrainStore, blobs: BlobStore, ai: BrainAI):
        self.uid, self.item_id, self.task_id = uid, item_id, task_id
        self.store, self.blobs, self.ai = store, blobs, ai
        self.started = monotonic()
        self.timings: dict[str, int] = {}
        self.item: dict = {}

    def _ms(self, since: float) -> int:
        return int((monotonic() - since) * 1000)

    def stage(self, status: str, progress: float, changes: Optional[dict] = None) -> bool:
        row = self.store.update_item(self.uid, self.item_id, {"status": status, "progress": progress, **(changes or {})},
                                     task_id=self.task_id, statuses=ACTIVE)
        if not row:
            return False
        self.item = row
        events.publish(self.uid, "item.progress", item_id=self.item_id, status=status, progress=progress, title=row["title"])
        return True

    def fail(self, code: str) -> None:
        row = self.store.update_item(self.uid, self.item_id, {"status": "failed", "failure_code": code,
                                                              "timings_ms": {**self.timings, "total": self._ms(self.started)}},
                                     task_id=self.task_id, statuses=ACTIVE)
        if row:
            events.publish(self.uid, "item.failed", item_id=self.item_id, failure_code=code)
            _notify_telegram_failed(row, code)

    # ------------------------------------------------------------------ stages

    def extract(self) -> Extraction:
        started = monotonic()
        item = self.item
        data = self.blobs.get(item["object_path"]) if item.get("object_path") else None
        inp = ExtractInput(kind=item["kind"], data=data, mime_type=item.get("mime_type"), filename=item["title"],
                           url=item.get("source_url"), youtube_id=item.get("youtube_id"),
                           text=data.decode("utf-8") if item["kind"] == "text" and data else None)
        extraction = extract(inp, self.ai)
        changes: dict = {"metadata": {**(item.get("metadata") or {}), **extraction.metadata}}
        if extraction.thumbnail:
            path = object_path(self.uid, self.item_id, "thumbnail.jpg")
            self.blobs.put(path, extraction.thumbnail, extraction.thumbnail_mime or "image/jpeg")
            changes["thumbnail_path"] = path
        if extraction.title:
            changes["title"] = extraction.title[:300]
        for key in ("language", "page_count", "duration_sec"):
            if getattr(extraction, key) is not None:
                changes[key] = getattr(extraction, key)
        self.timings["extract"] = self._ms(started)
        changes["timings_ms"] = dict(self.timings)
        if not self.stage("classifying", 0.45, changes):
            raise _Cancelled()
        return extraction

    def classify(self, extraction: Extraction, graph: dict) -> Classification:
        started = monotonic()
        result = classify(self.store, self.uid, self.item, extraction, graph, self.ai)
        self.timings["classify"] = self._ms(started)
        return result

    def publish(self, extraction: Extraction, result: Classification) -> dict:
        started = monotonic()
        concept_texts = [f"{c.name}: {c.summary}" for c in result.concepts]
        chunk_vectors = self.ai.embed([c.text for c in extraction.chunks], task_type="RETRIEVAL_DOCUMENT")
        concept_vectors = self.ai.embed(concept_texts, task_type="SEMANTIC_SIMILARITY")
        course, topic = placement_payload(result.placement)
        payload = {
            "course": course,
            "topic": topic,
            "item": {"title": result.title, "summary": result.summary, "language": result.language,
                     "confidence": round(result.placement.confidence, 3), "alternatives": alternatives_json(result),
                     "timings_ms": dict(self.timings)},
            "chunks": [{"ordinal": i, "anchor_kind": c.anchor.kind, "page": c.anchor.page, "slide": c.anchor.slide,
                        "start_sec": c.anchor.start_sec, "end_sec": c.anchor.end_sec, "paragraph": c.anchor.paragraph,
                        "heading": c.anchor.heading, "body": c.text, "embedding": chunk_vectors[i]}
                       for i, c in enumerate(extraction.chunks)],
            "concepts": [{"name": c.name, "summary": c.summary, "chunk_ordinals": c.chunk_ordinals,
                          "embedding": concept_vectors[i]} for i, c in enumerate(result.concepts)],
        }
        published = self.store.publish_item(self.uid, self.item_id, self.task_id, payload)
        if not published:
            raise _Cancelled()
        self.timings["embed_publish"] = self._ms(started)
        events.publish(self.uid, "item.progress", item_id=self.item_id, status="linking", progress=0.8, title=result.title)
        return published

    def finish(self, published: dict, gaps_before: set[str]) -> None:
        started = monotonic()
        catalog = Catalog(self.store, self.uid)
        concept_ids = [c["id"] for c in published.get("concepts", [])]
        try:
            new_links = link_concepts(self.store, self.uid, concept_ids, catalog.courses, self.ai)
        except Exception:  # noqa: BLE001 — linking must never block filing
            logger.exception("brain_pipeline link_failed item=%s", self.item_id)
            new_links = []
        self.timings["link"] = self._ms(started)
        self.timings["total"] = self._ms(self.started)
        row = self.store.update_item(self.uid, self.item_id,
                                     {"status": "filed", "progress": 1, "filed_at": datetime.now(timezone.utc).isoformat(), "timings_ms": dict(self.timings)},
                                     task_id=self.task_id, statuses=("linking",))
        if not row:
            raise _Cancelled()
        catalog = Catalog(self.store, self.uid)  # fresh counts after linking
        view = catalog.item(row)
        course = catalog.courses.get(row["course_id"])
        topic = catalog.topics.get(row["topic_id"]) if row.get("topic_id") else None
        concepts = [catalog.concepts[c] for c in view["concept_ids"] if c in catalog.concepts]
        events.publish(self.uid, "item.filed", item=view, course=course, topic=topic,
                       new_course=bool(published.get("course_created")), new_topic=bool(published.get("topic_created")),
                       concepts=concepts)
        headline = None
        for link in new_links:
            source, target = catalog.concepts.get(link["source_concept_id"]), catalog.concepts.get(link["target_concept_id"])
            if not source or not target:
                continue
            cross = source["course_id"] != target["course_id"]
            payload = {**link, "cross_course": cross}
            payload.pop("user_id", None)
            events.publish(self.uid, "link.created", link=payload, source=source, target=target,
                           source_course=catalog.courses.get(source["course_id"]),
                           target_course=catalog.courses.get(target["course_id"]))
            if cross and headline is None:
                headline = f"{source['name']} ↔ {target['name']}"
        gaps_after = {g["id"]: g for g in gap_alerts(catalog.graph)}
        for gap_id in gaps_before - set(gaps_after):
            events.publish(self.uid, "gap.resolved", gap_id=gap_id)
        for gap_id in set(gaps_after) - gaps_before:
            events.publish(self.uid, "gap.detected", gap=gaps_after[gap_id])
        _notify_telegram_filed(row, course["title"] if course else "", topic["title"] if topic else None, headline)
        logger.info("brain_pipeline item=%s kind=%s status=filed concepts=%d links=%d timings=%s",
                    self.item_id, row["kind"], len(view["concept_ids"]), len(new_links), self.timings)


class _Cancelled(Exception):
    """The item changed under us (deleted, retried, or account deletion)."""


def _notify_telegram_filed(row: dict, course: str, topic: Optional[str], cross_link: Optional[str]) -> None:
    if row.get("channel") != "telegram":
        return
    try:
        from app.services.brain.telegram.notify import notify_filed

        notify_filed(row, course, topic, cross_link)
    except Exception as error:  # noqa: BLE001 — a failed reply must not fail filing
        logger.warning("brain_pipeline telegram_notify_failed error_type=%s", type(error).__name__)


def _notify_telegram_failed(row: dict, code: str) -> None:
    if row.get("channel") != "telegram":
        return
    try:
        from app.services.brain.telegram.notify import notify_failed

        notify_failed(row, code)
    except Exception as error:  # noqa: BLE001
        logger.warning("brain_pipeline telegram_notify_failed error_type=%s", type(error).__name__)


def run(uid: str, item_id: str, task_id: str, *, store: BrainStore = brain_store, blobs: BlobStore = blob_store,
        ai: BrainAI = brain_ai) -> bool:
    job = Run(uid, item_id, task_id, store, blobs, ai)
    item = store.item(uid, item_id)
    if not item or str(item["task_id"]) != str(task_id) or item["status"] not in ("queued", "extracting") \
            or store.is_user_deleting(uid):
        return False
    job.item = item
    try:
        if not job.stage("extracting", 0.15):
            return False
        extraction = job.extract()
        graph = store.graph(uid)
        gaps_before = {g["id"] for g in gap_alerts(graph)}
        result = job.classify(extraction, graph)
        published = job.publish(extraction, result)
        job.finish(published, gaps_before)
        return True
    except ExtractionError as error:
        logger.info("brain_pipeline item=%s extraction_failed code=%s", item_id, error.code)
        job.fail(error.code)
    except AIUnavailable:
        job.fail("ai_unavailable")
    except _Cancelled:
        logger.info("brain_pipeline item=%s cancelled", item_id)
    except SoftTimeLimitExceeded:
        job.fail("internal")
    except Exception:  # noqa: BLE001
        logger.exception("brain_pipeline item=%s failed", item_id)
        job.fail("internal")
    return False


@celery_app.task(name="brain.process_item", soft_time_limit=170, time_limit=200)
def process_item(uid: str, item_id: str, task_id: str) -> bool:
    return run(uid, item_id, task_id)
