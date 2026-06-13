from __future__ import annotations

from app.notifications.providers.apprise import send_apprise_notification  # noqa: F401
from app.notifications.providers.discord import send_discord_notification  # noqa: F401
from app.notifications.providers.gotify import send_gotify_notification  # noqa: F401
from app.notifications.providers.home_assistant import send_homeassistant_notification  # noqa: F401
from app.notifications.providers.ntfy import send_ntfy_notification  # noqa: F401
from app.notifications.providers.slack import send_slack_notification  # noqa: F401
from app.notifications.providers.telegram import send_telegram_notification  # noqa: F401
from app.notifications.providers.web import send_web_notification  # noqa: F401
