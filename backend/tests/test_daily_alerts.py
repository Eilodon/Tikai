"""
Tests for daily_alerts worker — specifically the _build_alert_message decision logic.
The cron itself is integration-level; here we cover the pure logic in isolation.
"""

from decimal import Decimal
from types import SimpleNamespace

from app.tasks.daily_alerts import _build_alert_message, ALERT_LEAK_THRESHOLD


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
        s = _snapshot(top_leaks=[{"name": "SKU-X", "estimated_loss": "500000"}])
        result = _build_alert_message(s)
        assert result is not None
        title, body = result
        assert "rò rỉ" in title.lower() or "phát hiện" in title.lower()
        assert "SKU-X" in body

    def test_critical_sku_returns_message_when_no_big_leak(self):
        s = _snapshot(
            top_leaks=[{"name": "Y", "estimated_loss": "10000"}],
            top_skus=[{"sku_name": "SKU-Y", "health_status": "critical"}],
        )
        result = _build_alert_message(s)
        assert result is not None
        title, body = result
        assert "SKU-Y" in body

    def test_leak_picks_max_loss(self):
        s = _snapshot(top_leaks=[
            {"name": "small", "estimated_loss": "100000"},
            {"name": "BIG", "estimated_loss": "1000000"},
        ])
        result = _build_alert_message(s)
        assert result is not None
        _, body = result
        assert "BIG" in body

    def test_threshold_value(self):
        assert ALERT_LEAK_THRESHOLD == Decimal("100000")
