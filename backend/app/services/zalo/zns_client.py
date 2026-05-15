"""
Zalo Notification Service (ZNS) Client.

DESIGN:
- ZNS sends template-only messages — every template must be pre-approved by Zalo
- Templates use placeholder substitution: e.g. {sku_name}, {margin_pct}
- Phone number format: Vietnamese 10-11 digits (validated in shop.seller_phone)
- Fire-and-forget invariant: never raises — log + return False

REQUIREMENTS to actually send (set ENV vars):
- ZALO_OA_ID (Official Account ID from business.zalo.me)
- ZALO_ZNS_ACCESS_TOKEN (OAuth access token, refresh via separate worker)

STATUS: scaffold ready; activation requires Zalo Business approval + template registration.
Until then, send_zns_message() is a no-op that returns False and logs intent.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from app.models.shop import Shop

log = structlog.get_logger()

ZNS_API_BASE = "https://business.openapi.zalo.me"

TEMPLATE_MARGIN_ALERT = "tikai_margin_alert"
TEMPLATE_SETTLEMENT_ARRIVED = "tikai_settlement"
TEMPLATE_WEEKLY_DIGEST = "tikai_weekly"


async def send_zns_message(
    phone: str,
    template_id: str,
    template_data: dict,
) -> bool:
    """Send a ZNS message. Returns True on success.

    Until Zalo approval, this is a no-op that logs the intended message.
    """
    from app.core.config import get_settings

    settings = get_settings()

    if not settings.zns_enabled:
        log.info(
            "zns.no_op",
            phone=_mask_phone(phone),
            template_id=template_id,
            template_data=template_data,
            reason="zalo_credentials_not_configured",
        )
        return False

    payload = {
        "phone": phone,
        "template_id": template_id,
        "template_data": template_data,
        "tracking_id": f"tikai-{template_id}-{phone[-4:]}",
    }

    def _send() -> bool:
        try:
            import httpx
            with httpx.Client(timeout=10) as client:
                resp = client.post(
                    f"{ZNS_API_BASE}/v2/zns/send",
                    headers={"access_token": settings.zalo_zns_access_token},
                    json=payload,
                )
                if resp.status_code == 200:
                    body = resp.json()
                    if body.get("error") == 0:
                        return True
                    log.warning("zns.send_rejected", error=body.get("error"), msg=body.get("message"))
                    return False
                log.warning("zns.send_http_error", status=resp.status_code, body=resp.text[:200])
                return False
        except Exception as exc:
            log.warning("zns.send_failed", error=str(exc))
            return False

    try:
        return await asyncio.to_thread(_send)
    except Exception as exc:
        log.warning("zns.thread_failed", error=str(exc))
        return False


async def send_zns_to_shop(
    shop: Shop,
    template_id: str,
    template_data: dict,
) -> bool:
    """Send ZNS to a shop's registered phone. Skip if shop hasn't enabled ZNS."""
    if not getattr(shop, "zns_enabled", False) or not getattr(shop, "seller_phone", None):
        return False
    return await send_zns_message(shop.seller_phone, template_id, template_data)


def _mask_phone(phone: str) -> str:
    if len(phone) < 5:
        return "***"
    return f"{phone[:3]}***{phone[-2:]}"
