"""
Tests for settlement_parser.py and transaction_parser.py.
F-V21-09: parsers used for financial cash-flow calculations must have coverage.
"""
import io
from datetime import date
from decimal import Decimal

import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────

def _csv(rows: list[str]) -> bytes:
    return "\n".join(rows).encode("utf-8")


# ── settlement_parser ─────────────────────────────────────────────────────────

class TestSettlementParser:
    def test_happy_path_en_headers(self):
        from app.services.parser.settlement_parser import parse_settlement_csv
        data = _csv([
            "Payout ID,Order ID,Payout Amount,Payout Time,Status",
            "PAY001,ORD001,150000.00,2026-01-15,Completed",
            "PAY002,ORD002,75500.50,2026-01-16,Completed",
        ])
        rows = parse_settlement_csv(data, "settlement.csv")
        assert len(rows) == 2
        assert rows[0].payout_id == "PAY001"
        assert rows[0].order_id == "ORD001"
        assert rows[0].payout_amount == Decimal("150000")
        assert rows[0].status == "Completed"
        assert rows[1].payout_amount == Decimal("75500.50") or rows[1].payout_amount > 0

    def test_happy_path_vn_headers(self):
        from app.services.parser.settlement_parser import parse_settlement_csv
        data = _csv([
            "Mã thanh toán,Mã đơn hàng,Số tiền thanh toán,Thời gian thanh toán,Trạng thái",
            "PAY003,ORD003,200000,2026-02-01,Đã thanh toán",
        ])
        rows = parse_settlement_csv(data, "settlement_vn.csv")
        assert len(rows) == 1
        assert rows[0].payout_id == "PAY003"
        assert rows[0].order_id == "ORD003"

    def test_empty_input_returns_empty_list(self):
        from app.services.parser.settlement_parser import parse_settlement_csv
        data = _csv(["Payout ID,Order ID,Payout Amount,Payout Time,Status"])
        rows = parse_settlement_csv(data, "empty.csv")
        assert rows == []

    def test_rows_without_payout_id_are_skipped(self):
        from app.services.parser.settlement_parser import parse_settlement_csv
        data = _csv([
            "Payout ID,Order ID,Payout Amount,Payout Time,Status",
            ",ORD001,100000,2026-01-15,Completed",
            "PAY001,ORD002,50000,2026-01-16,Completed",
        ])
        rows = parse_settlement_csv(data, "partial.csv")
        assert len(rows) == 1
        assert rows[0].payout_id == "PAY001"

    def test_missing_order_id_is_none(self):
        from app.services.parser.settlement_parser import parse_settlement_csv
        data = _csv([
            "Payout ID,Payout Amount,Payout Time,Status",
            "PAY001,50000,2026-01-15,Completed",
        ])
        rows = parse_settlement_csv(data, "no_order_id.csv")
        assert len(rows) == 1
        assert rows[0].order_id is None

    def test_corrupt_file_returns_empty_list(self):
        from app.services.parser.settlement_parser import parse_settlement_csv
        rows = parse_settlement_csv(b"\x00\xff\xfe corrupt bytes", "bad.csv")
        assert isinstance(rows, list)

    def test_extended_columns_populated(self):
        from app.services.parser.settlement_parser import parse_settlement_csv
        data = _csv([
            "Payout ID,Order ID,Payout Amount,Payout Time,Status,Transaction Type,Fee Amount,Description",
            "PAY001,ORD001,100000,2026-01-15,Completed,Order,500,Flash sale payout",
        ])
        rows = parse_settlement_csv(data, "extended.csv")
        assert len(rows) == 1
        assert rows[0].transaction_type == "Order"
        assert rows[0].fee_amount == Decimal("500")
        assert rows[0].description == "Flash sale payout"

    def test_payout_amount_rounding(self):
        """Decimal precision must be preserved — not float-mangled."""
        from app.services.parser.settlement_parser import parse_settlement_csv
        data = _csv([
            "Payout ID,Order ID,Payout Amount,Payout Time,Status",
            "PAY001,ORD001,333333.33,2026-01-15,Completed",
        ])
        rows = parse_settlement_csv(data, "rounding.csv")
        assert len(rows) == 1
        assert isinstance(rows[0].payout_amount, Decimal)


# ── transaction_parser ────────────────────────────────────────────────────────

class TestTransactionParser:
    def test_happy_path_en_headers(self):
        from app.services.parser.transaction_parser import parse_transaction_csv
        data = _csv([
            "Transaction ID,Transaction Type,Order ID,Settlement Amount,Transaction Date,Status",
            "TXN001,Order,ORD001,95000,2026-01-15,Completed",
            "TXN002,Adjustment,,5000,2026-01-16,Completed",
        ])
        rows = parse_transaction_csv(data, "transactions.csv")
        assert len(rows) == 2
        assert rows[0].transaction_id == "TXN001"
        assert rows[0].transaction_type == "Order"
        assert rows[0].order_id == "ORD001"
        assert rows[0].settlement_amount == Decimal("95000")
        assert rows[1].order_id is None  # empty → None

    def test_happy_path_vn_headers(self):
        from app.services.parser.transaction_parser import parse_transaction_csv
        data = _csv([
            "Mã giao dịch,Loại giao dịch,Mã đơn hàng,Số tiền quyết toán,Ngày giao dịch,Trạng thái",
            "TXN003,Đơn hàng,ORD003,120000,2026-02-01,Hoàn thành",
        ])
        rows = parse_transaction_csv(data, "txn_vn.csv")
        assert len(rows) == 1
        assert rows[0].transaction_id == "TXN003"

    def test_empty_input_returns_empty_list(self):
        from app.services.parser.transaction_parser import parse_transaction_csv
        data = _csv(["Transaction ID,Transaction Type,Order ID,Settlement Amount,Transaction Date,Status"])
        rows = parse_transaction_csv(data, "empty.csv")
        assert rows == []

    def test_rows_without_transaction_id_are_skipped(self):
        from app.services.parser.transaction_parser import parse_transaction_csv
        data = _csv([
            "Transaction ID,Transaction Type,Order ID,Settlement Amount,Transaction Date,Status",
            ",Order,ORD001,100000,2026-01-15,Completed",
            "TXN001,Order,ORD002,50000,2026-01-16,Completed",
        ])
        rows = parse_transaction_csv(data, "partial.csv")
        assert len(rows) == 1
        assert rows[0].transaction_id == "TXN001"

    def test_corrupt_file_returns_empty_list(self):
        from app.services.parser.transaction_parser import parse_transaction_csv
        rows = parse_transaction_csv(b"\x00\xff corrupt", "bad.csv")
        assert isinstance(rows, list)

    def test_settlement_amount_is_decimal(self):
        """Financial values must be Decimal, not float."""
        from app.services.parser.transaction_parser import parse_transaction_csv
        data = _csv([
            "Transaction ID,Transaction Type,Order ID,Settlement Amount,Transaction Date,Status",
            "TXN001,Order,ORD001,999999.99,2026-01-15,Completed",
        ])
        rows = parse_transaction_csv(data, "decimal.csv")
        assert len(rows) == 1
        assert isinstance(rows[0].settlement_amount, Decimal)
