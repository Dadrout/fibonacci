"""Original captures and thumbnails, plus short-lived signed media URLs.

Objects live under `<user_id>/<item_id>/<name>` either on a local volume (offline demo,
development) or in the private Supabase Storage bucket `brain-captures`. Browsers fetch
them through `/api/v1/brain/media/<token>`; the token is an HMAC over owner, path, type,
and expiry, so `<img>`/`<audio>` work without auth headers and links expire.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import time
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)
BUCKET = "brain-captures"
MEDIA_PREFIX = "/api/v1/brain/media/"


class BlobError(RuntimeError):
    pass


def object_path(uid: str, item_id: str, name: str) -> str:
    safe = "".join(ch for ch in name if ch.isalnum() or ch in "._-")[:80] or "file"
    return f"{uid}/{item_id}/{safe}"


class BlobStore:
    def __init__(self, session: Optional[requests.Session] = None):
        self.session = session or requests.Session()

    @property
    def local(self) -> bool:
        return settings.BRAIN_BLOB_STORE.strip().lower() != "supabase"

    def _local_path(self, path: str) -> Path:
        root = Path(settings.BRAIN_MEDIA_DIR).resolve()
        target = (root / path).resolve()
        if root not in target.parents:
            raise BlobError("Invalid object path")
        return target

    def _storage(self, method: str, path: str, **kwargs) -> requests.Response:
        key = settings.SUPABASE_SERVICE_ROLE_KEY
        if not settings.SUPABASE_URL or not key:
            raise BlobError("Supabase Storage is not configured")
        response = self.session.request(
            method, f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1/{path}",
            headers={"apikey": key, "Authorization": f"Bearer {key}", **kwargs.pop("headers", {})}, timeout=30, **kwargs,
        )
        response.raise_for_status()
        return response

    def put(self, path: str, data: bytes, content_type: str) -> None:
        if self.local:
            target = self._local_path(path)
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_suffix(target.suffix + ".tmp")
            tmp.write_bytes(data)
            os.replace(tmp, target)
            return
        self._storage("POST", f"object/{BUCKET}/{quote(path, safe='/')}", data=data,
                      headers={"Content-Type": content_type or "application/octet-stream", "x-upsert": "true"})

    def get(self, path: str) -> bytes:
        if self.local:
            target = self._local_path(path)
            if not target.exists():
                raise BlobError("Object not found")
            return target.read_bytes()
        return self._storage("GET", f"object/{BUCKET}/{quote(path, safe='/')}").content

    def delete_prefix(self, prefix: str) -> None:
        """Remove every object under `<uid>/<item_id>/` (or `<uid>/`)."""
        if not prefix or prefix.count("/") < 1:
            raise BlobError("Refusing to delete without an owner prefix")
        if self.local:
            root = self._local_path(prefix.rstrip("/"))
            if root.is_dir():
                for child in sorted(root.rglob("*"), reverse=True):
                    child.unlink() if child.is_file() else child.rmdir()
                root.rmdir()
            return
        while True:
            rows = self._storage("POST", f"object/list/{BUCKET}", json={"prefix": prefix, "limit": 1000, "offset": 0}).json()
            names = [f"{prefix.rstrip('/')}/{row['name']}" for row in rows if row.get("id")]
            if not names:
                break
            self._storage("DELETE", f"object/{BUCKET}", json={"prefixes": names})


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _secret() -> bytes:
    secret = settings.BRAIN_MEDIA_SECRET
    if not secret:
        if settings.ENVIRONMENT.strip().lower() == "production":
            raise BlobError("BRAIN_MEDIA_SECRET is not configured")
        # Development without a secret: derive one from the service key so links still work locally.
        secret = hashlib.sha256((settings.BRAIN_LOCAL_SERVICE_KEY or settings.SUPABASE_SERVICE_ROLE_KEY or "dev").encode()).hexdigest()
    return secret.encode()


def sign_media(uid: str, path: Optional[str], mime: Optional[str], ttl: Optional[int] = None) -> Optional[str]:
    """Same-origin URL for an owned object, or None when there is nothing to show."""
    if not path:
        return None
    if not path.startswith(f"{uid}/"):
        raise BlobError("Object does not belong to this user")
    claims = {"u": uid, "p": path, "m": mime or "application/octet-stream",
              "e": int(time.time()) + (ttl or settings.BRAIN_MEDIA_TTL_SECONDS)}
    body = _b64(json.dumps(claims, separators=(",", ":")).encode())
    signature = _b64(hmac.new(_secret(), body.encode(), hashlib.sha256).digest())
    return f"{MEDIA_PREFIX}{body}.{signature}"


def verify_media(token: str) -> Optional[dict]:
    """Return {u, p, m, e} for a valid, unexpired token; None otherwise."""
    try:
        body, signature = token.split(".", 1)
        expected = _b64(hmac.new(_secret(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(expected, signature):
            return None
        claims = json.loads(_unb64(body))
        if int(claims["e"]) < time.time() or not str(claims["p"]).startswith(f"{claims['u']}/"):
            return None
        return claims
    except (ValueError, KeyError, TypeError):
        return None


blob_store = BlobStore()
