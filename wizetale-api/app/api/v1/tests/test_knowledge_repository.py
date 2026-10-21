import requests

from app.core.config import settings
from app.services.knowledge_repository import SupabaseKnowledgeRepository


def test_search_uses_database_rpc_with_subject_and_grade_scope(monkeypatch):
    monkeypatch.setattr(settings, "SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "server-only-test-key")
    response = requests.Response()
    response.status_code = 200
    response._content = b'[{"canonical_topic":"The Silk Road","match_type":"grounded"}]'
    calls = []

    def fake_request(_session, method, url, **kwargs):
        calls.append((method, url, kwargs))
        return response

    monkeypatch.setattr(requests.Session, "request", fake_request)
    repository = SupabaseKnowledgeRepository()

    entries = repository.search("The Silk Road", "history", "13-15")

    assert entries[0]["canonical_topic"] == "The Silk Road"
    method, url, kwargs = calls[0]
    assert method == "POST"
    assert url.endswith("/rest/v1/rpc/search_knowledge_entries")
    assert kwargs["json"] == {
        "query_text": "The Silk Road",
        "subject_filter": "history",
        "grade_band_filter": "13-15",
        "result_limit": 3,
    }
    assert kwargs["headers"]["Authorization"] == "Bearer server-only-test-key"


def test_repository_returns_no_entries_when_supabase_is_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "SUPABASE_URL", None)
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_ROLE_KEY", None)

    assert SupabaseKnowledgeRepository().search("The Silk Road", "history", "13-15") == []


def test_knowledge_service_builds_source_context_and_marks_exact_match_grounded():
    from app.services.knowledge_service import KnowledgeService

    entry = {
        "canonical_topic": "The Silk Road",
        "match_type": "exact",
        "facts": ["Routes linked many regions through trade."],
        "sources": [{"title": "UNESCO Silk Roads", "url": "https://example.org/silk-roads"}],
    }
    service = KnowledgeService(repository=type("Repo", (), {"search": lambda *_: [entry]})())

    result = service.retrieve("The Silk Road", "history", "13-15")

    assert result.status == "grounded"
    assert "Routes linked many regions through trade." in result.prompt_context
    assert result.sources == entry["sources"]


def test_knowledge_service_marks_keyword_only_match_partial():
    from app.services.knowledge_service import KnowledgeService

    service = KnowledgeService(repository=type(
        "Repo", (), {"search": lambda *_: [{"match_type": "partial", "facts": [], "sources": []}]}
    )())

    assert service.retrieve("Silk routes", "history", "13-15").status == "partial"


def test_knowledge_service_returns_empty_context_when_no_entry_matches():
    from app.services.knowledge_service import KnowledgeService

    service = KnowledgeService(repository=type("Repo", (), {"search": lambda *_: []})())

    result = service.retrieve("Uncatalogued topic", "history", "13-15")

    assert result.status == "none"
    assert result.prompt_context == ""
    assert result.sources == []
