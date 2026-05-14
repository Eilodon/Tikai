"""
Email Service — SendGrid integration for weekly digest.

DESIGN DECISIONS:
- Uses sendgrid Python SDK (pyproject.toml: sendgrid>=6.11.0)
- Fire-and-forget: never raises — logs error only
- Template: inline HTML, no external template service dependency
- Rate: max 1 email per shop per week (enforced by caller via idempotency check
  in worker.py — if receipt already has email_sent=True, skip)
- Financial data safety: numbers formatted from Decimal strings, never AI text numbers

INVARIANT: send_weekly_digest() never raises — always returns bool.
Caller must never let email failure block receipt creation or DB flush.

FIXES (v2.0.1):
- FIX: AI-generated content (headline, sections) now html.escape()'d before
  interpolation into HTML template — prevents broken layout from <, >, & in AI output
- FIX: _format_vnd() broken double-replace for non-integer millions (1.5M → "1.5M ₫"
  instead of "1,5M ₫") — removed erroneous second .replace(",", ".", 2) call
- FIX: sg.send() runs in thread pool executor (run_in_executor) — it's a synchronous
  HTTP call; calling it directly in an async function blocked the event loop
- FIX: CTA link uses settings.app_base_url (not hardcoded "https://app.tikai.vn")
  so staging/preview environments don't email-link to production
"""
import asyncio
import html as html_lib

import structlog

from app.core.config import get_settings

log = structlog.get_logger()

# Module-level settings (loaded once)
settings = get_settings()

# ── HTML Template ─────────────────────────────────────────────────────────────
# Inline CSS only — email clients strip <style> blocks
# {confirmed_saved} and {estimated_saved} are formatted numbers (safe).
# All other {placeholders} that accept AI-generated text MUST be html.escape()'d
# before .format() is called — see send_weekly_digest() below.
_DIGEST_HTML = """<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{headline}</title>
</head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;padding:24px 0">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%">

        <!-- Header -->
        <tr><td style="background:#111;color:#fff;padding:20px 24px;border-radius:12px 12px 0 0">
          <div style="font-size:11px;color:#9ca3af;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:4px">Tikai</div>
          <div style="font-size:20px;font-weight:700;line-height:1.3">{headline}</div>
          <div style="font-size:13px;color:#d1d5db;margin-top:4px">{shop_name} · {period_label}</div>
        </td></tr>

        <!-- Body -->
        <tr><td style="background:#f9fafb;padding:24px;border:1px solid #e5e7eb;border-top:none">

          <!-- Metrics row -->
          <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:20px">
            <tr>
              <td width="48%" style="background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:16px;vertical-align:top">
                <div style="font-size:12px;color:#6b7280;margin-bottom:6px">Đã tiết kiệm (xác nhận)</div>
                <div style="font-size:22px;font-weight:700;color:#059669">{confirmed_saved}</div>
              </td>
              <td width="4%"></td>
              <td width="48%" style="background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:16px;vertical-align:top">
                <div style="font-size:12px;color:#6b7280;margin-bottom:6px">Ước tính tiết kiệm</div>
                <div style="font-size:22px;font-weight:700;color:#2563eb">{estimated_saved}</div>
              </td>
            </tr>
          </table>

          <!-- Sections -->
          <div style="margin-bottom:16px">
            <div style="font-size:15px;font-weight:600;color:#374151;margin-bottom:6px">✅ Đã làm được</div>
            <div style="font-size:14px;color:#374151;line-height:1.6">{confirmed_section}</div>
          </div>
          <div style="margin-bottom:16px">
            <div style="font-size:15px;font-weight:600;color:#374151;margin-bottom:6px">📊 Cơ hội cải thiện</div>
            <div style="font-size:14px;color:#374151;line-height:1.6">{estimated_section}</div>
          </div>
          <div style="margin-bottom:24px">
            <div style="font-size:15px;font-weight:600;color:#374151;margin-bottom:6px">🎯 Tuần tới tập trung vào</div>
            <div style="font-size:14px;color:#374151;line-height:1.6">{next_week_focus}</div>
          </div>

          <!-- CTA — URL from settings.app_base_url, not hardcoded -->
          <div style="text-align:center">
            <a href="{app_base_url}/overview?utm_source=email&amp;utm_medium=weekly_digest&amp;utm_campaign=weekly"
               style="display:inline-block;background:#111;color:#fff;padding:12px 28px;
                      border-radius:8px;text-decoration:none;font-size:14px;font-weight:600">
              Xem chi tiết trên Tikai →
            </a>
          </div>
        </td></tr>

        <!-- Footer -->
        <tr><td style="background:#f3f4f6;padding:16px 24px;border-radius:0 0 12px 12px;
                       border:1px solid #e5e7eb;border-top:none">
          <p style="font-size:12px;color:#9ca3af;margin:0;line-height:1.6">
            {disclaimer}<br><br>
            Nhận email này vì bạn bật thông báo tại Tikai.<br>
            <a href="{app_base_url}/settings?utm_source=email&amp;utm_medium=weekly_digest#notifications"
               style="color:#6b7280">Tắt thông báo email</a>
          </p>
        </td></tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


def _format_vnd(decimal_str: str) -> str:
    """Format Decimal string as VND for email display (Vietnamese locale).

    FIX v2.0.1: Previous version had a broken double-replace for non-integer millions:
      f"{millions:.1f}M ₫".replace(".", ",", 1).replace(",", ".", 2)
    This reverted the comma-dot swap: "1.5M ₫" → "1,5M ₫" → back to "1.5M ₫".
    Fixed to a single .replace(".", ",") — simple and correct.

    Examples (VN locale uses dot as thousands separator, comma as decimal):
      5_000_000  → "5M ₫"
      1_500_000  → "1,5M ₫"   (was "1.5M ₫" before fix)
      2_300_000  → "2,3M ₫"   (was "2.3M ₫" before fix)
      50_000     → "50.000 ₫"
      999        → "999 ₫"
    """
    try:
        val = float(decimal_str)
        if val >= 1_000_000:
            millions = val / 1_000_000
            if millions == int(millions):
                # e.g. 5.0M → "5M ₫" (thousands sep dot for large integers not needed here)
                return f"{int(millions):,}M ₫".replace(",", ".")
            # FIX: single replace only — "1.5" → "1,5" (VN decimal comma) ✓
            return f"{millions:.1f}M ₫".replace(".", ",")
        if val >= 1_000:
            # e.g. 50000 → "50.000 ₫" (VN thousands sep is dot)
            return f"{val:,.0f} ₫".replace(",", ".")
        return f"{val:.0f} ₫"
    except (ValueError, TypeError):
        return "—"


def _escape(text: str) -> str:
    """Escape AI-generated text for safe HTML interpolation.

    Converts newlines to <br> after escaping so multi-line AI output renders
    as intended in email clients rather than collapsing whitespace.
    """
    return html_lib.escape(text, quote=False).replace("\n", "<br>")


async def send_weekly_digest(
    *,
    to_email: str,
    shop_name: str,
    period_label: str,
    headline: str,
    confirmed_section: str,
    estimated_section: str,
    next_week_focus: str,
    disclaimer: str,
    total_confirmed_saved: str,
    total_estimated_saved: str,
) -> bool:
    """
    Send weekly digest email via SendGrid.
    Returns True if sent, False if skipped or failed.
    NEVER raises — all exceptions caught and logged.

    v1.2.0 INVARIANT: this function is fire-and-forget.
    Caller (worker.py) must not await this inside the DB transaction.
    Email failure must never rollback a successfully created WeeklyReceipt.

    v2.0.1 FIXES applied in this function:
    - All AI-generated strings (headline, sections) are html.escape()'d via _escape()
      before being interpolated into the HTML template.
    - sg.send() (synchronous HTTP) is now wrapped in run_in_executor so it does
      not block the asyncio event loop during the weekly batch job.
    - CTA and unsubscribe links use settings.app_base_url (not hardcoded URL).
    """
    if not settings.email_enabled:
        log.info("email.skipped_no_config", to=to_email)
        return False

    # Render HTML
    # FIX v2.0.1: escape all AI-generated content before HTML interpolation.
    # _format_vnd() output (e.g. "1,5M ₫") is safe — no user/AI input.
    # shop_name and period_label come from DB/config, not AI — still escape for safety.
    html_content = _DIGEST_HTML.format(
        headline=_escape(headline),
        shop_name=_escape(shop_name),
        period_label=_escape(period_label),
        confirmed_saved=_format_vnd(total_confirmed_saved),
        estimated_saved=_format_vnd(total_estimated_saved),
        confirmed_section=_escape(confirmed_section),
        estimated_section=_escape(estimated_section),
        next_week_focus=_escape(next_week_focus),
        disclaimer=_escape(disclaimer),
        app_base_url=settings.app_base_url,   # FIX v2.0.1: not hardcoded
    )

    try:
        import sendgrid  # type: ignore[import]
        from sendgrid.helpers.mail import Mail  # type: ignore[import]

        message = Mail(
            from_email=(settings.email_from_address, settings.email_from_name),
            to_emails=to_email,
            subject=f"[Tikai] {shop_name}: {headline} — {period_label}",
            html_content=html_content,
        )
        sg = sendgrid.SendGridAPIClient(api_key=settings.sendgrid_api_key)

        # FIX v2.0.1: sg.send() is a synchronous blocking HTTP call.
        # Running it directly in async context blocks the event loop for ~200–500ms
        # per shop during the Monday batch — unacceptable at scale.
        # run_in_executor offloads to a thread pool so the event loop stays free.
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: sg.send(message))

        success = response.status_code in (200, 202)
        log.info(
            "email.sent" if success else "email.send_failed",
            to=to_email,
            status=response.status_code,
        )
        return success
    except ImportError:
        log.error("email.sendgrid_not_installed",
                  hint="pip install sendgrid>=6.11.0")
        return False
    except Exception as e:
        log.error("email.exception", to=to_email, error=str(e)[:200])
        return False
