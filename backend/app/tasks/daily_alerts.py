"""
Daily Alert Worker.

Cron: every day at 8AM VN (1AM UTC).
For each active shop with push_subscription_json:
  1. Load latest InsightSnapshot
  2. If any top_skus has health_status='critical' OR top_leaks has estimated_loss > threshold:
     → send Web Push with the most actionable message

INVARIANT: never raises — fire-and-forget. One shop failing must not affect others.
Budget guard: send at most 1 push per shop per 24h (idempotency via Redis key TTL).
"""

from decimal import Decimal

import structlog
from sqlalchemy import select

from app.models.insight_snapshot import InsightSnapshot
from app.models.shop import Shop
from app.services.push.web_push import send_push_to_shop

log = structlog.get_logger()

ALERT_LEAK_THRESHOLD = Decimal("100000")


async def _shop_was_alerted_today(shop_id: str, redis) -> bool:
    key = f"daily_alert_sent:{shop_id}"
    return bool(await redis.get(key))


async def _mark_shop_alerted(shop_id: str, redis) -> None:
    key = f"daily_alert_sent:{shop_id}"
    await redis.set(key, "1", ex=24 * 60 * 60)


def _build_alert_message(snapshot: InsightSnapshot) -> tuple[str, str] | None:
    """Return (title, body) if there's something worth alerting about, else None."""
    leaks = snapshot.top_leaks_json or []
    skus = snapshot.top_skus_json or []

    if leaks:
        top_leak = max(leaks, key=lambda leak: Decimal(str(leak.get("estimated_loss", "0"))))
        loss = Decimal(str(top_leak.get("estimated_loss", "0")))
        if loss >= ALERT_LEAK_THRESHOLD:
            name = top_leak.get("name", "")
            return (
                "⚠ Phát hiện rò rỉ doanh thu",
                f"{name} đang mất ~{loss:,.0f}đ kỳ này — mở Tikai để xem cách fix",
            )

    critical_skus = [s for s in skus if s.get("health_status") == "critical"]
    if critical_skus:
        first = critical_skus[0]
        return (
            "⚠ SKU đang lỗ",
            f"{first.get('sku_name', '')} ở trạng thái nguy hiểm — xem chi tiết ngay",
        )

    return None


async def trigger_daily_alerts(ctx: dict) -> None:
    """Cron — runs daily at 1AM UTC = 8AM Vietnam."""
    from app.core.redis import get_redis

    AsyncSessionLocal = ctx["db_session_factory"]  # noqa: N806
    redis = await get_redis()

    async with AsyncSessionLocal() as db:
        shops = list(
            await db.scalars(
                select(Shop).where(
                    Shop.is_active == True,  # noqa: E712
                    Shop.push_subscription_json.isnot(None),
                )
            )
        )

    total = len(shops)
    sent_count = 0
    skipped_dup = 0
    skipped_no_signal = 0
    failed = 0

    for shop in shops:
        try:
            if await _shop_was_alerted_today(str(shop.id), redis):
                skipped_dup += 1
                continue

            async with AsyncSessionLocal() as db:
                snapshot = await db.scalar(
                    select(InsightSnapshot)
                    .where(InsightSnapshot.shop_id == shop.id)
                    .order_by(InsightSnapshot.period_end.desc())
                    .limit(1)
                )

            if not snapshot:
                skipped_no_signal += 1
                continue

            msg = _build_alert_message(snapshot)
            if msg is None:
                skipped_no_signal += 1
                continue

            title, body = msg
            success = await send_push_to_shop(shop, title=title, body=body, url="/overview")
            if success:
                await _mark_shop_alerted(str(shop.id), redis)
                sent_count += 1
            else:
                failed += 1
        except Exception as e:
            log.warning("daily_alert.shop_failed", shop_id=str(shop.id), error=str(e))
            failed += 1

    log.info(
        "daily_alerts.complete",
        total=total,
        sent=sent_count,
        skipped_dup=skipped_dup,
        skipped_no_signal=skipped_no_signal,
        failed=failed,
    )
