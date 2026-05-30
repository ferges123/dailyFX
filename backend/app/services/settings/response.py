from __future__ import annotations

from app.schemas.settings import SettingsResponse
from app.security import decrypt_secret


def build_settings_response(row) -> SettingsResponse:
    return SettingsResponse.from_model(
        row,
        immich_api_key=decrypt_secret(row.encrypted_immich_api_key),
        openai_api_key=decrypt_secret(row.encrypted_openai_api_key),
        gemini_api_key=decrypt_secret(row.encrypted_gemini_api_key),
        openrouter_api_key=decrypt_secret(row.encrypted_openrouter_api_key),
        byteplus_api_key=decrypt_secret(row.encrypted_byteplus_api_key),
        xiaomi_api_key=decrypt_secret(row.encrypted_xiaomi_api_key),
        local_ai_api_key=decrypt_secret(row.encrypted_local_ai_api_key),
    )
