from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from app.config import get_settings
from app.models.settings import SettingsModel
from app.schemas.generation import GenerationExampleResponse
from app.services.generation.modules import MODULES
from app.services.immich import build_immich_client

EXAMPLE_PRESET_CONFIGS: dict[str, dict] = {
    "collage": {"styles": ["clarendon", "perpetua", "valencia", "lark"]},
    "instafilter": {"styles": ["clarendon"]},
}


@dataclass(frozen=True)
class ExamplePreviewResult:
    module_name: str
    title: str
    summary: str
    image_path: Path
    source_asset_id: str


class _ThumbnailClient:
    def __init__(self, image_bytes: bytes) -> None:
        self._image_bytes = image_bytes

    async def get_asset_thumbnail(self, asset_id: str, size: str = "preview") -> tuple[bytes, str | None]:
        return self._image_bytes, None

    async def get_asset_data(self, asset_id: str) -> bytes:
        return self._image_bytes

    async def get_asset_exif(self, asset_id: str) -> dict:
        return {}


def _example_dir() -> Path:
    path = get_settings().data_dir / "generation-examples"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _example_meta_path(module_name: str) -> Path:
    return _example_dir() / f"{module_name}.json"


def _example_image_path(module_name: str) -> Path:
    return _example_dir() / f"{module_name}.png"


def _example_source_asset_id() -> str:
    return get_settings().example_asset_id.strip()


async def ensure_example_preview(module_name: str, settings: SettingsModel) -> ExamplePreviewResult:
    module = MODULES.get(module_name)
    if module is None:
        raise KeyError(module_name)
    if not getattr(module, "show_example", True):
        raise KeyError(module_name)

    source_asset_id = _example_source_asset_id()
    if not source_asset_id:
        raise RuntimeError("Example asset ID is not configured")

    image_path = _example_image_path(module_name)
    meta_path = _example_meta_path(module_name)
    if image_path.exists() and meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text())
        except json.JSONDecodeError:
            meta = {}
        if meta.get("source_asset_id") == source_asset_id:
            return ExamplePreviewResult(
                module_name=module_name,
                title=str(meta.get("title") or module.label),
                summary=str(meta.get("summary") or module.description),
                image_path=image_path,
                source_asset_id=source_asset_id,
            )

    client = build_immich_client(settings)
    thumbnail_bytes, _ = await client.get_asset_thumbnail(source_asset_id, size="preview")
    preview_client = _ThumbnailClient(thumbnail_bytes)
    asset = SimpleNamespace(
        id=source_asset_id,
        original_file_name="Example asset",
        created_at=None,
    )

    seed = f"example:{module_name}:{source_asset_id}"
    state = random.getstate()
    random.seed(seed)
    try:
        result = await module.run([asset], EXAMPLE_PRESET_CONFIGS.get(module_name, module.default_config or {}), preview_client, settings)
    finally:
        random.setstate(state)

    image_path.write_bytes(result.image_bytes)
    meta_path.write_text(
        json.dumps(
            {
                "module_name": module_name,
                "title": result.title,
                "summary": result.summary,
                "source_asset_id": source_asset_id,
                "config": result.config,
            },
            indent=2,
        )
    )
    return ExamplePreviewResult(
        module_name=module_name,
        title=result.title,
        summary=result.summary,
        image_path=image_path,
        source_asset_id=source_asset_id,
    )


async def list_example_previews(settings: SettingsModel) -> list[GenerationExampleResponse]:
    previews: list[GenerationExampleResponse] = []
    for module in MODULES.values():
        if not getattr(module, "show_example", True):
            continue
        try:
            preview = await ensure_example_preview(module.name, settings)
        except Exception:
            continue
        previews.append(
            GenerationExampleResponse(
                module_name=preview.module_name,
                label=module.label,
                title=preview.title,
                summary=preview.summary,
                source_asset_id=preview.source_asset_id,
                image_url=f"/api/generation/examples/{preview.module_name}",
            )
        )
    return previews
