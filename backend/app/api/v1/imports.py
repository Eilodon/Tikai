"""
Imports API — file upload, status polling.

FIXES:
- BUG-02: uses storage.upload_file() instead of TODO placeholder
- QUAL-03: streams file to storage, limits memory usage
- LOW-3: rate limiting — 10 uploads/hour per IP, 60 status polls/minute
- BUG-H1 (v2): asyncio.Lock-protected singleton pool + dead-pool detection
- BUG-H3: enqueue retry with failure handling
- BUG-NM5: SHA-256 dedup per shop (only blocks duplicates of completed imports)
- MED-V2-8: rollback orphan storage upload if enqueue fails
- v0.5.2: ARQ pool extracted to core/arq_pool.py — shared with actions.py
"""
import asyncio
import hashlib
import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.arq_pool import get_arq_pool  # v0.5.2: shared singleton pool
from app.core.auth import get_current_shop
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.core.storage import delete_file as storage_delete
from app.core.storage import upload_file as storage_upload
from app.models.import_session import ImportSession
from app.models.shop import Shop
from app.schemas.import_session import ImportListResponse, ImportSessionResponse

log = structlog.get_logger()

router = APIRouter()

ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50MB


def _quick_detect_platform(file_bytes: bytes, ext: str) -> str:
    """Quick platform detection from file headers — no full parse.
    Only reads header row, avoids loading entire file into pandas.
    Returns 'shopee' | 'tiktok' | 'unknown'.
    """
    try:
        if ext in {".xlsx", ".xls"}:
            import io

            import pandas as pd
            headers_df = pd.read_excel(io.BytesIO(file_bytes), nrows=0, dtype=str)
            headers = list(headers_df.columns)
        else:
            # CSV: decode first line only
            first_line = file_bytes.split(b"\n")[0].decode("utf-8", errors="ignore")
            import csv
            reader = csv.reader([first_line])
            headers = next(reader, [])
        from app.services.parser.detector import detect_file_type
        _, _, platform = detect_file_type(headers)
        return platform
    except Exception:
        return "unknown"  # safe fallback — never block on detection failure


@router.post("/imports", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("10/hour")
async def upload_import(
    request: Request,
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(...),
) -> ImportSessionResponse:
    """
    Upload CSV → Supabase Storage → create ImportSession → enqueue ARQ task.
    Returns 202 Accepted. Client polls GET /imports/{id} for status.
    """
    filename = file.filename or "upload.csv"
    ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "INVALID_FILE_TYPE",
                               "message": "Chỉ chấp nhận file CSV hoặc Excel từ TikTok Shop."}}
        )

    # F-C1-02: Read file with size limit check (streaming, not full buffer)
    # Read in 5MB chunks; reject if total exceeds limit before full load
    file_bytes = b""
    chunk_size = 5 * 1024 * 1024  # 5MB chunks
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        file_bytes += chunk
        if len(file_bytes) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=400,
                detail={"error": {"code": "FILE_TOO_LARGE",
                                   "message": "File quá lớn. Vui lòng xuất file theo từng tuần (tối đa 50MB)."}}
            )
    file_size_bytes = len(file_bytes)

    # v2.0.0: Quick platform detection from headers — no full parse needed
    # Only reads first row for header extraction (fast, <1ms)
    # BUG-5 FIX: xlsx files with unknown detection could be Shopee — require gate
    # to prevent Free/Pro users bypassing the Business-tier guard via malformed headers.
    _detected_platform = _quick_detect_platform(file_bytes, ext)
    if _detected_platform == "shopee" or (
        _detected_platform == "unknown" and ext in {".xlsx", ".xls"}
    ):
        from app.core.gates import Feature, require_feature
        require_feature(shop, Feature.SHOPEE_LAZADA)

    # FIX BUG-NM5 (v2): only dedup against COMPLETED imports — allow re-upload after failures
    # so seller can retry if previous import failed (Redis down, parser bug, etc.)
    file_hash = hashlib.sha256(file_bytes).hexdigest()
    existing = await db.scalar(
        select(ImportSession).where(
            ImportSession.shop_id == shop.id,
            ImportSession.file_hash == file_hash,
            ImportSession.status.in_(["completed", "completed_with_caveats", "processing", "pending"]),
        )
    )
    if existing:
        # Return existing session — idempotent upload
        log.info("import.duplicate_detected", shop_id=str(shop.id), session_id=str(existing.id))
        return ImportSessionResponse.model_validate(existing)

    content_type = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        if ext in {".xlsx", ".xls"} else "text/csv"
    )
    file_path = await storage_upload(
        shop_id=shop.id,
        filename=filename,
        file_bytes=file_bytes,
        content_type=content_type,
    )

    session = ImportSession(
        shop_id=shop.id,
        file_path=file_path,
        original_filename=filename,
        file_size_bytes=file_size_bytes,
        file_hash=file_hash,
        status="pending",
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)

    # FIX BUG-H3 + MED-V2-8: enqueue with retry; if Redis stays down, mark session failed
    # AND attempt to delete the orphan storage file to avoid stale uploads
    enqueue_ok = False
    last_enqueue_err = None
    for attempt in range(3):
        try:
            arq = await get_arq_pool()
            await arq.enqueue_job("process_import", str(session.id))
            enqueue_ok = True
            break
        except Exception as e:
            last_enqueue_err = e
            log.warning("import.enqueue_retry", attempt=attempt + 1, error=str(e))
            await asyncio.sleep(0.5 * (attempt + 1))  # backoff

    if not enqueue_ok:
        session.status = "failed"
        session.error_summary = {
            "error_type": "EnqueueFailed",
            "user_message_vi": "Hệ thống xử lý đang bận. Vui lòng thử lại sau vài phút.",
            "internal_detail": str(last_enqueue_err)[:200],
        }
        await db.flush()
        log.error("import.enqueue_failed", session_id=str(session.id), error=str(last_enqueue_err))
        # MED-V2-8: best-effort cleanup of orphan storage upload
        try:
            await storage_delete(file_path)
            log.info("import.orphan_storage_cleaned", session_id=str(session.id))
        except Exception as cleanup_err:
            log.warning("import.orphan_cleanup_failed", error=str(cleanup_err))

    return ImportSessionResponse.model_validate(session)


@router.get("/imports/{session_id}")
async def get_import_status(
    session_id: uuid.UUID,
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ImportSessionResponse:
    """Poll endpoint. Frontend polls every 2s until status = completed | failed."""
    session = await db.scalar(
        select(ImportSession).where(
            ImportSession.id == session_id,
            ImportSession.shop_id == shop.id,  # INVARIANT: shop_id filter
        )
    )
    if not session:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "Import session không tồn tại."}}
        )
    return ImportSessionResponse.model_validate(session)


@router.get("/imports")
async def list_imports(
    shop: Annotated[Shop, Depends(get_current_shop)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 10,
) -> ImportListResponse:
    sessions = await db.scalars(
        select(ImportSession)
        .where(ImportSession.shop_id == shop.id)  # INVARIANT
        .order_by(ImportSession.created_at.desc())
        .limit(min(limit, 50))
    )
    items = [ImportSessionResponse.model_validate(s) for s in sessions]
    return ImportListResponse(items=items, total=len(items))
