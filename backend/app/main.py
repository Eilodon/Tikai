"""
FastAPI entrypoint.
FIX ISSUE-08: Sentry initialized on startup.
LOW-3: Rate limiting via slowapi.
LOW-6: /healthz and /readyz endpoints for Docker + k8s health probes.
v1.0.0: Version string updated from hardcoded "0.4.0" to "1.0.0".
"""

import time
import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.errors import register_exception_handlers
from app.api.v1 import (
    actions,
    admin,
    cogs,
    creators,
    demo,
    imports,
    insights,
    inventory,
    livestream,
    reconcile,
    shops,
    tools,
    weekly_receipts,
)
from app.core.config import get_settings
from app.core.database import engine
from app.core.logging import configure_logging
from app.core.rate_limit import limiter
from app.core.storage import close_client as close_storage_client

APP_VERSION = "2.2.0"

settings = get_settings()
configure_logging()
log = structlog.get_logger()


def _init_sentry() -> None:
    """FIX ISSUE-08: Initialize Sentry if DSN is configured."""
    if not settings.sentry_dsn:
        return
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        integrations=[FastApiIntegration(), SqlalchemyIntegration()],
        traces_sample_rate=0.1 if settings.is_production else 0.0,
        send_default_pii=False,
    )
    log.info("sentry.initialized")


async def _startup_checks() -> None:
    """ADR-FIN-002 + ADR-AI-003: log operator-critical state at startup.

    Fee config: a missing Shopee config at import time causes silent fallback to TikTok
    rates → wrong P&L for all Shopee sellers. Log CRITICAL so ops catches it before sellers.

    AI models: log which model strings are active so deprecation is visible in startup logs
    without making a live Anthropic call (avoids blocking startup on network issues).
    """
    from sqlalchemy import text as sa_text

    from app.core.database import AsyncSessionLocal
    from app.services.ai.client import MODEL_SMALL, MODEL_STANDARD

    log.info("ai.models_active", standard=MODEL_STANDARD, small=MODEL_SMALL)

    try:
        async with AsyncSessionLocal() as db:
            count = await db.scalar(
                sa_text("SELECT COUNT(*) FROM fee_configs WHERE platform = 'shopee'")
            )
            if not count:
                log.critical(
                    "startup.fee_config_missing",
                    platform="shopee",
                    detail="No Shopee fee config found — Shopee imports will use TikTok rates (wrong P&L)",
                )
            else:
                log.info("startup.fee_config_ok", platform="shopee", count=count)
    except Exception as e:
        log.warning("startup.fee_config_check_failed", error=str(e))


@asynccontextmanager
async def lifespan(app: FastAPI):
    _init_sentry()
    log.info("tikai.startup", environment=settings.environment, version=APP_VERSION)
    await _startup_checks()
    yield
    from app.core.arq_pool import close_arq_pool

    await close_arq_pool()
    await engine.dispose()
    await close_storage_client()
    log.info("tikai.shutdown")


app = FastAPI(
    title="Tikai API",
    version=APP_VERSION,
    default_response_class=ORJSONResponse,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url=None,
    lifespan=lifespan,
)

# ── Middleware ────────────────────────────────────────────────────────────────

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def request_telemetry(request: Request, call_next):
    """Structured request log with latency and correlation id for ops triage."""
    start = time.perf_counter()
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        log.exception(
            "http.request_failed",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            duration_ms=duration_ms,
        )
        raise

    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    response.headers["x-request-id"] = request_id
    if request.url.path not in {"/healthz", "/readyz", "/health"}:
        log.info(
            "http.request",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
    return response


register_exception_handlers(app)

# ── Routes ────────────────────────────────────────────────────────────────────

app.include_router(shops.router, prefix="/v1", tags=["shops"])
app.include_router(imports.router, prefix="/v1", tags=["imports"])
app.include_router(insights.router, prefix="/v1", tags=["insights"])
app.include_router(actions.router, prefix="/v1", tags=["actions"])
app.include_router(cogs.router, prefix="/v1", tags=["cogs"])
app.include_router(weekly_receipts.router, prefix="/v1", tags=["weekly-receipts"])
app.include_router(livestream.router, prefix="/v1", tags=["livestream"])
app.include_router(tools.router, prefix="/v1", tags=["tools"])
app.include_router(reconcile.router, prefix="/v1", tags=["reconcile"])
app.include_router(inventory.router, prefix="/v1", tags=["inventory"])
app.include_router(demo.router, prefix="/v1", tags=["demo"])
app.include_router(creators.router, prefix="/v1", tags=["creators"])
app.include_router(admin.router, prefix="/v1", tags=["admin"])

# ── Health Endpoints ──────────────────────────────────────────────────────────


@app.get("/healthz", tags=["ops"], include_in_schema=False)
async def healthz():
    """Liveness probe — Docker / Railway / k8s."""
    return {"status": "ok", "version": APP_VERSION}


@app.get("/readyz", tags=["ops"], include_in_schema=False)
async def readyz():
    """Readiness probe — checks DB, Redis, and Storage before accepting traffic."""
    from sqlalchemy import text as sa_text

    from app.core.database import AsyncSessionLocal
    from app.core.redis import get_redis

    errors: dict[str, str] = {}

    try:
        async with AsyncSessionLocal() as db:
            await db.execute(sa_text("SELECT 1"))
    except Exception as e:
        errors["db"] = str(e)

    try:
        r = await get_redis()
        await r.ping()
    except Exception as e:
        errors["redis"] = str(e)

    try:
        from app.core.storage import check_storage_ready

        await check_storage_ready()
    except Exception as e:
        errors["storage"] = str(e)

    if errors:
        return ORJSONResponse(
            status_code=503,
            content={"status": "not_ready", "errors": errors},
        )
    return {"status": "ready", "db": "ok", "redis": "ok", "storage": "ok"}


@app.get("/health", tags=["ops"], include_in_schema=False)
async def health():
    """Legacy health endpoint — kept for backward compat. Prefer /healthz.
    ADR-SEC-006: removed 'environment' and 'rule_engine' fields — no auth required
    on this endpoint so exposing them helps attackers fingerprint the stack.
    """
    return {"status": "ok", "version": APP_VERSION}
