from __future__ import annotations

from app.schemas.settings import SettingsResponse


def build_settings_response(row) -> SettingsResponse:
    return SettingsResponse.from_model(row)
