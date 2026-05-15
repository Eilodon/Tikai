"""
Web Push Notification Sender.
Uses VAPID protocol via pywebpush.
VAPID keys must be set in env: VAPID_PRIVATE_KEY, VAPID_PUBLIC_KEY, VAPID_CLAIMS_EMAIL.

INVARIANT: never raises — log and return False on any failure.
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from app.models.shop import Shop

log = structlog.get_logger()


async def send_web_push(
    subscription: dict,
    title: str,
    body: str,
    url: str = "/",
) -> bool:
    """Send a Web Push notification. Returns True on success."""
    from app.core.config import get_settings

    settings = get_settings()

    if not settings.vapid_private_key or not settings.vapid_public_key:
        log.warning("web_push.vapid_keys_missing")
        return False

    payload = json.dumps({"title": title, "body": body, "url": url})

    def _send() -> bool:
        try:
            from pywebpush import webpush

            webpush(
                subscription_info=subscription,
                data=payload,
                vapid_private_key=settings.vapid_private_key,
                vapid_claims={
                    "sub": f"mailto:{settings.vapid_claims_email}",
                },
            )
            return True
        except Exception as exc:
            log.warning("web_push.send_failed", error=str(exc))
            return False

    try:
        return await asyncio.to_thread(_send)
    except Exception as exc:
        log.warning("web_push.thread_failed", error=str(exc))
        return False


async def send_push_to_shop(shop: Shop, title: str, body: str, url: str = "/") -> bool:
    """Helper: skip if push_subscription_json is None."""
    if not shop.push_subscription_json:
        return False
    return await send_web_push(shop.push_subscription_json, title, body, url)
