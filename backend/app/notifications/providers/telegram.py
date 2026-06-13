from __future__ import annotations

import json

import httpx

from app.notifications.base import NotificationTestResult

from .base import _extract_json_response


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
