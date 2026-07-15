from __future__ import annotations

import httpx

from app.notifications.base import NotificationTestResult


async def send_discord_notification(
    webhook_url: str,
    title: str,
    message: str,
    detail: str | None = None,
    click_url: str | None = None,
    image_url: str | None = None,
) -> NotificationTestResult:
    if not webhook_url or not webhook_url.strip():
        raise ValueError("Discord Webhook URL is required")

    embed = {
        "title": title,
        "description": message,
        "color": 3447003,  # Discord Blue
    }

    if detail:
        embed["description"] = f"{message}\n\n{detail}"

    if click_url:
        embed["url"] = click_url

    if image_url:
        embed["image"] = {"url": image_url}

    payload = {"embeds": [embed]}

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(webhook_url.strip(), json=payload)

    if response.status_code in {401, 403}:
        raise PermissionError("Discord rejected the webhook URL")
    if response.status_code >= 400:
        raise ConnectionError(f"Discord returned HTTP {response.status_code}: {response.text}")

    return NotificationTestResult(
        ok=True,
        provider="discord",
        message=message,
        detail="Sent successfully to Discord",
    )
