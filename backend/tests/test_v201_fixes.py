"""
Tests for Tikai v2.0.1 bug fixes.

Covers all 5 issues found in v2.0.0 code review:
  1. Order.platform not set in process_import bulk insert → Shopee orders stored as "tiktok"
  2. Email HTML: no html.escape on AI content → layout breaks on <, >, &
  3. _format_vnd() broken double-replace for non-integer millions (1.5M → "1.5M" not "1,5M")
  4. sw.js CACHE_VERSION stale (structural check — verify version bumped to v2.0.1)
  5. test_parser.py: 2-tuple unpack of detect_file_type() → ValueError (v2.0.0 returns 3-tuple)
     [Fixed in test_parser.py directly — verified here as a smoke test]
"""
import inspect
from decimal import Decimal
import pytest


# ─── FIX 1: Order.platform in process_import bulk insert ─────────────────────

class TestOrderPlatformFix:
    """
    process_import.py must set platform on every Order row.
    Without this, all Shopee orders were stored with platform="tiktok" (server_default),
    breaking the ix_orders_shop_id_platform index and per-platform P&L queries.
    """

    def test_process_import_sets_platform_on_order(self):
        from app.tasks import process_import as pm
        source = inspect.getsource(pm.process_import)

        # The Order() constructor call must include platform=
        # (look for it explicitly rather than just "platform" anywhere in file)
        assert "platform=_order_platform" in source or "platform=parse_result.platform" in source, (
            "process_import must set platform= on each Order() row. "
            "Without this, Shopee orders are stored as 'tiktok' via server_default, "
            "breaking all per-platform P&L queries."
        )

    def test_platform_variable_set_before_order_insert(self):
        """_order_platform must be resolved before the Order() list comprehension."""
        from app.tasks import process_import as pm
        source = inspect.getsource(pm.process_import)

        platform_assign_idx = source.find("_order_platform = parse_result.platform")
        order_insert_idx = source.find("orders_to_insert = [")

        if platform_assign_idx == -1:
            # Alternative: direct inline
            assert "platform=parse_result.platform" in source, (
                "Either assign _order_platform before the loop, "
                "or inline platform=parse_result.platform in Order()."
            )
        else:
            assert platform_assign_idx < order_insert_idx, (
                "_order_platform must be assigned BEFORE the orders_to_insert list comprehension"
            )

    def test_session_platform_also_set(self):
        """import_session.platform must also be set (was correct in v2.0.0)."""
        from app.tasks import process_import as pm
        source = inspect.getsource(pm.process_import)
        assert "session.platform" in source, (
            "import_session.platform must also be updated to match parse_result.platform"
        )


# ─── FIX 2: Email HTML escaping ──────────────────────────────────────────────

class TestEmailHtmlEscaping:
    """
    AI-generated content (headline, sections, disclaimer) must be html.escape()'d
    before interpolation into the email HTML template.
    Without this, strings containing <, >, &, " from AI output break the email layout.
    """

    def test_email_client_imports_html_module(self):
        from app.services.email import client
        source = inspect.getsource(client)
        assert "import html" in source or "html_lib" in source, (
            "email/client.py must import Python's html module for html.escape(). "
            "v2.0.0 had no escaping — AI content like '<strong>text</strong>' "
            "would inject raw HTML into the email template."
        )

    def test_escape_helper_exists(self):
        from app.services.email.client import _escape
        assert callable(_escape), "_escape() helper must exist in email/client.py"

    def test_escape_sanitizes_html_chars(self):
        from app.services.email.client import _escape
        result = _escape('<script>alert("xss")</script>')
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_escape_converts_newlines_to_br(self):
        """Multi-line AI output should render as line breaks in email."""
        from app.services.email.client import _escape
        result = _escape("Line one\nLine two")
        assert "<br>" in result
        assert "\n" not in result

    def test_send_weekly_digest_uses_escape(self):
        from app.services.email import client
        source = inspect.getsource(client.send_weekly_digest)
        # All AI fields must be escaped — check at least headline and confirmed_section
        assert "_escape(headline)" in source, (
            "send_weekly_digest must escape headline before HTML interpolation"
        )
        assert "_escape(confirmed_section)" in source, (
            "send_weekly_digest must escape confirmed_section"
        )
        assert "_escape(next_week_focus)" in source, (
            "send_weekly_digest must escape next_week_focus"
        )

    def test_no_raw_ai_content_in_format_call(self):
        """Raw unescaped AI fields must not appear in .format() call."""
        from app.services.email import client
        source = inspect.getsource(client.send_weekly_digest)
        # Find the .format() call block — confirmed_section= should be _escape(...)
        assert "confirmed_section=confirmed_section," not in source, (
            "confirmed_section must be wrapped in _escape(), not passed raw to .format()"
        )
        assert "headline=headline," not in source, (
            "headline must be wrapped in _escape(), not passed raw to .format()"
        )


# ─── FIX 3: _format_vnd non-integer millions ─────────────────────────────────

class TestFormatVND:
    """
    _format_vnd() must use Vietnamese locale (comma as decimal separator).
    v2.0.0 had a broken double-replace that reverted the VN formatting:
      "1.5M ₫".replace(".", ",", 1)  →  "1,5M ₫"  (correct VN)
               .replace(",", ".", 2)  →  "1.5M ₫"  (WRONG — reverted!)
    """

    def _fmt(self, val: str) -> str:
        from app.services.email.client import _format_vnd
        return _format_vnd(val)

    # ── Non-integer millions (the previously broken cases) ──────────────────
    def test_one_point_five_million(self):
        result = self._fmt("1500000")
        assert result == "1,5M ₫", (
            f"Expected '1,5M ₫' (VN locale), got {result!r}. "
            "v2.0.0 double-replace bug returned '1.5M ₫'."
        )

    def test_two_point_three_million(self):
        result = self._fmt("2300000")
        assert result == "2,3M ₫", f"Expected '2,3M ₫', got {result!r}"

    def test_ten_point_seven_million(self):
        result = self._fmt("10700000")
        assert result == "10,7M ₫", f"Expected '10,7M ₫', got {result!r}"

    # ── Integer millions (should still work) ────────────────────────────────
    def test_five_million_integer(self):
        result = self._fmt("5000000")
        assert result == "5M ₫", f"Expected '5M ₫', got {result!r}"

    def test_ten_million_integer(self):
        result = self._fmt("10000000")
        assert result == "10M ₫", f"Expected '10M ₫', got {result!r}"

    # ── Thousands ────────────────────────────────────────────────────────────
    def test_fifty_thousand(self):
        result = self._fmt("50000")
        assert "50" in result and "₫" in result
        # VN thousands sep is dot: "50.000 ₫"
        assert "." in result, f"Expected dot thousands separator in {result!r}"

    def test_hundreds(self):
        result = self._fmt("999")
        assert result == "999 ₫"

    def test_zero(self):
        result = self._fmt("0")
        assert result == "0 ₫"

    # ── Edge cases ────────────────────────────────────────────────────────────
    def test_invalid_returns_dash(self):
        assert self._fmt("not_a_number") == "—"

    def test_empty_returns_dash(self):
        assert self._fmt("") == "—"

    def test_decimal_string(self):
        """Decimal string "1500000.00" (from DB) must be handled."""
        result = self._fmt("1500000.00")
        assert result == "1,5M ₫", f"Expected '1,5M ₫', got {result!r}"


# ─── FIX 4: sw.js CACHE_VERSION ──────────────────────────────────────────────

class TestServiceWorkerVersion:
    """
    CACHE_VERSION in sw.js must not be the stale v1.0.0 string.
    After each deploy, the old cache version prefix triggers cleanup in the
    'activate' event, ensuring PWA users receive fresh assets.
    """

    def test_cache_version_not_stale(self):
        import os
        sw_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "..", "frontend", "public", "sw.js"
        )
        sw_path = os.path.normpath(sw_path)
        if not os.path.exists(sw_path):
            pytest.skip("sw.js not found — running in backend-only test context")

        with open(sw_path) as f:
            content = f.read()

        assert 'CACHE_VERSION = "tikai-v1.0.0"' not in content, (
            "sw.js CACHE_VERSION is still 'tikai-v1.0.0'. "
            "Bump it to the current version string on every deploy, "
            "or PWA users will serve stale JS/CSS after deploy."
        )

    def test_cache_version_present(self):
        import os
        sw_path = os.path.normpath(os.path.join(
            os.path.dirname(__file__),
            "..", "..", "..", "frontend", "public", "sw.js"
        ))
        if not os.path.exists(sw_path):
            pytest.skip("sw.js not found")
        with open(sw_path) as f:
            content = f.read()
        assert "CACHE_VERSION" in content, "sw.js must define CACHE_VERSION"
        assert "tikai-v" in content, "CACHE_VERSION must follow 'tikai-v{VERSION}' format"


# ─── FIX 5: detect_file_type 3-tuple (smoke test) ────────────────────────────

class TestDetectFileTypeTuple:
    """
    detect_file_type() returns a 3-tuple since v2.0.0.
    test_parser.py had 4 callers using 2-tuple unpack → ValueError at test time.
    This test ensures the fix in test_parser.py is correct.
    """

    def test_returns_exactly_3_elements(self):
        from app.services.parser.detector import detect_file_type
        result = detect_file_type(["Order ID", "Product Name", "SKU ID",
                                   "Original Price", "Order Status", "Order Creation Time"])
        assert len(result) == 3, (
            f"detect_file_type must return (file_type, confidence, platform) — "
            f"got {len(result)} elements. "
            "Old 2-tuple unpack in test_parser.py would crash with ValueError."
        )

    def test_three_tuple_unpacks_cleanly(self):
        from app.services.parser.detector import detect_file_type
        # This is exactly the unpack form that was broken before the fix
        file_type, score, platform = detect_file_type(
            ["Order ID", "SKU ID", "Original Price", "Order Status", "Order Creation Time"]
        )
        assert isinstance(file_type, str)
        assert isinstance(score, float)
        assert isinstance(platform, str)


# ─── FIX async sg.send (structural) ─────────────────────────────────────────

class TestEmailAsyncSend:
    """
    sg.send() is a synchronous blocking HTTP call.
    It must be wrapped in run_in_executor so it doesn't block the event loop
    during the Monday weekly batch job.
    """

    def test_uses_run_in_executor(self):
        from app.services.email import client
        source = inspect.getsource(client.send_weekly_digest)
        assert "run_in_executor" in source, (
            "sg.send() must be run via asyncio.get_event_loop().run_in_executor(). "
            "Calling it directly in async context blocks the event loop per shop "
            "during the weekly batch job (~200-500ms per SendGrid HTTP call)."
        )

    def test_uses_app_base_url_not_hardcoded(self):
        """CTA link must come from settings.app_base_url, not hardcoded."""
        from app.services.email import client
        source = inspect.getsource(client.send_weekly_digest)
        assert "app_base_url" in source, (
            "send_weekly_digest must use settings.app_base_url for CTA link, "
            "not hardcoded 'https://app.tikai.vn'. "
            "Staging environments would email-link to production without this."
        )
        assert "https://app.tikai.vn" not in source, (
            "Hardcoded production URL found in send_weekly_digest. "
            "Use settings.app_base_url instead."
        )
