"""
P&L Calculator — aggregates per SKU and per creator.
INVARIANT: margin = None khi thiếu COGS. KHÔNG fake về 0.
"""
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

from app.services.parser.base import RawOrderRow
from app.services.rule_engine.fee_calculator import calculate_net_revenue, safe_divide

SKUHealthStatus = Literal["healthy", "warning", "critical"]


@dataclass
class SKUSummary:
    sku_id: str
    sku_name: str
    gmv: Decimal
    net_revenue: Decimal
    order_count: int
    refund_count: int
    refund_rate: Decimal          # 0-1
    total_cogs: Decimal | None    # None nếu seller chưa nhập
    margin: Decimal | None        # net_revenue - total_cogs; None nếu thiếu COGS
    margin_pct: Decimal | None    # margin / net_revenue; None nếu thiếu COGS
    affiliate_commission: Decimal
    voucher_cost: Decimal
    gmv_rank: int                 # 1 = highest GMV, set after sorting
    # Feature 2: SKU Health Score
    health_status: SKUHealthStatus = "healthy"
    health_reasons: list[str] = field(default_factory=list)


@dataclass
class CreatorSummary:
    creator_id: str
    creator_name: str
    attributed_gmv: Decimal
    attributed_net_revenue: Decimal
    total_commission: Decimal
    order_count: int
    # FIX P0-4: renamed from 'roi' and formula corrected.
    # OLD (wrong): roi = attributed_gmv / total_commission
    #   → GMV always > commission, so this is almost always > 1 and never flags real losses.
    # NEW (correct): revenue_efficiency = attributed_net_revenue / total_commission
    #   → net_revenue already deducts all platform fees, so efficiency < 1 means
    #     the commission paid exceeds what the creator actually generated after fees.
    # Label as "Revenue Efficiency" in UI — NOT "ROI" (true ROI requires COGS + sample cost).
    revenue_efficiency: Decimal | None  # None if commission=0
    # Feature 4: Creator Scorecard
    performance_label: Literal["star", "break_even", "losing"] = "break_even"
    suggested_max_commission_rate: Decimal | None = None


def _compute_sku_health(
    sku: "SKUSummary",
    baseline_refund_rate: Decimal,
) -> tuple[SKUHealthStatus, list[str]]:
    """Classify SKU health. INVARIANT: critical check first, warning only if not critical."""
    from app.services.rule_engine.baselines import DEFAULT_BASELINE  # avoid circular at module level
    reasons: list[str] = []
    status: SKUHealthStatus = "healthy"

    if sku.margin is not None and sku.margin < Decimal("0"):
        status = "critical"
        reasons.append(f"Margin âm: {sku.margin:,.0f}đ")
    if sku.net_revenue < Decimal("0"):
        status = "critical"
        reasons.append("Net revenue âm sau phí")
    if sku.refund_rate > baseline_refund_rate * Decimal("2"):
        status = "critical"
        reasons.append(f"Hoàn hàng {sku.refund_rate:.0%} — cao hơn 2× chuẩn ngành")

    if status == "critical":
        return status, reasons

    if sku.total_cogs is None:
        status = "warning"
        reasons.append("Chưa nhập giá vốn — không tính được margin")
    elif sku.margin_pct is not None and sku.margin_pct < Decimal("0.10"):
        status = "warning"
        reasons.append(f"Margin thấp: {sku.margin_pct:.0%}")
    if sku.refund_rate > baseline_refund_rate * Decimal("1.2"):
        status = "warning"
        reasons.append(f"Hoàn hàng {sku.refund_rate:.0%} — trên mức chuẩn")
    nr = sku.net_revenue
    if nr > 0 and sku.voucher_cost > nr * Decimal("0.30"):
        status = "warning"
        reasons.append(f"Voucher chiếm {sku.voucher_cost / nr:.0%} net revenue")

    return status, reasons


def calculate_sku_summaries(
    rows: list[RawOrderRow],
    cogs_map: dict[str, Decimal],  # {sku_id: cogs_per_unit}
    category_baselines: dict[str, Decimal] | None = None,
) -> list[SKUSummary]:
    """
    Group by sku_id, aggregate metrics.
    cogs_map comes from seller's manual input.
    If sku_id not in cogs_map → total_cogs = None, margin = None.
    """
    agg: dict[str, dict] = defaultdict(lambda: {
        "sku_name": "", "gmv": Decimal("0"), "net_revenue": Decimal("0"),
        "order_count": 0, "refund_count": 0, "total_quantity": 0,
        "affiliate_commission": Decimal("0"), "voucher_cost": Decimal("0"),
    })

    for row in rows:
        a = agg[row.sku_id]
        a["sku_name"] = row.sku_name
        a["gmv"] += row.gmv
        a["net_revenue"] += calculate_net_revenue(row)
        a["order_count"] += 1
        # FIX P0-3: accumulate actual quantity for COGS calculation
        # An order with qty=3 consumes 3x COGS, not 1x
        a["total_quantity"] += row.quantity
        if row.status.lower() in ("refunded", "returned", "cancelled"):
            a["refund_count"] += 1
        a["affiliate_commission"] += row.affiliate_commission
        a["voucher_cost"] += row.voucher_cost

    summaries: list[SKUSummary] = []
    for sku_id, a in agg.items():
        nr = a["net_revenue"]
        order_count = a["order_count"]
        total_quantity = a["total_quantity"]
        cogs_per_unit = cogs_map.get(sku_id)
        # FIX P0-3: multiply by total_quantity (units sold), not order_count (orders)
        # If seller entered COGS per unit, we need total units, not total orders
        total_cogs = cogs_per_unit * total_quantity if cogs_per_unit is not None else None
        margin = (nr - total_cogs) if total_cogs is not None else None
        # FIX BUG-NH2: use GMV as denominator (e-commerce standard)
        # Old: safe_divide(margin, nr) — when nr<0 (fees>GMV), sign inverts (loss shows as gain!)
        # New: safe_divide(margin, gmv) — always positive denominator, intuitive to seller
        sku_gmv = a["gmv"]
        margin_pct = safe_divide(margin, sku_gmv) if margin is not None and sku_gmv > 0 else None

        summaries.append(SKUSummary(
            sku_id=sku_id,
            sku_name=a["sku_name"],
            gmv=a["gmv"],
            net_revenue=nr,
            order_count=order_count,
            refund_count=a["refund_count"],
            refund_rate=safe_divide(Decimal(a["refund_count"]), Decimal(order_count)),
            total_cogs=total_cogs,
            margin=margin,
            margin_pct=margin_pct,
            affiliate_commission=a["affiliate_commission"],
            voucher_cost=a["voucher_cost"],
            gmv_rank=0,  # set below
        ))

    # Sort by GMV desc, assign rank
    summaries.sort(key=lambda x: x.gmv, reverse=True)
    for i, s in enumerate(summaries):
        s.gmv_rank = i + 1

    # Feature 2: Compute health score for each SKU
    from app.services.rule_engine.baselines import DEFAULT_BASELINE
    baselines = category_baselines or {}
    for s in summaries:
        baseline = baselines.get(s.sku_id, DEFAULT_BASELINE)
        s.health_status, s.health_reasons = _compute_sku_health(s, baseline)

    return summaries


def calculate_creator_summaries(rows: list[RawOrderRow]) -> list[CreatorSummary]:
    """
    Group by creator_id. Only rows with creator_id != None.

    FIX P0-4: revenue_efficiency = attributed_net_revenue / total_commission
    net_revenue already deducts platform fees, transaction fees, vouchers, refunds.
    A creator with efficiency < 1.0 is generating less net revenue than they cost in commission.
    This is the actionable signal — NOT GMV/commission which almost never flags a real problem.

    Note: this is still NOT true ROI (would need COGS + sample_cost). Label as
    "Revenue Efficiency" in all UI and AI narratives.
    """
    agg: dict[str, dict] = defaultdict(lambda: {
        "creator_name": "", "gmv": Decimal("0"), "net_revenue": Decimal("0"),
        "commission": Decimal("0"), "order_count": 0,
    })

    for row in rows:
        if not row.creator_id:
            continue
        a = agg[row.creator_id]
        a["creator_name"] = row.creator_name or row.creator_id
        a["gmv"] += row.gmv
        a["net_revenue"] += calculate_net_revenue(row)
        a["commission"] += row.affiliate_commission
        a["order_count"] += 1

    summaries: list[CreatorSummary] = []
    for creator_id, a in agg.items():
        commission = a["commission"]
        net_rev = a["net_revenue"]
        # revenue_efficiency: net_revenue vs what we paid the creator
        # < 1.0 → creator cost more than they generated after all fees
        revenue_efficiency = safe_divide(net_rev, commission) if commission > 0 else None

        # Feature 4: performance_label based on revenue_efficiency
        if revenue_efficiency is not None:
            if revenue_efficiency >= Decimal("2.0"):
                performance_label = "star"
            elif revenue_efficiency >= Decimal("1.0"):
                performance_label = "break_even"
            else:
                performance_label = "losing"
        else:
            performance_label = "break_even"  # no commission cost → not losing

        # Feature 4: suggested_max_commission_rate = (net_rev / gmv) × 0.8
        # = max 80% of margin vs GMV as commission, to keep seller profitable
        gmv = a["gmv"]
        suggested_max_commission_rate: Decimal | None = None
        if gmv > 0 and net_rev > 0:
            margin_ratio = net_rev / gmv
            suggested_max_commission_rate = (margin_ratio * Decimal("0.8")).quantize(Decimal("0.0001"))

        summaries.append(CreatorSummary(
            creator_id=creator_id,
            creator_name=a["creator_name"],
            attributed_gmv=a["gmv"],
            attributed_net_revenue=net_rev,
            total_commission=commission,
            order_count=a["order_count"],
            revenue_efficiency=revenue_efficiency,
            performance_label=performance_label,
            suggested_max_commission_rate=suggested_max_commission_rate,
        ))

    summaries.sort(key=lambda x: x.attributed_gmv, reverse=True)
    return summaries
