import json

from pydantic import BaseModel, Field, field_validator

from app.utils.url_utils import validate_http_url


class SettingsBase(BaseModel):
    immich_url: str | None = None
    local_ai_base_url: str | None = None
    ai_vision_hourly_limit: int = Field(default=30, ge=1, le=1000)
    ai_image_hourly_limit: int = Field(default=10, ge=1, le=1000)
    debug_mode: bool = False
    favorite_albums_json: str | None = None
    ai_custom_prompt: str | None = Field(default=None, max_length=10000)
    retention_enabled: bool = True
    retention_rejected_files_days: int | None = Field(default=7, ge=1)
    retention_rejected_metadata_days: int | None = Field(default=90, ge=1)
    retention_failed_files_days: int | None = Field(default=7, ge=1)
    retention_failed_metadata_days: int | None = Field(default=90, ge=1)
    retention_uploaded_files_days: int | None = Field(default=30, ge=1)
    retention_uploaded_metadata_days: int | None = Field(default=30, ge=1)
    retention_task_days: int | None = Field(default=30, ge=1)
    retention_audit_days: int | None = Field(default=180, ge=1)
    retention_backup_count: int = Field(default=7, ge=1, le=365)

    @field_validator("immich_url", mode="before")
    @classmethod
    def validate_immich_url(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        return validate_http_url(value, "Immich URL")

    @field_validator("local_ai_base_url", mode="before")
    @classmethod
    def validate_local_ai_base_url(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        return validate_http_url(value, "Local AI base URL")

    @field_validator("favorite_albums_json", mode="before")
    @classmethod
    def validate_favorite_albums_json(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("favorite_albums_json must be valid JSON") from exc
        if not isinstance(parsed, list):
            raise ValueError("favorite_albums_json must be a JSON array")
        return value


class SettingsUpdate(SettingsBase):
    immich_api_key: str | None = None
    openai_api_key: str | None = None
    gemini_api_key: str | None = None
    openrouter_api_key: str | None = None
    byteplus_api_key: str | None = None
    xiaomi_api_key: str | None = None
    local_ai_api_key: str | None = None


class SettingsResponse(SettingsBase):
    immich_api_key_masked: str | None = None
    openai_api_key_masked: str | None = None
    gemini_api_key_masked: str | None = None
    openrouter_api_key_masked: str | None = None
    byteplus_api_key_masked: str | None = None
    xiaomi_api_key_masked: str | None = None
    local_ai_api_key_masked: str | None = None

    @classmethod
    def from_model(
        cls,
        row: object,
    ) -> "SettingsResponse":
        return cls(
            immich_url=row.immich_url,
            local_ai_base_url=row.local_ai_base_url,
            ai_vision_hourly_limit=row.ai_vision_hourly_limit or 30,
            ai_image_hourly_limit=row.ai_image_hourly_limit or 10,
            debug_mode=row.debug_mode,
            favorite_albums_json=row.favorite_albums_json,
            ai_custom_prompt=row.ai_custom_prompt,
            retention_enabled=getattr(row, "retention_enabled", True),
            retention_rejected_files_days=getattr(row, "retention_rejected_files_days", 7),
            retention_rejected_metadata_days=getattr(row, "retention_rejected_metadata_days", 90),
            retention_failed_files_days=getattr(row, "retention_failed_files_days", 7),
            retention_failed_metadata_days=getattr(row, "retention_failed_metadata_days", 90),
            retention_uploaded_files_days=getattr(row, "retention_uploaded_files_days", 30),
            retention_uploaded_metadata_days=getattr(row, "retention_uploaded_metadata_days", 30),
            retention_task_days=getattr(row, "retention_task_days", 30),
            retention_audit_days=getattr(row, "retention_audit_days", 180),
            retention_backup_count=getattr(row, "retention_backup_count", 7),
            immich_api_key_masked="********" if getattr(row, "encrypted_immich_api_key", None) else None,
            openai_api_key_masked="********" if getattr(row, "encrypted_openai_api_key", None) else None,
            gemini_api_key_masked="********" if getattr(row, "encrypted_gemini_api_key", None) else None,
            openrouter_api_key_masked="********" if getattr(row, "encrypted_openrouter_api_key", None) else None,
            byteplus_api_key_masked="********" if getattr(row, "encrypted_byteplus_api_key", None) else None,
            xiaomi_api_key_masked="********" if getattr(row, "encrypted_xiaomi_api_key", None) else None,
            local_ai_api_key_masked="********" if getattr(row, "encrypted_local_ai_api_key", None) else None,
        )


class ConnectionTestResponse(BaseModel):
    ok: bool
    message: str
    provider: str
    detail: str | None = None
    model: str | None = None
    server_url: str | None = None
    user_email: str | None = None
    user_id: str | None = None
    server_version: str | None = None


class AvailableModelsResponse(BaseModel):
    vision_models: list[dict[str, str]]
    image_models: list[dict[str, str]]
