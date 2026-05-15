"""
Settlement Reconciler — so sánh computed P&L với actual settlement payout.

INVARIANT: không write DB, không gọi AI, tất cả in-memory.
INVARIANT: dùng Decimal, không dùng float.

Gap thường gặp (15-25% GMV vs tiền nhận):
1. Shipping Fee Adjustment — carrier weight discrepancy (âm thầm)
2. Affiliate commission non-refundable after return (TikTok không clawback)
3. Refund Administration Fee — 20% of referral fee khi có refund
4. Reserve holds — TikTok giữ lại khi có performance issues
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal


@dataclass
class ReconciliationResult:
    # Summary
    total_payout: Decimal
    expected_payout: Decimal
    gap: Decimal  # total_payout - expected_payout (positive = more than expected)

    # Hidden cost breakdown
    shipping_adjustments_total: Decimal
    refund_admin_fees_total: Decimal
    non_clawback_commissions: Decimal
    reserve_held: Decimal

    # Actionable signals
    high_shipping_adj_skus: list[str]
    commission_waste_on_returns: Decimal

    # Verdict
    verdict: Literal["matched", "minor_gap", "major_gap", "investigate"]
    action_items_vi: list[str] = field(default_factory=list)


def reconcile_settlement(
    settlement_rows: "list",
    expected_payout: Decimal,
    commission_on_refunded_orders: Decimal = Decimal("0"),
) -> ReconciliationResult:
    """
    Cross-reference parsed settlement rows against expected P&L payout.

    settlement_rows: list[SettlementRow] from parse_settlement_csv().
    expected_payout: computed net_revenue from Rule Engine (what seller should receive).
    commission_on_refunded_orders: sum of commissions paid on refunded orders (from CreatorSummary).
    """
    total_payout = sum(
        (row.payout_amount for row in settlement_rows if row.payout_amount > 0),
        Decimal("0"),
    )

    # Shipping weight adjustments — carrier-level weight discrepancy deductions
    shipping_adj_by_sku: dict[str, Decimal] = {}
    for row in settlement_rows:
        if row.is_shipping_weight_adjustment:
            sku = row.seller_sku or "_unknown"
            shipping_adj_by_sku.setdefault(sku, Decimal("0"))
            shipping_adj_by_sku[sku] += abs(row.fee_amount)

    shipping_adjustments_total = sum(shipping_adj_by_sku.values(), Decimal("0"))
    high_shipping_adj_skus = [
        sku for sku, amt in shipping_adj_by_sku.items() if amt >= Decimal("100000")
    ]

    # Refund Administration Fee — ~20% of referral fee per refund row
    refund_admin_fees_total = Decimal("0")
    for row in settlement_rows:
        desc_lower = row.description.lower()
        adj_lower = row.adjustment_type.lower()
        if "refund" in desc_lower and "admin" in desc_lower and row.fee_amount < 0:
            refund_admin_fees_total += abs(row.fee_amount)
        elif "refund" in adj_lower and "fee" in adj_lower:
            refund_admin_fees_total += abs(row.fee_amount)

    # Reserve holds — amounts withheld pending performance review
    reserve_held = Decimal("0")
    for row in settlement_rows:
        combined = (row.adjustment_type + " " + row.description).lower()
        if "reserve" in combined or "hold" in combined or "withhold" in combined:
            reserve_held += abs(row.fee_amount)

    # Non-clawback commissions are provided externally (from CreatorSummary)
    non_clawback_commissions = commission_on_refunded_orders
    commission_waste_on_returns = commission_on_refunded_orders

    # Gap analysis
    gap = total_payout - expected_payout
    gap_pct = abs(gap) / expected_payout if expected_payout > 0 else Decimal("0")

    if gap_pct < Decimal("0.02"):
        verdict: Literal["matched", "minor_gap", "major_gap", "investigate"] = "matched"
    elif gap_pct < Decimal("0.05"):
        verdict = "minor_gap"
    elif gap_pct < Decimal("0.15"):
        verdict = "major_gap"
    else:
        verdict = "investigate"

    # Generate actionable items
    action_items_vi: list[str] = []

    if high_shipping_adj_skus:
        skus_str = ", ".join(high_shipping_adj_skus[:3])
        action_items_vi.append(
            f"Cập nhật cân nặng thực tế cho SKU: {skus_str} "
            f"(bị khấu trừ {shipping_adjustments_total:,.0f}đ phí vận chuyển)"
        )

    if non_clawback_commissions > Decimal("50000"):
        action_items_vi.append(
            f"Hoa hồng affiliate {non_clawback_commissions:,.0f}đ bị mất do hoàn hàng "
            "(TikTok không hoàn lại) — cân nhắc điều khoản creator"
        )

    if refund_admin_fees_total > 0:
        action_items_vi.append(
            f"Phí quản lý hoàn hàng {refund_admin_fees_total:,.0f}đ — "
            "giảm tỷ lệ hoàn hàng để tiết kiệm khoản này"
        )

    if reserve_held > 0:
        action_items_vi.append(
            f"TikTok đang giữ {reserve_held:,.0f}đ — "
            "kiểm tra performance metrics trên Seller Center để giải phóng"
        )

    if verdict in ("major_gap", "investigate") and not action_items_vi:
        action_items_vi.append(
            "Chênh lệch lớn không giải thích được — liên hệ TikTok Shop Support "
            "với settlement period và order IDs"
        )

    return ReconciliationResult(
        total_payout=total_payout,
        expected_payout=expected_payout,
        gap=gap,
        shipping_adjustments_total=shipping_adjustments_total,
        refund_admin_fees_total=refund_admin_fees_total,
        non_clawback_commissions=non_clawback_commissions,
        reserve_held=reserve_held,
        high_shipping_adj_skus=high_shipping_adj_skus,
        commission_waste_on_returns=commission_waste_on_returns,
        verdict=verdict,
        action_items_vi=action_items_vi,
    )
