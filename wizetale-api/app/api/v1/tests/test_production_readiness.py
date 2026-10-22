import asyncio

import pytest
from fastapi import HTTPException

from app.api import dependencies
from app.core.config import Settings


def test_production_configuration_lists_missing_required_settings():
    settings = Settings(
        ENVIRONMENT="production",
        MEDIA_STORAGE_PROVIDER="r2",
        API_ALLOWED_ORIGINS="https://example.test",
        SUPABASE_URL=None,
        SUPABASE_PUBLISHABLE_KEY=None,
        SUPABASE_SERVICE_ROLE_KEY=None,
        GEMINI_API_KEY=None,
        R2_ENDPOINT_URL=None,
        R2_ACCESS_KEY_ID=None,
        R2_SECRET_ACCESS_KEY=None,
        R2_BUCKET_NAME=None,
    )

    errors = settings.production_configuration_errors()

    assert "SUPABASE_URL" in errors
    assert "SUPABASE_PUBLISHABLE_KEY" in errors
    assert "SUPABASE_SERVICE_ROLE_KEY" in errors
    assert "GEMINI_API_KEY" in errors
    assert "R2_ACCESS_KEY_ID" in errors


def test_production_configuration_accepts_configured_active_providers():
    settings = Settings(
        ENVIRONMENT="production",
        SUPABASE_URL="https://project.supabase.co",
        SUPABASE_PUBLISHABLE_KEY="publishable-test-key",
        SUPABASE_SERVICE_ROLE_KEY="service-test-key",
        BRAIN_MEDIA_SECRET="brain-media-test-secret",
        GEMINI_API_KEY="gemini-test-key",
        GEMINI_BILLING_TIER="paid",
        AI_PROVIDER="gemini",
        IMAGE_PROVIDER="gemini",
        TTS_PROVIDER="edge",
        MEDIA_STORAGE_PROVIDER="supabase",
        API_ALLOWED_ORIGINS="https://example.test",
        REDIS_URL="redis://redis:6379/0",
    )

    assert settings.production_configuration_errors() == []


def test_production_configuration_rejects_debug_mode():
    settings = Settings(ENVIRONMENT="production", DEBUG=True)

    assert "DEBUG must be false" in settings.production_configuration_errors()


def test_production_configuration_requires_paid_gemini_tier():
    settings = Settings(
        ENVIRONMENT="production",
        SUPABASE_URL="https://project.supabase.co",
        SUPABASE_PUBLISHABLE_KEY="publishable-test-key",
        SUPABASE_SERVICE_ROLE_KEY="service-test-key",
        GEMINI_API_KEY="gemini-test-key",
        GEMINI_BILLING_TIER="unknown",
        R2_ENDPOINT_URL="https://account.r2.cloudflarestorage.com",
        R2_ACCESS_KEY_ID="r2-access-test-key",
        R2_SECRET_ACCESS_KEY="r2-secret-test-key",
        R2_BUCKET_NAME="stories",
        REDIS_URL="redis://redis:6379/0",
    )

    assert "GEMINI_BILLING_TIER must be paid" in settings.production_configuration_errors()


def test_production_configuration_rejects_sample_values():
    settings = Settings(
        ENVIRONMENT="production",
        SUPABASE_URL="https://YOUR_PROJECT.supabase.co",
        SUPABASE_PUBLISHABLE_KEY="YOUR_SUPABASE_PUBLISHABLE_KEY",
        SUPABASE_SERVICE_ROLE_KEY="YOUR_SUPABASE_SERVICE_ROLE_KEY",
        AI_PROVIDER="none",
        IMAGE_PROVIDER="none",
        TTS_PROVIDER="edge",
        MEDIA_STORAGE_PROVIDER="supabase",
        REDIS_URL="redis://redis:6379/0",
    )

    errors = settings.production_configuration_errors()

    assert "SUPABASE_URL" in errors
    assert "SUPABASE_PUBLISHABLE_KEY" in errors
    assert "SUPABASE_SERVICE_ROLE_KEY" in errors


def test_production_configuration_rejects_wildcard_or_insecure_origins():
    wildcard = Settings(
        ENVIRONMENT="production",
        API_ALLOWED_ORIGINS="*",
        GEMINI_API_KEY="gemini-test-key",
        GEMINI_BILLING_TIER="paid",
        TTS_PROVIDER="edge",
        MEDIA_STORAGE_PROVIDER="supabase",
    )
    http_origin = Settings(
        ENVIRONMENT="production",
        API_ALLOWED_ORIGINS="http://wizetale.com",
        GEMINI_API_KEY="gemini-test-key",
        GEMINI_BILLING_TIER="paid",
        TTS_PROVIDER="edge",
        MEDIA_STORAGE_PROVIDER="supabase",
    )

    assert "API_ALLOWED_ORIGINS must list explicit HTTPS origins" in wildcard.production_configuration_errors()
    assert "API_ALLOWED_ORIGINS must list explicit HTTPS origins" in http_origin.production_configuration_errors()


def test_production_configuration_requires_secure_service_origins():
    settings = Settings(
        ENVIRONMENT="production",
        SUPABASE_URL="http://project.supabase.co",
        R2_ENDPOINT_URL="https://account.r2.cloudflarestorage.com/path",
        AI_PROVIDER="none",
        IMAGE_PROVIDER="none",
        TTS_PROVIDER="edge",
        MEDIA_STORAGE_PROVIDER="supabase",
        REDIS_URL="redis://redis:6379/0",
    )

    errors = settings.production_configuration_errors()

    assert "SUPABASE_URL must be a valid HTTPS origin" in errors
    assert "R2_ENDPOINT_URL must be a valid HTTPS origin" in errors


def test_user_rate_limit_counts_are_isolated_by_user_and_expire():
    consume = getattr(dependencies, "consume_user_rate_limit", None)
    assert callable(consume), "an atomic Redis-backed user limiter must be available"

    class Pipeline:
        def __init__(self, store):
            self.store = store
            self.key = None
            self.window = None
            self.expire_nx = False

        def incr(self, key):
            self.key = key
            return self

        def expire(self, key, seconds, nx=False):
            self.window = seconds
            self.expire_nx = nx
            return self

        def ttl(self, key):
            self.ttl_key = key
            return self

        async def execute(self):
            self.store.counts[self.key] = self.store.counts.get(self.key, 0) + 1
            if not self.expire_nx or self.key not in self.store.ttls:
                self.store.ttls[self.key] = self.window
            return [self.store.counts[self.key], self.expire_nx, self.store.ttls[self.ttl_key]]

    class FakeRedis:
        def __init__(self):
            self.counts = {}
            self.ttls = {}

        def pipeline(self, transaction=True):
            pipeline = Pipeline(self)
            return pipeline

    redis_client = FakeRedis()
    key_a = "fibonacci:rate-limit:draft:learner-a"
    asyncio.run(consume(redis_client, "learner-a", "draft", 2, 60))
    redis_client.ttls[key_a] -= 20
    asyncio.run(consume(redis_client, "learner-a", "draft", 2, 60))
    assert redis_client.ttls[key_a] == 40
    with pytest.raises(HTTPException) as error:
        asyncio.run(consume(redis_client, "learner-a", "draft", 2, 60))
    assert error.value.status_code == 429
    assert error.value.headers["Retry-After"] == "40"
    asyncio.run(consume(redis_client, "learner-b", "draft", 2, 60))
    key_b = "fibonacci:rate-limit:draft:learner-b"
    assert redis_client.counts[key_b] == 1
    assert redis_client.ttls[key_b] == 60
    del redis_client.counts[key_a]
    del redis_client.ttls[key_a]
    asyncio.run(consume(redis_client, "learner-a", "draft", 2, 60))
    assert redis_client.counts[key_a] == 1
    assert redis_client.ttls[key_a] == 60


def test_ai_routes_use_user_rate_limits():
    from app.main import app

    def specs(path, method):
        from app.api.v1 import stories, generate
        assert method.lower() in app.openapi()["paths"][path]
        route = next(route for router in (stories.router, generate.router) for route in router.routes if route.path == path.removeprefix("/api/v1") and method in route.methods)
        return [
            getattr(dependency.call, "rate_limit_spec", None)
            for dependency in route.dependant.dependencies
        ]

    assert ("story-draft", 5, 60) in specs("/api/v1/story-drafts", "POST")
    assert ("story-render", 3, 60) in specs("/api/v1/story-drafts/{draft_id}/render", "POST")
    assert ("prompt-enhancement", 10, 60) in specs("/api/v1/enhance-prompt", "POST")
    assert ("ai-health", 10, 60) in specs("/api/v1/ai/health", "GET")
    assert ("story-history", 30, 60) in specs("/api/v1/stories", "GET")


def test_legacy_auth_module_reuses_supabase_user_verification():
    from app.services import auth_service

    assert auth_service.get_current_user is dependencies.get_current_user


def test_account_deletion_service_and_storage_cleanup_are_available():
    import importlib.util

    from app.services.story_repository import story_repository

    assert importlib.util.find_spec("app.services.account_deletion") is not None
    assert callable(getattr(story_repository, "delete_user_assets", None))

@pytest.mark.parametrize('upstream_status', [429, 500, 503])
def test_auth_provider_outage_does_not_reject_a_valid_session(monkeypatch, upstream_status):
    from starlette.requests import Request
    from types import SimpleNamespace
    monkeypatch.setattr(dependencies.settings, 'SUPABASE_URL', 'https://project.supabase.co')
    monkeypatch.setattr(dependencies.settings, 'SUPABASE_PUBLISHABLE_KEY', 'test-key')
    async def response(*args, **kwargs):
        return SimpleNamespace(status_code=upstream_status)
    monkeypatch.setattr(dependencies, 'run_in_threadpool', response)
    request = Request({'type':'http', 'headers':[(b'authorization', b'Bearer test-token')]})
    with pytest.raises(HTTPException) as error:
        asyncio.run(dependencies.get_current_user(request))
    assert error.value.status_code == 503
