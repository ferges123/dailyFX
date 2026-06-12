from __future__ import annotations

# Re-export Web notification provider
from app.notifications.providers.web import (
    test_web_notification,
    send_web_notification,
)

# Re-export Ntfy notification provider
from app.notifications.providers.ntfy import (
    test_ntfy_notification,
    send_ntfy_notification,
)

# Re-export Gotify notification provider
from app.notifications.providers.gotify import (
    test_gotify_notification,
    send_gotify_notification,
)

# Re-export Telegram notification provider
from app.notifications.providers.telegram import (
    html_escape,
    send_telegram_notification,
)

# Re-export Home Assistant notification provider
from app.notifications.providers.home_assistant import (
    test_homeassistant_notification,
    send_homeassistant_notification,
)

# Re-export Apprise notification provider
from app.notifications.providers.apprise import (
    test_apprise_notification,
    send_apprise_notification,
)

# Re-export Discord notification provider
from app.notifications.providers.discord import (
    test_discord_notification,
    send_discord_notification,
)

# Re-export Slack notification provider
from app.notifications.providers.slack import (
    test_slack_notification,
    send_slack_notification,
)
