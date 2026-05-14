"""
Action Rules — IF-THEN triggers producing ActionTrigger objects.
INVARIANT: rule_id strings are stable identifiers — KHÔNG rename.
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from app.services.rule_engine.baselines import DEFAULT_BASELINE
from app.services.rule_engine.pl_calculator import CreatorSummary, SKUSummary

ActionType = Literal[
    "reduce_voucher", "pause_creator", "fix_pdp", "check_cogs", "review_script"
]


@dataclass
class ActionTrigger:
    rule_id: str
    entity_type: Literal["sku", "creator", "shop"]
    entity_id: str
    entity_name: str
    metric_key: str    # key in source data — used for AI fact-anchoring
    metric_value: Decimal
    priority: int      # 1 = highest


def evaluate_rules(
    sku_summaries: list[SKUSummary],
    creator_summaries: list[CreatorSummary],
    category_baselines: dict[str, Decimal],
) -> list[ActionTrigger]:
    """
    Evaluate all rules. Return sorted by priority ASC (1 = highest).
    Deduplicate: max 1 trigger per rule per entity.
    """
    triggers: list[ActionTrigger] = []
    seen: set[tuple[str, str]] = set()  # (rule_id, entity_id)

    def add(t: ActionTrigger) -> None:
        key = (t.rule_id, t.entity_id)
        if key not in seen:
            seen.add(key)
            triggers.append(t)

    # ── SKU rules ────────────────────────────────────────────
    for sku in sku_summaries:
        if sku.gmv_rank > 20:
            continue

        # Rule: sku_margin_negative
        if sku.margin is not None and sku.margin < Decimal("0"):
            add(ActionTrigger(
                rule_id="sku_margin_negative",
                entity_type="sku",
                entity_id=sku.sku_id,
                entity_name=sku.sku_name,
                metric_key="margin",
                metric_value=sku.margin,
                priority=1,
            ))

        # Rule: sku_refund_spike
        baseline = category_baselines.get(sku.sku_id, DEFAULT_BASELINE)  # FIX BUG-H5
        if sku.refund_rate > baseline * Decimal("1.5"):
            add(ActionTrigger(
                rule_id="sku_refund_spike",
                entity_type="sku",
                entity_id=sku.sku_id,
                entity_name=sku.sku_name,
                metric_key="refund_rate",
                metric_value=sku.refund_rate,
                priority=2,
            ))

        # Rule: cogs_missing_top_sku
        if sku.total_cogs is None:
            add(ActionTrigger(
                rule_id="cogs_missing_top_sku",
                entity_type="sku",
                entity_id=sku.sku_id,
                entity_name=sku.sku_name,
                metric_key="cogs",
                metric_value=Decimal("0"),
                priority=3,
            ))

    # ── Creator rules ─────────────────────────────────────────
    for creator in creator_summaries:
        # FIX P0-4: use revenue_efficiency (net_revenue/commission), not roi (gmv/commission)
        if creator.revenue_efficiency is not None and creator.revenue_efficiency < Decimal("1.0"):
            add(ActionTrigger(
                rule_id="creator_roi_below_one",
                entity_type="creator",
                entity_id=creator.creator_id,
                entity_name=creator.creator_name,
                metric_key="revenue_efficiency",
                metric_value=creator.revenue_efficiency,
                priority=2,
            ))

    # Sort by priority ASC
    triggers.sort(key=lambda t: t.priority)
    return triggers
