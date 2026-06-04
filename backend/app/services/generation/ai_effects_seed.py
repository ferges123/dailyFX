from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.ai_effects import _normalize_effect_id


class AIEffectSeedItem(BaseModel):
    id: str = Field(max_length=255)
    title: str = Field(max_length=255)
    description: str | None = None
    positive_prompt: str
    negative_prompt: str | None = None
    custom_prompt_placeholder: str | None = Field(default=None, max_length=255)
    default_weight: int = Field(default=1, ge=0, le=100)

    model_config = ConfigDict(extra="forbid")

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return _normalize_effect_id(value)


class AIEffectManifestEntry(BaseModel):
    id: str = Field(max_length=255)
    display_group: str | None = Field(default=None, max_length=255)
    hidden: bool = False

    model_config = ConfigDict(extra="forbid")

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return _normalize_effect_id(value)


class AIEffectManifest(BaseModel):
    schema_version: int = Field(default=1, ge=1)
    effects: list[AIEffectManifestEntry] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    @field_validator("effects", mode="before")
    @classmethod
    def normalize_effects(
        cls,
        value: list[object] | object,
    ) -> list[object]:
        if isinstance(value, list):
            normalized: list[object] = []
            for item in value:
                if isinstance(item, str):
                    normalized.append({"id": item})
                else:
                    normalized.append(item)
            return normalized
        return value


class AIEffectHash(BaseModel):
    value: str


def get_seed_dir() -> Path:
    return Path(__file__).with_name("ai_effects_data")


def get_seed_manifest_path() -> Path:
    return get_seed_dir() / "manifest.json"


def get_seed_path(effect_id: str) -> Path:
    normalized_id = _normalize_effect_id(effect_id)
    return get_seed_dir() / f"{normalized_id}.json"


def load_seed_effect(effect_id: str) -> AIEffectSeedItem | None:
    path = get_seed_path(effect_id)
    if not path.exists():
        return None
    return AIEffectSeedItem.model_validate(json.loads(path.read_text(encoding="utf-8")))


def load_seed_manifest() -> AIEffectManifest:
    path = get_seed_manifest_path()
    if not path.exists():
        raise FileNotFoundError(f"AI effects manifest not found: {path}")
    return AIEffectManifest.model_validate(json.loads(path.read_text(encoding="utf-8")))


def get_seed_manifest_entry_map() -> dict[str, AIEffectManifestEntry]:
    manifest = load_seed_manifest()
    entry_map: dict[str, AIEffectManifestEntry] = {}
    for entry in manifest.effects:
        if entry.id in entry_map:
            raise ValueError(f"Duplicate AI effect id in manifest: {entry.id}")
        entry_map[entry.id] = entry
    return entry_map


def load_seed_effects() -> list[AIEffectSeedItem]:
    seed_dir = get_seed_dir()
    if not seed_dir.exists():
        raise FileNotFoundError(f"AI effects seed directory not found: {seed_dir}")

    manifest = load_seed_manifest()
    if manifest.schema_version != 1:
        raise ValueError(f"Unsupported AI effect manifest schema version: {manifest.schema_version}")

    effects: list[AIEffectSeedItem] = []
    seen_ids: set[str] = set()
    for entry in manifest.effects:
        normalized_id = entry.id
        if normalized_id in seen_ids:
            raise ValueError(f"Duplicate AI effect id in manifest: {normalized_id}")
        seen_ids.add(normalized_id)
        item = load_seed_effect(normalized_id)
        if item is None:
            raise ValueError(f"Manifest references missing AI effect seed: {normalized_id}")
        effects.append(item)

    return effects


def get_seed_order_map() -> dict[str, int]:
    manifest = load_seed_manifest()
    order: dict[str, int] = {}
    for index, entry in enumerate(manifest.effects):
        order[entry.id] = index
    return order


def get_seed_hidden_map() -> dict[str, bool]:
    entry_map = get_seed_manifest_entry_map()
    return {effect_id: entry.hidden for effect_id, entry in entry_map.items()}


def seed_effect_hash(
    effect: AIEffectSeedItem,
    *,
    display_group: str | None = None,
    hidden: bool = False,
) -> AIEffectHash:
    payload = {
        "id": effect.id,
        "title": effect.title,
        "description": effect.description,
        "display_group": display_group,
        "positive_prompt": effect.positive_prompt,
        "negative_prompt": effect.negative_prompt,
        "custom_prompt_placeholder": effect.custom_prompt_placeholder,
        "hidden": hidden,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return AIEffectHash(value=digest)
