"""
Fee Calculator — deterministic, Decimal-only.
INVARIANT: KHÔNG dùng float. KHÔNG gọi AI. KHÔNG gọi DB.

v1.0.0 FIXES:
- FeeConfigData now includes transaction_fee_rate + order_processing_fee_per_order
  (was in DB model but not in lightweight dataclass → new TikTok fees never estimated)
- apply_fee_config now estimates transaction_fee + order_processing_fee when missing
  from export file (older TikTok exports don't have these columns)
- import dataclasses moved to module level (was inside per-row loop — anti-pattern)
"""

import dataclasses
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.services.parser.base import RawOrderRow


@dataclass
class FeeConfigData:
    """Lightweight fee config passed to rule engine — no DB model dependency.

    v1.0.0: Added transaction_fee_rate and order_processing_fee_per_order.
    v2.1.0: Added effective_from/effective_to for per-order date-based config selection
    (F-1B-01 follow-up: prevents mid-period rate changes from affecting all orders).
    """

    version: str
    platform_commission_rate: Decimal
    transaction_fee_rate: Decimal = Decimal("0")
    order_processing_fee_per_order: Decimal = Decimal("0")
    category_overrides: dict[str, Decimal] = field(default_factory=dict)
    effective_from: date | None = None  # inclusive lower bound
    effective_to: date | None = None  # inclusive upper bound; None = current


def calculate_net_revenue(row: RawOrderRow) -> Decimal:
    """
    net_revenue = gmv
                - platform_commission
                - transaction_fee          (FIX P0-3: TikTok 6% từ 09/05/2026)
                - order_processing_fee     (FIX P0-3: 3,000 VND/đơn từ 27/10/2025)
                - affiliate_commission
                - voucher_cost
                - shipping_subsidy
                - refund_amount

    INVARIANT: result CÓ THỂ âm (voucher > gmv). Đây là valid — không clamp về 0.

    P0-3 WHY THIS MATTERS: transaction_fee (6%) + order_processing_fee (3,000đ/đơn)
    cộng lại tạo ra khoảng 7-9% undercount trong Net Revenue nếu bỏ qua.
    Với shop 186M GMV/tuần, đây là ~14M/tuần sai lệch — đủ để flip margin dương → âm.
    """
    return (
        row.gmv
        - row.platform_commission
        - row.transaction_fee
        - row.order_processing_fee
        - row.affiliate_commission
        - row.voucher_cost
        - row.shipping_subsidy
        - row.refund_amount
    )


def select_fee_config_for_date(order_date: date, configs: "list[FeeConfigData]") -> "FeeConfigData":
    """Pick the FeeConfig effective on order_date.

    Configs must be sorted by effective_from ascending.
    Iterates newest-first so the most specific match wins.
    Falls back to the oldest config when no perfect match exists
    (covers orders before the first recorded fee change).
    """
    for cfg in reversed(configs):
        from_ok = cfg.effective_from is None or cfg.effective_from <= order_date
        to_ok = cfg.effective_to is None or cfg.effective_to >= order_date
        if from_ok and to_ok:
            return cfg
    return configs[0]


def apply_fee_config(
    rows: list[RawOrderRow],
    fee_configs: "list[FeeConfigData] | FeeConfigData",
) -> tuple[list[RawOrderRow], list[str]]:
    """
    Cross-check row fees vs fee_config. Estimate missing fees.

    v1.0.0: Now also estimates transaction_fee and order_processing_fee when
    zero in the row but fee_config has non-zero rates. This covers older TikTok
    exports that don't include these columns → parser leaves them as 0.

    Without this, shops importing pre-09/05/2026 export formats would show
    inflated Net Revenue (missing 6% transaction_fee + 3,000 VND/order).
    The FeeConfig table already has these rates (from migration 0002) — we
    just needed to wire them through to apply_fee_config.

    KHÔNG raise — chỉ note discrepancies.
    """
    if isinstance(fee_configs, FeeConfigData):
        fee_configs = [fee_configs]
    multi_config = len(fee_configs) > 1

    updated: list[RawOrderRow] = []
    notes: list[str] = []

    for row in rows:
        fee_config = (
            select_fee_config_for_date(row.order_date, fee_configs)
            if multi_config
            else fee_configs[0]
        )
        # ── Platform commission estimation ────────────────────────────────────
        if row.gmv > 0 and row.platform_commission == Decimal("0"):
            estimated = row.gmv * fee_config.platform_commission_rate
            if estimated > Decimal("0"):
                notes.append(
                    f"order {row.tiktok_order_id}: platform_commission=0, "
                    f"estimated={estimated} from config rate {fee_config.platform_commission_rate}"
                )
                row = dataclasses.replace(row, platform_commission=estimated)

        # ── Transaction fee estimation (v1.0.0 NEW) ───────────────────────────
        # If the export file doesn't have a transaction_fee column (older format),
        # parser sets it to 0. Estimate from fee_config if available.
        if (
            row.gmv > 0
            and row.transaction_fee == Decimal("0")
            and fee_config.transaction_fee_rate > Decimal("0")
        ):
            # transaction_fee is applied to buyer-paid GMV, not net revenue
            estimated_tf = row.gmv * fee_config.transaction_fee_rate
            notes.append(
                f"order {row.tiktok_order_id}: transaction_fee=0, "
                f"estimated={estimated_tf} from config rate {fee_config.transaction_fee_rate}"
            )
            row = dataclasses.replace(row, transaction_fee=estimated_tf)

        # ── Order processing fee estimation (v1.0.0 NEW) ─────────────────────
        # Fixed per-completed-order fee. Only for non-refunded orders.
        if (
            row.order_processing_fee == Decimal("0")
            and fee_config.order_processing_fee_per_order > Decimal("0")
            and row.status.lower() not in ("refunded", "returned", "cancelled")
        ):
            notes.append(
                f"order {row.tiktok_order_id}: order_processing_fee=0, "
                f"estimated={fee_config.order_processing_fee_per_order} (config fixed fee)"
            )
            row = dataclasses.replace(
                row, order_processing_fee=fee_config.order_processing_fee_per_order
            )

        updated.append(row)

    return updated, notes


def safe_divide(
    numerator: Decimal, denominator: Decimal, default: Decimal = Decimal("0")
) -> Decimal:
    """INVARIANT: always check denominator != 0."""
    if denominator == Decimal("0"):
        return default
    return numerator / denominator
