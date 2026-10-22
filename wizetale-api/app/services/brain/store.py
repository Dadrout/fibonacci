"""Brain persistence over PostgREST — the hosted Supabase project or the local brain database.

Every call is scoped to one user id: filters include `user_id`, and server functions take
`p_uid`. The service credential bypasses RLS, so never drop the owner filter.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Iterable, Optional, Sequence

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)

ITEM_COLUMNS = (
    "id,user_id,kind,channel,status,progress,title,summary,language,course_id,topic_id,confidence,alternatives,"
    "source_url,youtube_id,object_path,thumbnail_path,mime_type,byte_count,content_hash,duration_sec,page_count,"
    "failure_code,task_id,request_id,timings_ms,metadata,captured_at,filed_at,updated_at"
)
CHUNK_COLUMNS = "id,item_id,ordinal,anchor_kind,page,slide,start_sec,end_sec,paragraph,heading,body"


class BrainStoreError(RuntimeError):
    pass


def _in(values: Iterable[Any]) -> str:
    return "in.(" + ",".join(str(v) for v in values) + ")"


class BrainStore:
    def __init__(self, session: Optional[requests.Session] = None):
        self.session = session or requests.Session()

    # ------------------------------------------------------------------ transport

    @property
    def local(self) -> bool:
        return settings.BRAIN_STORE.strip().lower() == "local"

    def _base(self) -> tuple[str, dict[str, str]]:
        if self.local:
            key = settings.BRAIN_LOCAL_SERVICE_KEY
            if not key:
                raise BrainStoreError("BRAIN_LOCAL_SERVICE_KEY is not configured")
            return settings.BRAIN_LOCAL_REST_URL.rstrip("/"), {"Authorization": f"Bearer {key}"}
        if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
            raise BrainStoreError("Supabase is not configured")
        key = settings.SUPABASE_SERVICE_ROLE_KEY
        return f"{settings.SUPABASE_URL.rstrip('/')}/rest/v1", {"apikey": key, "Authorization": f"Bearer {key}"}

    def request(self, method: str, path: str, *, params: Optional[dict[str, str]] = None,
                payload: Any = None, prefer: Optional[str] = None, timeout: float = 10) -> Any:
        base, headers = self._base()
        headers = {**headers, "Content-Type": "application/json"}
        if prefer:
            headers["Prefer"] = prefer
        url = f"{base}/{path}"
        try:
            response = self.session.request(method, url, params=params, json=payload, headers=headers, timeout=timeout)
        except (requests.ConnectionError, requests.Timeout):
            if method.upper() != "GET":
                raise
            response = self.session.request(method, url, params=params, json=payload, headers=headers, timeout=timeout)
        if response.status_code >= 400:
            # PostgREST errors carry SQL details, not user content; keep the message short.
            logger.warning("brain_store %s %s -> %s %s", method, path.split("?")[0], response.status_code,
                           response.text[:300].replace("\n", " "))
            response.raise_for_status()
        if response.status_code == 204 or not response.content:
            return None
        return response.json()

    def rpc(self, name: str, payload: dict[str, Any], timeout: float = 15) -> Any:
        return self.request("POST", f"rpc/{name}", payload=payload, timeout=timeout)

    def _rows(self, table: str, params: dict[str, str]) -> list[dict]:
        return self.request("GET", table, params=params) or []

    def _one(self, table: str, params: dict[str, str]) -> Optional[dict]:
        rows = self._rows(table, {**params, "limit": "1"})
        return rows[0] if rows else None

    # ------------------------------------------------------------------ accounts

    def ensure_user(self, uid: str, email: Optional[str]) -> None:
        """Local store only: mirror the account into the local auth.users table."""
        if self.local:
            self.rpc("brain_local_ensure_user", {"p_uid": uid, "p_email": email or f"{uid}@local.invalid"})

    def delete_user_brain(self, uid: str) -> None:
        """Local store only (hosted rows cascade from auth.users): remove every brain row of a user."""
        if not self.local:
            return
        for table in ("brain_telegram_links", "brain_telegram_codes", "brain_study_plans", "brain_refile_events",
                      "brain_items", "brain_courses"):
            self.request("DELETE", table, params={"user_id": f"eq.{uid}"})

    def is_user_deleting(self, uid: str) -> bool:
        return bool(self._rows("account_deletion_locks", {"user_id": f"eq.{uid}", "select": "user_id", "limit": "1"}))

    # ------------------------------------------------------------------ items

    def create_item(self, record: dict[str, Any]) -> dict:
        """Insert a capture. Returns the existing row when (user_id, request_id) was already used."""
        if record.get("request_id"):
            existing = self._one("brain_items", {"user_id": f"eq.{record['user_id']}",
                                                 "request_id": f"eq.{record['request_id']}", "select": ITEM_COLUMNS})
            if existing:
                return existing
        try:
            rows = self.request("POST", "brain_items", params={"select": ITEM_COLUMNS}, payload=record,
                                prefer="return=representation")
        except requests.HTTPError as error:
            if error.response is not None and error.response.status_code == 409 and record.get("request_id"):
                existing = self._one("brain_items", {"user_id": f"eq.{record['user_id']}",
                                                     "request_id": f"eq.{record['request_id']}", "select": ITEM_COLUMNS})
                if existing:
                    return existing
            raise
        return rows[0]

    def item(self, uid: str, item_id: str) -> Optional[dict]:
        return self._one("brain_items", {"id": f"eq.{item_id}", "user_id": f"eq.{uid}", "select": ITEM_COLUMNS})

    def items(self, uid: str, *, status: Optional[str] = None, course_id: Optional[str] = None,
              topic_ids: Optional[Sequence[str]] = None, before: Optional[str] = None, limit: int = 25) -> list[dict]:
        params = {"user_id": f"eq.{uid}", "select": ITEM_COLUMNS, "order": "captured_at.desc,id.desc", "limit": str(limit)}
        if status:
            params["status"] = f"eq.{status}"
        if course_id:
            params["course_id"] = f"eq.{course_id}"
        if topic_ids:
            params["topic_id"] = _in(topic_ids)
        if before:
            params["captured_at"] = f"lt.{before}"
        return self._rows("brain_items", params)

    def items_by_ids(self, uid: str, ids: Sequence[str]) -> list[dict]:
        if not ids:
            return []
        return self._rows("brain_items", {"user_id": f"eq.{uid}", "id": _in(set(ids)), "select": ITEM_COLUMNS})

    def update_item(self, uid: str, item_id: str, changes: dict[str, Any], *, task_id: Optional[str] = None,
                    statuses: Optional[Sequence[str]] = None) -> Optional[dict]:
        """Guarded update: pass the worker's task_id so a stale worker cannot overwrite newer state."""
        params = {"id": f"eq.{item_id}", "user_id": f"eq.{uid}", "select": ITEM_COLUMNS}
        if task_id:
            params["task_id"] = f"eq.{task_id}"
        if statuses:
            params["status"] = _in(statuses)
        rows = self.request("PATCH", "brain_items", params=params, payload=changes, prefer="return=representation")
        return rows[0] if rows else None

    def publish_item(self, uid: str, item_id: str, task_id: str, payload: dict[str, Any]) -> Optional[dict]:
        return self.rpc("brain_publish_item", {"p_uid": uid, "p_item": item_id, "p_task": task_id, "p_payload": payload}, timeout=30)

    def delete_item(self, uid: str, item_id: str) -> Optional[dict]:
        return self.rpc("brain_delete_item", {"p_uid": uid, "p_item": item_id})

    def refile_item(self, uid: str, item_id: str, *, course_id: Optional[str], new_course_title: Optional[str],
                    topic_id: Optional[str], new_topic_title: Optional[str], auto_topic: bool) -> Optional[dict]:
        return self.rpc("brain_refile_item", {
            "p_uid": uid, "p_item": item_id, "p_course": course_id, "p_new_course_title": new_course_title,
            "p_topic": topic_id, "p_new_topic_title": new_topic_title, "p_auto_topic": auto_topic,
        })

    def counts(self, uid: str) -> dict[str, int]:
        def count(table: str, extra: Optional[dict[str, str]] = None) -> int:
            base, headers = self._base()
            response = self.session.get(
                f"{base}/{table}", params={"user_id": f"eq.{uid}", "select": "id", "limit": "1", **(extra or {})},
                headers={**headers, "Prefer": "count=exact"}, timeout=10,
            )
            response.raise_for_status()
            total = response.headers.get("Content-Range", "*/0").split("/")[-1]
            return int(total) if total.isdigit() else 0

        return {
            "items": count("brain_items", {"status": "eq.filed"}),
            "processing": count("brain_items", {"status": "in.(queued,extracting,classifying,linking)"}),
            "failed": count("brain_items", {"status": "eq.failed"}),
        }

    # ------------------------------------------------------------------ chunks

    def chunks(self, uid: str, item_id: str, limit: int = 50) -> list[dict]:
        return self._rows("brain_chunks", {"user_id": f"eq.{uid}", "item_id": f"eq.{item_id}",
                                           "select": CHUNK_COLUMNS, "order": "ordinal.asc", "limit": str(limit)})

    def chunks_by_ids(self, uid: str, ids: Sequence[str]) -> list[dict]:
        if not ids:
            return []
        return self._rows("brain_chunks", {"user_id": f"eq.{uid}", "id": _in(set(ids)), "select": CHUNK_COLUMNS})

    def chunks_for_items(self, uid: str, item_ids: Sequence[str], limit: int = 400) -> list[dict]:
        if not item_ids:
            return []
        return self._rows("brain_chunks", {"user_id": f"eq.{uid}", "item_id": _in(set(item_ids)),
                                           "select": CHUNK_COLUMNS, "order": "item_id,ordinal", "limit": str(limit)})

    def match_chunks(self, uid: str, embedding: list[float], *, limit: int = 12,
                     course_ids: Optional[Sequence[str]] = None, item_ids: Optional[Sequence[str]] = None) -> list[dict]:
        return self.rpc("brain_match_chunks", {"p_uid": uid, "p_embedding": embedding, "p_limit": limit,
                                               "p_course_ids": list(course_ids) if course_ids else None,
                                               "p_item_ids": list(item_ids) if item_ids else None}) or []

    def search_chunks(self, uid: str, query: str, limit: int = 20) -> list[dict]:
        return self.rpc("brain_search_chunks", {"p_uid": uid, "p_query": query, "p_limit": limit}) or []

    def chunk_concepts(self, uid: str, *, chunk_ids: Optional[Sequence[str]] = None,
                       concept_ids: Optional[Sequence[str]] = None, limit: int = 500) -> list[dict]:
        params = {"user_id": f"eq.{uid}", "select": "chunk_id,concept_id", "limit": str(limit)}
        if chunk_ids is not None:
            if not chunk_ids:
                return []
            params["chunk_id"] = _in(set(chunk_ids))
        if concept_ids is not None:
            if not concept_ids:
                return []
            params["concept_id"] = _in(set(concept_ids))
        return self._rows("brain_chunk_concepts", params)

    # ------------------------------------------------------------------ courses, topics, concepts, links

    def graph(self, uid: str) -> dict:
        return self.rpc("brain_graph", {"p_uid": uid}, timeout=20)

    def courses(self, uid: str) -> list[dict]:
        return self._rows("brain_courses", {"user_id": f"eq.{uid}", "select": "*", "order": "created_at.asc"})

    def course(self, uid: str, course_id: str) -> Optional[dict]:
        return self._one("brain_courses", {"id": f"eq.{course_id}", "user_id": f"eq.{uid}", "select": "*"})

    def rename_course(self, uid: str, course_id: str, title: str) -> Optional[dict]:
        rows = self.request("PATCH", "brain_courses", params={"id": f"eq.{course_id}", "user_id": f"eq.{uid}", "select": "*"},
                            payload={"title": title, "created_by": "user"}, prefer="return=representation")
        return rows[0] if rows else None

    def topics(self, uid: str, course_id: Optional[str] = None) -> list[dict]:
        params = {"user_id": f"eq.{uid}", "select": "*", "order": "sequence.asc.nullslast,created_at.asc"}
        if course_id:
            params["course_id"] = f"eq.{course_id}"
        return self._rows("brain_topics", params)

    def concepts(self, uid: str, *, ids: Optional[Sequence[str]] = None, course_id: Optional[str] = None,
                 with_embedding: bool = False) -> list[dict]:
        columns = "id,course_id,topic_id,name,summary,created_at" + (",embedding" if with_embedding else "")
        params = {"user_id": f"eq.{uid}", "select": columns, "order": "created_at.asc"}
        if ids is not None:
            if not ids:
                return []
            params["id"] = _in(set(ids))
        if course_id:
            params["course_id"] = f"eq.{course_id}"
        return self._rows("brain_concepts", params)

    def match_concepts(self, uid: str, embedding: list[float], *, exclude: Sequence[str] = (), limit: int = 8,
                       min_similarity: float = 0.5) -> list[dict]:
        return self.rpc("brain_match_concepts", {"p_uid": uid, "p_embedding": embedding, "p_exclude": list(exclude),
                                                 "p_limit": limit, "p_min_similarity": min_similarity}) or []

    def links(self, uid: str, concept_ids: Optional[Sequence[str]] = None) -> list[dict]:
        params = {"user_id": f"eq.{uid}", "select": "*", "order": "created_at.asc"}
        if concept_ids is not None:
            if not concept_ids:
                return []
            ids = ",".join(set(concept_ids))
            params["or"] = f"(source_concept_id.in.({ids}),target_concept_id.in.({ids}))"
        return self._rows("brain_concept_links", params)

    def add_links(self, uid: str, links: list[dict]) -> list[str]:
        if not links:
            return []
        result = self.rpc("brain_add_links", {"p_uid": uid, "p_links": links}) or []
        return [row if isinstance(row, str) else row.get("brain_add_links") for row in result]

    def links_by_ids(self, uid: str, ids: Sequence[str]) -> list[dict]:
        if not ids:
            return []
        return self._rows("brain_concept_links", {"user_id": f"eq.{uid}", "id": _in(ids), "select": "*"})

    def refile_events(self, uid: str, limit: int = 12) -> list[dict]:
        return self._rows("brain_refile_events", {"user_id": f"eq.{uid}", "select": "*", "order": "created_at.desc",
                                                  "limit": str(limit)})

    # ------------------------------------------------------------------ plans

    def claim_plan(self, record: dict[str, Any]) -> Optional[dict]:
        rows = self.request("POST", "brain_study_plans", params={"on_conflict": "id"}, payload=record,
                            prefer="resolution=ignore-duplicates,return=representation")
        return rows[0] if rows else None

    def plan(self, uid: str, plan_id: str) -> Optional[dict]:
        return self._one("brain_study_plans", {"id": f"eq.{plan_id}", "user_id": f"eq.{uid}", "select": "*"})

    def plans(self, uid: str, course_id: str, limit: int = 10) -> list[dict]:
        return self._rows("brain_study_plans", {"user_id": f"eq.{uid}", "course_id": f"eq.{course_id}", "select": "*",
                                                "order": "created_at.desc", "limit": str(limit)})

    def finish_plan(self, uid: str, plan_id: str, changes: dict[str, Any]) -> Optional[dict]:
        rows = self.request("PATCH", "brain_study_plans",
                            params={"id": f"eq.{plan_id}", "user_id": f"eq.{uid}", "status": "eq.generating", "select": "*"},
                            payload=changes, prefer="return=representation")
        return rows[0] if rows else None

    def save_plan_secrets(self, uid: str, plan_id: str, answer_key: dict) -> None:
        self.request("POST", "brain_plan_secrets", params={"on_conflict": "plan_id"},
                     payload={"plan_id": plan_id, "user_id": uid, "answer_key": answer_key},
                     prefer="resolution=merge-duplicates,return=minimal")

    def plan_secrets(self, uid: str, plan_id: str) -> Optional[dict]:
        row = self._one("brain_plan_secrets", {"plan_id": f"eq.{plan_id}", "user_id": f"eq.{uid}", "select": "answer_key"})
        return row["answer_key"] if row else None

    def add_attempt(self, record: dict[str, Any]) -> dict:
        return self.request("POST", "brain_quiz_attempts", payload=record, prefer="return=representation")[0]

    # ------------------------------------------------------------------ Telegram

    def telegram_link(self, uid: str) -> Optional[dict]:
        return self._one("brain_telegram_links", {"user_id": f"eq.{uid}", "select": "*"})

    def telegram_link_for_chat(self, chat_id: int) -> Optional[dict]:
        return self._one("brain_telegram_links", {"chat_id": f"eq.{chat_id}", "select": "*"})

    def save_telegram_code(self, uid: str, code_hash: str, expires_at: datetime) -> None:
        self.request("POST", "brain_telegram_codes", payload={
            "code_hash": code_hash, "user_id": uid, "expires_at": expires_at.astimezone(timezone.utc).isoformat()},
            prefer="return=minimal")

    def redeem_telegram_code(self, code_hash: str, chat_id: int, telegram_user_id: Optional[int],
                             username: Optional[str]) -> Optional[str]:
        return self.rpc("brain_redeem_telegram_code", {"p_code_hash": code_hash, "p_chat_id": chat_id,
                                                       "p_telegram_user_id": telegram_user_id, "p_username": username})

    def unlink_telegram(self, uid: str) -> None:
        self.request("DELETE", "brain_telegram_links", params={"user_id": f"eq.{uid}"})


brain_store = BrainStore()
