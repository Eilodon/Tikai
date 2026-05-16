"""
COGS API — seller inputs cost-of-goods per SKU.
FIX QUAL-05: uses ORM-style update via mapped column, not raw text() SQL.
v1.0.0: Rate limiting on POST + result cap on GET (was unbounded for shops with 1000+ SKUs).
v2.1.0: POST /cogs/bulk-import accepts CSV upload.
"""

import csv
import io
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
    total_skus: int = 0  # v1.0.0: inform frontend if results were capped


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


@router.get("/cogs/template.csv")
async def download_cogs_template(
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Download CSV template pre-filled with shop's existing SKUs and current COGS.
    Seller opens in Excel, fills in cogs_per_unit, uploads via /cogs/bulk-import.
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

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["sku_id", "sku_name", "cogs_per_unit", "note (VND)"])
    for row in sku_rows:
        writer.writerow([row.sku_id, row.sku_name, cogs_map.get(row.sku_id, "0"), ""])

    content = buf.getvalue().encode("utf-8-sig")  # BOM for Excel
    filename = f"cogs_template_{date.today()}.csv"
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/cogs")
@limiter.limit("30/hour")  # v1.0.0: prevent repeated JSONB writes on shop record
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


def _parse_decimal(raw: str) -> Decimal:
    """Parse a locale-aware decimal string to Decimal.

    Handles:
    - US format:     "1,234.56"  → 1234.56
    - European format: "1.234,56" → 1234.56
    - Plain:         "123456"    → 123456
    - No separator:  "1234.56"   → 1234.56

    Rule: if both '.' and ',' appear, the last one is the decimal separator.
    If only ',' appears: if it splits into exactly two parts where the right
    part is NOT 3 digits, treat it as decimal; otherwise treat as thousands.
    """
    # Remove spaces and non-breaking spaces
    s = raw.strip().replace(" ", "").replace(" ", "")
    if not s:
        raise InvalidOperation("empty string")

    if "," in s and "." in s:
        # Both present: last character wins as decimal separator
        if s.rfind(",") > s.rfind("."):
            # European: "1.234,56" → remove dots, replace comma with dot
            s = s.replace(".", "").replace(",", ".")
        else:
            # US: "1,234.56" → remove commas
            s = s.replace(",", "")
    elif "," in s:
        # Comma only: check if it's a decimal separator or thousands separator
        parts = s.split(",")
        if len(parts) == 2 and len(parts[1]) != 3:
            # "1234,56" or "1,5" — comma is decimal separator
            s = s.replace(",", ".")
        else:
            # "1,234" or "1,234,567" — comma is thousands separator
            s = s.replace(",", "")
    # else: dot only or no separator — keep as-is

    return Decimal(s)


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
        raw_cogs_str = str(row.get(cogs_col, "")).strip()
        if not sku_id:
            skipped += 1
            continue
        try:
            cogs_val = _parse_decimal(raw_cogs_str)
            if cogs_val <= 0:
                raise ValueError("must be positive")
        except (InvalidOperation, ValueError):
            errors.append(
                f"Dòng {i}: SKU '{sku_id}' — giá trị '{raw_cogs_str}' không hợp lệ (cần số dương VND)."
            )
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

    log.info(
        "cogs.bulk_import",
        shop_id=str(shop.id),
        updated=updated,
        skipped=skipped,
        errors=len(errors),
    )
    return COGSBulkImportResponse(updated=updated, skipped=skipped, errors=errors)


# ── COGS Time-Series Entries ──────────────────────────────────────────────────


class COGSEntryItem(BaseModel):
    sku_id: str = Field(..., max_length=100)
    cogs_per_unit: Decimal = Field(..., gt=0)
    effective_date: date
    note: str | None = Field(None, max_length=200)


class COGSEntryResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    shop_id: str
    sku_id: str
    cogs_per_unit: str
    effective_date: date
    note: str | None
    created_at: date


@router.get("/cogs/history/{sku_id}")
async def get_cogs_history(
    sku_id: str,
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[COGSEntryResponse]:
    """Return COGS history for a SKU, ordered by effective_date desc, capped at 24."""
    from app.models.cogs_entry import COGSEntry

    rows = await db.scalars(
        select(COGSEntry)
        .where(COGSEntry.shop_id == shop.id, COGSEntry.sku_id == sku_id)
        .order_by(COGSEntry.effective_date.desc())
        .limit(24)
    )
    return [
        COGSEntryResponse(
            id=str(r.id),
            shop_id=str(r.shop_id),
            sku_id=r.sku_id,
            cogs_per_unit=str(r.cogs_per_unit),
            effective_date=r.effective_date,
            note=r.note,
            created_at=r.created_at.date() if hasattr(r.created_at, "date") else r.created_at,
        )
        for r in rows
    ]


@router.post("/cogs/entries", status_code=201)
@limiter.limit("30/hour")
async def create_cogs_entry(
    request: Request,
    body: COGSEntryItem,
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> COGSEntryResponse:
    """Create a timed COGS entry for a SKU."""
    from app.models.cogs_entry import COGSEntry

    entry = COGSEntry(
        shop_id=shop.id,
        sku_id=body.sku_id,
        cogs_per_unit=body.cogs_per_unit,
        effective_date=body.effective_date,
        note=body.note,
    )
    db.add(entry)
    await db.flush()
    await db.refresh(entry)
    return COGSEntryResponse(
        id=str(entry.id),
        shop_id=str(entry.shop_id),
        sku_id=entry.sku_id,
        cogs_per_unit=str(entry.cogs_per_unit),
        effective_date=entry.effective_date,
        note=entry.note,
        created_at=entry.created_at.date()
        if hasattr(entry.created_at, "date")
        else entry.created_at,
    )
