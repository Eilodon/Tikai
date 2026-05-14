"""Test BUG-NH1 fix: quantity handles Excel float-strings."""
from app.services.parser.order_parser import _parse_quantity, _require_date
from datetime import date
import pytest


class TestQuantityParsing:
    def test_excel_float_string_two(self):
        # Old code: '2.0'.isdigit() == False → returned 1
        # New code: int(float('2.0')) → 2
        assert _parse_quantity("2.0") == 2

    def test_plain_integer_string(self):
        assert _parse_quantity("3") == 3

    def test_decimal_truncated(self):
        assert _parse_quantity("2.5") == 2

    def test_empty_defaults_to_one(self):
        assert _parse_quantity("") == 1
        assert _parse_quantity(None) == 1  # type: ignore

    def test_invalid_defaults_to_one(self):
        assert _parse_quantity("abc") == 1

    def test_negative_clamped_to_one(self):
        assert _parse_quantity("-5") == 1
        assert _parse_quantity("0") == 1


class TestDateGuard:
    """Test BUG-NH3 fix: order_date guard."""

    def test_valid_date_passes(self):
        d = date(2026, 5, 9)
        assert _require_date(d, "2026-05-09", column_exists=True) == d

    def test_unparseable_raises(self):
        with pytest.raises(ValueError, match="Cannot parse order_date"):
            _require_date(None, "xyz-bad", column_exists=True)

    def test_empty_value_when_column_present_raises(self):
        # FIX HIGH-V2-3: empty value with column present is also corrupt
        with pytest.raises(ValueError):
            _require_date(None, "", column_exists=True)

    def test_column_missing_falls_back_to_today(self):
        result = _require_date(None, "", column_exists=False)
        assert result == date.today()
