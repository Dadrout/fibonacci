from fastapi import Depends, HTTPException, Request, status
from app.core.config import settings
import logging
import requests
from starlette.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)

async def get_current_user(request: Request):
    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid Supabase access token is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not settings.SUPABASE_URL or not settings.SUPABASE_PUBLISHABLE_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase authentication is not configured.",
        )

    try:
        response = await run_in_threadpool(
            requests.get,
            f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/user",
            headers={
                "apikey": settings.SUPABASE_PUBLISHABLE_KEY,
                "Authorization": f"Bearer {token.strip()}",
            },
            timeout=5,
        )
    except requests.RequestException as error:
        logger.warning("Supabase token verification request failed: %s", error)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is temporarily unavailable.",
        ) from error

    if response.status_code == 429 or response.status_code >= 500:
        raise HTTPException(
            status_code=503,
            detail="Authentication service is temporarily unavailable. Please try again shortly.",
        )
    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user = response.json()
    except ValueError as error:
        raise HTTPException(status_code=401, detail="Invalid authentication response.") from error
    if not isinstance(user, dict) or not user.get("id"):
        raise HTTPException(status_code=401, detail="Invalid authentication response.")
    return {"uid": user["id"], "email": user.get("email")}


async def consume_user_rate_limit(redis_client, user_id: str, action: str, limit: int, window_seconds: int) -> None:
    """Atomically count one user action and reject excess requests."""
    key = f"talespark:rate-limit:{action}:{user_id}"
    try:
        pipeline = redis_client.pipeline(transaction=True)
        pipeline.incr(key)
        pipeline.expire(key, window_seconds, nx=True)
        pipeline.ttl(key)
        results = await pipeline.execute()
    except Exception as error:
        logger.warning("Redis request limiting is unavailable (%s)", type(error).__name__)
        raise HTTPException(status_code=503, detail="Request limiting is temporarily unavailable.") from error
    if int(results[0]) > limit:
        retry_after = max(1, int(results[2]))
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Try again shortly.",
            headers={"Retry-After": str(retry_after)},
        )


def rate_limit_user_action(action: str, limit: int, window_seconds: int = 60):
    async def enforce_limit(request: Request, user: dict = Depends(get_current_user)) -> None:
        redis_client = getattr(request.app.state, "redis_client", None)
        if redis_client is None:
            raise HTTPException(status_code=503, detail="Request limiting is temporarily unavailable.")
        user_id = user.get("uid")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authenticated user ID is missing")
        await consume_user_rate_limit(redis_client, str(user_id), action, limit, window_seconds)

    enforce_limit.rate_limit_spec = (action, limit, window_seconds)
    return enforce_limit
