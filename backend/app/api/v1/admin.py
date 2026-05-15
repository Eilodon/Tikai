"""
Admin-only endpoints. Protected by X-Admin-Key header matching ADMIN_SECRET env var.
Not in OpenAPI docs (include_in_schema=False).
"""

from datetime import date

import structlog
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.core.config import get_settings

router = APIRouter()
log = structlog.get_logger()
settings = get_settings()

_BENCHMARK_TTL = 90 * 24 * 3600  # 90 days in seconds


def _check_admin_key(request: Request) -> None:
    key = request.headers.get("X-Admin-Key", "")
    if not settings.admin_secret or key != settings.admin_secret:
        raise HTTPException(403, detail={"error": {"code": "FORBIDDEN"}})


class BenchmarkUpdateRequest(BaseModel):
    category: str
    metric: str  # "refund_rate" | "margin_pct" | "fee_burden_pct"
    value: str  # string to avoid float — caller sends "0.042"
    source: str
    note: str = ""


@router.post("/admin/benchmarks", include_in_schema=False)
async def update_benchmark(request: Request, body: BenchmarkUpdateRequest) -> dict:
    """Update industry benchmark override in Redis. TTL=90 days."""
    _check_admin_key(request)

    from app.core.redis import cache_set_safe

    key = f"tikai:benchmark:{body.category}:{body.metric}"
    payload = {
        "value": body.value,
        "source": body.source,
        "note": body.note,
        "updated_at": str(date.today()),
    }
    await cache_set_safe(key, payload, ttl_seconds=_BENCHMARK_TTL)

    log.info(
        "admin.benchmark_updated",
        category=body.category,
        metric=body.metric,
        source=body.source,
    )
    return {"status": "ok", "key": key, "value": body.value}
