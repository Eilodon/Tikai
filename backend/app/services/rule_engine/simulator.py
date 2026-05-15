"""
What-If Simulator — re-run P&L cho 1 SKU với params giả định.
INVARIANT: KHÔNG write vào DB. KHÔNG gọi AI. Tất cả in-memory.
INVARIANT: dùng Decimal, không dùng float.

Key insight: InsightSnapshot đã có đủ aggregated metrics để simulate.
Không cần re-read DB hay re-parse CSV.
"""

from dataclasses import dataclass
from decimal import Decimal

from app.services.rule_engine.fee_calculator import FeeConfigData, safe_divide


@dataclass
class SimulatorParams:
    """Params user muốn thay đổi — None = giữ nguyên từ snapshot thực."""

    affiliate_rate: Decimal | None = None
    voucher_rate: Decimal | None = None
    price_change_pct: Decimal | None = None  # -0.20 = giảm 20% giá
    platform_commission_rate: Decimal | None = None


@dataclass
class SimulationResult:
    # Before (từ snapshot thực)
    current_net_revenue: Decimal
    current_margin: Decimal | None
    current_margin_pct: Decimal | None

    # After (tính theo params mới)
    simulated_net_revenue: Decimal
    simulated_margin: Decimal | None
    simulated_margin_pct: Decimal | None

    # Delta
    net_revenue_delta: Decimal
    margin_delta: Decimal | None

    # "Cần bán thêm bao nhiêu đơn để bù lại?"
    breakeven_extra_orders: int | None  # None nếu không tính được

    verdict: str


def simulate_sku(
    sku_snapshot: dict,
    params: SimulatorParams,
    current_fee_config: FeeConfigData,
    cogs_per_unit: Decimal | None,
) -> SimulationResult:
    """
    Re-run P&L cho 1 SKU với params giả định.

    Approach: tính delta trên aggregated numbers, không per-order.
    Simplified model: assume order volume stays constant, only rates change.
    """
    current_gmv = Decimal(str(sku_snapshot.get("gmv", 0)))
    current_net_revenue = Decimal(str(sku_snapshot.get("net_revenue", 0)))
    current_aff = Decimal(str(sku_snapshot.get("affiliate_commission", 0) or 0))
    current_voucher = Decimal(str(sku_snapshot.get("voucher_cost", 0) or 0))
    order_count = int(sku_snapshot.get("order_count", 1) or 1)
    # BUG-SIM-01: use total_quantity (units sold) for COGS, not order_count (orders placed).
    # One order can contain multiple units; using order_count understates COGS for multi-unit orders.
    total_quantity = int(sku_snapshot.get("total_quantity") or order_count)

    # Current margin
    cogs_total = cogs_per_unit * total_quantity if cogs_per_unit is not None else None
    current_margin = (current_net_revenue - cogs_total) if cogs_total is not None else None
    current_margin_pct = (
        safe_divide(current_margin, current_gmv)
        if current_margin is not None and current_gmv > 0
        else None
    )

    # New affiliate cost
    if params.affiliate_rate is not None:
        new_aff = current_gmv * params.affiliate_rate
        aff_delta = current_aff - new_aff  # positive = saving
    else:
        new_aff = current_aff
        aff_delta = Decimal("0")

    # New voucher cost
    if params.voucher_rate is not None:
        new_voucher = current_gmv * params.voucher_rate
        voucher_delta = current_voucher - new_voucher
    else:
        new_voucher = current_voucher
        voucher_delta = Decimal("0")

    # Price change impact on net revenue
    price_delta_on_nr = Decimal("0")
    if params.price_change_pct is not None:
        # Simplified: volume stays same, price changes → GMV changes
        # Net revenue changes by gmv_delta × (1 - platform_rate_total)
        gmv_delta = current_gmv * params.price_change_pct
        total_rate = (
            current_fee_config.platform_commission_rate + current_fee_config.transaction_fee_rate
        )
        price_delta_on_nr = gmv_delta * (Decimal("1") - total_rate)

    simulated_net_revenue = current_net_revenue + aff_delta + voucher_delta + price_delta_on_nr
    simulated_margin = (simulated_net_revenue - cogs_total) if cogs_total is not None else None
    simulated_margin_pct = (
        safe_divide(simulated_margin, current_gmv)
        if simulated_margin is not None and current_gmv > 0
        else None
    )

    net_revenue_delta = simulated_net_revenue - current_net_revenue
    margin_delta = (
        simulated_margin - current_margin
        if simulated_margin is not None and current_margin is not None
        else None
    )

    # Breakeven: if flash sale reduces revenue, how many extra orders needed?
    breakeven_extra_orders = None
    if net_revenue_delta < 0 and order_count > 0:
        revenue_per_order = safe_divide(current_net_revenue, Decimal(order_count))
        if revenue_per_order > 0:
            extra = abs(net_revenue_delta) / revenue_per_order
            breakeven_extra_orders = int(extra.to_integral_value()) + 1

    # Human-readable verdict
    if simulated_margin_pct is not None and current_margin_pct is not None:
        direction = "tăng" if (margin_delta or Decimal("0")) >= 0 else "giảm"
        verdict = (
            f"Với thay đổi này, margin {direction} "
            f"từ {current_margin_pct:.0%} → {simulated_margin_pct:.0%}"
        )
    else:
        delta_str = (
            f"+{net_revenue_delta:,.0f}đ"
            if net_revenue_delta >= 0
            else f"{net_revenue_delta:,.0f}đ"
        )
        verdict = f"Net revenue thay đổi {delta_str}"

    return SimulationResult(
        current_net_revenue=current_net_revenue,
        current_margin=current_margin,
        current_margin_pct=current_margin_pct,
        simulated_net_revenue=simulated_net_revenue,
        simulated_margin=simulated_margin,
        simulated_margin_pct=simulated_margin_pct,
        net_revenue_delta=net_revenue_delta,
        margin_delta=margin_delta,
        breakeven_extra_orders=breakeven_extra_orders,
        verdict=verdict,
    )
