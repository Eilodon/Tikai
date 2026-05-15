"""
Leak Detector — ranks revenue leaks by estimated impact.
INVARIANT: estimated_loss từ Rule Engine calculations, KHÔNG phải AI.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from app.services.rule_engine.baselines import get_refund_baseline_for_shop_category
from app.services.rule_engine.pl_calculator import CreatorSummary, SKUSummary

LeakReason = Literal[
    "voucher_high",
    "affiliate_high",
    "cogs_missing",
    "refund_spike",
    "commission_exceeds_margin",
]


@dataclass
class LeakItem:
    type: Literal["sku", "creator", "category"]
    id: str
    name: str
    estimated_loss: Decimal
    reason: LeakReason
    confidence: Literal["high", "medium", "low"]
    can_act_now: bool


def detect_top_leaks(
    sku_summaries: list[SKUSummary],
    creator_summaries: list[CreatorSummary],
    category_baselines: dict[str, Decimal],
    top_n: int = 3,
    shop_category: str | None = None,
) -> list[LeakItem]:
    """
    Collect all leaks, score by estimated_loss, return top_n.

    Baseline precedence: per-SKU override (category_baselines) → shop-level category
    benchmark (industry_data.py) → global DEFAULT_BASELINE.
    """
    leaks: list[LeakItem] = []

    # SKU leaks
    for sku in sku_summaries:
        if sku.gmv_rank > 20:
            continue  # only top-20 SKUs

        # Negative margin
        if sku.margin is not None and sku.margin < Decimal("0"):
            # Determine primary driver
            reason: LeakReason = (
                "voucher_high" if sku.voucher_cost >= sku.affiliate_commission else "affiliate_high"
            )
            leaks.append(
                LeakItem(
                    type="sku",
                    id=sku.sku_id,
                    name=sku.sku_name,
                    estimated_loss=abs(sku.margin),
                    reason=reason,
                    confidence="high",
                    can_act_now=True,
                )
            )

        # Refund spike vs category baseline (per-SKU override → shop category → global default)
        shop_fallback = get_refund_baseline_for_shop_category(shop_category)
        baseline = category_baselines.get(sku.sku_id, shop_fallback)
        if sku.refund_rate > baseline * Decimal("1.5"):
            leaks.append(
                LeakItem(
                    type="sku",
                    id=sku.sku_id,
                    name=sku.sku_name,
                    estimated_loss=sku.net_revenue * sku.refund_rate,
                    reason="refund_spike",
                    confidence="medium",
                    can_act_now=True,
                )
            )

        # Missing COGS — can't calculate loss, but flag it
        if sku.total_cogs is None:
            leaks.append(
                LeakItem(
                    type="sku",
                    id=sku.sku_id,
                    name=sku.sku_name,
                    estimated_loss=Decimal("0"),  # unknown
                    reason="cogs_missing",
                    confidence="low",
                    can_act_now=False,
                )
            )

    # Creator leaks
    for creator in creator_summaries:
        # FIX P0-4: use revenue_efficiency (net_revenue / commission), not roi (gmv / commission).
        # Old condition `commission > gmv` was almost never true → creators never flagged.
        # New condition: efficiency < 1.0 means commission > net_revenue → real loss.
        if creator.revenue_efficiency is not None and creator.revenue_efficiency < Decimal("1.0"):
            loss = creator.total_commission - creator.attributed_net_revenue
            loss = max(loss, Decimal("0"))
            confidence = "high" if creator.revenue_efficiency < Decimal("0.5") else "medium"
            leaks.append(
                LeakItem(
                    type="creator",
                    id=creator.creator_id,
                    name=creator.creator_name,
                    estimated_loss=loss,
                    reason="commission_exceeds_margin",
                    confidence=confidence,
                    can_act_now=True,
                )
            )

    # Deduplicate: keep highest estimated_loss per entity_id
    seen: dict[str, LeakItem] = {}
    for leak in leaks:
        existing = seen.get(leak.id)
        if existing is None or leak.estimated_loss > existing.estimated_loss:
            seen[leak.id] = leak

    # Sort by estimated_loss desc, return top_n
    ranked = sorted(seen.values(), key=lambda x: x.estimated_loss, reverse=True)
    return ranked[:top_n]
