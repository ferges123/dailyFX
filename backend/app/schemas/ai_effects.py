from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _normalize_effect_id(value: str) -> str:
    normalized = value.strip().lower()
    if not normalized:
        raise ValueError("Effect id is required")
    if not normalized.replace("_", "").isalnum() or not normalized[0].isalpha():
        raise ValueError("Effect id must use lowercase letters, numbers, and underscores")
    return normalized


class AIEffectBase(BaseModel):
    id: str = Field(max_length=255)
    title: str = Field(max_length=255)
    description: str | None = None
    display_group: str | None = Field(default=None, max_length=255)
    positive_prompt: str
    negative_prompt: str | None = None
    custom_prompt_placeholder: str | None = Field(default=None, max_length=255)
    enabled: bool = True

    @field_validator("id")
    @classmethod
    def validate_effect_id(cls, value: str) -> str:
        return _normalize_effect_id(value)


class AIEffectCreate(AIEffectBase):
    pass


class AIEffectUpdate(AIEffectBase):
    pass


class AIEffectResponse(AIEffectBase):
    source: Literal["builtin", "custom", "imported"]
    display_group: str | None = None
    hidden: bool = False
    builtin_hash: str | None = None
    latest_builtin_hash: str | None = None
    user_modified_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_model(cls, row: object) -> "AIEffectResponse":
        return cls.model_validate(row)


class AIEffectImportItem(AIEffectBase):
    source: Literal["builtin", "custom", "imported"] | None = None


class AIEffectImportRequest(BaseModel):
    schema_version: int = 1
    overwrite_existing: bool = False
    effects: list[AIEffectImportItem]


class AIEffectExportRequest(BaseModel):
    schema_version: int = 1
    effects: list[AIEffectResponse]


class AIEffectImportResult(BaseModel):
    added: list[str] = Field(default_factory=list)
    updated: list[str] = Field(default_factory=list)
    skipped: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    invalid: list[str] = Field(default_factory=list)
