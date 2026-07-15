from __future__ import annotations

import httpx

from app.notifications.base import NotificationTestResult
from app.utils.safe_logging import redact_url

from .base import _extract_json_response, _normalize_base_url


async def send_ntfy_notification(
    notification_url: str,
    topic: str,
    token: str | None,
    title: str,
    message: str,
    detail: str | None = None,
    click_url: str | None = None,
    image_url: str | None = None,
) -> NotificationTestResult:
    if not topic.strip():
        raise ValueError("ntfy topic is required")
    base_url = _normalize_base_url(notification_url)
    target_url = f"{base_url}/{topic.strip()}"
    headers = {
        "Content-Type": "text/plain; charset=utf-8",
        "Title": title,
    }
    if click_url:
        headers["Click"] = click_url
    if image_url:
        headers["Attach"] = image_url
    if token:
        headers["Authorization"] = f"Bearer {token}"

    body = message if detail is None else f"{message}\n{detail}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(target_url, content=body, headers=headers)

    if response.status_code in {401, 403}:
        raise PermissionError("ntfy rejected the token")
    if response.status_code >= 400:
        raise ConnectionError(f"ntfy returned HTTP {response.status_code}")

    payload = _extract_json_response(response, "ntfy")
    message_id = payload.get("id")
    if not message_id:
        raise ConnectionError("ntfy response did not include a message id")

    return NotificationTestResult(
        ok=True,
        provider="ntfy",
        message=message,
        detail=f"{redact_url(target_url)} ({message_id})",
    )
