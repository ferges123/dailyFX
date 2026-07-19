from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.utils.url_utils import validate_http_url


class AppSettings(BaseSettings):
    app_env: str = Field(default="development", alias="APP_ENV")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8438, alias="APP_PORT", ge=1, le=65535)
    data_dir: Path = Field(default=Path("./data"), alias="DATA_DIR")
    database_url: str = Field(default="sqlite:///./data/app.db", alias="DATABASE_URL")
    app_secret_key: str = Field(alias="APP_SECRET_KEY")
    immich_thumbnail_cache_ttl: str | int = Field(default="7d", alias="IMMICH_THUMBNAIL_CACHE_TTL")
    immich_thumbnail_cache_ttl_seconds: int = Field(default=604800, alias="IMMICH_THUMBNAIL_CACHE_TTL_SECONDS")
    immich_thumbnail_cache_retention: str | int = Field(default="30d", alias="IMMICH_THUMBNAIL_CACHE_RETENTION")
    immich_thumbnail_cache_retention_seconds: int = Field(
        default=2592000, alias="IMMICH_THUMBNAIL_CACHE_RETENTION_SECONDS"
    )
    example_asset_id: str = Field(default="", alias="EXAMPLE_ASSET_ID")
    cors_origins: str = Field(default="", alias="CORS_ORIGINS")
    app_access_token: str | None = Field(default=None, alias="APP_ACCESS_TOKEN")
    review_token_ttl_seconds: int = Field(default=86400, alias="REVIEW_TOKEN_TTL_SECONDS", ge=60, le=2592000)
    app_contact_email: str = Field(default="dailyfx@localhost", alias="APP_CONTACT_EMAIL")
    app_external_url: str | None = Field(default=None, alias="APP_EXTERNAL_URL")
    log_json: bool = Field(default=False, alias="LOG_JSON")
    require_auth_for_review: bool = Field(default=False, alias="REQUIRE_AUTH_FOR_REVIEW")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    @model_validator(mode="before")
    @classmethod
    def load_deprecated_cache_settings(cls, data: dict) -> dict:
        import os

        # Support backward compatibility by mapping deprecated _SECONDS settings
        ttl_sec = (
            data.get("immich_thumbnail_cache_ttl_seconds")
            or data.get("IMMICH_THUMBNAIL_CACHE_TTL_SECONDS")
            or os.environ.get("IMMICH_THUMBNAIL_CACHE_TTL_SECONDS")
        )
        if ttl_sec is not None:
            data["immich_thumbnail_cache_ttl"] = ttl_sec

        ret_sec = (
            data.get("immich_thumbnail_cache_retention_seconds")
            or data.get("IMMICH_THUMBNAIL_CACHE_RETENTION_SECONDS")
            or os.environ.get("IMMICH_THUMBNAIL_CACHE_RETENTION_SECONDS")
        )
        if ret_sec is not None:
            data["immich_thumbnail_cache_retention"] = ret_sec

        return data

    @field_validator("immich_thumbnail_cache_ttl", "immich_thumbnail_cache_retention", mode="after")
    @classmethod
    def validate_duration(cls, value: str | int) -> str | int:
        from app.utils.duration import parse_duration_to_seconds

        try:
            parse_duration_to_seconds(value)
        except ValueError as e:
            raise ValueError(str(e))
        return value

    @model_validator(mode="after")
    def resolve_cache_settings(self) -> "AppSettings":
        from app.utils.duration import parse_duration_to_seconds

        # Resolve TTL
        if "immich_thumbnail_cache_ttl" in self.model_fields_set:
            self.immich_thumbnail_cache_ttl_seconds = parse_duration_to_seconds(self.immich_thumbnail_cache_ttl)
        elif "immich_thumbnail_cache_ttl_seconds" in self.model_fields_set:
            self.immich_thumbnail_cache_ttl = self.immich_thumbnail_cache_ttl_seconds
        else:
            self.immich_thumbnail_cache_ttl_seconds = parse_duration_to_seconds(self.immich_thumbnail_cache_ttl)

        # Resolve Retention
        if "immich_thumbnail_cache_retention" in self.model_fields_set:
            self.immich_thumbnail_cache_retention_seconds = parse_duration_to_seconds(
                self.immich_thumbnail_cache_retention
            )
        elif "immich_thumbnail_cache_retention_seconds" in self.model_fields_set:
            self.immich_thumbnail_cache_retention = self.immich_thumbnail_cache_retention_seconds
        else:
            self.immich_thumbnail_cache_retention_seconds = parse_duration_to_seconds(
                self.immich_thumbnail_cache_retention
            )

        return self

    @property
    def secret_key_material(self) -> str:
        return self.app_secret_key

    @field_validator("app_external_url", mode="before")
    @classmethod
    def validate_app_external_url(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        return validate_http_url(value, "APP_EXTERNAL_URL")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def validate_cors_origins(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            return ""

        origins = [origin.strip().rstrip("/") for origin in normalized.split(",") if origin.strip()]
        for origin in origins:
            parsed = urlparse(origin)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.path not in {"", "/"}:
                raise ValueError("CORS_ORIGINS entries must be absolute http:// or https:// origins")
            if parsed.params or parsed.query or parsed.fragment:
                raise ValueError("CORS_ORIGINS entries must be absolute http:// or https:// origins")
        return ",".join(origins)

    @field_validator("app_contact_email", mode="before")
    @classmethod
    def validate_app_contact_email(cls, value: str) -> str:
        normalized = value.strip()
        parts = normalized.split("@")
        if len(parts) != 2 or not parts[0] or not parts[1] or " " in normalized:
            raise ValueError("APP_CONTACT_EMAIL must be a valid email address")
        return normalized

    @property
    def cors_origin_list(self) -> list[str]:
        origins = [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
        if origins:
            return origins
        return [
            "http://localhost:8439",
            "http://127.0.0.1:8439",
            "http://web:80",
        ]


@lru_cache
def get_settings() -> AppSettings:
    return AppSettings()
