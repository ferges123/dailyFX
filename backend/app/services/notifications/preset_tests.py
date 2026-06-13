from __future__ import annotations

from app.models.notification_preset import NotificationPresetModel
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
from app.security import decrypt_secret


async def run_notification_preset_test(row: NotificationPresetModel) -> tuple[list[str], list[str]]:
    providers = [p.strip() for p in (row.provider or "").split(",") if p.strip()]
    if not providers:
        raise ValueError("No providers configured")

    token = decrypt_secret(row.encrypted_token)
    results: list[str] = []
    errors: list[str] = []

    for provider in providers:
        try:
            if provider == "web":
                await send_web_notification(
                    title="Test notification",
                    message="dailyFX test",
                    detail="This is a test from dailyFX.",
                    url="/",
                    image=None,
                )
            elif provider == "ntfy":
                if not row.url or not row.topic:
                    errors.append("ntfy: URL or topic not configured")
                    continue
                await send_ntfy_notification(
                    row.url,
                    row.topic,
                    token,
                    "Test notification",
                    "dailyFX test",
                    "This is a test from dailyFX.",
                )
            elif provider == "gotify":
                if not row.url:
                    errors.append("gotify: URL not configured")
                    continue
                await send_gotify_notification(
                    row.url,
                    token or "",
                    "Test notification",
                    "dailyFX test",
                    "This is a test from dailyFX.",
                )
            elif provider == "telegram":
                if not row.topic:
                    errors.append("telegram: Chat ID not configured")
                    continue
                await send_telegram_notification(
                    token or "",
                    row.topic,
                    "Test notification",
                    "dailyFX test",
                    "This is a test from dailyFX.",
                )
            elif provider == "homeassistant":
                if not row.url:
                    errors.append("homeassistant: Server URL not configured")
                    continue
                await send_homeassistant_notification(
                    row.url,
                    token or "",
                    row.topic,
                    "Test notification",
                    "dailyFX test",
                    "This is a test from dailyFX.",
                )
            elif provider == "apprise":
                if not row.url:
                    errors.append("apprise: Apprise URL not configured")
                    continue
                await send_apprise_notification(
                    row.url,
                    "Test notification",
                    "dailyFX test",
                    "This is a test from dailyFX.",
                )
            elif provider == "discord":
                if not row.webhook_url:
                    errors.append("discord: Webhook URL not configured")
                    continue
                await send_discord_notification(
                    row.webhook_url,
                    "Test notification",
                    "dailyFX test",
                    "This is a test from dailyFX.",
                )
            elif provider == "slack":
                if not row.webhook_url:
                    errors.append("slack: Webhook URL not configured")
                    continue
                await send_slack_notification(
                    row.webhook_url,
                    "Test notification",
                    "dailyFX test",
                    "This is a test from dailyFX.",
                )
            results.append(provider)
        except Exception as exc:
            errors.append(f"{provider}: {exc}")

    return results, errors
