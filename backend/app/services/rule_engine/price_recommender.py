"""
Price Recommender — reverse P&L từ COGS + target margin → giá bán tối thiểu.
INVARIANT: KHÔNG dùng float. KHÔNG gọi AI. KHÔNG gọi DB.
INVARIANT: min_price >= cogs_per_unit.
INVARIANT: raises ValueError nếu total_rate_deductions >= 1.0 (impossible margin).
"""
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class PriceRecommendation:
    min_price: Decimal           # giá bán tối thiểu để đạt target margin
    target_margin_pct: Decimal   # margin seller muốn (input)
    actual_margin_pct: Decimal   # margin thực với giá này (verify == target)
    breakdown: dict[str, Decimal]
    warning: str | None          # e.g. "Giá này cao hơn thị trường 40%"


def recommend_price(
    cogs_per_unit: Decimal,
    target_margin_pct: Decimal,            # 0.0 → 1.0
    platform_commission_rate: Decimal,
    transaction_fee_rate: Decimal,
    order_processing_fee: Decimal,
    affiliate_rate: Decimal,
    voucher_rate: Decimal,
    shipping_subsidy_rate: Decimal = Decimal("0"),
) -> PriceRecommendation:
    """
    Reverse P&L: từ COGS + desired margin → giá bán tối thiểu.

    Công thức:
      price × (1 - rate_fees - margin_rate) = COGS + fixed_fees
      → price = (COGS + fixed_fees) / (1 - rate_fees - margin_rate)

    Rate fees gồm: platform_commission + transaction_fee + affiliate + voucher + shipping_subsidy
    Fixed fees gồm: order_processing_fee (3,000 VND/đơn — absolute, không phải %)
    """
    if target_margin_pct < Decimal("0") or target_margin_pct >= Decimal("1"):
        raise ValueError(f"target_margin_pct phải trong khoảng [0, 1), nhận {target_margin_pct}")
    if cogs_per_unit < Decimal("0"):
        raise ValueError("cogs_per_unit không thể âm")

    total_rate_deductions = (
        platform_commission_rate
        + transaction_fee_rate
        + affiliate_rate
        + voucher_rate
        + shipping_subsidy_rate
        + target_margin_pct
    )

    if total_rate_deductions >= Decimal("1.0"):
        raise ValueError(
            f"Không thể đạt margin {target_margin_pct:.0%}: "
            f"tổng các khoản trừ {total_rate_deductions:.0%} ≥ 100%"
        )

    denominator = Decimal("1") - total_rate_deductions
    min_price = (cogs_per_unit + order_processing_fee) / denominator

    # Verify actual margin
    deductions = (
        cogs_per_unit
        + order_processing_fee
        + min_price * platform_commission_rate
        + min_price * transaction_fee_rate
        + min_price * affiliate_rate
        + min_price * voucher_rate
        + min_price * shipping_subsidy_rate
    )
    actual_margin = min_price - deductions
    actual_margin_pct = actual_margin / min_price if min_price > 0 else Decimal("0")

    return PriceRecommendation(
        min_price=min_price.quantize(Decimal("1")),
        target_margin_pct=target_margin_pct,
        actual_margin_pct=actual_margin_pct,
        breakdown={
            "cogs": cogs_per_unit,
            "platform_commission": (min_price * platform_commission_rate).quantize(Decimal("1")),
            "transaction_fee": (min_price * transaction_fee_rate).quantize(Decimal("1")),
            "order_processing": order_processing_fee,
            "affiliate": (min_price * affiliate_rate).quantize(Decimal("1")),
            "voucher": (min_price * voucher_rate).quantize(Decimal("1")),
            "margin": actual_margin.quantize(Decimal("1")),
        },
        warning=None,
    )
