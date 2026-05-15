import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, field_validator

from app.schemas import CanContinueMode, FileType


class ImportRescueMessage(BaseModel):
    """AI-generated rescue message for failed/limited imports."""

    file_type_guess: FileType
    file_type_confidence: str  # high | medium | low
    missing_columns: list[str]
    can_continue_mode: CanContinueMode
    user_message_vi: str
    next_step_instruction: str
    missing_data: list[str] = []


class ImportSessionResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    shop_id: uuid.UUID
    original_filename: str
    file_type: FileType
    status: str
    can_continue_mode: CanContinueMode | None
    date_range_start: date | None
    date_range_end: date | None
    rows_parsed: int
    rows_failed: int
    # ADR-SEC-007: error_summary is a raw dict in the DB but may contain
    # 'internal_detail' (exception message, possibly with file paths or schema info).
    # Strip it here so it never reaches the client.
    error_summary: dict[str, Any] | None
    ai_rescue_message: ImportRescueMessage | None
    # P0-1 fix: top 5 SKUs by GMV populated after successful import, for COGS prompt
    top_skus_for_cogs: list[dict] = []
    created_at: datetime
    updated_at: datetime

    @field_validator("error_summary", mode="after")
    @classmethod
    def _strip_internal_detail(cls, v: dict | None) -> dict | None:
        if v and "internal_detail" in v:
            v = {k: val for k, val in v.items() if k != "internal_detail"}
        return v or None


class ImportListResponse(BaseModel):
    items: list[ImportSessionResponse]
    total: int
