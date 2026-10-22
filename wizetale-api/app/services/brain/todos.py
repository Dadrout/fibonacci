"""To-dos: tasks the student types in the app or sends to the Telegram bot (owner-read RLS, server writes)."""
from __future__ import annotations

from typing import Optional

from app.services.brain import events
from app.services.brain.store import BrainStore, brain_store

COLUMNS = "id,title,due,done,source,created_at"


def _clip(value: Optional[str], limit: int) -> Optional[str]:
    value = " ".join((value or "").split())[:limit]
    return value or None


def list_todos(uid: str, store: BrainStore = brain_store) -> list[dict]:
    return store.request("GET", "brain_todos", params={"user_id": f"eq.{uid}", "select": COLUMNS,
                                                       "order": "done.asc,created_at.desc", "limit": "200"}) or []


def create_many(uid: str, todos: list[tuple[str, Optional[str]]], source: str, store: BrainStore = brain_store) -> list[dict]:
    rows = [{"user_id": uid, "title": title, "due": _clip(due, 80), "source": source}
            for raw, due in todos if (title := _clip(raw, 300))]
    if not rows:
        return []
    created = store.request("POST", f"brain_todos?select={COLUMNS}", payload=rows, prefer="return=representation") or []
    events.publish(uid, "todos.changed")
    return created


def update(uid: str, todo_id: str, fields: dict, store: BrainStore = brain_store) -> Optional[dict]:
    rows = store.request("PATCH", f"brain_todos?select={COLUMNS}", params={"id": f"eq.{todo_id}", "user_id": f"eq.{uid}"},
                         payload=fields, prefer="return=representation") or []
    if rows:
        events.publish(uid, "todos.changed")
    return rows[0] if rows else None


def delete(uid: str, todo_id: str, store: BrainStore = brain_store) -> bool:
    rows = store.request("DELETE", "brain_todos", params={"id": f"eq.{todo_id}", "user_id": f"eq.{uid}"},
                         prefer="return=representation") or []
    if rows:
        events.publish(uid, "todos.changed")
    return bool(rows)
