"""
ARQ Worker.
FIX BUG-07: verify_action_impact registered in functions list.
v1.0.0: Removed duplicate `from datetime import...` inside loop body.
v2.1.0: Converted monolithic run_weekly_receipts to per-shop ARQ jobs.
"""

import uuid
from datetime import UTC, datetime, timedelta  # v1.0.0: module-level only

import structlog
from arq import cron
from arq.connections import RedisSettings
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.services.email.client import send_weekly_digest
from app.tasks.daily_alerts import trigger_daily_alerts
from app.tasks.process_import import process_import
from app.tasks.verify_action_impact import verify_action_impact

settings = get_settings()
log = structlog.get_logger()


async def startup(ctx: dict) -> None:
    # ADR-ARCH-004: reduced pool size — worker is a single process so 5+5=10 connections
    # is sufficient and leaves headroom for 2 API replicas (5+10 each = 30 total vs
    # Supabase Pro limit of 100 or free limit of 15).
    engine = create_async_engine(
        settings.database_url, pool_size=5, max_overflow=5, pool_pre_ping=True
    )
    # ADR-ARCH-005: store engine explicitly so shutdown() can dispose it cleanly.
    # async_sessionmaker has no public .kw attribute in SQLAlchemy 2.x — accessing
    # session_factory.kw raises AttributeError and the engine leaks on shutdown.
    ctx["db_engine"] = engine
    ctx["db_session_factory"] = async_sessionmaker(
        bind=engine, expire_on_commit=False, autoflush=False
    )
    log.info("arq.worker.startup", environment=settings.environment)


async def shutdown(ctx: dict) -> None:
    # ADR-ARCH-005: dispose the engine directly (was broken — used engine.kw which
    # doesn't exist on async_sessionmaker in SQLAlchemy 2.x).
    engine = ctx.get("db_engine")
    if engine:
        await engine.dispose()
    log.info("arq.worker.shutdown")


async def trigger_weekly_receipts(ctx: dict) -> None:
    """Cron trigger — Monday 8AM VN (1AM UTC).

    Lightweight: queries all active shops, enqueues one per-shop job each.
    Per-shop jobs run independently with their own timeout + ARQ dedup via _job_id.
    Replaces the old monolithic run that capped at 30 shops and risked SIGKILL
    silently skipping shops N+1 through end.
    """
    from sqlalchemy import select

    from app.models.shop import Shop

    vn_now = datetime.now(UTC) + timedelta(hours=7)
    iso_year, iso_week, _ = vn_now.isocalendar()
    week_label = f"tuần {iso_week}/{iso_year}"

    AsyncSessionLocal = ctx["db_session_factory"]  # noqa: N806
    # BUG-C1 FIX: ARQ injects the Redis pool as ctx["redis"] (ArqRedis object),
    # NOT ctx["arq"]. ctx.get("arq") always returns None → zero jobs ever enqueued.
    arq = ctx.get("redis")
    async with AsyncSessionLocal() as db:
        shop_ids = list(
            await db.scalars(select(Shop.id).where(Shop.is_active == True))  # noqa: E712
        )

    if not shop_ids:
        log.info("weekly_receipts.trigger.no_active_shops")
        return

    enqueued = 0
    for shop_id in shop_ids:
        # _job_id guarantees idempotency — re-triggering cron (e.g. after worker restart)
        # will be a no-op for shops already processed this week.
        job_id = f"weekly-receipt-{shop_id}-{week_label}"
        if arq:
            await arq.enqueue_job(
                "process_weekly_receipt_for_shop", str(shop_id), week_label, _job_id=job_id
            )
        enqueued += 1

    log.info("weekly_receipts.trigger.done", enqueued=enqueued, week=week_label)


async def process_weekly_receipt_for_shop(ctx: dict, shop_id: str, week_label: str) -> None:
    """Per-shop weekly receipt job — runs in its own ARQ slot with full job_timeout.

    Isolated: one shop failing has zero effect on others.
    Idempotent: DB-level check + _job_id ARQ dedup prevent double-processing.
    """
    from decimal import Decimal

    from sqlalchemy import select

    from app.models.ai_action import AIAction
    from app.models.shop import Shop
    from app.models.weekly_receipt import WeeklyReceipt
    from app.schemas.ai_service import CompletedAction, WeeklyReceiptInput
    from app.services.ai import run_weekly_receipt

    shop_uuid = uuid.UUID(shop_id)
    AsyncSessionLocal = ctx["db_session_factory"]  # noqa: N806
    async with AsyncSessionLocal() as db:
        shop = await db.scalar(select(Shop).where(Shop.id == shop_uuid))
        if not shop:
            log.warning("weekly_receipt_for_shop.shop_not_found", shop_id=shop_id)
            return

        existing = await db.scalar(
            select(WeeklyReceipt.shop_id).where(
                WeeklyReceipt.shop_id == shop_uuid,
                WeeklyReceipt.period_label == week_label,
            )
        )
        if existing:
            log.info("weekly_receipt_for_shop.already_done", shop_id=shop_id, week=week_label)
            return

        week_ago = datetime.now(UTC) - timedelta(days=7)
        actions = list(
            await db.scalars(
                select(AIAction).where(
                    AIAction.shop_id == shop_uuid,
                    AIAction.status == "done",
                    AIAction.completed_at >= week_ago,
                )
            )
        )

        if not actions:
            log.info("weekly_receipt_for_shop.no_actions", shop_id=shop_id)
            return

        completed = [
            CompletedAction(
                action_title=a.title,
                completed_at=a.completed_at.isoformat() if a.completed_at else "",
                is_confirmed_impact=a.is_confirmed_impact,
                confirmed_delta=a.confirmed_delta,
                estimated_delta=None,
            )
            for a in actions
        ]
        total_confirmed = sum(
            (a.confirmed_delta or Decimal("0")) for a in actions if a.is_confirmed_impact
        )

        # FIX BUG-NH4 (v2): heuristic estimate per rule_id
        total_estimated = Decimal("0")
        for a in actions:
            if a.is_confirmed_impact:
                continue
            src = a.source_insight_json or {}
            try:
                mv = Decimal(str(src.get("metric_value", "0")))
            except Exception:
                mv = Decimal("0")
            rule = a.rule_trigger or ""
            if rule == "sku_margin_negative":
                total_estimated += abs(mv)
            elif rule == "creator_roi_below_one":
                pass  # mv is ratio not money — skip estimation

        # BUG-H1 FIX: prices from UPGRADE_MESSAGES in gates.py
        # Old values: pro=99k (wrong), business=299k (wrong). Added pro_trial + enterprise.
        _subscription_cost_map = {
            "free": Decimal("0"),
            "pro_trial": Decimal("0"),  # free trial period
            "pro": Decimal("299000"),  # 299k/tháng per UPGRADE_MESSAGES
            "business": Decimal("799000"),  # 799k/tháng per UPGRADE_MESSAGES
            "enterprise": Decimal("2000000"),  # ~2M/tháng (estimate — verify with sales)
        }
        _tier = getattr(shop, "subscription_tier", "free") or "free"
        receipt_input = WeeklyReceiptInput(
            shop_name=shop.shop_name,
            period_label=week_label,
            actions_completed=completed,
            total_confirmed_saved=total_confirmed,
            total_estimated_saved=total_estimated,
            subscription_cost_vnd=_subscription_cost_map.get(_tier, Decimal("0")),
        )
        receipt_output = await run_weekly_receipt(receipt_input, shop_id)

        receipt = WeeklyReceipt(
            shop_id=shop_uuid,
            period_label=week_label,
            total_confirmed_saved=total_confirmed,
            total_estimated_saved=total_estimated,
            actions_completed_count=len(actions),
            headline=receipt_output.headline,
            confirmed_section=receipt_output.confirmed_section,
            estimated_section=receipt_output.estimated_section,
            next_week_focus=receipt_output.next_week_focus,
            disclaimer=receipt_output.disclaimer,
        )
        db.add(receipt)
        await db.flush()
        await db.commit()

        log.info("weekly_receipt_for_shop.done", shop_id=shop_id, week=week_label)

        # ── Email digest ─────────────────────────────────────────────────
        # Fire-and-forget: NEVER let email failure block receipt creation.
        # L8-H02: email digest is a Pro+ feature — skip for Free tier regardless of flag.

        # BUG-L1 FIX: avoid coupling email digest access to Feature.ZALO_PUSH gate.
        # Check subscription tier directly — email digest is a Pro+ feature.
        _email_tier_ok = getattr(shop, "subscription_tier", "free") not in ("free",)
        if _email_tier_ok and shop.email_digest_enabled and shop.notification_email:
            sent = await send_weekly_digest(
                to_email=shop.notification_email,
                shop_name=shop.shop_name,
                period_label=week_label,
                headline=receipt_output.headline,
                confirmed_section=receipt_output.confirmed_section,
                estimated_section=receipt_output.estimated_section,
                next_week_focus=receipt_output.next_week_focus,
                disclaimer=receipt_output.disclaimer,
                total_confirmed_saved=str(total_confirmed),
                total_estimated_saved=str(total_estimated),
            )
            if sent:
                receipt.email_sent = True
                receipt.email_sent_at = datetime.now(UTC)
                await db.flush()
                await db.commit()
            log.info("weekly_receipt_for_shop.email_dispatch", shop_id=shop_id, sent=sent)


# Keep old name registered as no-op for backward compat with any manually enqueued jobs
async def run_weekly_receipts(ctx: dict) -> None:
    """Deprecated: replaced by trigger_weekly_receipts + process_weekly_receipt_for_shop."""
    log.warning("run_weekly_receipts.deprecated", advice="use trigger_weekly_receipts instead")
    await trigger_weekly_receipts(ctx)


async def cleanup_stuck_imports(ctx: dict) -> None:
    """F-08: Mark import sessions stuck in 'processing' or 'pending' > threshold as failed.

    Two stuck cases:
    1. status='processing' > 10min: job was SIGKILL'd AFTER the status commit landed.
    2. status='pending' > 20min: job was SIGKILL'd BEFORE the status commit (race window),
       OR the ARQ enqueue succeeded but the worker never picked it up (Redis issue).
    ADR-ARCH-002: case 2 is rare post-fix (process_import now commits before heavy work)
    but kept as defense-in-depth for edge cases and legacy sessions.
    """
    from sqlalchemy import or_
    from sqlalchemy import update as sa_update

    from app.models.import_session import ImportSession

    AsyncSessionLocal = ctx["db_session_factory"]  # noqa: N806
    async with AsyncSessionLocal() as db:
        processing_cutoff = datetime.now(UTC) - timedelta(minutes=10)
        pending_cutoff = datetime.now(UTC) - timedelta(minutes=20)

        result = await db.execute(
            sa_update(ImportSession)
            .where(
                or_(
                    # Case 1: stuck in processing (SIGKILL after commit)
                    (
                        (ImportSession.status == "processing")
                        & (ImportSession.updated_at < processing_cutoff)
                    ),
                    # Case 2: stuck in pending (SIGKILL before commit, or worker never picked up)
                    (
                        (ImportSession.status == "pending")
                        & (ImportSession.updated_at < pending_cutoff)
                    ),
                )
            )
            .values(
                status="failed",
                error_summary={
                    "error_type": "Timeout",
                    "user_message_vi": (
                        "Xử lý quá lâu. Vui lòng thử lại. "
                        "Nếu file lớn hơn 10.000 đơn, hãy xuất theo từng tuần."
                    ),
                },
            )
        )
        await db.commit()
        count = result.rowcount
        if count > 0:
            log.warning("cleanup_stuck_imports.fixed", count=count)
        else:
            log.info("cleanup_stuck_imports.nothing_to_fix")


class WorkerSettings:
    functions = [
        process_import,
        trigger_weekly_receipts,
        process_weekly_receipt_for_shop,
        run_weekly_receipts,  # deprecated shim — kept so old enqueued jobs don't 404
        verify_action_impact,
        cleanup_stuck_imports,
        trigger_daily_alerts,
    ]
    cron_jobs = [
        cron(trigger_weekly_receipts, weekday=0, hour=1, minute=0),
        cron(cleanup_stuck_imports, minute=5),  # F-08: runs at :05 every hour
        cron(trigger_daily_alerts, hour=1, minute=15),  # daily 8:15AM VN
    ]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 10
    job_timeout = 300
    keep_result = 3600
    # L7-H03: retry failed jobs once on transient errors (e.g. DB unavailable, SIGKILL).
    # process_import is idempotent (idempotency check at step 4) so retries are safe.
    max_tries = 2
