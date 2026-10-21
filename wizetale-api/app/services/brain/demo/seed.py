"""DEMO_MODE seed: one demo student, three courses, ~40 items, pre-computed links.

    python -m app.services.brain.demo.seed            # inside the api container
    python -m app.services.brain.demo.seed --check    # report what is there

Idempotent: wipes the demo student's brain (keeping their Telegram link) and rebuilds it
from seed_data.json — the same sample content the web app's mock mode shows. Embeddings
come from Gemini through the recorded cache, so a re-seed works offline once recorded.
Only for the local brain store; refuses to run in production.
"""
from __future__ import annotations

import argparse
import io
import json
import logging
import sys
import textwrap
import uuid
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from app.core.config import settings
from app.services.brain.ai.client import brain_ai
from app.services.brain.blobs import blob_store, object_path
from app.services.brain.store import brain_store

logger = logging.getLogger("brain.seed")
DATA = Path(__file__).with_name("seed_data.json")
NAMESPACE = uuid.UUID("6f1b0c3e-5a1e-4f1e-9c51-b7a1f1b0d3e0")
FONT_PATHS = ["/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf", "/usr/share/fonts/noto/NotoSans-Regular.ttf"]


def _font(size: int) -> ImageFont.ImageFont:
    for path in FONT_PATHS:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _picture(title: str, lines: list[str], *, photo: bool) -> bytes:
    """A slide-like (photo) or page-like (PDF) preview with the passage text."""
    width, height = (960, 540) if photo else (620, 820)
    image = Image.new("RGB", (width, height), "#fbfcfa")
    draw = ImageDraw.Draw(image)
    draw.text((48, 40), textwrap.shorten(title, 60), fill="#14231c", font=_font(34 if photo else 26))
    y = 110
    for line in lines:
        for wrapped in textwrap.wrap(line, 52 if photo else 46)[:6]:
            draw.text((52, y), wrapped, fill="#2b3a33", font=_font(24 if photo else 19))
            y += 34 if photo else 28
        y += 12
    if photo:
        canvas = Image.new("RGB", (width + 80, height + 80), "#2a2f2c")
        canvas.paste(image.rotate(-2.2, expand=False, fillcolor="#2a2f2c"), (40, 40))
        image = canvas.filter(ImageFilter.GaussianBlur(1.1))
    image.thumbnail((480, 480))
    out = io.BytesIO()
    image.save(out, format="JPEG", quality=80)
    return out.getvalue()


def _chunk_columns(anchor: dict) -> dict:
    return {"anchor_kind": anchor["kind"], "page": anchor.get("page"), "slide": anchor.get("slide"),
            "start_sec": anchor.get("start_sec"), "end_sec": anchor.get("end_sec"),
            "paragraph": anchor.get("paragraph"), "heading": anchor.get("heading")}


def wipe(uid: str) -> None:
    for table in ("brain_study_plans", "brain_refile_events", "brain_telegram_codes", "brain_items", "brain_courses"):
        brain_store.request("DELETE", table, params={"user_id": f"eq.{uid}"})


def seed(uid: str, email: str) -> dict:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    brain_store.ensure_user(uid, email)
    wipe(uid)
    blob_store.delete_prefix(f"{uid}/") if Path(settings.BRAIN_MEDIA_DIR, uid).exists() else None

    brain_store.request("POST", "brain_courses", payload=[
        {"id": c["id"], "user_id": uid, "title": c["title"], "code": c["code"], "color_index": c["color_index"],
         "created_by": "auto", "created_at": c["created_at"]} for c in data["courses"]], prefer="return=minimal")
    brain_store.request("POST", "brain_topics", payload=[
        {"id": t["id"], "user_id": uid, "course_id": t["course_id"], "title": t["title"], "sequence": t["sequence"],
         "sequence_kind": t["sequence_kind"], "created_at": t["created_at"]} for t in data["topics"]], prefer="return=minimal")
    concept_vectors = brain_ai.embed([f"{k['name']}: {k['summary']}" for k in data["concepts"]], task_type="SEMANTIC_SIMILARITY")
    brain_store.request("POST", "brain_concepts", payload=[
        {"id": k["id"], "user_id": uid, "course_id": k["course_id"], "topic_id": k["topic_id"], "name": k["name"],
         "summary": k["summary"], "embedding": vector, "created_at": k["created_at"]}
        for k, vector in zip(data["concepts"], concept_vectors)], prefer="return=minimal")

    chunks_by_item: dict[str, list[dict]] = {}
    for chunk in data["chunks"]:
        chunks_by_item.setdefault(chunk["item_id"], []).append(chunk)
    items = []
    for item in data["items"]:
        row = {key: item[key] for key in ("id", "kind", "status", "title", "summary", "language", "course_id", "topic_id",
                                          "confidence", "alternatives", "source_url", "youtube_id", "duration_sec",
                                          "page_count", "failure_code", "captured_at", "filed_at")}
        row.update({"user_id": uid, "channel": item["channel"], "progress": 1 if item["status"] == "filed" else 0.2,
                    "task_id": str(uuid.uuid5(NAMESPACE, item["id"])), "metadata": {"seed": True},
                    "timings_ms": {"extract": 1800, "classify": 1400, "link": 900, "total": 4100} if item["status"] == "filed" else {},
                    "thumbnail_path": None, "object_path": None, "mime_type": None})
        lines = [c["text"] for c in chunks_by_item.get(item["id"], [])]
        if item["kind"] in ("photo", "pdf") and lines:
            picture = _picture(item["title"].split("—")[-1].strip().removesuffix(".pdf"), lines, photo=item["kind"] == "photo")
            path = object_path(uid, item["id"], "thumbnail.jpg")
            blob_store.put(path, picture, "image/jpeg")
            row["thumbnail_path"] = path
            if item["kind"] == "photo":
                row["object_path"], row["mime_type"] = path, "image/jpeg"
        items.append(row)
    brain_store.request("POST", "brain_items", payload=items, prefer="return=minimal")

    chunk_rows, mentions = [], []
    texts = [c["text"] for c in data["chunks"]]
    vectors = brain_ai.embed(texts, task_type="RETRIEVAL_DOCUMENT")
    for chunk, vector in zip(data["chunks"], vectors):
        chunk_id = str(uuid.uuid5(NAMESPACE, f"{chunk['item_id']}:{chunk['ordinal']}"))
        chunk_rows.append({"id": chunk_id, "user_id": uid, "item_id": chunk["item_id"], "ordinal": chunk["ordinal"],
                           "body": chunk["text"], "embedding": vector, **_chunk_columns(chunk["anchor"])})
        mentions.extend({"chunk_id": chunk_id, "concept_id": concept, "user_id": uid} for concept in chunk["concept_ids"])
    brain_store.request("POST", "brain_chunks", payload=chunk_rows, prefer="return=minimal")
    brain_store.request("POST", "brain_chunk_concepts", payload=mentions, prefer="return=minimal")
    brain_store.request("POST", "brain_concept_links", payload=[
        {"user_id": uid, "source_concept_id": l["source_concept_id"], "target_concept_id": l["target_concept_id"],
         "strength": l["strength"], "relation": l["relation"], "rationale": l["rationale"], "method": "verified",
         "created_at": l["created_at"]} for l in data["links"]], prefer="return=minimal")
    missing = sum(1 for v in [*concept_vectors, *vectors] if v is None)
    return {"courses": len(data["courses"]), "topics": len(data["topics"]), "concepts": len(data["concepts"]),
            "items": len(items), "passages": len(chunk_rows), "links": len(data["links"]), "missing_embeddings": missing}


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="only report the demo brain's size")
    args = parser.parse_args()
    if settings.ENVIRONMENT.strip().lower() == "production" or not brain_store.local:
        print("Refusing: the demo seed runs only against the local brain store outside production.", file=sys.stderr)
        return 2
    uid = settings.BRAIN_DEMO_USER_ID
    if args.check:
        graph = brain_store.graph(uid)
        print(json.dumps({k: len(v) for k, v in graph.items() if isinstance(v, list)}))
        return 0
    started = datetime.now(timezone.utc)
    result = seed(uid, settings.BRAIN_DEMO_EMAIL)
    result["seconds"] = round((datetime.now(timezone.utc) - started).total_seconds(), 1)
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
