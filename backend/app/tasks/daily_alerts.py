"""
Daily Alert Worker.

Cron: every day at 8AM VN (1AM UTC).
For each active shop with push_subscription_json:
  1. Load latest InsightSnapshot
  2. If any top_skus has health_status='critical' OR top_leaks has estimated_loss > threshold:
     → send Web Push with the most actionable message

INVARIANT: never raises — fire-and-forget. One shop failing must not affect others.
Budget guard: send at most 1 push per shop per 24h (idempotency via Redis key TTL).

L6-H01: shops are loaded in pages of PAGE_SIZE (not all at once) and each page is
processed with bounded parallelism (semaphore MAX_CONCURRENT) to avoid OOM on large
shop counts while still finishing within the cron window.
"""

import asyncio
from decimal import Decimal

import structlog
from sqlalchemy import select

from app.models.insight_snapshot import InsightSnapshot
from app.models.shop import Shop
from app.services.push.web_push import send_push_to_shop

log = structlog.get_logger()

ALERT_LEAK_THRESHOLD = Decimal("100000")
_PAGE_SIZE = 100
_MAX_CONCURRENT = 10


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
            leak_name = top_leak.get("name", "")
            body = (
                f"{leak_name} đang rò rỉ doanh thu — mở Tikai để xem chi tiết"
                if leak_name
                else "Phát hiện rò rỉ doanh thu — mở Tikai để xem chi tiết"
            )
            return (
                "⚠ Phát hiện rò rỉ doanh thu",
                body,
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
    semaphore = asyncio.Semaphore(_MAX_CONCURRENT)

    total = 0
    sent_count = 0
    skipped_dup = 0
    skipped_no_signal = 0
    failed = 0

    async def _process_one(shop: Shop) -> tuple[int, int, int, int]:
        """Returns (sent, skipped_dup, skipped_no_signal, failed)."""
        async with semaphore:
            try:
                if await _shop_was_alerted_today(str(shop.id), redis):
                    return (0, 1, 0, 0)

                async with AsyncSessionLocal() as db:
                    snapshot = await db.scalar(
                        select(InsightSnapshot)
                        .where(InsightSnapshot.shop_id == shop.id)
                        .order_by(InsightSnapshot.period_end.desc())
                        .limit(1)
                    )

                if not snapshot:
                    return (0, 0, 1, 0)

                msg = _build_alert_message(snapshot)
                if msg is None:
                    return (0, 0, 1, 0)

                title, body = msg
                success = await send_push_to_shop(shop, title=title, body=body, url="/overview")
                if success:
                    await _mark_shop_alerted(str(shop.id), redis)
                    return (1, 0, 0, 0)
                return (0, 0, 0, 1)
            except Exception as e:
                log.warning("daily_alert.shop_failed", shop_id=str(shop.id), error=str(e))
                return (0, 0, 0, 1)

    # Paginate shops to avoid loading all into memory at once (L6-H01)
    offset = 0
    while True:
        async with AsyncSessionLocal() as db:
            page = list(
                await db.scalars(
                    select(Shop)
                    .where(
                        Shop.is_active == True,  # noqa: E712
                        Shop.push_subscription_json.isnot(None),
                    )
                    .order_by(Shop.id)
                    .limit(_PAGE_SIZE)
                    .offset(offset)
                )
            )

        if not page:
            break

        total += len(page)
        results = await asyncio.gather(*[_process_one(s) for s in page])
        for s, d, ns, f in results:
            sent_count += s
            skipped_dup += d
            skipped_no_signal += ns
            failed += f

        offset += _PAGE_SIZE

    log.info(
        "daily_alerts.complete",
        total=total,
        sent=sent_count,
        skipped_dup=skipped_dup,
        skipped_no_signal=skipped_no_signal,
        failed=failed,
    )
