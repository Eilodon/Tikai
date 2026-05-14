import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, field_validator

from app.schemas import ConfidenceLevel, MoneyVND


class LeakItem(BaseModel):
    """A detected revenue leak. estimated_loss ALWAYS from Rule Engine — never AI."""

    type: Literal["sku", "creator", "category"]
    id: str
    name: str
    estimated_loss: MoneyVND
    reason: Literal[
        "voucher_high",
        "affiliate_high",
        "cogs_missing",
        "refund_spike",
        "commission_exceeds_margin",
    ]
    confidence: ConfidenceLevel
    can_act_now: bool

    @field_validator("estimated_loss")
    @classmethod
    def estimated_loss_non_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("estimated_loss must be non-negative")
        return v


class ActionTrigger(BaseModel):
    """Rule Engine trigger — input for Action Coach AI function."""

    rule_id: str
    entity_type: Literal["sku", "creator", "shop"]
    entity_id: str
    entity_name: str
    metric_key: str  # key in source data, used for fact-anchoring
    metric_value: MoneyVND
    priority: int  # 1 = highest priority


class SKUSummaryItem(BaseModel):
    """Top SKU summary for frontend display."""

    sku_id: str
    sku_name: str
    gmv: MoneyVND
    net_revenue: MoneyVND
    order_count: int
    refund_rate: Decimal  # 0-1
    margin_pct: Decimal | None  # None if COGS missing — ratio relative to GMV
    margin: Decimal | None = None  # absolute VND (net_revenue - COGS); None if COGS missing
    gmv_rank: int


# FIX BUG-C2: CreatorSummaryItem was missing — top_creators always empty in API response
class CreatorSummaryItem(BaseModel):
    """Creator summary for frontend display — mirrors CreatorSummary dataclass.
    NOTE: BUG-NC1 must be fixed in process_import.py BEFORE deploying this fix,
    otherwise existing snapshots will fail deserialization.
    """

    creator_id: str
    creator_name: str
    attributed_gmv: MoneyVND
    attributed_net_revenue: MoneyVND
    total_commission: MoneyVND
    order_count: int
    # revenue_efficiency = attributed_net_revenue / total_commission
    # < 1.0 means creator cost > net revenue generated after all platform fees
    revenue_efficiency: Decimal | None  # None if commission=0


class InsightSnapshotResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    shop_id: uuid.UUID
    period_start: date
    period_end: date

    gmv_total: MoneyVND
    net_revenue: MoneyVND
    total_orders: int
    total_refunds: int
    refund_rate: Decimal
    cash_in_14d: MoneyVND | None

    top_leaks: list[LeakItem]
    top_skus: list[SKUSummaryItem]
    top_creators: list[CreatorSummaryItem]  # FIX BUG-C2: was missing, creator table always empty
    action_triggers: list[ActionTrigger]

    rule_engine_version: str
    fee_config_version: str
    cogs_coverage_pct: Decimal
    is_net_revenue_mode: bool
    # NEW: period metadata for incomplete-period warning
    days_in_period: int = 7
    is_partial_period: bool = False
    created_at: datetime
