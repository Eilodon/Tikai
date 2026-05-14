"""
Shared ARQ connection pool — singleton with health check + dead-pool detection.

INVARIANT: ALL routers and tasks that enqueue ARQ jobs must use get_arq_pool()
from this module. Never import ArqRedis.from_url() directly elsewhere.

FIX v0.5.2: actions.py was creating a new Redis connection per request.
Extracted to shared module so imports.py + actions.py + future routers reuse same pool.
"""

import asyncio

import structlog

log = structlog.get_logger()

_arq_pool = None
_arq_lock = asyncio.Lock()


async def get_arq_pool():
    """Get or create singleton ARQ Redis pool with health check.

    - asyncio.Lock prevents race when multiple coroutines initialize simultaneously
    - ping() health check detects dead pools after Redis restart
    - Auto-recreate on connection error (no manual app restart needed)
    """
    global _arq_pool
    async with _arq_lock:
        if _arq_pool is not None:
            try:
                # ADR-ASYNC-005: timeout prevents lock starvation when Redis is slow (not dead).
                # Without timeout, all concurrent callers pile up on _arq_lock during a Redis
                # hiccup — 60 actions/min × lock wait = cascading 503s. 2s covers normal RTT.
                await asyncio.wait_for(_arq_pool.ping(), timeout=2.0)
                return _arq_pool
            except TimeoutError:
                log.warning("arq.pool_ping_timeout")
                try:
                    await _arq_pool.close()
                except Exception:
                    pass
                _arq_pool = None
            except Exception as e:
                log.warning("arq.pool_dead_recreating", error=str(e))
                try:
                    await _arq_pool.close()
                except Exception:
                    pass
                _arq_pool = None
        if _arq_pool is None:
            from arq.connections import ArqRedis

            from app.core.config import get_settings

            s = get_settings()
            _arq_pool = await ArqRedis.from_url(s.redis_url)
        return _arq_pool


async def close_arq_pool() -> None:
    """Close the pool — call on app shutdown."""
    global _arq_pool
    async with _arq_lock:
        if _arq_pool is not None:
            try:
                await _arq_pool.close()
            except Exception as e:
                log.warning("arq.close_failed", error=str(e))
            _arq_pool = None
