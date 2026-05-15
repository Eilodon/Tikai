"""
Tests for Shopee order export parsing — v2.0.0.
Uses real Shopee VN export column names (verified against Shopee Seller Center VN, May 2026).

INVARIANT: Shopee exports must parse to the same RawOrderRow schema as TikTok exports.
The Rule Engine is platform-agnostic — it operates on RawOrderRow regardless of source.
"""

import io
from decimal import Decimal

import pandas as pd

from app.services.parser.detector import detect_file_type
from app.services.parser.order_parser import parse_order_csv

# ── Sample Shopee export data ─────────────────────────────────────────────────

SHOPEE_SAMPLE_ROWS = [
    {
        "Order ID": "240501ABCDE123",
        "Product Name": "Kem dưỡng da ban đêm",
        "Product SKU ID": "SKU-CREAM-001",
        "Original Price": "150000",
        "Order Status": "Completed",
        "Order Creation Date": "2026-05-01 10:30:00",
        "Quantity": "2",
        "Commission Fee": "3000",
        "Transaction Fee": "3000",
        "Seller Voucher": "10000",
        "Shipping Fee Subsidy": "15000",
        "Return Amount": "0",
    }
]

SHOPEE_SAMPLE_VI_ROWS = [
    {
        "Mã đơn hàng": "240501XYZW456",
        "Tên sản phẩm": "Serum vitamin C",
        "Mã SKU": "SKU-SERUM-002",
        "Giá sản phẩm": "250000",
        "Trạng thái đơn hàng": "Hoàn thành",
        "Ngày đặt hàng": "2026-05-02 09:15:00",
        "Số lượng": "1",
        "Phí hoa hồng": "5000",
        "Số tiền hoàn": "0",
    }
]

TIKTOK_HEADERS = [
    "Order ID",
    "Product Name",
    "SKU ID",
    "Original Price",
    "Order Status",
    "Order Creation Time",
    "Platform Commission Fee",
]


def _make_shopee_csv(rows: list[dict]) -> bytes:
    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    df.to_csv(buf, index=False, encoding="utf-8")
    return buf.getvalue()


# ── Detector tests ────────────────────────────────────────────────────────────


class TestShopeeDetector:
    def test_detects_shopee_en_file_type(self):
        csv_bytes = _make_shopee_csv(SHOPEE_SAMPLE_ROWS)
        headers = list(pd.read_csv(io.BytesIO(csv_bytes), nrows=0).columns)
        file_type, confidence, platform = detect_file_type(headers)
        assert platform == "shopee", f"Expected platform='shopee', got '{platform}'"
        assert confidence >= 0.4, f"Expected confidence >= 0.4, got {confidence}"
        assert "shopee" in file_type

    def test_detects_shopee_vi_file_type(self):
        csv_bytes = _make_shopee_csv(SHOPEE_SAMPLE_VI_ROWS)
        headers = list(pd.read_csv(io.BytesIO(csv_bytes), nrows=0).columns)
        file_type, confidence, platform = detect_file_type(headers)
        assert platform == "shopee"

    def test_does_not_misdetect_tiktok_as_shopee(self):
        _, _, platform = detect_file_type(TIKTOK_HEADERS)
        assert platform == "tiktok", (
            f"TikTok export should not be misdetected as Shopee. Got platform='{platform}'"
        )

    def test_detect_returns_3_tuple(self):
        """v2.0.0: detect_file_type returns (file_type, confidence, platform)."""
        result = detect_file_type(TIKTOK_HEADERS)
        assert len(result) == 3, (
            f"detect_file_type must return 3-tuple (type, confidence, platform), got {len(result)} elements"
        )
        file_type, confidence, platform = result
        assert isinstance(file_type, str)
        assert isinstance(confidence, float)
        assert isinstance(platform, str)


# ── Parser tests ──────────────────────────────────────────────────────────────


class TestShopeeParser:
    def test_parse_shopee_csv_returns_rows(self):
        csv_bytes = _make_shopee_csv(SHOPEE_SAMPLE_ROWS)
        result = parse_order_csv(csv_bytes, "shopee_order_20260501.csv")
        assert len(result.rows) == 1, "Expected 1 parsed row"
        assert result.platform == "shopee", (
            f"ParseResult.platform should be 'shopee', got '{result.platform}'"
        )

    def test_shopee_gmv_parsed_correctly(self):
        csv_bytes = _make_shopee_csv(SHOPEE_SAMPLE_ROWS)
        result = parse_order_csv(csv_bytes, "shopee_orders.csv")
        row = result.rows[0]
        assert row.gmv == Decimal("150000"), f"Expected GMV=150000, got {row.gmv}"

    def test_shopee_quantity_parsed(self):
        csv_bytes = _make_shopee_csv(SHOPEE_SAMPLE_ROWS)
        result = parse_order_csv(csv_bytes, "shopee_orders.csv")
        assert result.rows[0].quantity == 2, (
            f"Expected quantity=2 (from 'Quantity'='2'), got {result.rows[0].quantity}"
        )

    def test_shopee_fees_mapped(self):
        csv_bytes = _make_shopee_csv(SHOPEE_SAMPLE_ROWS)
        result = parse_order_csv(csv_bytes, "shopee_orders.csv")
        row = result.rows[0]
        assert row.platform_commission == Decimal("3000"), (
            f"Commission Fee not mapped correctly: {row.platform_commission}"
        )
        assert row.voucher_cost == Decimal("10000"), (
            f"Seller Voucher not mapped: {row.voucher_cost}"
        )

    def test_shopee_no_failed_rows(self):
        csv_bytes = _make_shopee_csv(SHOPEE_SAMPLE_ROWS)
        result = parse_order_csv(csv_bytes, "shopee_orders.csv")
        assert len(result.failed_rows) == 0, (
            f"Expected 0 failed rows, got {len(result.failed_rows)}: {result.failed_rows}"
        )

    def test_shopee_order_id_preserved(self):
        csv_bytes = _make_shopee_csv(SHOPEE_SAMPLE_ROWS)
        result = parse_order_csv(csv_bytes, "shopee_orders.csv")
        assert result.rows[0].tiktok_order_id == "240501ABCDE123"

    def test_shopee_vi_export_parses(self):
        """Vietnamese-language Shopee export should also parse correctly."""
        csv_bytes = _make_shopee_csv(SHOPEE_SAMPLE_VI_ROWS)
        result = parse_order_csv(csv_bytes, "shopee_vi_orders.csv")
        assert len(result.rows) == 1
        assert result.platform == "shopee"
        assert result.rows[0].gmv == Decimal("250000")
