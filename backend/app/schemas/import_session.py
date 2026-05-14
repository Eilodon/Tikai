import uuid
from datetime import date, datetime

from pydantic import BaseModel

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
    error_summary: dict | None
    ai_rescue_message: ImportRescueMessage | None
    created_at: datetime
    updated_at: datetime


class ImportListResponse(BaseModel):
    items: list[ImportSessionResponse]
    total: int
