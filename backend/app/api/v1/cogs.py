"""
COGS API — seller inputs cost-of-goods per SKU.
FIX QUAL-05: uses ORM-style update via mapped column, not raw text() SQL.
v1.0.0: Rate limiting on POST + result cap on GET (was unbounded for shops with 1000+ SKUs).
v2.1.0: POST /cogs/bulk-import accepts CSV upload.
"""
import csv
import io
from decimal import Decimal, InvalidOperation
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import structlog
from app.core.auth import get_current_shop
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.models.order import Order
from app.models.shop import Shop

log = structlog.get_logger()

router = APIRouter()

# Cap: any shop with more than 500 distinct SKUs is extraordinary;
# returning more would degrade the settings UI without adding value.
MAX_COGS_SKUS = 500


class COGSItem(BaseModel):
    sku_id: str
    sku_name: str
    cogs_per_unit: Decimal = Field(..., gt=0, description="Cost per unit in VND")


class COGSBatchRequest(BaseModel):
    items: list[COGSItem]


class COGSItemResponse(BaseModel):
    sku_id: str
    sku_name: str
    cogs_per_unit: str  # string to preserve Decimal precision


class COGSBatchResponse(BaseModel):
    updated: int
    items: list[COGSItemResponse]
    total_skus: int = 0   # v1.0.0: inform frontend if results were capped


@router.get("/cogs")
async def get_cogs(
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> COGSBatchResponse:
    """Get COGS for all SKUs this shop has ever imported.
    v1.0.0: Capped at MAX_COGS_SKUS (500) — unbounded query could return thousands
    of rows for high-volume shops and degrade the settings page load time.
    """
    result = await db.execute(
        select(Order.sku_id, Order.sku_name)
        .where(Order.shop_id == shop.id)
        .distinct()
        .order_by(Order.sku_name)
        .limit(MAX_COGS_SKUS)
    )
    sku_rows = result.fetchall()
    cogs_map: dict = shop.cogs_map or {}

    items = [
        COGSItemResponse(
            sku_id=row.sku_id,
            sku_name=row.sku_name,
            cogs_per_unit=str(cogs_map.get(row.sku_id, "0")),
        )
        for row in sku_rows
    ]
    return COGSBatchResponse(updated=0, items=items, total_skus=len(items))


@router.post("/cogs")
@limiter.limit("30/hour")   # v1.0.0: prevent repeated JSONB writes on shop record
async def upsert_cogs(
    request: Request,
    body: COGSBatchRequest,
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> COGSBatchResponse:
    """Upsert COGS for multiple SKUs.
    FIX QUAL-05: uses shop.cogs_map ORM column directly.
    """
    current: dict = dict(shop.cogs_map or {})
    for item in body.items:
        current[item.sku_id] = str(item.cogs_per_unit)

    shop.cogs_map = current
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(shop, "cogs_map")
    await db.flush()

    return COGSBatchResponse(
        updated=len(body.items),
        items=[
            COGSItemResponse(
                sku_id=i.sku_id,
                sku_name=i.sku_name,
                cogs_per_unit=str(i.cogs_per_unit),
            )
            for i in body.items
        ],
        total_skus=len(body.items),
    )


# ── Bulk CSV Import ───────────────────────────────────────────────────────────

class COGSBulkImportResponse(BaseModel):
    updated: int
    skipped: int
    errors: list[str]


@router.post("/cogs/bulk-import")
@limiter.limit("10/hour")
async def bulk_import_cogs(
    request: Request,
    file: UploadFile,
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> COGSBulkImportResponse:
    """Upload a CSV file with columns: sku_id, cogs_per_unit (VND).
    Optional third column sku_name is ignored (for human readability).
    Rows with invalid cogs_per_unit are skipped and reported in errors.
    Max 500 rows per upload (matches MAX_COGS_SKUS cap).
    """
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            422,
            detail={"error": {"code": "INVALID_FILE", "message": "Chỉ chấp nhận file .csv"}},
        )

    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")  # utf-8-sig strips BOM from Excel exports
    except UnicodeDecodeError:
        text = raw.decode("latin-1", errors="replace")

    reader = csv.DictReader(io.StringIO(text))
    # Normalise header names (strip whitespace, lower)
    if reader.fieldnames is None:
        raise HTTPException(
            422,
            detail={"error": {"code": "EMPTY_FILE", "message": "File trống hoặc không có header."}},
        )

    headers = {h.strip().lower(): h for h in reader.fieldnames}
    sku_col = headers.get("sku_id") or headers.get("sku id") or headers.get("mã sku")
    cogs_col = (
        headers.get("cogs_per_unit")
        or headers.get("cogs per unit")
        or headers.get("giá vốn")
        or headers.get("cogs")
    )
    if not sku_col or not cogs_col:
        raise HTTPException(
            422,
            detail={
                "error": {
                    "code": "MISSING_COLUMNS",
                    "message": "File thiếu cột sku_id hoặc cogs_per_unit.",
                }
            },
        )

    current: dict = dict(shop.cogs_map or {})
    updated = 0
    skipped = 0
    errors: list[str] = []

    for i, row in enumerate(reader, start=2):
        if updated + skipped >= MAX_COGS_SKUS:
            errors.append(f"Dừng ở dòng {i}: vượt giới hạn {MAX_COGS_SKUS} SKU mỗi lần upload.")
            break

        sku_id = str(row.get(sku_col, "")).strip()
        raw_cogs = str(row.get(cogs_col, "")).strip().replace(",", "").replace(".", "")
        if not sku_id:
            skipped += 1
            continue
        try:
            cogs_val = Decimal(raw_cogs)
            if cogs_val <= 0:
                raise ValueError("must be positive")
        except (InvalidOperation, ValueError):
            errors.append(f"Dòng {i}: SKU '{sku_id}' — giá trị '{raw_cogs}' không hợp lệ (cần số dương).")
            skipped += 1
            continue

        current[sku_id] = str(cogs_val)
        updated += 1

    if updated > 0:
        shop.cogs_map = current
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(shop, "cogs_map")
        await db.flush()
        await db.commit()

    log.info("cogs.bulk_import", shop_id=str(shop.id), updated=updated, skipped=skipped, errors=len(errors))
    return COGSBulkImportResponse(updated=updated, skipped=skipped, errors=errors)
