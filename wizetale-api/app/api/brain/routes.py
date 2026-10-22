"""Fibonacci Brain HTTP API (`/api/v1/brain/...`). Contract: wizetale-app/lib/brain-types.ts."""
from __future__ import annotations

import hmac
import logging
from datetime import date, timedelta
from typing import Optional
from uuid import UUID

import requests
from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.concurrency import run_in_threadpool

from app.api.dependencies import consume_user_rate_limit, get_current_user
from app.core.config import settings
from app.domain.brain.models import (
    CaptureCreateRequest, ExamPlanRequest, QuizAnswerRequest, RefileRequest, RenameCourseRequest, WebChannel,
)
from app.services.brain import events
from app.services.brain.blobs import BlobError, blob_store, verify_media
from app.services.brain.capture import CaptureRejected, capture_service
from app.services.brain.plans import answer as answer_question, plan_view, refresh_refs
from app.services.brain.store import brain_store
from app.services.brain.views import Catalog, gap_alerts

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/brain", tags=["brain"])


class BrainError(Exception):
    def __init__(self, status: int, code: str, detail: str, headers: Optional[dict] = None):
        super().__init__(detail)
        self.status, self.code, self.detail, self.headers = status, code, detail, headers


async def brain_error_handler(request: Request, exc: BrainError) -> JSONResponse:
    return JSONResponse({"detail": exc.detail, "code": exc.code}, status_code=exc.status, headers=exc.headers)


# ---------------------------------------------------------------- auth and limits

def demo_allowed() -> bool:
    return settings.DEMO_MODE and settings.ENVIRONMENT.strip().lower() != "production" and bool(settings.BRAIN_DEMO_TOKEN)


async def brain_user(request: Request) -> dict:
    """Supabase user, or the seeded demo student when DEMO_MODE presents the server-only demo token."""
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() == "bearer" and demo_allowed() and hmac.compare_digest(token.strip(), settings.BRAIN_DEMO_TOKEN or ""):
        return {"uid": settings.BRAIN_DEMO_USER_ID, "email": settings.BRAIN_DEMO_EMAIL, "demo": True}
    try:
        return await get_current_user(request)
    except Exception as error:
        status = getattr(error, "status_code", 401)
        raise BrainError(status, "unauthorized" if status == 401 else "unavailable", "Sign in to continue.") from error


async def owner(user: dict = Depends(brain_user)) -> str:
    uid = str(user["uid"])
    if await run_in_threadpool(brain_store.is_user_deleting, uid):
        raise BrainError(409, "conflict", "Account deletion is in progress.")
    return uid


async def limit(request: Request, uid: str, action: str, count: int, window: int = 60) -> None:
    client = getattr(request.app.state, "redis_client", None)
    if client is None:
        return  # development without Redis: no per-user limit
    try:
        await consume_user_rate_limit(client, uid, f"brain-{action}", count, window)
    except Exception as error:
        if getattr(error, "status_code", None) == 429:
            raise BrainError(429, "rate_limited", "Too many requests. Try again shortly.",
                             headers=getattr(error, "headers", None)) from error
        raise BrainError(503, "unavailable", "Request limiting is temporarily unavailable.") from error


async def call(fn, *args, **kwargs):
    try:
        return await run_in_threadpool(fn, *args, **kwargs)
    except CaptureRejected as error:
        status = {"too_large": 413, "unsupported_type": 415, "conflict": 409}.get(error.code, 422)
        raise BrainError(status, error.code, str(error)) from error
    except requests.HTTPError as error:
        status = error.response.status_code if error.response is not None else 503
        if status in (400, 404, 409, 422):
            raise BrainError(409 if status == 409 else 422, "invalid_input" if status != 409 else "conflict",
                             "The request could not be applied. Refresh and try again.") from error
        raise BrainError(503, "unavailable", "The Brain is temporarily unavailable.") from error
    except (requests.ConnectionError, requests.Timeout) as error:
        raise BrainError(503, "unavailable", "The Brain is temporarily unavailable.") from error


def _catalog(uid: str) -> Catalog:
    return Catalog(brain_store, uid)


# ---------------------------------------------------------------- overview, items

@router.get("/overview")
async def overview(uid: str = Depends(owner), user: dict = Depends(brain_user)):
    def build():
        brain_store.ensure_user(uid, user.get("email"))
        catalog = _catalog(uid)
        recent = brain_store.items(uid, limit=20)
        counts = brain_store.counts(uid)
        from app.services.brain.telegram import linking

        return {
            "counts": {"items": counts["items"], "processing": counts["processing"], "courses": len(catalog.courses),
                       "concepts": len(catalog.concepts), "cross_links": sum(1 for l in catalog.graph["links"] if l["cross_course"])},
            "recent_items": catalog.items(recent), "gaps": gap_alerts(catalog.graph),
            "telegram": linking.status(uid), "demo_mode": bool(user.get("demo")) or settings.DEMO_MODE,
        }
    return await call(build)


@router.post("/captures", status_code=202)
async def create_capture(body: CaptureCreateRequest, request: Request, uid: str = Depends(owner), user: dict = Depends(brain_user)):
    await limit(request, uid, "capture", 30)
    if body.url:
        row = await call(capture_service.from_link, uid, user.get("email"), body.url, channel=body.channel,
                         request_id=str(body.request_id))
    else:
        row = await call(capture_service.from_text, uid, user.get("email"), body.text or "", title=body.title,
                         channel=body.channel, request_id=str(body.request_id))
    return await call(lambda: _catalog(uid).item(row))


@router.post("/captures/upload", status_code=202)
async def upload_capture(request: Request, file: UploadFile = File(...), channel: WebChannel = Form("web_drop"),
                         request_id: UUID = Form(...), uid: str = Depends(owner), user: dict = Depends(brain_user)):
    await limit(request, uid, "capture", 30)
    try:
        data = await file.read(settings.BRAIN_MAX_UPLOAD_BYTES + 1)
    finally:
        await file.close()
    if len(data) > settings.BRAIN_MAX_UPLOAD_BYTES:
        raise BrainError(413, "too_large", "Choose a file up to 20 MB.")
    row = await call(capture_service.from_upload, uid, user.get("email"), data, file.filename or "file", file.content_type,
                     channel=channel, request_id=str(request_id))
    return await call(lambda: _catalog(uid).item(row))


# ---------------------------------------------------------------- demo tools (DEMO_MODE only, never in production)

def demo_tools_allowed() -> bool:
    return settings.DEMO_MODE and settings.ENVIRONMENT.strip().lower() != "production"


@router.post("/demo/hero", status_code=202)
async def demo_send_hero(request: Request, uid: str = Depends(owner), user: dict = Depends(brain_user)):
    """Send the three demo inputs (slide photo, lecture video, PDF) through the normal capture pipeline."""
    if not demo_tools_allowed():
        raise BrainError(404, "not_found", "Not found.")
    for _ in range(3):
        await limit(request, uid, "capture", 30)
    from app.services.brain.demo import hero

    try:
        rows = await call(hero.send, capture_service, uid, user.get("email"))
    except hero.HeroInputsMissing as error:
        raise BrainError(503, "unavailable", "The demo files are not on this server.") from error
    return await call(lambda: {"items": _catalog(uid).items(rows)})


@router.post("/demo/reset")
async def demo_reset(uid: str = Depends(owner)):
    """Put the demo student's Brain back to its starting state. The Telegram link stays."""
    if not demo_tools_allowed() or uid != settings.BRAIN_DEMO_USER_ID or not brain_store.local:
        raise BrainError(404, "not_found", "Not found.")
    from app.services.brain.demo.seed import seed

    result = await call(seed, uid, settings.BRAIN_DEMO_EMAIL)
    return {"courses": result["courses"], "items": result["items"]}


@router.get("/items")
async def list_items(status: Optional[str] = Query(None, pattern="^(queued|extracting|classifying|linking|filed|failed)$"),
                     course_id: Optional[UUID] = None, limit_: int = Query(25, alias="limit", ge=1, le=100),
                     cursor: Optional[str] = Query(None, max_length=40), uid: str = Depends(owner)):
    def build():
        rows = brain_store.items(uid, status=status, course_id=str(course_id) if course_id else None, before=cursor,
                                 limit=limit_ + 1)
        page = rows[:limit_]
        return {"items": _catalog(uid).items(page), "next_cursor": page[-1]["captured_at"] if len(rows) > limit_ else None}
    return await call(build)


async def _item(uid: str, item_id: UUID) -> dict:
    row = await call(brain_store.item, uid, str(item_id))
    if not row:
        raise BrainError(404, "not_found", "Item not found.")
    return row


@router.get("/items/{item_id}")
async def get_item(item_id: UUID, uid: str = Depends(owner)):
    row = await _item(uid, item_id)

    def build():
        catalog = _catalog(uid)
        view = catalog.item(row)
        chunks = brain_store.chunks(uid, row["id"], limit=50)
        from app.services.brain.views import anchor_of

        return {"item": view,
                "chunks": [{"id": c["id"], "item_id": c["item_id"], "ordinal": c["ordinal"], "anchor": anchor_of(c), "text": c["body"]}
                           for c in chunks],
                "concepts": [catalog.concepts[c] for c in view["concept_ids"] if c in catalog.concepts]}
    return await call(build)


@router.delete("/items/{item_id}", status_code=204)
async def delete_item(item_id: UUID, uid: str = Depends(owner)):
    await _item(uid, item_id)
    await call(brain_store.delete_item, uid, str(item_id))
    try:
        await run_in_threadpool(blob_store.delete_prefix, f"{uid}/{item_id}/")
    except Exception as error:  # noqa: BLE001 — the row is gone; orphaned blobs are cleaned with the account
        logger.warning("brain_delete blob_cleanup_failed error_type=%s", type(error).__name__)
    events.publish(uid, "item.deleted", item_id=str(item_id))
    return Response(status_code=204)


@router.post("/items/{item_id}/refile")
async def refile(item_id: UUID, body: RefileRequest, uid: str = Depends(owner)):
    row = await _item(uid, item_id)
    if row["status"] != "filed":
        raise BrainError(409, "conflict", "Only filed items can be moved.")
    result = await call(brain_store.refile_item, uid, str(item_id),
                        course_id=str(body.course_id) if body.course_id else None, new_course_title=body.new_course_title,
                        topic_id=str(body.topic_id) if body.topic_id else None, new_topic_title=body.new_topic_title,
                        auto_topic="topic_id" not in body.model_fields_set and not body.new_topic_title)
    if not result:
        raise BrainError(409, "conflict", "This item changed. Refresh and try again.")

    def build():
        catalog = _catalog(uid)
        view = catalog.item(brain_store.item(uid, str(item_id)))
        events.publish(uid, "item.refiled", item=view)
        return {"item": view, "course": catalog.courses[result["course_id"]],
                "topic": catalog.topics.get(result["topic_id"]) if result.get("topic_id") else None, "learned": True}
    return await call(build)


@router.post("/items/{item_id}/retry", status_code=202)
async def retry(item_id: UUID, request: Request, uid: str = Depends(owner)):
    await limit(request, uid, "retry", 10)
    row = await _item(uid, item_id)
    if row["status"] != "failed":
        raise BrainError(409, "conflict", "Only failed items can be retried.")
    from uuid import uuid4

    task_id = str(uuid4())
    updated = await call(brain_store.update_item, uid, str(item_id),
                         {"status": "queued", "failure_code": None, "progress": 0.02, "task_id": task_id}, statuses=("failed",))
    if not updated:
        raise BrainError(409, "conflict", "This item changed. Refresh and try again.")
    await call(capture_service.enqueue, uid, str(item_id), task_id)
    return await call(lambda: _catalog(uid).item(updated))


# ---------------------------------------------------------------- graph, concepts, courses, gaps, search

@router.get("/graph")
async def graph(uid: str = Depends(owner)):
    return await call(brain_store.graph, uid)


@router.get("/concepts/{concept_id}")
async def concept(concept_id: UUID, uid: str = Depends(owner)):
    def build():
        catalog = _catalog(uid)
        row = catalog.concepts.get(str(concept_id))
        if not row:
            return None
        mentions = brain_store.chunk_concepts(uid, concept_ids=[row["id"]], limit=20)
        sources = catalog.sources(brain_store.chunks_by_ids(uid, [m["chunk_id"] for m in mentions]))
        sources.sort(key=lambda s: s["captured_at"], reverse=True)
        linked = []
        for link in catalog.graph["links"]:
            if row["id"] in (link["source_concept_id"], link["target_concept_id"]):
                other = catalog.concepts.get(link["target_concept_id"] if link["source_concept_id"] == row["id"] else link["source_concept_id"])
                if other:
                    linked.append({"link": link, "concept": other, "course": catalog.courses[other["course_id"]]})
        linked.sort(key=lambda entry: (not entry["link"]["cross_course"], -entry["link"]["strength"]))
        return {"concept": row, "course": catalog.courses[row["course_id"]],
                "topic": catalog.topics.get(row["topic_id"]) if row.get("topic_id") else None, "sources": sources, "linked": linked}
    result = await call(build)
    if result is None:
        raise BrainError(404, "not_found", "Concept not found.")
    return result


@router.get("/courses/{course_id}")
async def course(course_id: UUID, uid: str = Depends(owner)):
    def build():
        catalog = _catalog(uid)
        row = catalog.courses.get(str(course_id))
        if not row:
            return None
        items = catalog.items(brain_store.items(uid, course_id=row["id"], limit=200))
        topics = sorted((t for t in catalog.topics.values() if t["course_id"] == row["id"]),
                        key=lambda t: (t.get("sequence") is None, t.get("sequence") or 0, t["created_at"]))
        return {"course": row, "topics": [{"topic": t, "items": [i for i in items if i["topic_id"] == t["id"]]} for t in topics],
                "loose_items": [i for i in items if not i["topic_id"]], "gaps": gap_alerts(catalog.graph, row["id"])}
    result = await call(build)
    if result is None:
        raise BrainError(404, "not_found", "Course not found.")
    return result


@router.patch("/courses/{course_id}")
async def rename_course(course_id: UUID, body: RenameCourseRequest, uid: str = Depends(owner)):
    row = await call(brain_store.rename_course, uid, str(course_id), body.title)
    if not row:
        raise BrainError(404, "not_found", "Course not found.")
    return await call(lambda: _catalog(uid).courses[row["id"]])


@router.get("/gaps")
async def gaps(uid: str = Depends(owner)):
    return await call(lambda: gap_alerts(brain_store.graph(uid)))


@router.get("/search")
async def search(q: str = Query(min_length=1, max_length=200), limit_: int = Query(20, alias="limit", ge=1, le=50),
                 uid: str = Depends(owner)):
    def build():
        from app.services.brain.ai.client import brain_ai

        catalog = _catalog(uid)
        needle = q.strip().lower()
        hits = [{"kind": "concept", "score": 1.0 if needle == k["name"].lower() else 0.9 if needle in k["name"].lower() else 0.7,
                 "concept": k} for k in catalog.concepts.values()
                if needle in k["name"].lower() or needle in (k.get("summary") or "").lower()]
        scores: dict[str, float] = {r["chunk_id"]: min(0.69, 0.4 + float(r["rank"])) for r in brain_store.search_chunks(uid, q, limit_)}
        vector = brain_ai.embed([q], task_type="RETRIEVAL_QUERY")[0]
        if vector:
            for match in brain_store.match_chunks(uid, vector, limit=limit_):
                if match["similarity"] >= 0.55:
                    scores[match["chunk_id"]] = max(scores.get(match["chunk_id"], 0), round(float(match["similarity"]) * 0.8, 3))
        ranked = sorted(scores.items(), key=lambda kv: -kv[1])[:limit_]
        sources = {s["chunk_id"]: s for s in catalog.sources(brain_store.chunks_by_ids(uid, [cid for cid, _ in ranked]))}
        hits += [{"kind": "passage", "score": score, "source": sources[cid]} for cid, score in ranked if cid in sources]
        hits.sort(key=lambda h: -h["score"])
        return {"query": q, "hits": hits[:limit_]}
    return await call(build)


# ---------------------------------------------------------------- exam mode

@router.post("/courses/{course_id}/exam-plan", status_code=202)
async def create_plan(course_id: UUID, body: ExamPlanRequest, request: Request, uid: str = Depends(owner)):
    await limit(request, uid, "plan", 6)
    course_row = await call(brain_store.course, uid, str(course_id))
    if not course_row:
        raise BrainError(404, "not_found", "Course not found.")
    exam_date = body.exam_date or (date.today() + timedelta(days=body.days))
    record = {"id": str(body.request_id), "user_id": uid, "course_id": str(course_id), "days": body.days,
              "exam_date": exam_date.isoformat(), "language": body.language, "status": "generating"}
    claimed = await call(brain_store.claim_plan, record)
    if not claimed:
        previous = await call(brain_store.plan, uid, str(body.request_id))
        if not previous or previous["course_id"] != str(course_id):
            raise BrainError(409, "conflict", "This request id was already used.")
        return plan_view(previous)
    from app.services.brain.plans import generate_plan

    try:
        await run_in_threadpool(generate_plan.apply_async, args=[uid, claimed["id"]], task_id=f"plan-{claimed['id']}")
    except Exception as error:  # noqa: BLE001
        await call(brain_store.finish_plan, uid, claimed["id"], {"status": "failed", "failure_code": "internal"})
        raise BrainError(503, "unavailable", "Plan generation could not start.") from error
    return plan_view(claimed)


@router.get("/plans/{plan_id}")
async def get_plan(plan_id: UUID, uid: str = Depends(owner)):
    row = await call(brain_store.plan, uid, str(plan_id))
    if not row:
        raise BrainError(404, "not_found", "Plan not found.")
    return await call(lambda: refresh_refs(uid, plan_view(row), brain_store))


@router.get("/courses/{course_id}/plans")
async def course_plans(course_id: UUID, uid: str = Depends(owner)):
    rows = await call(brain_store.plans, uid, str(course_id))
    return await call(lambda: [refresh_refs(uid, plan_view(r), brain_store) for r in rows])


@router.post("/plans/{plan_id}/quiz/{question_id}/answer")
async def answer(plan_id: UUID, question_id: str, body: QuizAnswerRequest, uid: str = Depends(owner)):
    if not question_id.startswith("q") or not question_id[1:].isdigit() or len(question_id) > 4:
        raise BrainError(422, "invalid_input", "Unknown question.")
    result = await call(answer_question, uid, str(plan_id), question_id, body.option_id)
    if not result:
        raise BrainError(404, "not_found", "Question not found.")
    return result


# ---------------------------------------------------------------- Telegram

@router.get("/telegram/status")
async def telegram_status(uid: str = Depends(owner)):
    from app.services.brain.telegram import linking

    return await call(linking.status, uid)


@router.post("/telegram/link-code")
async def telegram_link_code(request: Request, uid: str = Depends(owner)):
    from app.services.brain.telegram import linking

    if not settings.TELEGRAM_BOT_TOKEN:
        raise BrainError(503, "telegram_not_configured", "The Telegram bot is not configured.")
    await limit(request, uid, "telegram-code", 10, 600)
    return await call(linking.create_link_code, uid)


@router.delete("/telegram/link", status_code=204)
async def telegram_unlink(uid: str = Depends(owner)):
    await call(brain_store.unlink_telegram, uid)
    return Response(status_code=204)


@router.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    from app.services.brain.telegram import webhook

    body = await request.json()
    accepted = await run_in_threadpool(webhook.handle_webhook, body, request.headers.get("X-Telegram-Bot-Api-Secret-Token"))
    return Response(status_code=200 if accepted else 401)


# ---------------------------------------------------------------- realtime and media

@router.get("/events")
async def stream_events(request: Request, uid: str = Depends(owner)):
    last_id = request.headers.get("Last-Event-ID")
    return StreamingResponse(events.stream(uid, last_id), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no", "Connection": "keep-alive"})


@router.get("/media/{token}")
async def media(token: str, request: Request):
    claims = verify_media(token)
    if not claims:
        raise BrainError(404, "not_found", "This link has expired.")
    try:
        data = await run_in_threadpool(blob_store.get, claims["p"])
    except BlobError as error:
        raise BrainError(404, "not_found", "File not found.") from error
    headers = {"Cache-Control": "private, max-age=600", "X-Content-Type-Options": "nosniff",
               "Content-Security-Policy": "default-src 'none'; sandbox", "Accept-Ranges": "bytes"}
    range_header = request.headers.get("Range", "")
    if range_header.startswith("bytes="):
        start_text, _, end_text = range_header[6:].partition("-")
        try:
            start = int(start_text) if start_text else max(0, len(data) - int(end_text))
            end = min(int(end_text), len(data) - 1) if end_text and start_text else len(data) - 1
        except ValueError:
            start, end = 0, len(data) - 1
        if start >= len(data) or start > end:
            return Response(status_code=416, headers={"Content-Range": f"bytes */{len(data)}"})
        headers["Content-Range"] = f"bytes {start}-{end}/{len(data)}"
        return Response(data[start:end + 1], status_code=206, media_type=claims["m"], headers=headers)
    return Response(data, media_type=claims["m"], headers=headers)
