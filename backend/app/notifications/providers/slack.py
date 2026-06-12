from __future__ import annotations
import httpx
from app.notifications.base import NotificationTestResult

async def test_slack_notification(
    webhook_url: str,
) -> NotificationTestResult:
    return await send_slack_notification(
        webhook_url=webhook_url,
        title="dailyFX",
        message="dailyFX Slack notification test",
    )


async def send_slack_notification(
    webhook_url: str,
    title: str,
    message: str,
    detail: str | None = None,
    click_url: str | None = None,
    image_url: str | None = None,
) -> NotificationTestResult:
    if not webhook_url or not webhook_url.strip():
        raise ValueError("Slack Webhook URL is required")

    fallback_text = f"*{title}*\n{message}"
    if detail:
        fallback_text += f"\n\n{detail}"

    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{title}*\n{message}",
            },
        }
    ]
    if detail:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{detail}",
            },
        })
    if image_url:
        blocks.append({
            "type": "image",
            "image_url": image_url,
            "alt_text": title,
        })
    if click_url:
        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "🔎 Review Image",
                    },
                    "url": click_url,
                    "action_id": "review_image",
                }
            ],
        })

    payload = {
        "text": fallback_text,
        "blocks": blocks,
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(webhook_url.strip(), json=payload)

    if response.status_code in {401, 403}:
        raise PermissionError("Slack rejected the webhook URL")
    if response.status_code >= 400:
        raise ConnectionError(f"Slack returned HTTP {response.status_code}: {response.text}")

    return NotificationTestResult(
        ok=True,
        provider="slack",
        message=message,
        detail="Sent successfully to Slack",
    )
