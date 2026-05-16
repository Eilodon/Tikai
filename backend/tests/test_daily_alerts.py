"""
Tests for daily_alerts worker — specifically the _build_alert_message decision logic.
The cron itself is integration-level; here we cover the pure logic in isolation.
"""

from decimal import Decimal
from types import SimpleNamespace

from app.tasks.daily_alerts import ALERT_LEAK_THRESHOLD, _build_alert_message


def _snapshot(top_leaks=None, top_skus=None):
    return SimpleNamespace(
        top_leaks_json=top_leaks or [],
        top_skus_json=top_skus or [],
    )


class TestBuildAlertMessage:
    def test_no_data_returns_none(self):
        result = _build_alert_message(_snapshot())
        assert result is None

    def test_leak_below_threshold_returns_none(self):
        s = _snapshot(top_leaks=[{"name": "X", "estimated_loss": "50000"}])
        result = _build_alert_message(s)
        assert result is None

    def test_leak_above_threshold_returns_message(self):
        # L8-C01: push body must NOT contain business-specific names (lock-screen privacy)
        s = _snapshot(top_leaks=[{"name": "SKU-X", "estimated_loss": "500000"}])
        result = _build_alert_message(s)
        assert result is not None
        title, body = result
        assert "rò rỉ" in title.lower() or "phát hiện" in title.lower()
        assert "SKU-X" not in body
        assert "Tikai" in body

    def test_critical_sku_returns_message_when_no_big_leak(self):
        # L8-C01: SKU name must not appear on lock screen
        s = _snapshot(
            top_leaks=[{"name": "Y", "estimated_loss": "10000"}],
            top_skus=[{"sku_name": "SKU-Y", "health_status": "critical"}],
        )
        result = _build_alert_message(s)
        assert result is not None
        title, body = result
        assert "SKU-Y" not in body
        assert "nguy hiểm" in body

    def test_leak_picks_max_loss(self):
        # Max-loss selection still works even though body is generic
        s = _snapshot(
            top_leaks=[
                {"name": "small", "estimated_loss": "100000"},
                {"name": "BIG", "estimated_loss": "1000000"},
            ]
        )
        result = _build_alert_message(s)
        assert result is not None
        _, body = result
        assert "BIG" not in body
        assert "Tikai" in body

    def test_threshold_value(self):
        assert ALERT_LEAK_THRESHOLD == Decimal("100000")
