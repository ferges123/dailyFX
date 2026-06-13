from __future__ import annotations

import asyncio

from app.notifications.base import NotificationTestResult


async def test_apprise_notification(
    notification_url: str,
) -> NotificationTestResult:
    return await send_apprise_notification(
        notification_url=notification_url,
        title="dailyFX",
        message="dailyFX notification test",
    )


async def send_apprise_notification(
    notification_url: str,
    title: str,
    message: str,
    detail: str | None = None,
    image_path: str | None = None,
) -> NotificationTestResult:
    if not notification_url or not notification_url.strip():
        raise ValueError("Apprise URL is required")

    import apprise

    apobj = apprise.Apprise()
    urls = [u.strip() for u in notification_url.split(",") if u.strip()]
    for url in urls:
        apobj.add(url)

    body = message if detail is None else f"{message}\n{detail}"

    def _send():
        return apobj.send(
            body=body,
            title=title,
            attach=image_path if image_path else None,
        )

    success = await asyncio.to_thread(_send)

    if not success:
        raise ConnectionError("Apprise failed to send the notification")

    return NotificationTestResult(
        ok=True,
        provider="apprise",
        message=message,
        detail=f"Sent to {len(urls)} Apprise destination(s)",
    )
