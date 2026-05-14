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
    cash_in_14d: Decimal        # expected settlement within next 14 days
    cash_in_30d: Decimal        # expected settlement within next 30 days
    pending_total: Decimal      # total unsettled amount
    settled_total: Decimal      # already settled


# TikTok VN typical settlement window: 14-16 days after order completion
SETTLEMENT_DAYS = 14


def calculate_settlement_forecast(
    rows: list[RawOrderRow],
    reference_date: date | None = None,
) -> SettlementForecast:
    """
    Estimate cash-in-14d based on completed orders not yet settled.
    Conservative estimate: uses net_revenue of completed orders within window.
    """
    from app.services.rule_engine.fee_calculator import calculate_net_revenue

    ref = reference_date or date.today()

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

        if days_since_order >= SETTLEMENT_DAYS:
            # Already within settlement window — should be settled
            settled += nr
        else:
            # Order placed, settlement pending
            pending += nr
            # Will it settle within 14 days from today?
            days_until_settlement = SETTLEMENT_DAYS - days_since_order
            if days_until_settlement <= 14:
                cash_14d += nr
            if days_until_settlement <= 30:
                cash_30d += nr

    return SettlementForecast(
        cash_in_14d=cash_14d,
        cash_in_30d=cash_30d,
        pending_total=pending,
        settled_total=settled,
    )
