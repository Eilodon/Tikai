"""
Settlement Export Parser.
Handles TikTok Shop Settlement/Payout Export format.
"""

import io
from datetime import date
from decimal import Decimal

import chardet
import pandas as pd
import structlog

from app.services.parser.normalizer import parse_date, parse_money

log = structlog.get_logger()

SETTLEMENT_COLUMN_ALIASES: dict[str, list[str]] = {
    "payout_id": ["Payout ID", "Mã thanh toán"],
    "order_id": ["Order ID", "Mã đơn hàng"],
    "payout_amount": ["Payout Amount", "Số tiền thanh toán"],
    "payout_time": ["Payout Time", "Thời gian thanh toán"],
    "status": ["Status", "Trạng thái"],
    # Extended columns — present in newer TikTok settlement exports
    "transaction_type": ["Transaction Type", "Loại giao dịch"],
    "fee_amount": ["Fee Amount", "Số tiền phí", "Fee"],
    "description": ["Description", "Mô tả", "Remarks"],
    "adjustment_type": ["Adjustment Type", "Loại điều chỉnh"],
    "seller_sku": ["Seller SKU", "SKU người bán", "SKU"],
}


class SettlementRow:
    def __init__(
        self,
        payout_id: str,
        order_id: str | None,
        payout_amount: Decimal,
        payout_date: date | None,
        status: str,
        transaction_type: str = "",
        fee_amount: Decimal = Decimal("0"),
        description: str = "",
        adjustment_type: str = "",
        seller_sku: str = "",
    ):
        self.payout_id = payout_id
        self.order_id = order_id
        self.payout_amount = payout_amount
        self.payout_date = payout_date
        self.status = status
        self.transaction_type = transaction_type
        self.fee_amount = fee_amount
        self.description = description
        self.adjustment_type = adjustment_type
        self.seller_sku = seller_sku


def parse_settlement_csv(file_bytes: bytes, filename: str) -> list[SettlementRow]:
    """Parse TikTok Settlement Export for actual payout verification."""
    detected = chardet.detect(file_bytes)
    encoding = detected.get("encoding") or "utf-8"

    try:
        if filename.lower().endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(file_bytes), dtype=str)
        else:
            df = pd.read_csv(
                io.BytesIO(file_bytes), encoding=encoding, dtype=str, keep_default_na=False
            )
    except Exception as e:
        log.error("settlement_parser.read_failed", error=str(e))
        return []

    df.columns = [str(c).strip() for c in df.columns]
    headers_lower = {h.lower().strip(): h for h in df.columns}

    col_map: dict[str, str] = {}
    for canonical, aliases in SETTLEMENT_COLUMN_ALIASES.items():
        for alias in aliases:
            if alias.lower() in headers_lower:
                col_map[canonical] = headers_lower[alias.lower()]
                break

    rows: list[SettlementRow] = []
    for _, raw in df.iterrows():

        def get(key: str) -> str:
            col = col_map.get(key)
            return str(raw.get(col, "")).strip() if col else ""

        payout_id = get("payout_id")
        if not payout_id:
            continue

        rows.append(
            SettlementRow(
                payout_id=payout_id,
                order_id=get("order_id") or None,
                payout_amount=parse_money(get("payout_amount")),
                payout_date=parse_date(get("payout_time")),
                status=get("status"),
                transaction_type=get("transaction_type"),
                fee_amount=parse_money(get("fee_amount")),
                description=get("description"),
                adjustment_type=get("adjustment_type"),
                seller_sku=get("seller_sku"),
            )
        )

    log.info("settlement_parser.complete", rows=len(rows))
    return rows
