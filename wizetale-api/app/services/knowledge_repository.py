"""Server-side access to the shared, reviewed knowledge library."""

from __future__ import annotations

from typing import Any

import requests

from app.core.config import settings


class SupabaseKnowledgeRepository:
    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()

    def search(self, query: str, subject: str, grade_band: str) -> list[dict[str, Any]]:
        if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
            return []

        response = self.session.request(
            "POST",
            f"{settings.SUPABASE_URL.rstrip('/')}/rest/v1/rpc/search_knowledge_entries",
            json={
                "query_text": query,
                "subject_filter": subject,
                "grade_band_filter": grade_band,
                "result_limit": 3,
            },
            headers={
                "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
                "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
                "Content-Type": "application/json",
            },
            timeout=10,
        )
        response.raise_for_status()
        return response.json()


knowledge_repository = SupabaseKnowledgeRepository()
