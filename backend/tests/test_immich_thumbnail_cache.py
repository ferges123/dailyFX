import asyncio
import os
import time
from pathlib import Path

import pytest

from app.config import AppSettings
from app.services.immich_thumbnail_cache import (
    _get_cache_dir,
    _locks,
    cleanup_cache,
    get_cached_immich_thumbnail,
)


# Mock Settings Row
class FakeSettingsRow:
    def __init__(self):
        self.immich_url = "http://localhost:8080"
        self.encrypted_immich_api_key = "fake-key"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def mock_settings(tmp_path, monkeypatch):
    # Clear the lru_cache for get_settings to avoid stale configuration
    from app.config import get_settings as config_get_settings

    config_get_settings.cache_clear()

    # Create fake app settings
    fake_app_settings = AppSettings(
        app_secret_key="fake-secret",
        immich_thumbnail_cache_ttl_seconds=604800,
        immich_thumbnail_cache_retention_seconds=2592000,
    )

    # Force data_dir to use the tmp_path to isolate cache files per test
    monkeypatch.setattr(fake_app_settings, "data_dir", tmp_path)

    monkeypatch.setattr("app.services.immich_thumbnail_cache.get_settings", lambda: fake_app_settings)
    monkeypatch.setattr("app.config.get_settings", lambda: fake_app_settings)
    return fake_app_settings


@pytest.mark.anyio
async def test_cache_miss_then_hit(mock_settings, monkeypatch):
    settings_row = FakeSettingsRow()
    fetch_calls = 0

    async def mock_fetch(settings, asset_id, size):
        nonlocal fetch_calls
        fetch_calls += 1
        return b"image-data", "image/png"

    monkeypatch.setattr("app.services.immich_thumbnail_cache.fetch_from_immich", mock_fetch)

    # 1. First request - cache miss, should fetch from Immich and write to disk
    cached1 = await get_cached_immich_thumbnail(settings_row, "asset-1", "preview")
    assert cached1.cache_hit is False
    assert cached1.content == b"image-data"
    assert cached1.content_type == "image/png"
    assert cached1.path is None
    assert cached1.etag is not None
    assert fetch_calls == 1

    # Verify files exist in cache directory
    cache_dir = _get_cache_dir()
    assert cache_dir.is_dir()
    files = list(cache_dir.iterdir())
    assert len(files) == 2  # .bin and .json

    # 2. Second request - cache hit, should read from cache, no fetch
    cached2 = await get_cached_immich_thumbnail(settings_row, "asset-1", "preview")
    assert cached2.cache_hit is True
    assert cached2.content is None
    assert cached2.content_type == "image/png"
    assert cached2.path is not None
    assert cached2.path.is_file()
    assert cached2.etag == cached1.etag
    assert fetch_calls == 1


@pytest.mark.anyio
async def test_different_sizes_and_assets(mock_settings, monkeypatch):
    settings_row = FakeSettingsRow()

    async def mock_fetch(settings, asset_id, size):
        return f"{asset_id}-{size}".encode("utf-8"), "image/jpeg"

    monkeypatch.setattr("app.services.immich_thumbnail_cache.fetch_from_immich", mock_fetch)

    cached_preview = await get_cached_immich_thumbnail(settings_row, "asset-1", "preview")
    cached_thumb = await get_cached_immich_thumbnail(settings_row, "asset-1", "thumbnail")
    cached_asset2 = await get_cached_immich_thumbnail(settings_row, "asset-2", "preview")

    assert cached_preview.etag != cached_thumb.etag
    assert cached_preview.etag != cached_asset2.etag


@pytest.mark.anyio
async def test_expired_entry_refreshes(mock_settings, monkeypatch):
    settings_row = FakeSettingsRow()
    fetch_calls = 0

    async def mock_fetch(settings, asset_id, size):
        nonlocal fetch_calls
        fetch_calls += 1
        return f"image-data-{fetch_calls}".encode("utf-8"), "image/png"

    monkeypatch.setattr("app.services.immich_thumbnail_cache.fetch_from_immich", mock_fetch)

    # First request
    await get_cached_immich_thumbnail(settings_row, "asset-1", "preview")
    assert fetch_calls == 1

    # Force expiration by setting TTL to 0
    mock_settings.immich_thumbnail_cache_ttl_seconds = 0

    # Second request - expired, should fetch again
    cached = await get_cached_immich_thumbnail(settings_row, "asset-1", "preview")
    assert cached.cache_hit is False
    assert cached.content == b"image-data-2"
    assert fetch_calls == 2


@pytest.mark.anyio
async def test_write_error_still_returns_image(mock_settings, monkeypatch):
    settings_row = FakeSettingsRow()

    async def mock_fetch(settings, asset_id, size):
        return b"image-data", "image/png"

    monkeypatch.setattr("app.services.immich_thumbnail_cache.fetch_from_immich", mock_fetch)

    # Mock mkdir to throw an error
    def mock_mkdir(*args, **kwargs):
        raise PermissionError("No write permissions")

    monkeypatch.setattr(Path, "mkdir", mock_mkdir)

    # Should succeed returning the fetched image despite cache write error
    cached = await get_cached_immich_thumbnail(settings_row, "asset-1", "preview")
    assert cached.cache_hit is False
    assert cached.content == b"image-data"


@pytest.mark.anyio
async def test_empty_or_error_not_cached(mock_settings, monkeypatch):
    settings_row = FakeSettingsRow()

    async def mock_fetch(settings, asset_id, size):
        return b"", "image/png"

    monkeypatch.setattr("app.services.immich_thumbnail_cache.fetch_from_immich", mock_fetch)

    # Empty content should not be cached
    cached = await get_cached_immich_thumbnail(settings_row, "asset-1", "preview")
    assert cached.cache_hit is False

    cache_dir = _get_cache_dir()
    if cache_dir.exists():
        assert len(list(cache_dir.iterdir())) == 0


@pytest.mark.anyio
async def test_concurrent_requests_only_one_fetch(mock_settings, monkeypatch):
    settings_row = FakeSettingsRow()
    fetch_calls = 0

    async def mock_fetch(settings, asset_id, size):
        nonlocal fetch_calls
        fetch_calls += 1
        await asyncio.sleep(0.1)  # Simulate network latency
        return b"image-data", "image/png"

    monkeypatch.setattr("app.services.immich_thumbnail_cache.fetch_from_immich", mock_fetch)

    # Run 3 concurrent requests
    tasks = [
        get_cached_immich_thumbnail(settings_row, "asset-1", "preview"),
        get_cached_immich_thumbnail(settings_row, "asset-1", "preview"),
        get_cached_immich_thumbnail(settings_row, "asset-1", "preview"),
    ]

    results = await asyncio.gather(*tasks)

    # Only the first one should fetch, the others should hit cache
    assert fetch_calls == 1
    assert results[0].cache_hit is False
    assert results[1].cache_hit is True
    assert results[2].cache_hit is True

    # Verify locks dictionary is cleaned up
    assert len(_locks) == 0


@pytest.mark.anyio
async def test_cleanup_removes_old_files_only(mock_settings, monkeypatch):
    cache_dir = _get_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Create fake files
    old_file = cache_dir / "old.bin"
    new_file = cache_dir / "new.bin"

    old_file.write_bytes(b"old")
    new_file.write_bytes(b"new")

    # Backdate old file modification time
    now = time.time()
    retention = mock_settings.immich_thumbnail_cache_retention_seconds

    old_mtime = now - retention - 10
    os.utime(old_file, (old_mtime, old_mtime))

    # Run cleanup
    await cleanup_cache()

    assert not old_file.exists()
    assert new_file.exists()
