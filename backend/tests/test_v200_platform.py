"""
Tests for v2.0.0 multi-platform infrastructure.
Verifies: detect_file_type 3-tuple, platform gate in imports.py,
ParseResult.platform field, process_import platform-aware fee lookup.
"""
import inspect


class TestDetectorV200:
    """detect_file_type must return 3-tuple with platform."""

    def test_returns_three_tuple(self):
        from app.services.parser.detector import detect_file_type
        result = detect_file_type(["Order ID", "Product Name", "SKU ID",
                                   "Original Price", "Order Status", "Order Creation Time"])
        assert len(result) == 3

    def test_tiktok_platform(self):
        from app.services.parser.detector import detect_file_type
        _, _, platform = detect_file_type(["Order ID", "Product Name", "SKU ID",
                                           "Original Price", "Order Status", "Order Creation Time"])
        assert platform == "tiktok"

    def test_shopee_platform(self):
        from app.services.parser.detector import detect_file_type
        shopee_headers = ["Order ID", "Product Name", "Product SKU ID",
                          "Original Price", "Order Status", "Order Creation Date",
                          "Transaction Fee"]
        _, _, platform = detect_file_type(shopee_headers)
        assert platform == "shopee"

    def test_unknown_platform_on_gibberish(self):
        from app.services.parser.detector import detect_file_type
        _, confidence, platform = detect_file_type(["foo", "bar", "baz"])
        assert platform == "unknown"
        assert confidence < 0.4


class TestNormalizerV200:
    """build_column_map must be platform-aware."""

    def test_tiktok_uses_tiktok_aliases(self):
        from app.services.parser.normalizer import build_column_map
        col_map = build_column_map(["Order ID", "SKU ID", "Original Price"], platform="tiktok")
        assert "tiktok_order_id" in col_map
        assert "sku_id" in col_map

    def test_shopee_uses_shopee_aliases(self):
        from app.services.parser.normalizer import build_column_map
        col_map = build_column_map(
            ["Order ID", "Product SKU ID", "Original Price", "Order Creation Date"],
            platform="shopee"
        )
        assert "tiktok_order_id" in col_map  # Shopee "Order ID" maps to canonical
        assert "sku_id" in col_map           # "Product SKU ID" → sku_id

    def test_default_platform_is_tiktok(self):
        """build_column_map() without platform arg should default to tiktok."""
        from app.services.parser.normalizer import build_column_map
        col_map_explicit = build_column_map(["Order ID", "SKU ID"], platform="tiktok")
        col_map_default = build_column_map(["Order ID", "SKU ID"])
        assert col_map_explicit == col_map_default


class TestParseResultPlatformField:
    """ParseResult must include platform field."""

    def test_parse_result_has_platform(self):
        import dataclasses
        from app.services.parser.base import ParseResult
        fields = {f.name for f in dataclasses.fields(ParseResult)}
        assert "platform" in fields, "ParseResult missing 'platform' field (v2.0.0)"

    def test_parse_result_platform_default_tiktok(self):
        from app.services.parser.base import ParseResult
        from datetime import date
        pr = ParseResult(file_type="order_export")
        assert pr.platform == "tiktok", "ParseResult.platform default should be 'tiktok'"


class TestImportsGateCheck:
    """imports.py must gate Shopee uploads for non-Business tier."""

    def test_quick_detect_function_exists(self):
        from app.api.v1 import imports
        source = inspect.getsource(imports)
        assert "_quick_detect_platform" in source, (
            "imports.py must have _quick_detect_platform() helper for header-only detection"
        )

    def test_shopee_gate_check_in_upload_endpoint(self):
        from app.api.v1 import imports
        source = inspect.getsource(imports.upload_import)
        assert "shopee" in source.lower(), (
            "upload_import must check platform and gate Shopee to Business tier"
        )
        assert "require_feature" in source or "SHOPEE_LAZADA" in source, (
            "Shopee gate check must call require_feature with Feature.SHOPEE_LAZADA"
        )


class TestProcessImportPlatformFeeConfig:
    """process_import must do platform-aware fee config lookup."""

    def test_process_import_uses_platform_fee_lookup(self):
        from app.tasks import process_import as pm
        source = inspect.getsource(pm.process_import)
        assert "platform" in source, (
            "process_import must use parse_result.platform for fee config lookup"
        )
        # Should filter fee_configs by platform
        assert "FeeConfig.platform" in source or "platform == platform" in source or \
               ".where(FeeConfig.platform" in source, (
            "process_import must filter fee_configs by platform"
        )
