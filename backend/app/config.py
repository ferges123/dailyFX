from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.utils.url_utils import validate_http_url


class AppSettings(BaseSettings):
    app_env: str = Field(default="development", alias="APP_ENV")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8438, alias="APP_PORT", ge=1, le=65535)
    data_dir: Path = Field(default=Path("./data"), alias="DATA_DIR")
    database_url: str = Field(default="sqlite:///./data/app.db", alias="DATABASE_URL")
    app_secret_key: str = Field(alias="APP_SECRET_KEY")
    example_asset_id: str = Field(default="", alias="EXAMPLE_ASSET_ID")
    cors_origins: str = Field(default="", alias="CORS_ORIGINS")
    app_access_token: str | None = Field(default=None, alias="APP_ACCESS_TOKEN")
    app_contact_email: str = Field(default="dailyfx@localhost", alias="APP_CONTACT_EMAIL")
    app_external_url: str | None = Field(default=None, alias="APP_EXTERNAL_URL")
    log_json: bool = Field(default=False, alias="LOG_JSON")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

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
