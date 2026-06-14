import asyncio
from pathlib import Path

from PIL import Image

from app.services.studio.local_asset import StudioLocalAsset, StudioLocalAssetClient


def write_image(path: Path, fmt: str = "JPEG") -> None:
    image = Image.new("RGB", (32, 24), color=(30, 120, 80))
    image.save(path, format=fmt)


def test_local_asset_client_reads_source_bytes(tmp_path: Path) -> None:
    source = tmp_path / "temp" / "studio" / "session-1" / "source.jpg"
    source.parent.mkdir(parents=True)
    write_image(source)
    original = source.read_bytes()

    asset = StudioLocalAsset(
        id="studio://session-1/source.jpg",
        path=source,
        original_file_name="source.jpg",
        mime_type="image/jpeg",
        created_at="2026-06-11T10:00:00Z",
    )
    client = StudioLocalAssetClient(temp_root=tmp_path / "temp" / "studio", assets={asset.id: asset})

    assert asyncio.run(client.get_asset_data(asset.id)) == original


def test_local_asset_client_rejects_unknown_asset(tmp_path: Path) -> None:
    client = StudioLocalAssetClient(temp_root=tmp_path / "temp" / "studio", assets={})

    import pytest

    with pytest.raises(FileNotFoundError):
        asyncio.run(client.get_asset_data("studio://missing/source.jpg"))


def test_local_asset_client_rejects_path_outside_temp_root(tmp_path: Path) -> None:
    outside = tmp_path / "outside.jpg"
    write_image(outside)
    asset = StudioLocalAsset(
        id="studio://bad/source.jpg",
        path=outside,
        original_file_name="source.jpg",
        mime_type="image/jpeg",
        created_at="2026-06-11T10:00:00Z",
    )
    client = StudioLocalAssetClient(temp_root=tmp_path / "temp" / "studio", assets={asset.id: asset})

    import pytest

    with pytest.raises(ValueError, match="outside Studio temp root"):
        asyncio.run(client.get_asset_data(asset.id))


def test_local_asset_client_returns_thumbnail_bytes(tmp_path: Path) -> None:
    source = tmp_path / "temp" / "studio" / "session-1" / "source.png"
    source.parent.mkdir(parents=True)
    write_image(source, fmt="PNG")
    asset = StudioLocalAsset(
        id="studio://session-1/source.png",
        path=source,
        original_file_name="source.png",
        mime_type="image/png",
        created_at="2026-06-11T10:00:00Z",
    )
    client = StudioLocalAssetClient(temp_root=tmp_path / "temp" / "studio", assets={asset.id: asset})

    thumbnail, content_type = asyncio.run(client.get_asset_thumbnail(asset.id, size="preview"))

    assert content_type == "image/jpeg"
    assert thumbnail.startswith(b"\xff\xd8")


def test_local_asset_client_returns_minimal_exif(tmp_path: Path) -> None:
    source = tmp_path / "temp" / "studio" / "session-1" / "source.jpg"
    source.parent.mkdir(parents=True)
    write_image(source)
    asset = StudioLocalAsset(
        id="studio://session-1/source.jpg",
        path=source,
        original_file_name="source.jpg",
        mime_type="image/jpeg",
        created_at="2026-06-11T10:00:00Z",
    )
    client = StudioLocalAssetClient(temp_root=tmp_path / "temp" / "studio", assets={asset.id: asset})

    exif = asyncio.run(client.get_asset_exif(asset.id))

    assert isinstance(exif, dict)
