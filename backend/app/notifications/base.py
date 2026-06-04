from dataclasses import dataclass
from typing import Literal

NotificationProviderName = Literal["web", "ntfy", "gotify", "telegram", "homeassistant", "apprise", "discord", "slack"]


@dataclass(frozen=True)
class NotificationTestResult:
    ok: bool
    provider: NotificationProviderName
    message: str
    detail: str | None = None
