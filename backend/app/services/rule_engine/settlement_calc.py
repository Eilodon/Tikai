"""
Settlement Calculator — cash-in-14d forecast.
INVARIANT: deterministic, Decimal-only. No AI, no network calls.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.services.parser.base import RawOrderRow


@dataclass
class SettlementForecast:
    cash_in_14d: Decimal  # expected settlement within next 14 days
    cash_in_30d: Decimal  # expected settlement within next 30 days
    pending_total: Decimal  # total unsettled amount
    settled_total: Decimal  # already settled
    settlement_days: int  # tier used for this forecast


# TikTok VN settlement tier thresholds (ADR-005)
_TIER1_DAYS = 7   # LDR < 2% AND SFCR < 1%
_TIER2_DAYS = 14  # LDR 2–5% (default)
_TIER3_DAYS = 31  # LDR > 5% OR SFCR > 2%

SETTLEMENT_DAYS = _TIER2_DAYS  # kept for backwards-compat imports


def get_settlement_days(ldr_rate: Decimal | None, sfcr_rate: Decimal | None) -> int:
    """Return settlement window (days) based on TikTok shop health metrics."""
    ldr = ldr_rate or Decimal("0")
    sfcr = sfcr_rate or Decimal("0")

    if ldr > Decimal("0.05") or sfcr > Decimal("0.02"):
        return _TIER3_DAYS
    if ldr < Decimal("0.02") and sfcr < Decimal("0.01"):
        return _TIER1_DAYS
    return _TIER2_DAYS


def calculate_settlement_forecast(
    rows: list[RawOrderRow],
    reference_date: date | None = None,
    ldr_rate: Decimal | None = None,
    sfcr_rate: Decimal | None = None,
) -> SettlementForecast:
    """
    Estimate cash-in-14d based on completed orders not yet settled.
    Conservative estimate: uses net_revenue of completed orders within window.
    Settlement window is dynamic: Tier1=7d, Tier2=14d, Tier3=31d based on shop health.
    """
    from app.services.rule_engine.fee_calculator import calculate_net_revenue

    ref = reference_date or date.today()
    settlement_days = get_settlement_days(ldr_rate, sfcr_rate)

    cash_14d = Decimal("0")
    cash_30d = Decimal("0")
    pending = Decimal("0")
    settled = Decimal("0")

    for row in rows:
        if row.status.lower() in ("refunded", "returned", "cancelled"):
            continue

        nr = calculate_net_revenue(row)
        if nr <= 0:
            continue

        days_since_order = (ref - row.order_date).days

        if days_since_order < 0:
            continue  # future-dated order — skip silently to avoid corrupting forecast

        if days_since_order >= settlement_days:
            # Already within settlement window — should be settled
            settled += nr
        else:
            # Order placed, settlement pending
            pending += nr
            days_until_settlement = settlement_days - days_since_order
            if days_until_settlement <= 14:
                cash_14d += nr
            if days_until_settlement <= 30:
                cash_30d += nr

    return SettlementForecast(
        cash_in_14d=cash_14d,
        cash_in_30d=cash_30d,
        pending_total=pending,
        settled_total=settled,
        settlement_days=settlement_days,
    )
