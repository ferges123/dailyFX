from dataclasses import dataclass
from typing import Any, Protocol

from app.models.settings import SettingsModel


@dataclass(frozen=True)
class ModuleDefinition:
    name: str
    label: str
    description: str
    default_weight: int = 1
    source_asset_count: int = 1
    default_enabled: bool = True
    default_config: dict[str, Any] | None = None
    config_schema: list[dict[str, Any]] | None = None


@dataclass
class GenerationResult:
    title: str
    summary: str
    image_bytes: bytes
    generation_type: str
    provider: str
    model: str
    config: dict
    source_asset_ids: list[str]


class GenerationModule(Protocol):
    name: str
    label: str
    description: str
    default_weight: int
    source_asset_count: int
    default_config: dict[str, Any] | None
    config_schema: list[dict[str, Any]] | None

    async def run(
        self,
        page_items: list,
        config: dict,
        client,
        settings: SettingsModel,
    ) -> GenerationResult: ...
