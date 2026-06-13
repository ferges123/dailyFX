from __future__ import annotations

import httpx

from app.notifications.base import NotificationTestResult

from .base import _normalize_base_url


async def test_homeassistant_notification(
    notification_url: str,
    token: str | None,
    topic: str | None,
) -> NotificationTestResult:
    return await send_homeassistant_notification(
        notification_url=notification_url,
        token=token,
        topic=topic,
        title="dailyFX",
        message="dailyFX notification test",
    )


async def send_homeassistant_notification(
    notification_url: str,
    token: str | None,
    topic: str | None,
    title: str,
    message: str,
    detail: str | None = None,
    click_url: str | None = None,
    image_url: str | None = None,
) -> NotificationTestResult:
    if not token or not token.strip():
        raise ValueError("Home Assistant Access Token is required")
    base_url = _normalize_base_url(notification_url)
    service = (topic or "notify").strip()
    target_url = f"{base_url}/api/services/notify/{service}"

    payload = {
        "title": title,
        "message": message if detail is None else f"{message}\n{detail}",
    }

    if click_url or image_url:
        data = {}
        if click_url:
            data["url"] = click_url
            data["clickAction"] = click_url
            data["actions"] = [
                {
                    "action": "URI",
                    "title": "🔎 Review Image",
                    "uri": click_url,
                }
            ]
        if image_url:
            data["image"] = image_url
        payload["data"] = data

    headers = {
        "Authorization": f"Bearer {token.strip()}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(target_url, json=payload, headers=headers)

    if response.status_code in {401, 403}:
        raise PermissionError("Home Assistant rejected the token")
    if response.status_code >= 400:
        raise ConnectionError(f"Home Assistant returned HTTP {response.status_code}: {response.text}")

    return NotificationTestResult(
        ok=True,
        provider="homeassistant",
        message=message,
        detail=f"Sent via {service}",
    )
