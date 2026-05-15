import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.schemas import ActionStatus, ActionType, ConfidenceLevel


class AIActionResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    shop_id: uuid.UUID
    action_type: ActionType
    rule_trigger: str
    title: str
    why: str
    do_today: str
    expected_impact: str
    confidence: ConfidenceLevel
    status: ActionStatus
    completed_at: datetime | None
    is_confirmed_impact: bool
    confirmed_delta: Decimal | None
    created_at: datetime


class CompleteActionResponse(AIActionResponse):
    """Response after marking action as done."""

    pass


class AIActionListResponse(BaseModel):
    items: list[AIActionResponse]
    total: int
    pending_count: int
