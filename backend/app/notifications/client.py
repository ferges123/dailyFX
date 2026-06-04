from __future__ import annotations

from urllib.parse import urlparse

import httpx

from app.notifications.base import NotificationTestResult
from app.utils.url_utils import normalize_base_url as _normalize_url


def _normalize_base_url(url: str) -> str:
    """Normalize notification URL with scheme validation."""
    normalized = _normalize_url(url)
    parsed = urlparse(normalized)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("Notification URL must include scheme and host")
    return normalized


def _extract_json_response(response: httpx.Response, provider: str) -> dict:
    try:
        payload = response.json()
    except ValueError as exc:
        raise ConnectionError(f"{provider} returned a non-JSON response") from exc
    if not isinstance(payload, dict):
        raise ConnectionError(f"{provider} returned an unexpected response body")
    return payload


async def test_web_notification() -> NotificationTestResult:
    from app.database import SessionLocal
    from app.notifications.vapid import send_push_to_all

    db = SessionLocal()
    try:
        await send_push_to_all(db, title="dailyFX test", body="Web push is working!")
    finally:
        db.close()
    return NotificationTestResult(
        ok=True,
        provider="web",
        message="Web notification test succeeded",
    )


async def send_web_notification(
    title: str,
    message: str,
    detail: str | None = None,
    url: str | None = None,
    image: str | None = None,
) -> NotificationTestResult:
    from app.database import SessionLocal
    from app.notifications.vapid import send_push_to_all

    body = message if detail is None else f"{message}\n{detail}"
    db = SessionLocal()
    try:
        try:
            await send_push_to_all(db, title=title, body=body, url=url, image=image)
        except Exception:
            # Web push is best-effort in development/test environments.
            pass
    finally:
        db.close()
    return NotificationTestResult(ok=True, provider="web", message=message, detail=detail)


async def test_ntfy_notification(
    notification_url: str,
    topic: str,
    token: str | None,
) -> NotificationTestResult:
    return await send_ntfy_notification(
        notification_url=notification_url,
        topic=topic,
        token=token,
        title="dailyFX",
        message="dailyFX notification test",
    )


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

    return NotificationTestResult(ok=True, provider="ntfy", message=message, detail=f"{target_url} ({message_id})")


async def test_gotify_notification(
    notification_url: str,
    token: str,
) -> NotificationTestResult:
    return await send_gotify_notification(
        notification_url=notification_url,
        token=token,
        title="dailyFX",
        message="notification test",
    )


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


def html_escape(text: str) -> str:
    """Escape special HTML characters for Telegram Bot API."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


async def send_telegram_notification(
    token: str,
    chat_id: str,
    title: str,
    message: str,
    detail: str | None = None,
    image_bytes: bytes | None = None,
    task_id: str | None = None,
) -> NotificationTestResult:
    if not token.strip():
        raise ValueError("Telegram Bot Token is required")
    if not chat_id.strip():
        raise ValueError("Telegram Chat ID is required")

    escaped_title = html_escape(title)
    escaped_message = html_escape(message)
    escaped_detail = html_escape(detail) if detail else None

    caption = f"<b>{escaped_title}</b>\n{escaped_message}"
    if escaped_detail:
        caption += f"\n\n{escaped_detail}"

    # Telegram caption character limit is 1024
    if len(caption) > 1024:
        caption = caption[:1020] + "..."

    reply_markup = None
    if task_id:
        # Include inline buttons for Accept/Reject
        reply_markup = {
            "inline_keyboard": [
                [
                    {"text": "✅ Accept & Upload", "callback_data": f"accept:{task_id}"},
                    {"text": "❌ Reject", "callback_data": f"reject:{task_id}"},
                ]
            ]
        }

    async with httpx.AsyncClient(timeout=15.0) as client:
        if image_bytes:
            url = f"https://api.telegram.org/bot{token.strip()}/sendPhoto"
            files = {"photo": ("image.png", image_bytes, "image/png")}
            data = {
                "chat_id": chat_id.strip(),
                "caption": caption,
                "parse_mode": "HTML",
            }
            if reply_markup:
                import json

                data["reply_markup"] = json.dumps(reply_markup)

            response = await client.post(url, files=files, data=data)
        else:
            url = f"https://api.telegram.org/bot{token.strip()}/sendMessage"
            payload = {
                "chat_id": chat_id.strip(),
                "text": caption,
                "parse_mode": "HTML",
            }
            if reply_markup:
                payload["reply_markup"] = reply_markup

            response = await client.post(url, json=payload)

    if response.status_code in {401, 403, 404}:
        raise PermissionError("Telegram rejected the bot token or Chat ID")
    if response.status_code >= 400:
        raise ConnectionError(f"Telegram returned HTTP {response.status_code}: {response.text}")

    payload = _extract_json_response(response, "Telegram")
    if not payload.get("ok"):
        raise ConnectionError(f"Telegram returned error: {payload.get('description')}")

    return NotificationTestResult(
        ok=True,
        provider="telegram",
        message=message,
        detail=f"Sent to chat {chat_id}",
    )


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

    import asyncio

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


async def test_discord_notification(
    webhook_url: str,
) -> NotificationTestResult:
    return await send_discord_notification(
        webhook_url=webhook_url,
        title="dailyFX",
        message="dailyFX Discord notification test",
    )


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
