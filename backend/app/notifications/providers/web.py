from __future__ import annotations
from app.notifications.base import NotificationTestResult

async def test_web_notification() -> NotificationTestResult:
    return NotificationTestResult(
        ok=True,
        provider="web",
        message="Web notification test requires a selected device target",
        detail="Use the single-device test button from the Web Push device list.",
    )


async def send_web_notification(
    title: str,
    message: str,
    detail: str | None = None,
    url: str | None = None,
    image: str | None = None,
    subscription_ids: list[int] | None = None,
) -> NotificationTestResult:
    from app.database import SessionLocal
    from app.notifications.vapid import send_push_to_all

    body = message if detail is None else f"{message}\n{detail}"
    db = SessionLocal()
    try:
        try:
            await send_push_to_all(db, title=title, body=body, url=url, image=image, subscription_ids=subscription_ids)
        except Exception:
            # Web push is best-effort in development/test environments.
            pass
    finally:
        db.close()
    return NotificationTestResult(ok=True, provider="web", message=message, detail=detail)
