"""
Settlement Reconciliation API.

POST /v1/reconcile — upload a TikTok settlement CSV and cross-reference it
against the expected P&L from an existing InsightSnapshot.

INVARIANT: no AI calls, no float(), all Decimal.
Rate-limited: 20/hour per IP. Gated: Feature.BENCHMARKS (Pro+).
"""

import asyncio
import uuid
from decimal import Decimal
from typing import Annotated, Literal

import structlog
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_shop
from app.core.database import get_db
from app.core.gates import Feature, require_feature
from app.core.rate_limit import limiter
from app.models.insight_snapshot import InsightSnapshot
from app.models.shop import Shop
from app.services.parser.settlement_parser import parse_settlement_csv
from app.services.rule_engine.settlement_reconciler import reconcile_settlement

log = structlog.get_logger()

router = APIRouter()

MAX_SETTLEMENT_SIZE_BYTES = 20 * 1024 * 1024  # 20MB


class ReconcileResponse(BaseModel):
    total_payout: Decimal
    expected_payout: Decimal
    gap: Decimal
    gap_pct: Decimal  # abs(gap) / expected_payout, 0–1

    shipping_adjustments_total: Decimal
    refund_admin_fees_total: Decimal
    non_clawback_commissions: Decimal
    reserve_held: Decimal

    high_shipping_adj_skus: list[str]
    commission_waste_on_returns: Decimal

    verdict: Literal["matched", "minor_gap", "major_gap", "investigate"]
    action_items_vi: list[str]

    # Metadata
    settlement_rows_parsed: int
    snapshot_id: uuid.UUID | None = None


@router.post("/reconcile", status_code=status.HTTP_200_OK)
@limiter.limit("20/hour")
async def reconcile_settlement_upload(
    request: Request,
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(...),
    snapshot_id: uuid.UUID | None = Query(default=None),
    expected_payout_override: Decimal | None = Query(default=None, alias="expected_payout"),
) -> ReconcileResponse:
    """
    Upload a TikTok Settlement Export CSV and reconcile against expected P&L.

    Required: one of `snapshot_id` (to pull expected payout from an existing snapshot)
    or `expected_payout` (manual override in VND).

    Returns gap analysis, hidden cost breakdown, and Vietnamese action items.
    """
    require_feature(shop, Feature.BENCHMARKS)

    if snapshot_id is None and expected_payout_override is None:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "MISSING_EXPECTED_PAYOUT",
                    "message": "Cung cấp snapshot_id hoặc expected_payout để đối soát.",
                }
            },
        )

    # Read file with size guard
    file_bytes = b""
    chunk_size = 5 * 1024 * 1024
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        file_bytes += chunk
        if len(file_bytes) > MAX_SETTLEMENT_SIZE_BYTES:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "FILE_TOO_LARGE",
                        "message": "File settlement quá lớn (tối đa 20MB).",
                    }
                },
            )

    filename = file.filename or "settlement.csv"
    ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
    if ext not in {".csv", ".xlsx", ".xls"}:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "INVALID_FILE_TYPE",
                    "message": "Chỉ chấp nhận file CSV hoặc Excel từ TikTok Shop.",
                }
            },
        )

    # Resolve expected_payout
    expected_payout: Decimal
    resolved_snapshot_id: uuid.UUID | None = None

    if snapshot_id is not None:
        snapshot = await db.scalar(
            select(InsightSnapshot).where(
                InsightSnapshot.id == snapshot_id,
                InsightSnapshot.shop_id == shop.id,  # IDOR guard
            )
        )
        if snapshot is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": {
                        "code": "SNAPSHOT_NOT_FOUND",
                        "message": "Snapshot không tồn tại hoặc không thuộc shop này.",
                    }
                },
            )
        expected_payout = snapshot.net_revenue
        resolved_snapshot_id = snapshot.id
    else:
        expected_payout = expected_payout_override  # type: ignore[assignment]

    if expected_payout <= Decimal("0"):
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "INVALID_EXPECTED_PAYOUT",
                    "message": "expected_payout phải lớn hơn 0.",
                }
            },
        )

    # Parse settlement file in a thread (pandas is CPU-bound)
    rows = await asyncio.to_thread(parse_settlement_csv, file_bytes, filename)
    if not rows:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "EMPTY_SETTLEMENT",
                    "message": "Không đọc được dòng nào từ file settlement. "
                    "Kiểm tra định dạng file TikTok Settlement Export.",
                }
            },
        )

    # Sum non-clawback commissions from snapshot top_creators if available
    commission_on_refunded_orders = Decimal("0")
    if resolved_snapshot_id is not None and snapshot is not None:  # type: ignore[possibly-undefined]
        top_creators = snapshot.top_creators_json or []
        for c in top_creators:
            try:
                commission_on_refunded_orders += Decimal(
                    str(c.get("commission_on_refunded_orders", "0"))
                )
            except Exception:
                pass

    result = reconcile_settlement(
        settlement_rows=rows,
        expected_payout=expected_payout,
        commission_on_refunded_orders=commission_on_refunded_orders,
    )

    gap_pct = (
        abs(result.gap) / result.expected_payout
        if result.expected_payout > Decimal("0")
        else Decimal("0")
    )

    log.info(
        "reconcile.complete",
        shop_id=str(shop.id),
        snapshot_id=str(resolved_snapshot_id),
        verdict=result.verdict,
        gap_pct=str(gap_pct),
        rows=len(rows),
    )

    return ReconcileResponse(
        total_payout=result.total_payout,
        expected_payout=result.expected_payout,
        gap=result.gap,
        gap_pct=gap_pct,
        shipping_adjustments_total=result.shipping_adjustments_total,
        refund_admin_fees_total=result.refund_admin_fees_total,
        non_clawback_commissions=result.non_clawback_commissions,
        reserve_held=result.reserve_held,
        high_shipping_adj_skus=result.high_shipping_adj_skus,
        commission_waste_on_returns=result.commission_waste_on_returns,
        verdict=result.verdict,
        action_items_vi=result.action_items_vi,
        settlement_rows_parsed=len(rows),
        snapshot_id=resolved_snapshot_id,
    )
