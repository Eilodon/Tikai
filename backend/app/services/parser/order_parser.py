"""
Order CSV/Excel parser — entry point for all file formats.
v2.0.0: Platform-aware parsing. Shopee exports use SHOPEE_COLUMN_ALIASES.

INVARIANT: parse_order_csv() never raises for bad individual rows — they go to failed_rows.
Raises UnsupportedFileTypeError only when the file cannot be read at all.
"""

import io
import zipfile

import chardet
import pandas as pd
import structlog

from app.services.parser.base import CanContinueMode, ParseResult, RawOrderRow
from app.services.parser.detector import detect_file_type
from app.services.parser.exceptions import UnsupportedFileTypeError
from app.services.parser.normalizer import (
    build_column_map,
    mask_pii,
    parse_date,
    parse_money,
)

log = structlog.get_logger()

_XLSX_MAX_UNCOMPRESSED_MB = 50
_XLSX_MAX_COMPRESSION_RATIO = 100

REQUIRED_FOR_FULL = {"tiktok_order_id", "gmv", "order_date"}
REQUIRED_FOR_FEES = {"platform_commission", "affiliate_commission", "voucher_cost"}
REQUIRED_MINIMUM = {"tiktok_order_id", "gmv"}


def parse_order_csv(file_bytes: bytes, original_filename: str) -> ParseResult:
    """
    Parse TikTok or Shopee order export file.
    Returns ParseResult — never raises for bad rows.
    Raises UnsupportedFileTypeError if file cannot be read at all.
    """
    # 1. Encoding detection
    detected = chardet.detect(file_bytes)
    encoding = detected.get("encoding") or "utf-8"
    log.info("parser.encoding_detected", encoding=encoding, confidence=detected.get("confidence"))

    # 2. Read file
    try:
        if original_filename.lower().endswith((".xlsx", ".xls")):
            # L1-H01: ZIP bomb guard — XLSX is a ZIP archive; check ratio before decompressing.
            # XLS (legacy binary format) is not a zip, so skip the check for it.
            if original_filename.lower().endswith(".xlsx"):
                try:
                    with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
                        uncompressed = sum(zi.file_size for zi in zf.infolist())
                        compressed = len(file_bytes)
                        if uncompressed > _XLSX_MAX_UNCOMPRESSED_MB * 1024 * 1024:
                            raise UnsupportedFileTypeError(
                                f"File XLSX quá lớn sau giải nén ({uncompressed // (1024 * 1024)}MB). "
                                f"Giới hạn {_XLSX_MAX_UNCOMPRESSED_MB}MB."
                            )
                        if compressed > 0 and uncompressed / compressed > _XLSX_MAX_COMPRESSION_RATIO:
                            raise UnsupportedFileTypeError(
                                "File XLSX có tỷ lệ nén bất thường. "
                                "Vui lòng export lại từ TikTok Seller Center."
                            )
                except zipfile.BadZipFile:
                    raise UnsupportedFileTypeError("File XLSX không hợp lệ (định dạng ZIP bị lỗi).")
            df = pd.read_excel(io.BytesIO(file_bytes), dtype=str)
        else:
            df = pd.read_csv(
                io.BytesIO(file_bytes),
                encoding=encoding,
                dtype=str,
                keep_default_na=False,
            )
    except Exception as e:
        raise UnsupportedFileTypeError(f"Cannot read file: {e}") from e

    # 3. Normalize headers
    df.columns = [str(c).strip() for c in df.columns]
    headers = list(df.columns)

    # 4. Detect file type WITH platform (v2.0.0)
    file_type, confidence_score, platform = detect_file_type(headers)
    log.info(
        "parser.detected",
        file_type=file_type,
        platform=platform,
        confidence=confidence_score,
    )

    # 5. Build column map — platform-aware (v2.0.0)
    col_map = build_column_map(headers, platform=platform)
    missing = [c for c in REQUIRED_MINIMUM if c not in col_map]

    # 6. Determine can_continue_mode
    can_continue_mode = _determine_mode(col_map)

    # 7. Prepare masked sample rows for AI rescue
    sample_rows_masked = [mask_pii(row) for row in df.head(5).to_dict(orient="records")]

    # 8. Parse rows
    rows: list[RawOrderRow] = []
    failed_rows: list[dict] = []

    for _, raw_row in df.iterrows():
        row_dict = raw_row.to_dict()
        try:
            parsed = _parse_single_row(row_dict, col_map)
            if parsed is not None:
                rows.append(parsed)
        except Exception as e:
            log.warning("parser.row_failed", error=str(e))
            failed_rows.append(row_dict)

    # 9. Date range
    dates = [r.order_date for r in rows if r.order_date is not None]
    date_range_start = min(dates) if dates else None
    date_range_end = max(dates) if dates else None

    return ParseResult(
        file_type=file_type,
        platform=platform,  # v2.0.0
        rows=rows,
        failed_rows=failed_rows,
        missing_columns=missing,
        can_continue_mode=can_continue_mode,
        date_range_start=date_range_start,
        date_range_end=date_range_end,
        encoding_detected=encoding,
        sample_rows_masked=sample_rows_masked,
        headers=headers,
    )


def _determine_mode(col_map: dict[str, str]) -> CanContinueMode:
    has_minimum = all(c in col_map for c in REQUIRED_MINIMUM)
    if not has_minimum:
        return "blocked"
    has_fees = all(c in col_map for c in REQUIRED_FOR_FEES)
    has_date = "order_date" in col_map
    if has_fees and has_date:
        return "full"
    return "limited"


def _parse_quantity(raw: str) -> int:
    """FIX BUG-NH1: handle Excel float-strings like '2.0' — '2.0'.isdigit() is False.
    Uses Decimal intermediate to avoid float imprecision on large integers."""
    if not raw:
        return 1
    try:
        from decimal import Decimal, InvalidOperation

        return max(1, int(Decimal(raw.split(".")[0] if "." in raw else raw)))
    except (ValueError, TypeError, InvalidOperation):
        return 1


def _require_date(parsed_date, raw_value: str, column_exists: bool):
    """FIX BUG-NH3 (v2): raise if date column exists but empty or unparseable."""
    from datetime import date

    if parsed_date is not None:
        return parsed_date
    if column_exists:
        raise ValueError(f"Cannot parse order_date: {raw_value!r}")
    return date.today()  # column absent — legacy export format


def _parse_single_row(row: dict, col_map: dict[str, str]) -> RawOrderRow | None:
    """Parse one CSV/Excel row → RawOrderRow.
    Returns None for empty rows (silently skipped).
    Raises Exception for bad rows → goes to failed_rows.
    """

    def get(canonical: str, default: str = "") -> str:
        actual_col = col_map.get(canonical)
        if actual_col is None:
            return default
        return str(row.get(actual_col, default)).strip()

    order_id = get("tiktok_order_id")
    if not order_id:
        return None  # silently skip empty rows

    order_date = parse_date(get("order_date")) if "order_date" in col_map else None

    return RawOrderRow(
        tiktok_order_id=order_id,
        sku_id=get("sku_id") or f"unknown_{order_id}",
        sku_name=get("sku_name") or "Unknown SKU",
        gmv=parse_money(get("gmv")),
        platform_commission=parse_money(get("platform_commission")),
        affiliate_commission=parse_money(get("affiliate_commission")),
        voucher_cost=parse_money(get("voucher_cost")),
        shipping_subsidy=parse_money(get("shipping_subsidy")),
        refund_amount=parse_money(get("refund_amount")),
        order_date=_require_date(order_date, get("order_date"), "order_date" in col_map),
        status=get("status") or "unknown",
        quantity=_parse_quantity(get("quantity")),
        transaction_fee=parse_money(get("transaction_fee")),
        order_processing_fee=parse_money(get("order_processing_fee")),
        creator_id=get("creator_id") or None,
        creator_name=get("creator_name") or None,
        refund_reason_raw=get("refund_reason_raw") or None,
        parent_sku_id=get("parent_sku_id") or None,
    )
