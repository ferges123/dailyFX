import json
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.utils.date_utils import parse_date
from app.utils.url_utils import validate_http_url


class PersonFilterItem(BaseModel):
    personId: str
    mode: Literal["optional", "obligatory", "exclude"] = "optional"


# ── Filter Presets ────────────────────────────────────────────────────────────


class FilterPresetCreate(BaseModel):
    name: str = Field(max_length=255)
    album_ids: list[str] = Field(default_factory=list, max_length=100)
    person_filters: list[PersonFilterItem] = Field(default_factory=list, max_length=100)
    start_date: str | None = None
    end_date: str | None = None
    media_type: Literal["photo", "video", "all"] = "photo"

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def validate_dates(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        if parse_date(value) is None:
            raise ValueError("must be a valid YYYY-MM-DD date")
        return value

    @model_validator(mode="after")
    def validate_date_order(self) -> "FilterPresetCreate":
        if self.start_date and self.end_date and parse_date(self.start_date) > parse_date(self.end_date):
            raise ValueError("start_date must be on or before end_date")
        return self


class FilterPresetResponse(BaseModel):
    id: int
    name: str
    album_ids: list[str] = Field(default_factory=list)
    person_filters: list[PersonFilterItem] = Field(default_factory=list)
    start_date: str | None
    end_date: str | None
    media_type: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_model(cls, row: object) -> "FilterPresetResponse":
        return cls(
            id=row.id,
            name=row.name,
            album_ids=json.loads(row.album_ids_json or "[]"),
            person_filters=json.loads(row.person_filters_json or "[]"),
            start_date=row.start_date,
            end_date=row.end_date,
            media_type=row.media_type,
            created_at=row.created_at,
        )


# ── Effect Presets ────────────────────────────────────────────────────────────


class EffectPresetCreate(BaseModel):
    name: str = Field(max_length=255)
    groups: dict  # {module_name: {enabled, weight, config}}


class EffectPresetResponse(BaseModel):
    id: int
    name: str
    groups: dict
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_model(cls, row: object) -> "EffectPresetResponse":
        return cls(
            id=row.id,
            name=row.name,
            groups=json.loads(row.groups_json or "{}"),
            created_at=row.created_at,
        )


# ── Notification Presets ──────────────────────────────────────────────────────


class NotificationPresetCreate(BaseModel):
    name: str = Field(max_length=255)
    provider: str = Field(default="web", max_length=100)
    url: str | None = Field(default=None, max_length=2048)
    topic: str | None = Field(default=None, max_length=255)
    token: str | None = Field(default=None, max_length=4096)  # plain text — encrypted on save
    webhook_url: str | None = Field(default=None, max_length=2048)
    push_subscription_ids: list[int] = Field(default_factory=list)

    @field_validator("push_subscription_ids")
    @classmethod
    def validate_push_subscription_ids(cls, value: list[int]) -> list[int]:
        if any(item <= 0 for item in value):
            raise ValueError("push_subscription_ids must contain positive integers")
        if len(value) != len(set(value)):
            raise ValueError("push_subscription_ids must not contain duplicates")
        return value

    @field_validator("provider", mode="before")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("provider must be a comma-separated list of valid providers")
        normalized = ",".join(part.strip().lower() for part in value.split(",") if part.strip())
        if not normalized:
            return "web"
        allowed = {"web", "ntfy", "gotify", "telegram", "homeassistant", "apprise", "discord", "slack"}
        invalid = [part for part in normalized.split(",") if part not in allowed]
        if invalid:
            raise ValueError(f"provider contains invalid value(s): {', '.join(invalid)}")
        return normalized

    @model_validator(mode="after")
    def validate_urls(self) -> "NotificationPresetCreate":
        providers = {part.strip().lower() for part in self.provider.split(",") if part.strip()}
        needs_base_url = bool(providers & {"ntfy", "gotify", "homeassistant"})

        if self.url is not None and self.url != "":
            if needs_base_url:
                self.url = validate_http_url(self.url, "Server URL")
            else:
                self.url = self.url.strip()
        else:
            self.url = None

        if self.webhook_url is not None and self.webhook_url != "":
            self.webhook_url = validate_http_url(self.webhook_url, "Webhook URL")
        else:
            self.webhook_url = None

        return self


class NotificationPresetResponse(BaseModel):
    id: int
    name: str
    provider: str
    url: str | None
    topic: str | None
    has_token: bool
    token_masked: str | None = None
    webhook_url: str | None
    created_at: datetime
    push_subscription_ids: list[int] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_model(
        cls,
        row: object,
        *,
        token_masked: str | None = None,
    ) -> "NotificationPresetResponse":
        return cls(
            id=row.id,
            name=row.name,
            provider=row.provider,
            url=row.url,
            topic=row.topic,
            has_token=bool(row.encrypted_token),
            token_masked=token_masked,
            webhook_url=row.webhook_url,
            created_at=row.created_at,
            push_subscription_ids=[sub.id for sub in row.push_subscriptions] if hasattr(row, "push_subscriptions") else [],
        )



class NotificationPresetTestResponse(BaseModel):
    ok: bool
    sent: list[str]
    errors: list[str] = Field(default_factory=list)
