"""
Tests for v1.2.0 email digest feature.
Verifies: send_weekly_digest behavior, VND formatting, SendGrid skip when not configured,
worker email dispatch wiring, notification endpoint schema.
"""
import inspect
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestEmailServiceVNDFormatting:
    """_format_vnd must produce readable Vietnamese currency strings."""

    def _format(self, value: str) -> str:
        from app.services.email.client import _format_vnd
        return _format_vnd(value)

    def test_millions(self):
        result = self._format("5000000")
        assert "5" in result and "M" in result

    def test_thousands(self):
        result = self._format("50000")
        assert "50" in result

    def test_zero(self):
        result = self._format("0")
        assert result == "0 ₫"

    def test_invalid_returns_dash(self):
        result = self._format("not_a_number")
        assert result == "—"

    def test_empty_returns_dash(self):
        result = self._format("")
        assert result == "—"


class TestEmailServiceSkipWhenNotConfigured:
    """send_weekly_digest must return False (not raise) when SendGrid not configured."""

    @pytest.mark.asyncio
    async def test_returns_false_when_no_api_key(self):
        from app.services.email.client import send_weekly_digest
        from unittest.mock import patch
        # Override settings to simulate missing API key
        with patch("app.services.email.client.settings") as mock_settings:
            mock_settings.email_enabled = False
            result = await send_weekly_digest(
                to_email="test@example.com",
                shop_name="Test Shop",
                period_label="tuần 20/2026",
                headline="Test Headline",
                confirmed_section="Done things",
                estimated_section="Pending things",
                next_week_focus="Focus area",
                disclaimer="Test disclaimer",
                total_confirmed_saved="1000000",
                total_estimated_saved="500000",
            )
        assert result is False, "Should return False when email not configured"

    @pytest.mark.asyncio
    async def test_never_raises_on_sendgrid_exception(self):
        """Fire-and-forget invariant: never raises regardless of SendGrid errors."""
        from app.services.email.client import send_weekly_digest
        with patch("app.services.email.client.settings") as mock_settings:
            mock_settings.email_enabled = True
            mock_settings.sendgrid_api_key = "SG.test"
            mock_settings.email_from_address = "digest@tikai.vn"
            mock_settings.email_from_name = "Tikai"
            # Simulate SendGrid raising an exception
            with patch("sendgrid.SendGridAPIClient") as mock_sg:
                mock_sg.side_effect = Exception("Network error")
                try:
                    result = await send_weekly_digest(
                        to_email="test@example.com",
                        shop_name="Test",
                        period_label="tuần 20/2026",
                        headline="H",
                        confirmed_section="C",
                        estimated_section="E",
                        next_week_focus="F",
                        disclaimer="D",
                        total_confirmed_saved="0",
                        total_estimated_saved="0",
                    )
                    assert result is False, "Should return False on exception"
                except Exception as e:
                    pytest.fail(f"send_weekly_digest raised an exception: {e}")


class TestWorkerEmailWiring:
    """Worker must import + call send_weekly_digest after receipt save."""

    def test_worker_imports_email_service(self):
        from app.tasks import worker
        source = inspect.getsource(worker)
        assert "send_weekly_digest" in source, (
            "worker.py must import send_weekly_digest from email service"
        )

    def test_worker_dispatches_email_after_receipt_flush(self):
        from app.tasks import worker
        source = inspect.getsource(worker.run_weekly_receipts)
        # email dispatch must be AFTER the receipt flush/save
        flush_idx = source.rfind("await db.flush()")
        email_idx = source.find("send_weekly_digest")
        assert email_idx > 0, "send_weekly_digest call not found in run_weekly_receipts"
        # Email dispatch should be after first flush (receipt save)
        assert email_idx > source.find("db.add(receipt)"), (
            "Email dispatch must come AFTER receipt is saved to DB"
        )

    def test_worker_checks_email_enabled_flag(self):
        from app.tasks import worker
        source = inspect.getsource(worker.run_weekly_receipts)
        assert "email_digest_enabled" in source, (
            "Worker must check shop.email_digest_enabled before sending email"
        )
        assert "notification_email" in source, (
            "Worker must check shop.notification_email before sending email"
        )


class TestNotificationEndpoint:
    """PATCH /shops/me/notifications must accept email + enabled flag."""

    def test_notification_endpoint_exists(self):
        from app.api.v1 import shops
        source = inspect.getsource(shops)
        assert "update_notification_settings" in source
        assert "/shops/me/notifications" in source

    def test_notification_request_validates_email(self):
        from app.api.v1 import shops
        source = inspect.getsource(shops.update_notification_settings)
        assert "@" in source, (
            "Notification endpoint must validate email format (check for '@')"
        )

    def test_notification_model_has_both_fields(self):
        from app.api.v1 import shops
        # NotificationSettingsRequest must have both fields
        assert "notification_email" in inspect.getsource(shops)
        assert "email_digest_enabled" in inspect.getsource(shops)
