from __future__ import annotations

import logging
from pathlib import Path
from urllib.parse import urlencode

from app.notifications.client import (
    send_apprise_notification,
    send_discord_notification,
    send_gotify_notification,
    send_homeassistant_notification,
    send_ntfy_notification,
    send_slack_notification,
    send_telegram_notification,
    send_web_notification,
)
from app.security import create_review_token, decrypt_secret
from app.utils.safe_logging import redact_sensitive

logger = logging.getLogger(__name__)


def _with_review_token(url: str, review_token: str) -> str:
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}{urlencode({'review_token': review_token})}"


async def send_generation_notification(notification_preset, title: str, summary: str, image_url: str, task_id: str):
    if notification_preset is None:
        return

    from app.config import get_settings

    providers = [p.strip() for p in (notification_preset.provider or "").split(",") if p.strip()]
    notification_url = notification_preset.url
    notification_topic = notification_preset.topic
    notification_token = decrypt_secret(notification_preset.encrypted_token)
    full_title = f"New AI Generation: {title}"
    review_token = create_review_token(task_id)
    app_url = _with_review_token(f"/api/generation/review/{task_id}", review_token)

    ext_url = get_settings().app_external_url
    if ext_url:
        ext_url = ext_url.rstrip("/")
        abs_image_url = _with_review_token(f"{ext_url}/api/generation/review/{task_id}/thumbnail", review_token)
        abs_app_url = _with_review_token(f"{ext_url}/api/generation/review/{task_id}", review_token)
        detail = f"{summary}\n\nReview: {abs_app_url}"
    else:
        abs_image_url = None
        abs_app_url = None
        detail = f"{summary}\n\nImage: {image_url}"

    for provider in providers:
        try:
            if provider == "web":
                subscription_ids = (
                    [sub.id for sub in notification_preset.push_subscriptions]
                    if hasattr(notification_preset, "push_subscriptions")
                    else []
                )
                await send_web_notification(
                    title=full_title,
                    message=title,
                    detail=detail,
                    url=app_url,
                    image=_with_review_token(f"/api/generation/review/{task_id}/thumbnail", review_token),
                    subscription_ids=subscription_ids,
                )
            elif provider == "ntfy" and notification_url and notification_topic:
                await send_ntfy_notification(
                    notification_url,
                    notification_topic,
                    notification_token,
                    full_title,
                    title,
                    summary,
                    click_url=abs_app_url,
                    image_url=abs_image_url,
                )
            elif provider == "gotify" and notification_url:
                await send_gotify_notification(notification_url, notification_token or "", full_title, title, detail)
            elif provider == "homeassistant" and notification_url:
                await send_homeassistant_notification(
                    notification_url,
                    notification_token or "",
                    notification_topic,
                    full_title,
                    title,
                    detail,
                    click_url=abs_app_url,
                    image_url=abs_image_url,
                )
            elif provider == "telegram" and notification_topic:
                image_path = Path(get_settings().data_dir) / "results" / f"{task_id}.png"
                image_bytes = None
                if image_path.exists():
                    try:
                        image_bytes = image_path.read_bytes()
                    except Exception as read_err:
                        logger.warning("Failed to read image bytes for Telegram: %s", read_err)

                await send_telegram_notification(
                    token=notification_token or "",
                    chat_id=notification_topic,
                    title=full_title,
                    message=title,
                    detail=summary,
                    image_bytes=image_bytes,
                    task_id=task_id,
                    review_url=abs_app_url,
                )
            elif provider == "apprise" and notification_url:
                image_path = Path(get_settings().data_dir) / "results" / f"{task_id}.png"
                img_str = str(image_path) if image_path.exists() else None

                await send_apprise_notification(
                    notification_url=notification_url,
                    title=full_title,
                    message=title,
                    detail=detail,
                    image_path=img_str,
                )
            elif provider == "discord" and notification_preset.webhook_url:
                await send_discord_notification(
                    webhook_url=notification_preset.webhook_url,
                    title=full_title,
                    message=title,
                    detail=summary,
                    click_url=abs_app_url,
                    image_url=abs_image_url,
                )
            elif provider == "slack" and notification_preset.webhook_url:
                await send_slack_notification(
                    webhook_url=notification_preset.webhook_url,
                    title=full_title,
                    message=title,
                    detail=summary,
                    click_url=abs_app_url,
                    image_url=abs_image_url,
                )
        except Exception as e:
            logger.warning("Failed to send %s notification: %s", provider, e)


async def send_webhook(webhook_url: str | None, task_id: str, generation_type: str, title: str) -> None:
    if not webhook_url:
        return
    try:
        import httpx

        payload = {"task_id": task_id, "generation_type": generation_type, "title": title}
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(webhook_url, json=payload)
    except Exception as e:
        logger.warning("Webhook failed: %s", redact_sensitive(e))


async def dispatch_generation_outputs(
    *,
    notification_presets,
    webhook_url: str | None,
    result,
    task_id: str,
    image_url: str,
    title: str,
    summary: str,
) -> None:
    if notification_presets:
        for np_preset in notification_presets:
            await send_generation_notification(np_preset, title, summary, image_url, task_id)
            if np_preset.webhook_url:
                await send_webhook(np_preset.webhook_url, task_id, result.generation_type, title)
    elif webhook_url:
        await send_webhook(webhook_url, task_id, result.generation_type, title)
