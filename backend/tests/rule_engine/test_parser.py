"""
Tests for parser normalizer.
Run: pytest tests/rule_engine/test_parser.py -v
"""

from decimal import Decimal

from app.services.parser.detector import detect_file_type
from app.services.parser.normalizer import build_column_map, mask_pii, parse_date, parse_money


class TestParseMoney:
    def test_plain_integer(self):
        assert parse_money(186000) == Decimal("186000")

    def test_string_with_vnd_symbol(self):
        assert parse_money("₫186,000") == Decimal("186000")

    def test_string_with_vnd_text(self):
        assert parse_money("186,000 VND") == Decimal("186000")

    def test_string_with_commas(self):
        assert parse_money("186,000,000") == Decimal("186000000")

    def test_decimal_string(self):
        assert parse_money("186000.5000") == Decimal("186000.5000")

    def test_none_returns_zero(self):
        """CRITICAL INVARIANT: None input must return Decimal('0')."""
        result = parse_money(None)
        assert result == Decimal("0")
        assert isinstance(result, Decimal)

    def test_empty_string_returns_zero(self):
        assert parse_money("") == Decimal("0")

    def test_dash_returns_zero(self):
        assert parse_money("-") == Decimal("0")

    def test_nan_float_returns_zero(self):

        result = parse_money(float("nan"))
        assert result == Decimal("0")

    def test_result_is_always_decimal_never_float(self):
        """CRITICAL INVARIANT: result type must be Decimal."""
        for input_val in [100, "100", "₫100", None, "", 100.5]:
            result = parse_money(input_val)
            assert isinstance(result, Decimal), (
                f"parse_money({input_val!r}) returned {type(result)}, expected Decimal"
            )

    def test_zero_string(self):
        assert parse_money("0") == Decimal("0")

    def test_na_value_returns_zero(self):
        assert parse_money("N/A") == Decimal("0")
        assert parse_money("n/a") == Decimal("0")


class TestParseDate:
    def test_iso_format(self):
        from datetime import date

        result = parse_date("2026-05-01")
        assert result == date(2026, 5, 1)

    def test_iso_datetime_format(self):
        from datetime import date

        result = parse_date("2026-05-01 14:30:00")
        assert result == date(2026, 5, 1)

    def test_vietnamese_format(self):
        from datetime import date

        result = parse_date("01/05/2026")
        assert result == date(2026, 5, 1)

    def test_none_returns_none(self):
        assert parse_date(None) is None

    def test_empty_returns_none(self):
        assert parse_date("") is None

    def test_unparseable_returns_none(self):
        result = parse_date("not-a-date")
        assert result is None


class TestDetectFileType:
    def test_order_export_english(self):
        headers = [
            "Order ID",
            "Product Name",
            "SKU ID",
            "Original Price",
            "Order Status",
            "Order Creation Time",
        ]
        # FIX v2.0.1: detect_file_type returns 3-tuple since v2.0.0 (added platform).
        # Old 2-tuple unpack raised: ValueError: too many values to unpack (expected 2)
        file_type, score, platform = detect_file_type(headers)
        assert file_type == "order_export"
        assert score >= 0.7
        assert platform == "tiktok"

    def test_order_export_vietnamese(self):
        headers = [
            "Mã đơn hàng",
            "Tên sản phẩm",
            "Mã SKU",
            "Giá gốc",
            "Trạng thái đơn",
            "Ngày tạo đơn",
        ]
        file_type, score, platform = detect_file_type(headers)
        assert file_type == "order_export"
        assert platform == "tiktok"

    def test_unknown_returns_low_confidence(self):
        headers = ["Column A", "Column B", "Random Data", "Something Else"]
        file_type, score, platform = detect_file_type(headers)
        assert score < 0.4
        assert platform == "unknown"

    def test_transaction_export_detected(self):
        headers = ["Transaction ID", "Transaction Type", "Settlement Amount", "Transaction Date"]
        file_type, score, platform = detect_file_type(headers)
        assert file_type == "transaction_export"
        assert platform == "tiktok"


class TestBuildColumnMap:
    def test_maps_english_columns(self):
        headers = [
            "Order ID",
            "Product Name",
            "Original Price",
            "Order Status",
            "Order Creation Time",
        ]
        col_map = build_column_map(headers)
        assert "tiktok_order_id" in col_map
        assert col_map["tiktok_order_id"] == "Order ID"
        assert "gmv" in col_map
        assert "order_date" in col_map

    def test_case_insensitive_matching(self):
        headers = ["order id", "PRODUCT NAME", "Original Price"]
        col_map = build_column_map(headers)
        assert "tiktok_order_id" in col_map

    def test_unknown_columns_not_in_map(self):
        headers = ["Random Column", "Another Column"]
        col_map = build_column_map(headers)
        assert len(col_map) == 0


class TestMaskPII:
    def test_masks_buyer_name(self):
        row = {"buyer_name": "Nguyen Van A", "product": "Serum"}
        masked = mask_pii(row)
        assert masked["buyer_name"] == "***"
        assert masked["product"] == "Serum"

    def test_masks_phone_numbers(self):
        row = {"contact": "0901234567"}
        masked = mask_pii(row)
        assert masked["contact"] == "***"

    def test_does_not_mutate_original(self):
        row = {"buyer_name": "Nguyen Van A"}
        _ = mask_pii(row)
        assert row["buyer_name"] == "Nguyen Van A"

    def test_non_pii_fields_unchanged(self):
        row = {"sku_id": "SKU-001", "gmv": "100000"}
        masked = mask_pii(row)
        assert masked["sku_id"] == "SKU-001"
        assert masked["gmv"] == "100000"
