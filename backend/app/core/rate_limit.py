"""
Shared rate limiter — extracted from main.py to avoid circular imports.

INVARIANT: routers import `limiter` from here, NOT from app.main.
main.py also imports from here and registers it on the FastAPI app.

This fixes a circular import: routers like insights.py needed @limiter.limit()
but importing from app.main caused chicken-and-egg (main.py imports routers,
routers import main.py).
"""

from slowapi import Limiter
from starlette.requests import Request


def _get_real_ip(request: Request) -> str:
    # Railway APPENDS the real client IP as the LAST entry in X-Forwarded-For.
    # Taking [0] is spoofable: attacker sends "X-Forwarded-For: fake-ip" →
    # Railway produces "fake-ip, real-ip" → [0] returns fake-ip → rate limit bypass.
    # [-1] is always Railway's own observation and cannot be forged by the client.
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    entries = [e.strip() for e in forwarded_for.split(",") if e.strip()]
    if entries:
        return entries[-1]
    return (request.client.host if request.client else None) or "unknown"


# F-C1-04: Per-IP rate limiter (shared NAT trade-off accepted for now)
# Individual routers can override with shop_id-based limits if needed.
# DESIGN: Per-IP avoids complex Redis key management; per-shop requires
# auth + lookup on every request. Post-launch optimization if abuse detected.
limiter = Limiter(key_func=_get_real_ip, default_limits=["200/minute"])
