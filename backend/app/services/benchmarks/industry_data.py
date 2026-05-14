"""
Industry Benchmarks — TikTok Shop Vietnam.
Nguồn: Metric.vn 2025 annual report + YouNet ECI H1 2025.

Giai đoạn 1: hardcoded benchmarks từ public reports.
Giai đoạn 2 (khi ≥100 shops): aggregated anonymous benchmark từ Tikai data.

INVARIANT: mỗi BenchmarkComparison phải có source field — không show benchmark
           mà không có nguồn, tránh seller hiểu nhầm đây là số Tikai tự tính.
"""
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from app.services.rule_engine.fee_calculator import safe_divide

Category = Literal["fashion", "beauty", "food", "electronics", "home", "baby", "other"]

SOURCE = "Metric.vn / YouNet ECI 2025"

# Median refund rates by category (TikTok Shop VN)
REFUND_RATE_BENCHMARKS: dict[Category, Decimal] = {
    "fashion":     Decimal("0.15"),  # 15% — cao do size/màu issues
    "beauty":      Decimal("0.08"),
    "food":        Decimal("0.05"),
    "electronics": Decimal("0.06"),
    "home":        Decimal("0.10"),
    "baby":        Decimal("0.07"),
    "other":       Decimal("0.09"),
}

# Gross margin benchmarks (sau platform fees, trước COGS)
MARGIN_BENCHMARKS: dict[Category, Decimal] = {
    "fashion":     Decimal("0.25"),
    "beauty":      Decimal("0.35"),
    "food":        Decimal("0.15"),
    "electronics": Decimal("0.12"),
    "home":        Decimal("0.20"),
    "baby":        Decimal("0.22"),
    "other":       Decimal("0.20"),
}

# Total platform fee burden as % of GMV (all fees combined)
AVG_FEE_BURDEN: dict[Category, Decimal] = {
    "fashion":     Decimal("0.22"),
    "beauty":      Decimal("0.20"),
    "food":        Decimal("0.12"),
    "electronics": Decimal("0.15"),
    "home":        Decimal("0.18"),
    "baby":        Decimal("0.16"),
    "other":       Decimal("0.18"),
}


class BenchmarkComparison(BaseModel):
    metric: str
    metric_label: str  # Vietnamese label
    shop_value: Decimal
    industry_value: Decimal
    deviation_pct: Decimal          # (shop - industry) / industry
    verdict: Literal["better", "on_par", "worse"]
    label: str                       # human-readable verdict string
    category: Category
    source: str


def compare_to_industry(
    shop_refund_rate: Decimal,
    shop_margin_pct: Decimal | None,
    shop_fee_burden_pct: Decimal | None,
    category: Category,
) -> list[BenchmarkComparison]:
    """
    So sánh các chỉ số của shop với benchmark ngành.
    shop_margin_pct: tỷ lệ margin/GMV (None nếu chưa có COGS)
    shop_fee_burden_pct: tổng phí / GMV (None nếu không tính được)
    """
    results: list[BenchmarkComparison] = []

    # ── Refund Rate ──────────────────────────────────────────────────────────
    benchmark_refund = REFUND_RATE_BENCHMARKS[category]
    deviation = safe_divide(shop_refund_rate - benchmark_refund, benchmark_refund)

    if deviation < Decimal("-0.10"):
        verdict = "better"
        label = f"Tỷ lệ hoàn {shop_refund_rate:.0%} — tốt hơn ngành {category} ({benchmark_refund:.0%})"
    elif deviation > Decimal("0.30"):
        verdict = "worse"
        label = (
            f"Tỷ lệ hoàn {shop_refund_rate:.0%} — cao hơn ngành {benchmark_refund:.0%} "
            f"({deviation:+.0%})"
        )
    else:
        verdict = "on_par"
        label = f"Tỷ lệ hoàn {shop_refund_rate:.0%} — tương đương ngành ({benchmark_refund:.0%})"

    results.append(BenchmarkComparison(
        metric="refund_rate",
        metric_label="Tỷ lệ hoàn hàng",
        shop_value=shop_refund_rate,
        industry_value=benchmark_refund,
        deviation_pct=deviation,
        verdict=verdict,
        label=label,
        category=category,
        source=SOURCE,
    ))

    # ── Margin ───────────────────────────────────────────────────────────────
    if shop_margin_pct is not None:
        benchmark_margin = MARGIN_BENCHMARKS[category]
        margin_deviation = safe_divide(shop_margin_pct - benchmark_margin, benchmark_margin)

        if margin_deviation > Decimal("0.10"):
            margin_verdict = "better"
            margin_label = (
                f"Margin {shop_margin_pct:.0%} — tốt hơn ngành {benchmark_margin:.0%}"
            )
        elif margin_deviation < Decimal("-0.20"):
            margin_verdict = "worse"
            margin_label = (
                f"Margin {shop_margin_pct:.0%} — thấp hơn ngành {benchmark_margin:.0%} "
                f"({margin_deviation:+.0%})"
            )
        else:
            margin_verdict = "on_par"
            margin_label = f"Margin {shop_margin_pct:.0%} — tương đương ngành ({benchmark_margin:.0%})"

        results.append(BenchmarkComparison(
            metric="margin_pct",
            metric_label="Margin gộp",
            shop_value=shop_margin_pct,
            industry_value=benchmark_margin,
            deviation_pct=margin_deviation,
            verdict=margin_verdict,
            label=margin_label,
            category=category,
            source=SOURCE,
        ))

    # ── Fee Burden ───────────────────────────────────────────────────────────
    if shop_fee_burden_pct is not None:
        benchmark_fee = AVG_FEE_BURDEN[category]
        fee_deviation = safe_divide(shop_fee_burden_pct - benchmark_fee, benchmark_fee)

        if fee_deviation < Decimal("-0.10"):
            fee_verdict = "better"
            fee_label = f"Phí sàn {shop_fee_burden_pct:.0%} / GMV — thấp hơn ngành ({benchmark_fee:.0%})"
        elif fee_deviation > Decimal("0.15"):
            fee_verdict = "worse"
            fee_label = (
                f"Phí sàn {shop_fee_burden_pct:.0%} / GMV — cao hơn ngành {benchmark_fee:.0%} "
                f"({fee_deviation:+.0%})"
            )
        else:
            fee_verdict = "on_par"
            fee_label = f"Phí sàn {shop_fee_burden_pct:.0%} / GMV — tương đương ngành ({benchmark_fee:.0%})"

        results.append(BenchmarkComparison(
            metric="fee_burden_pct",
            metric_label="Tổng phí sàn / GMV",
            shop_value=shop_fee_burden_pct,
            industry_value=benchmark_fee,
            deviation_pct=fee_deviation,
            verdict=fee_verdict,
            label=fee_label,
            category=category,
            source=SOURCE,
        ))

    return results
