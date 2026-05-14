import asyncio
import json
from typing import Any

from redis.asyncio import Redis, from_url

from app.core.config import get_settings

settings = get_settings()

_redis_client: Redis | None = None
_redis_lock = asyncio.Lock()  # F-2-04: prevent race condition on cold start


async def get_redis() -> Redis:
    global _redis_client
    # F-2-04: double-checked locking (mirrors arq_pool.py pattern)
    if _redis_client is not None:
        return _redis_client
    async with _redis_lock:
        if _redis_client is None:
            _redis_client = from_url(settings.redis_url, decode_responses=True)
    return _redis_client


async def cache_get(key: str) -> Any | None:
    r = await get_redis()
    value = await r.get(key)
    if value is None:
        return None
    return json.loads(value)


async def cache_set(key: str, value: Any, ttl_seconds: int) -> None:
    r = await get_redis()
    await r.set(key, json.dumps(value, default=str), ex=ttl_seconds)


async def cache_delete(key: str) -> None:
    r = await get_redis()
    await r.delete(key)


async def cache_get_safe(key: str) -> Any | None:
    """FIX P0-5: Fail-open cache_get — Redis down → return None, never raise.

    AI functions must not crash when Redis is unavailable.
    Worst case: cache miss → re-run AI call → slightly higher cost, correct behavior.
    Hard dependency on Redis for cache was blocking tests and causing Aha Moment
    failures in environments without Redis (CI, local dev without Docker).
    """
    try:
        return await cache_get(key)
    except Exception as e:
        import structlog
        structlog.get_logger().warning("redis.cache_get_failed_open", key=key, error=str(e))
        return None


async def cache_set_safe(key: str, value: Any, ttl_seconds: int) -> None:
    """FIX P0-5: Fail-open cache_set — Redis down → skip caching silently, never raise."""
    try:
        await cache_set(key, value, ttl_seconds)
    except Exception as e:
        import structlog
        structlog.get_logger().warning("redis.cache_set_failed_open", key=key, error=str(e))


def ai_narrative_cache_key(shop_id: str, snapshot_id: str, function_name: str) -> str:
    """Stable cache key for AI narratives. Invalidated when snapshot changes."""
    return f"ai_narrative:{shop_id}:{snapshot_id}:{function_name}"
