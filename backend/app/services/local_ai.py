from __future__ import annotations

from app.models.settings import SettingsModel
from app.security import decrypt_secret
from app.utils.url_utils import validate_http_url


class LocalAIConfigurationError(RuntimeError):
    pass


def get_local_ai_base_url(settings: SettingsModel) -> str:
    base_url = getattr(settings, "local_ai_base_url", None)
    if not base_url:
        raise LocalAIConfigurationError("Local AI base URL is not configured")
    try:
        return validate_http_url(base_url, "Local AI base URL")
    except ValueError as exc:
        raise LocalAIConfigurationError(str(exc)) from exc


def get_local_ai_api_key(settings: SettingsModel) -> str | None:
    return decrypt_secret(getattr(settings, "encrypted_local_ai_api_key", None))
