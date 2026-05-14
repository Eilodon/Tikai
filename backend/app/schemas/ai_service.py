"""
AI Service I/O contracts.
INVARIANT: AI chỉ nhận những gì defined ở đây.
KHÔNG pass raw CSV, KHÔNG pass raw DB rows.
Tất cả số phải từ Rule Engine output.
"""
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, field_validator

from app.schemas import ConfidenceLevel, MoneyVND
from app.schemas.insight import LeakItem

# ── AI #1: Import Rescue ──────────────────────────────────────────────────────

class ImportRescueInput(BaseModel):
    headers: list[str]                    # column names từ file
    sample_rows: list[dict]               # max 5 rows, PII đã mask
    file_size_kb: int
    required_columns: list[str]

    @field_validator("sample_rows")
    @classmethod
    def limit_sample_rows(cls, v: list) -> list:
        return v[:5]  # hard limit 5 rows


class ImportRescueOutput(BaseModel):
    file_type_guess: Literal["order_export", "transaction_export", "settlement_export", "unknown"]
    file_type_confidence: Literal["high", "medium", "low"]
    missing_columns: list[str]
    can_continue_mode: Literal["full", "limited", "blocked"]
    user_message_vi: str
    next_step_instruction: str
    missing_data: list[str] = []


# ── AI #2: Aha Narrator ───────────────────────────────────────────────────────

class AhaNarrativeInput(BaseModel):
    shop_name: str
    period_label: str                     # "tuần từ 01/05 đến 07/05"
    gmv_total: MoneyVND
    net_revenue: MoneyVND
    cash_in_14d: MoneyVND | None = None   # FIX BUG-NH6: settlement forecast for narrative
    top_leaks: list[LeakItem]             # max 3 — enforced by caller
    is_net_revenue_mode: bool
    cogs_coverage_pct: Decimal

    @field_validator("top_leaks")
    @classmethod
    def limit_leaks(cls, v: list) -> list:
        return v[:3]


class AhaNarrativeOutput(BaseModel):
    summary: str                          # 2-3 câu
    key_insight: str                      # 1 câu vấn đề lớn nhất
    top_action_today: str                 # 1 câu action cụ thể
    missing_data: list[str] = []


# ── AI #3: Action Coach ───────────────────────────────────────────────────────

class ActionCoachInput(BaseModel):
    rule_id: str
    entity_id: str                        # FIX BUG-NC2+H7: unique entity ID for cache key
    entity_name: str
    metric_key: str
    metric_value: MoneyVND
    metric_label: str                     # human-readable Vietnamese label
    context_json: dict                    # additional context, NO raw financials


class ActionCoachOutput(BaseModel):
    action_title: str
    why_it_matters: str
    recommended_step: str
    risk_warning: str | None = None
    confidence: ConfidenceLevel
    forbidden_claims: list[str] = []      # AI self-declared things it cannot claim


# ── AI #4: Refund Clusterer ───────────────────────────────────────────────────

class RefundClusterInput(BaseModel):
    refund_reasons: list[str]             # raw text, max 200 items
    sku_name: str | None = None
    total_refund_count: int
    period_label: str

    @field_validator("refund_reasons")
    @classmethod
    def limit_reasons(cls, v: list) -> list:
        return v[:200]


class RefundCluster(BaseModel):
    label: str
    count: int
    pct: Decimal                          # 0-1
    sample_reasons: list[str]            # 2-3 examples


class RefundClusterOutput(BaseModel):
    clusters: list[RefundCluster]         # sorted by count desc, max 5
    suggested_actions: list[str]
    missing_data: list[str] = []


# ── AI #5: Weekly Receipt Writer ─────────────────────────────────────────────

class CompletedAction(BaseModel):
    action_title: str
    completed_at: str                     # ISO datetime string
    is_confirmed_impact: bool
    confirmed_delta: MoneyVND | None = None    # only if is_confirmed_impact
    estimated_delta: MoneyVND | None = None    # if not confirmed yet


class WeeklyReceiptInput(BaseModel):
    shop_name: str
    period_label: str
    actions_completed: list[CompletedAction]
    total_confirmed_saved: MoneyVND       # sum of confirmed_delta, from Rule Engine
    total_estimated_saved: MoneyVND       # sum of estimated_delta, from Rule Engine
    subscription_cost_vnd: MoneyVND


class WeeklyReceiptOutput(BaseModel):
    headline: str
    confirmed_section: str               # only confirmed savings
    estimated_section: str               # clearly labeled as estimate
    next_week_focus: str
    disclaimer: str                      # MANDATORY — never empty
    missing_data: list[str] = []

    @field_validator("disclaimer")
    @classmethod
    def disclaimer_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("disclaimer cannot be empty")
        return v


# ── AI #6: Support Reply (phase 2) ────────────────────────────────────────────
# Placeholder — không implement trong MVP
class SupportReplyInput(BaseModel):
    user_question: str
    context_snapshot: dict | None = None


class SupportReplyOutput(BaseModel):
    reply: str
    needs_human: bool = False
