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
    # Railway sets X-Forwarded-For with the real client IP as the first entry.
    # get_remote_address() would return the proxy IP, causing all users to share
    # a single rate-limit bucket (false throttling) or allow IP spoofing via header.
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return (request.client.host if request.client else None) or "unknown"


# F-C1-04: Per-IP rate limiter (shared NAT trade-off accepted for now)
# Individual routers can override with shop_id-based limits if needed.
# DESIGN: Per-IP avoids complex Redis key management; per-shop requires
# auth + lookup on every request. Post-launch optimization if abuse detected.
limiter = Limiter(key_func=_get_real_ip, default_limits=["200/minute"])
