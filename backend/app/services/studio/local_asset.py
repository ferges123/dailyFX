from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps


@dataclass(frozen=True)
class StudioLocalAsset:
    id: str
    path: Path
    original_file_name: str
    mime_type: str
    created_at: str


class StudioLocalAssetClient:
    def __init__(self, *, temp_root: Path, assets: dict[str, StudioLocalAsset]) -> None:
        self.temp_root = temp_root.resolve()
        self.assets = assets

    def _asset(self, asset_id: str) -> StudioLocalAsset:
        asset = self.assets.get(asset_id)
        if asset is None:
            raise FileNotFoundError(f"Studio asset not found: {asset_id}")
        return asset

    def _safe_path(self, asset: StudioLocalAsset) -> Path:
        path = asset.path.resolve()
        if path != self.temp_root and self.temp_root not in path.parents:
            raise ValueError("Studio asset path is outside Studio temp root")
        if not path.exists():
            raise FileNotFoundError(f"Studio asset file not found: {asset.id}")
        return path

    async def get_asset_data(self, asset_id: str) -> bytes:
        asset = self._asset(asset_id)
        return self._safe_path(asset).read_bytes()

    async def get_asset_thumbnail(self, asset_id: str, size: str = "preview") -> tuple[bytes, str | None]:
        asset = self._asset(asset_id)
        path = self._safe_path(asset)
        with Image.open(path) as image:
            image = ImageOps.exif_transpose(image) or image
            image.thumbnail((1440, 1440) if size == "preview" else (320, 320))
            output = BytesIO()
            image.convert("RGB").save(output, format="JPEG", quality=88, optimize=True)
        return output.getvalue(), "image/jpeg"

    async def get_asset_exif(self, asset_id: str) -> dict[str, Any]:
        asset = self._asset(asset_id)
        path = self._safe_path(asset)
        try:
            with Image.open(path) as image:
                exif = image.getexif()
                if not exif:
                    return {}
                return {str(key): value for key, value in exif.items()}
        except Exception:
            return {}

    async def get_asset_info(self, asset_id: str) -> dict[str, Any]:
        asset = self._asset(asset_id)
        self._safe_path(asset)
        return {
            "id": asset.id,
            "originalFileName": asset.original_file_name,
            "type": "IMAGE",
            "mimeType": asset.mime_type,
            "createdAt": asset.created_at,
            "updatedAt": asset.created_at,
            "exifInfo": await self.get_asset_exif(asset_id),
            "people": [],
        }


def build_studio_asset(*, session_id: str, path: Path, original_file_name: str, mime_type: str) -> StudioLocalAsset:
    suffix = path.suffix.lower() or ".image"
    return StudioLocalAsset(
        id=f"studio://{session_id}/source{suffix}",
        path=path,
        original_file_name=original_file_name,
        mime_type=mime_type,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
