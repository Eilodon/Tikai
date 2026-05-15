"""
Creator Cohort Retention Analysis.
INVARIANT: no DB, no AI — pure in-memory analysis of CreatorSummary lists.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal


@dataclass
class CreatorCohortInsight:
    creator_id: str
    creator_name: str
    trend: Literal["growing", "stable", "fading", "new", "churned"]
    gmv_first_period: Decimal
    gmv_last_period: Decimal
    change_pct: Decimal
    periods_active: int
    avg_orders_per_period: Decimal


def analyze_creator_cohort(
    creator_summaries_by_period: dict[str, list],
) -> list[CreatorCohortInsight]:
    """
    Compare creator performance across multiple periods.

    creator_summaries_by_period: dict mapping period label (e.g. "2026-W18") to
    list of CreatorSummary objects (from pl_calculator.py).

    Trend classification:
    - "growing": last_gmv > first_gmv * 1.2 (grew >20%)
    - "stable": within ±20% over the period window
    - "fading": last_gmv < first_gmv * 0.5 (dropped >50%)
    - "new": only appears in last period
    - "churned": only appears in first period, not in last

    Returns list sorted by gmv_last_period desc.
    """
    if not creator_summaries_by_period:
        return []

    periods = sorted(creator_summaries_by_period.keys())
    if not periods:
        return []

    first_period = periods[0]
    last_period = periods[-1]

    # Build creator-keyed dicts per period
    by_period: dict[str, dict[str, object]] = {}
    for period_key, summaries in creator_summaries_by_period.items():
        by_period[period_key] = {s.creator_id: s for s in summaries}

    # Collect all creator IDs across all periods
    all_creator_ids: set[str] = set()
    for summaries in creator_summaries_by_period.values():
        for s in summaries:
            all_creator_ids.add(s.creator_id)

    results: list[CreatorCohortInsight] = []

    for creator_id in all_creator_ids:
        # Find first appearance and name
        creator_name = creator_id
        for period_key in periods:
            summary = by_period[period_key].get(creator_id)
            if summary:
                creator_name = summary.creator_name
                break

        # GMV in first and last period
        first_summary = by_period[first_period].get(creator_id)
        last_summary = by_period[last_period].get(creator_id)

        gmv_first = Decimal(str(first_summary.attributed_gmv)) if first_summary else Decimal("0")
        gmv_last = Decimal(str(last_summary.attributed_gmv)) if last_summary else Decimal("0")

        # Count periods active and total orders
        periods_active = sum(1 for p in periods if by_period[p].get(creator_id) is not None)
        total_orders = sum(
            int(by_period[p][creator_id].order_count)
            for p in periods
            if by_period[p].get(creator_id) is not None
        )
        avg_orders = (
            Decimal(str(total_orders)) / Decimal(str(periods_active))
            if periods_active > 0
            else Decimal("0")
        )

        # Change pct — safe divide
        if gmv_first > 0:
            change_pct = (gmv_last - gmv_first) / gmv_first
        else:
            change_pct = Decimal("0")

        # Trend classification
        if first_summary is None and last_summary is not None:
            trend: Literal["growing", "stable", "fading", "new", "churned"] = "new"
        elif first_summary is not None and last_summary is None:
            trend = "churned"
        elif gmv_first > 0 and gmv_last > gmv_first * Decimal("1.2"):
            trend = "growing"
        elif gmv_first > 0 and gmv_last < gmv_first * Decimal("0.5"):
            trend = "fading"
        else:
            trend = "stable"

        results.append(
            CreatorCohortInsight(
                creator_id=creator_id,
                creator_name=creator_name,
                trend=trend,
                gmv_first_period=gmv_first,
                gmv_last_period=gmv_last,
                change_pct=change_pct,
                periods_active=periods_active,
                avg_orders_per_period=avg_orders,
            )
        )

    results.sort(key=lambda x: x.gmv_last_period, reverse=True)
    return results
