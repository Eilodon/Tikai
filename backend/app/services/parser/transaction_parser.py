"""
Transaction Export Parser.
Handles TikTok Shop Transaction Export format.
Used to cross-verify settlement amounts.
"""

import io
from datetime import date
from decimal import Decimal

import chardet
import pandas as pd
import structlog

from app.services.parser.normalizer import parse_date, parse_money

log = structlog.get_logger()


TRANSACTION_COLUMN_ALIASES: dict[str, list[str]] = {
    "transaction_id": ["Transaction ID", "Mã giao dịch"],
    "transaction_type": ["Transaction Type", "Loại giao dịch"],
    "order_id": ["Order ID", "Mã đơn hàng"],
    "settlement_amount": ["Settlement Amount", "Số tiền quyết toán"],
    "transaction_date": ["Transaction Date", "Ngày giao dịch"],
    "status": ["Status", "Trạng thái"],
}


class TransactionRow:
    def __init__(
        self,
        transaction_id: str,
        transaction_type: str,
        order_id: str | None,
        settlement_amount: Decimal,
        transaction_date: date | None,
        status: str,
    ):
        self.transaction_id = transaction_id
        self.transaction_type = transaction_type
        self.order_id = order_id
        self.settlement_amount = settlement_amount
        self.transaction_date = transaction_date
        self.status = status


def parse_transaction_csv(file_bytes: bytes, filename: str) -> list[TransactionRow]:
    """
    Parse TikTok Transaction Export.
    Returns list[TransactionRow] — settlement amounts for cash-in verification.
    """
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
        log.error("transaction_parser.read_failed", error=str(e))
        return []

    df.columns = [str(c).strip() for c in df.columns]

    # Build column map using transaction-specific aliases
    headers_lower = {h.lower().strip(): h for h in df.columns}
    col_map: dict[str, str] = {}
    for canonical, aliases in TRANSACTION_COLUMN_ALIASES.items():
        for alias in aliases:
            if alias.lower() in headers_lower:
                col_map[canonical] = headers_lower[alias.lower()]
                break

    rows: list[TransactionRow] = []
    for _, raw in df.iterrows():

        def get(key: str) -> str:
            col = col_map.get(key)
            return str(raw.get(col, "")).strip() if col else ""

        txn_id = get("transaction_id")
        if not txn_id:
            continue

        rows.append(
            TransactionRow(
                transaction_id=txn_id,
                transaction_type=get("transaction_type"),
                order_id=get("order_id") or None,
                settlement_amount=parse_money(get("settlement_amount")),
                transaction_date=parse_date(get("transaction_date")),
                status=get("status"),
            )
        )

    log.info("transaction_parser.complete", rows=len(rows))
    return rows
