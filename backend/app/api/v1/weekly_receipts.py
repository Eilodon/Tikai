"""
Weekly Receipts API.
v1.0.0: list_receipts limit capped at 52 (1 year) — was unbounded (user could pass limit=10000).
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_shop
from app.core.database import get_db
from app.models.shop import Shop
from app.models.weekly_receipt import WeeklyReceipt

router = APIRouter()

MAX_RECEIPTS = 52  # 1 year of weekly receipts — more than any seller would need


class WeeklyReceiptResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    period_label: str
    total_confirmed_saved: Decimal
    total_estimated_saved: Decimal
    actions_completed_count: int
    headline: str
    confirmed_section: str
    estimated_section: str
    next_week_focus: str
    disclaimer: str
    is_read: bool
    created_at: datetime


@router.get("/weekly-receipts/latest")
async def get_latest_receipt(
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WeeklyReceiptResponse:
    receipt = await db.scalar(
        select(WeeklyReceipt)
        .where(WeeklyReceipt.shop_id == shop.id)
        .order_by(WeeklyReceipt.created_at.desc())
        .limit(1)
    )
    if not receipt:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "NOT_FOUND",
                    "message": "Chưa có weekly receipt. Sẽ có sau tuần đầu tiên sử dụng.",
                }
            },
        )
    return WeeklyReceiptResponse.model_validate(receipt)


@router.get("/weekly-receipts")
async def list_receipts(
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=8, ge=1, le=MAX_RECEIPTS),  # v1.0.0: validated cap
) -> list[WeeklyReceiptResponse]:
    """List weekly receipts.
    v1.0.0: limit validated via Query(le=52) — previously uncapped user param.
    """
    receipts = await db.scalars(
        select(WeeklyReceipt)
        .where(WeeklyReceipt.shop_id == shop.id)
        .order_by(WeeklyReceipt.created_at.desc())
        .limit(limit)
    )
    return [WeeklyReceiptResponse.model_validate(r) for r in receipts]


@router.patch("/weekly-receipts/{receipt_id}/read")
async def mark_receipt_read(
    receipt_id: uuid.UUID,
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WeeklyReceiptResponse:
    receipt = await db.scalar(
        select(WeeklyReceipt).where(
            WeeklyReceipt.id == receipt_id,
            WeeklyReceipt.shop_id == shop.id,
        )
    )
    if not receipt:
        raise HTTPException(
            status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "Không tìm thấy."}}
        )

    receipt.is_read = True
    await db.flush()
    return WeeklyReceiptResponse.model_validate(receipt)
