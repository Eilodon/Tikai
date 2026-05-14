"""
ARQ Worker.
FIX BUG-07: verify_action_impact registered in functions list.
v1.0.0: Removed duplicate `from datetime import...` inside loop body.
"""
from datetime import UTC, datetime, timedelta  # v1.0.0: module-level only

import structlog
from arq import cron
from arq.connections import RedisSettings
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.services.email.client import send_weekly_digest
from app.tasks.process_import import process_import
from app.tasks.verify_action_impact import verify_action_impact

settings = get_settings()
log = structlog.get_logger()


async def startup(ctx: dict) -> None:
    engine = create_async_engine(settings.database_url, pool_size=5, max_overflow=10)
    ctx["db_session_factory"] = async_sessionmaker(
        bind=engine, expire_on_commit=False, autoflush=False
    )
    log.info("arq.worker.startup", environment=settings.environment)


async def shutdown(ctx: dict) -> None:
    log.info("arq.worker.shutdown")


async def run_weekly_receipts(ctx: dict) -> None:
    """Weekly batch — Monday 8AM VN (1AM UTC)."""
    from decimal import Decimal

    from sqlalchemy import select

    from app.models.ai_action import AIAction
    from app.models.shop import Shop
    from app.models.weekly_receipt import WeeklyReceipt
    from app.schemas.ai_service import CompletedAction, WeeklyReceiptInput
    from app.services.ai import run_weekly_receipt

    AsyncSessionLocal = ctx["db_session_factory"]  # noqa: N806
    async with AsyncSessionLocal() as db:
        shops = await db.scalars(select(Shop).where(Shop.is_active == True))  # noqa: E712
        total = skipped = 0

        for shop in shops:
            try:
                week_ago = datetime.now(UTC) - timedelta(days=7)
                actions = list(await db.scalars(
                    select(AIAction).where(
                        AIAction.shop_id == shop.id,
                        AIAction.status == "done",
                        AIAction.completed_at >= week_ago,
                    )
                ))
                if not actions:
                    skipped += 1
                    continue

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
                    (a.confirmed_delta or Decimal("0"))
                    for a in actions if a.is_confirmed_impact
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

                # FIX BUG-NM2 (v2): VN timezone ISO week boundary
                vn_now = datetime.now(UTC) + timedelta(hours=7)
                iso_year, iso_week, _ = vn_now.isocalendar()
                week_label = f"tuần {iso_week}/{iso_year}"

                # Idempotency check
                existing_receipt = await db.scalar(
                    select(WeeklyReceipt).where(
                        WeeklyReceipt.shop_id == shop.id,
                        WeeklyReceipt.period_label == week_label,
                    )
                )
                if existing_receipt:
                    skipped += 1
                    continue

                _subscription_cost_map = {
                    "free":     Decimal("0"),
                    "pro":      Decimal("99000"),
                    "business": Decimal("299000"),
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
                receipt_output = await run_weekly_receipt(receipt_input, str(shop.id))

                receipt = WeeklyReceipt(
                    shop_id=shop.id,
                    period_label=week_label,
                    total_confirmed_saved=total_confirmed,
                    # FIX v0.5.2: use total_estimated not hardcoded Decimal("0")
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
                total += 1

                # ── Email digest (v1.2.0) ────────────────────────────────
                # Fire-and-forget: NEVER let email failure block receipt creation.
                # email_sent / email_sent_at are tracking-only — not critical path.
                if shop.email_digest_enabled and shop.notification_email:
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
                    log.info(
                        "weekly_receipts.email_dispatch",
                        shop_id=str(shop.id),
                        sent=sent,
                    )

            except Exception as e:
                log.error("weekly_receipts.shop_failed", shop_id=str(shop.id), error=str(e))

        log.info("weekly_receipts.done", total=total, skipped=skipped)


async def cleanup_stuck_imports(ctx: dict) -> None:
    """F-08: Mark import sessions stuck in 'processing' > 10 min as failed.
    ARQ job_timeout=300s kills the worker process — Python except handler doesn't run
    → session stays 'processing' forever. This cron job fixes them hourly.
    """
    from sqlalchemy import update as sa_update
    from app.models.import_session import ImportSession

    AsyncSessionLocal = ctx["db_session_factory"]  # noqa: N806
    async with AsyncSessionLocal() as db:
        cutoff = datetime.now(UTC) - timedelta(minutes=10)
        result = await db.execute(
            sa_update(ImportSession)
            .where(
                ImportSession.status == "processing",
                ImportSession.updated_at < cutoff,
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
    functions = [process_import, run_weekly_receipts, verify_action_impact, cleanup_stuck_imports]
    cron_jobs = [
        cron(run_weekly_receipts, weekday=0, hour=1, minute=0),
        cron(cleanup_stuck_imports, minute=5),   # F-08: runs at :05 every hour
    ]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 10
    job_timeout = 300
    keep_result = 3600
