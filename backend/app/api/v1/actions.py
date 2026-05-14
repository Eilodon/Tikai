"""
Actions API.
FIX BUG-08: verify_action_impact is now actually enqueued after complete.
LOW-3: rate limiting — 60 action updates/minute per IP.
v0.5.2: ARQ pool extracted to core/arq_pool.py — no more per-request connection.
"""
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.arq_pool import get_arq_pool  # FIX v0.5.2: shared singleton pool
from app.core.auth import get_current_shop
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.models.ai_action import AIAction
from app.models.shop import Shop
from app.schemas.ai_action import AIActionListResponse, AIActionResponse

router = APIRouter()


@router.get("/actions")
async def list_actions(
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: Literal["pending", "done", "dismissed", "all"] = "pending",  # F-3-03: enum validation
) -> AIActionListResponse:
    query = select(AIAction).where(AIAction.shop_id == shop.id)
    if status_filter != "all":
        query = query.where(AIAction.status == status_filter)
    query = query.order_by(AIAction.created_at.desc()).limit(20)

    actions = list(await db.scalars(query))
    items = [AIActionResponse.model_validate(a) for a in actions]
    pending_count = sum(1 for i in items if i.status == "pending")
    return AIActionListResponse(items=items, total=len(items), pending_count=pending_count)


@router.patch("/actions/{action_id}/complete")
@limiter.limit("60/minute")  # LOW-3
async def complete_action(
    request: Request,
    action_id: uuid.UUID,
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AIActionResponse:
    """Mark action as done. Enqueues P&L verification task after 7 days."""
    action = await _get_action(action_id, shop.id, db)
    action.status = "done"
    action.completed_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(action)

    # FIX BUG-08: actually enqueue verify_action_impact (deferred 7 days)
    try:
        arq = await get_arq_pool()
        await arq.enqueue_job(
            "verify_action_impact",
            str(action.id),
            _defer_by=timedelta(days=7),
        )
    except Exception as e:
        # Non-fatal: log but don't fail the complete action request
        import structlog
        structlog.get_logger().warning(
            "actions.enqueue_verify_failed", action_id=str(action_id), error=str(e)
        )

    return AIActionResponse.model_validate(action)


@router.patch("/actions/{action_id}/dismiss")
@limiter.limit("60/minute")  # LOW-3
async def dismiss_action(
    request: Request,
    action_id: uuid.UUID,
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AIActionResponse:
    action = await _get_action(action_id, shop.id, db)
    action.status = "dismissed"
    await db.flush()
    await db.refresh(action)
    return AIActionResponse.model_validate(action)


async def _get_action(
    action_id: uuid.UUID, shop_id: uuid.UUID, db: AsyncSession
) -> AIAction:
    action = await db.scalar(
        select(AIAction).where(
            AIAction.id == action_id,
            AIAction.shop_id == shop_id,  # INVARIANT
        )
    )
    if not action:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "Action không tồn tại."}}
        )
    return action
