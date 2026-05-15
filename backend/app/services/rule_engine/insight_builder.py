"""
Insight Builder — orchestrates full Rule Engine pipeline.
Input: list[RawOrderRow] + config
Output: InsightData — immutable snapshot of all calculated metrics.
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.services.parser.base import RawOrderRow
from app.services.rule_engine.action_rules import ActionTrigger, evaluate_rules
from app.services.rule_engine.fee_calculator import (
    FeeConfigData,
    apply_fee_config,
    calculate_net_revenue,
    safe_divide,
)
from app.services.rule_engine.leak_detector import LeakItem, detect_top_leaks
from app.services.rule_engine.pl_calculator import (
    CreatorSummary,
    SKUSummary,
    calculate_creator_summaries,
    calculate_sku_summaries,
)


@dataclass
class InsightData:
    """
    Final Rule Engine output.
    INVARIANT: all numbers here come from Rule Engine — NEVER from AI.
    This is the input passed to AI Service (serialized as JSON).
    """

    shop_id: str
    period_start: date
    period_end: date

    # Aggregates
    gmv_total: Decimal
    net_revenue: Decimal
    total_orders: int
    total_refunds: int
    refund_rate: Decimal
    cash_in_14d: Decimal | None

    # Derived outputs
    top_leaks: list[LeakItem] = field(default_factory=list)
    top_skus: list[SKUSummary] = field(default_factory=list)  # top 20 by GMV
    top_creators: list[CreatorSummary] = field(default_factory=list)
    action_triggers: list[ActionTrigger] = field(default_factory=list)

    # Metadata
    rule_engine_version: str = "0.1.0"
    fee_config_version: str = ""
    fee_discrepancy_notes: list[str] = field(default_factory=list)
    cogs_coverage_pct: Decimal = Decimal("0")
    is_net_revenue_mode: bool = False
    # NEW: period completeness metadata
    days_in_period: int = 7
    is_partial_period: bool = False


def build_insight(
    rows: list[RawOrderRow],
    fee_configs: "list[FeeConfigData] | FeeConfigData",
    cogs_map: dict[str, Decimal],
    category_baselines: dict[str, Decimal],
    shop_id: str,
    rule_engine_version: str = "0.1.0",
    top_n_leaks: int = 3,
    shop_category: str | None = None,
) -> InsightData:
    """
    Full pipeline:
    1. Apply fee config cross-check
    2. Calculate SKU summaries
    3. Calculate creator summaries
    4. Detect top leaks
    5. Evaluate action rules
    6. Assemble InsightData
    """
    if isinstance(fee_configs, FeeConfigData):
        fee_configs = [fee_configs]
    # Primary config = most recently effective (last in ascending-sorted list)
    primary_config = fee_configs[-1]
    fee_config_version = (
        "+".join(c.version for c in fee_configs) if len(fee_configs) > 1 else primary_config.version
    )

    if not rows:
        return InsightData(
            shop_id=shop_id,
            period_start=date.today(),
            period_end=date.today(),
            gmv_total=Decimal("0"),
            net_revenue=Decimal("0"),
            total_orders=0,
            total_refunds=0,
            refund_rate=Decimal("0"),
            cash_in_14d=None,
            rule_engine_version=rule_engine_version,
            fee_config_version=fee_config_version,
        )

    # 1. Fee config — per-order selection when multiple configs cover the period
    rows_with_fees, discrepancy_notes = apply_fee_config(rows, fee_configs)

    # 2. SKU summaries (pass category_baselines for health score computation)
    sku_summaries = calculate_sku_summaries(rows_with_fees, cogs_map, category_baselines)
    top_skus = [s for s in sku_summaries if s.gmv_rank <= 20]

    # 3. Creator summaries
    creator_summaries = calculate_creator_summaries(rows_with_fees)

    # F-1B-04: Use full list for rule evaluation, cap snapshot at 50
    # Shops with 500+ creators would produce huge JSON blobs without this cap
    top_creators_snapshot_limit = 50

    # 4. Aggregates
    gmv_total = sum((r.gmv for r in rows_with_fees), Decimal("0"))
    net_revenue = sum((calculate_net_revenue(r) for r in rows_with_fees), Decimal("0"))
    total_orders = len(rows_with_fees)
    refund_statuses = {"refunded", "returned", "cancelled"}
    total_refunds = sum(1 for r in rows_with_fees if r.status.lower() in refund_statuses)
    refund_rate = safe_divide(Decimal(total_refunds), Decimal(total_orders))

    # 5. COGS coverage
    top_20_ids = {s.sku_id for s in top_skus}
    with_cogs = sum(1 for s in top_skus if s.total_cogs is not None)
    cogs_coverage_pct = (
        safe_divide(Decimal(with_cogs), Decimal(len(top_20_ids))) if top_20_ids else Decimal("0")
    )
    is_net_revenue_mode = cogs_coverage_pct < Decimal("0.5")

    # 6. Dates
    dates = [r.order_date for r in rows_with_fees]
    period_start = min(dates)
    period_end = max(dates)

    # 7. Leaks + triggers
    top_leaks = detect_top_leaks(
        sku_summaries,
        creator_summaries,
        category_baselines,
        top_n=top_n_leaks,
        shop_category=shop_category,
    )
    action_triggers = evaluate_rules(
        sku_summaries, creator_summaries, category_baselines, shop_category=shop_category
    )

    days_in_period = (period_end - period_start).days + 1
    is_partial_period = days_in_period < 5  # Less than 5 days = incomplete week

    return InsightData(
        shop_id=shop_id,
        period_start=period_start,
        period_end=period_end,
        gmv_total=gmv_total,
        net_revenue=net_revenue,
        total_orders=total_orders,
        total_refunds=total_refunds,
        refund_rate=refund_rate,
        cash_in_14d=None,  # populated separately from settlement data
        top_leaks=top_leaks,
        top_skus=top_skus,
        top_creators=creator_summaries[:top_creators_snapshot_limit],
        action_triggers=action_triggers,
        rule_engine_version=rule_engine_version,
        fee_config_version=fee_config_version,
        fee_discrepancy_notes=discrepancy_notes,
        cogs_coverage_pct=cogs_coverage_pct,
        is_net_revenue_mode=is_net_revenue_mode,
        days_in_period=days_in_period,
        is_partial_period=is_partial_period,
    )
