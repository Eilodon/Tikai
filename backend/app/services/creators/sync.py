"""
Creator Profile Sync — upserts CreatorProfile rows from InsightSnapshot.top_creators_json.
INVARIANT: pure DB upsert, no AI, no float.
Shared by:
  - POST /v1/creators/sync (manual trigger, gated)
  - process_import task (automatic after each successful import)
"""

import uuid
from decimal import Decimal

import structlog
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.creator_profile import CreatorProfile

log = structlog.get_logger()


async def sync_creators_from_snapshot(
    db: AsyncSession,
    shop_id: uuid.UUID,
    top_creators_json: list,
) -> int:
    """Upsert creator_profiles from a snapshot's top_creators_json. Returns count."""
    if not top_creators_json:
        return 0

    upserted = 0
    for c in top_creators_json:
        creator_id = c.get("creator_id")
        if not creator_id:
            continue

        gmv = Decimal(str(c.get("attributed_gmv", "0")))
        net_rev = Decimal(str(c.get("attributed_net_revenue", "0")))
        commission = Decimal(str(c.get("total_commission", "0")))
        order_count = int(c.get("order_count", 0))
        commission_on_refunds = Decimal(str(c.get("commission_on_refunded_orders", "0")))
        performance_label = c.get("performance_label", "break_even")
        suggested_rate_raw = c.get("suggested_max_commission_rate")
        suggested_rate = Decimal(str(suggested_rate_raw)) if suggested_rate_raw else None
        rev_eff_raw = c.get("revenue_efficiency")
        rev_eff = Decimal(str(rev_eff_raw)) if rev_eff_raw else None

        stmt = (
            pg_insert(CreatorProfile)
            .values(
                id=uuid.uuid4(),
                shop_id=shop_id,
                creator_id=creator_id,
                creator_name=c.get("creator_name", creator_id),
                gmv_30d=gmv,
                net_revenue_30d=net_rev,
                revenue_efficiency_30d=rev_eff,
                total_orders_lifetime=order_count,
                total_commission_paid=commission,
                commission_on_refunded_orders=commission_on_refunds,
                performance_label=performance_label,
                suggested_max_commission=suggested_rate,
            )
            .on_conflict_do_update(
                constraint="uq_creator_profiles_shop_creator",
                set_={
                    "creator_name": c.get("creator_name", creator_id),
                    "gmv_30d": gmv,
                    "net_revenue_30d": net_rev,
                    "revenue_efficiency_30d": rev_eff,
                    "total_orders_lifetime": order_count,
                    "total_commission_paid": commission,
                    "commission_on_refunded_orders": commission_on_refunds,
                    "performance_label": performance_label,
                    "suggested_max_commission": suggested_rate,
                },
            )
        )
        await db.execute(stmt)
        upserted += 1

    return upserted
