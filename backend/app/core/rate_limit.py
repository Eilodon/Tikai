"""
Shared rate limiter — extracted from main.py to avoid circular imports.

INVARIANT: routers import `limiter` from here, NOT from app.main.
main.py also imports from here and registers it on the FastAPI app.

This fixes a circular import: routers like insights.py needed @limiter.limit()
but importing from app.main caused chicken-and-egg (main.py imports routers,
routers import main.py).
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

# Per-IP rate limiter — for per-shop limiting, individual route decorators
# extract shop_id from JWT after auth dependency
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
