from __future__ import annotations

import httpx

from app.notifications.base import NotificationTestResult

from .base import _extract_json_response, _normalize_base_url


async def send_gotify_notification(
    notification_url: str,
    token: str,
    title: str,
    message: str,
    detail: str | None = None,
) -> NotificationTestResult:
    if not token.strip():
        raise ValueError("Gotify token is required")
    base_url = _normalize_base_url(notification_url)
    target_url = f"{base_url}/message?token={token.strip()}"

    payload = {"title": title, "message": message if detail is None else f"{message}\n{detail}", "priority": 5}

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(target_url, json=payload)

    if response.status_code in {401, 403}:
        raise PermissionError("Gotify rejected the token")
    if response.status_code >= 400:
        raise ConnectionError(f"Gotify returned HTTP {response.status_code}")

    payload = _extract_json_response(response, "Gotify")
    message_id = payload.get("id")
    if not message_id:
        raise ConnectionError("Gotify response did not include a message id")

    return NotificationTestResult(ok=True, provider="gotify", message=message, detail=f"{target_url} ({message_id})")
