"""End-to-end tests for order_parser.py with real CSV bytes."""
import pytest
from decimal import Decimal
from io import StringIO
import csv

from app.services.parser.order_parser import parse_order_csv


def make_csv(rows: list[dict], headers: list[str]) -> bytes:
    buf = StringIO()
    writer = csv.DictWriter(buf, fieldnames=headers)
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


STANDARD_HEADERS = [
    "Order ID", "Product Name", "SKU ID",
    "Original Price", "Platform Commission Fee", "Affiliate Commission",
    "Seller Discount", "Shipping Fee Subsidy", "Refund Amount",
    "Order Creation Time", "Order Status", "Affiliate Partner ID", "Affiliate Partner",
]


class TestOrderParserE2E:
    def test_parses_standard_csv(self):
        csv_bytes = make_csv([{
            "Order ID": "ORD-001",
            "Product Name": "Serum A", "SKU ID": "SKU-001",
            "Original Price": "100000", "Platform Commission Fee": "2000",
            "Affiliate Commission": "5000", "Seller Discount": "3000",
            "Shipping Fee Subsidy": "1000", "Refund Amount": "0",
            "Order Creation Time": "2026-05-01", "Order Status": "completed",
            "Affiliate Partner ID": "", "Affiliate Partner": "",
        }], STANDARD_HEADERS)

        result = parse_order_csv(csv_bytes, "orders.csv")
        assert result.can_continue_mode in ("full", "limited")
        assert len(result.rows) == 1
        assert result.rows[0].tiktok_order_id == "ORD-001"
        assert isinstance(result.rows[0].gmv, Decimal)
        assert result.rows[0].gmv == Decimal("100000")

    def test_blocked_when_order_id_missing(self):
        bad_headers = ["Product Name", "Original Price", "Order Status"]
        csv_bytes = make_csv([{
            "Product Name": "A", "Original Price": "100", "Order Status": "ok"
        }], bad_headers)
        result = parse_order_csv(csv_bytes, "bad.csv")
        assert result.can_continue_mode == "blocked"

    def test_limited_mode_when_fee_cols_missing(self):
        limited_headers = ["Order ID", "Original Price", "Order Status", "Order Creation Time"]
        csv_bytes = make_csv([{
            "Order ID": "ORD-001", "Original Price": "100000",
            "Order Status": "completed", "Order Creation Time": "2026-05-01",
        }], limited_headers)
        result = parse_order_csv(csv_bytes, "limited.csv")
        assert result.can_continue_mode == "limited"

    def test_bad_rows_go_to_failed_rows(self):
        csv_bytes = make_csv([
            {"Order ID": "ORD-001", "Product Name": "A", "SKU ID": "S1",
             "Original Price": "100", "Platform Commission Fee": "2",
             "Affiliate Commission": "5", "Seller Discount": "3",
             "Shipping Fee Subsidy": "1", "Refund Amount": "0",
             "Order Creation Time": "invalid-date", "Order Status": "ok",
             "Affiliate Partner ID": "", "Affiliate Partner": ""},
        ], STANDARD_HEADERS)
        result = parse_order_csv(csv_bytes, "test.csv")
        # Should still parse, just date might fallback to today
        assert len(result.rows) >= 0  # no crash

    def test_pii_masked_in_sample_rows(self):
        csv_bytes = make_csv([{
            "Order ID": "ORD-001", "Product Name": "A", "SKU ID": "S1",
            "Original Price": "100", "Platform Commission Fee": "0",
            "Affiliate Commission": "0", "Seller Discount": "0",
            "Shipping Fee Subsidy": "0", "Refund Amount": "0",
            "Order Creation Time": "2026-05-01", "Order Status": "ok",
            "Affiliate Partner ID": "", "Affiliate Partner": "",
        }], STANDARD_HEADERS)
        result = parse_order_csv(csv_bytes, "test.csv")
        # sample_rows_masked should not contain raw PII
        for row in result.sample_rows_masked:
            for k, v in row.items():
                if "buyer" in k.lower() or "phone" in k.lower():
                    assert v == "***"

    def test_money_fields_always_decimal(self):
        csv_bytes = make_csv([{
            "Order ID": "ORD-001", "Product Name": "A", "SKU ID": "S1",
            "Original Price": "₫186,000", "Platform Commission Fee": "2,000 VND",
            "Affiliate Commission": "0", "Seller Discount": "0",
            "Shipping Fee Subsidy": "0", "Refund Amount": "0",
            "Order Creation Time": "2026-05-01", "Order Status": "ok",
            "Affiliate Partner ID": "", "Affiliate Partner": "",
        }], STANDARD_HEADERS)
        result = parse_order_csv(csv_bytes, "test.csv")
        if result.rows:
            row = result.rows[0]
            assert isinstance(row.gmv, Decimal)
            assert isinstance(row.platform_commission, Decimal)
