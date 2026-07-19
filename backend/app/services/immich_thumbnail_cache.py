import asyncio
import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.config import get_settings
from app.models.settings import SettingsModel
from app.services.immich import get_asset_thumbnail as fetch_from_immich

logger = logging.getLogger(__name__)

# Global locks dictionary to serialize requests for the same asset+size: key -> (Lock, ref_count)
_locks: dict[str, tuple[asyncio.Lock, int]] = {}
_last_cleanup_time = 0.0


@dataclass
class CachedThumbnail:
    path: Path | None
    content: bytes | None
    content_type: str
    etag: str
    cache_hit: bool


def _get_cache_dir() -> Path:
    settings = get_settings()
    return settings.data_dir / "cache" / "immich-thumbnails"


def _get_cache_keys(asset_id: str, size: str) -> tuple[Path, Path]:
    # Use deterministic SHA256 of asset_id and size to prevent path traversal
    key_input = f"{asset_id}:{size}"
    cache_key = hashlib.sha256(key_input.encode("utf-8")).hexdigest()
    cache_dir = _get_cache_dir()

    img_path = cache_dir / f"{cache_key}.bin"
    meta_path = cache_dir / f"{cache_key}.json"
    return img_path, meta_path


async def cleanup_cache() -> None:
    try:
        cache_dir = _get_cache_dir().resolve()
        if not cache_dir.is_dir():
            return

        retention = get_settings().immich_thumbnail_cache_retention_seconds
        now = time.time()

        def sync_cleanup():
            logger.info("Starting opportunistic Immich thumbnail cache cleanup...")
            count = 0
            for path in cache_dir.iterdir():
                if not path.is_file():
                    continue
                try:
                    resolved_path = path.resolve()
                    if not resolved_path.is_relative_to(cache_dir):
                        logger.warning("Safety violation: path outside cache_dir: %s", path)
                        continue

                    mtime = resolved_path.stat().st_mtime
                    if now - mtime > retention:
                        resolved_path.unlink()
                        count += 1
                except Exception as e:
                    logger.warning("Failed to check/delete cache file %s: %s", path, e)
            if count > 0:
                logger.info("Cleaned up %d expired files from Immich thumbnail cache", count)

        await asyncio.to_thread(sync_cleanup)
    except Exception as e:
        logger.error("Error during Immich thumbnail cache cleanup: %s", e)


def trigger_opportunistic_cleanup() -> None:
    global _last_cleanup_time
    now = time.time()
    if now - _last_cleanup_time > 86400:
        _last_cleanup_time = now
        asyncio.create_task(cleanup_cache())


async def get_cached_immich_thumbnail(
    settings: SettingsModel,
    asset_id: str,
    size: str,
) -> CachedThumbnail:
    trigger_opportunistic_cleanup()
    img_path, meta_path = _get_cache_keys(asset_id, size)

    # 1. Fast path check: if cache exists and is valid, return immediately without locking
    if img_path.is_file() and meta_path.is_file():
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)

            cached_at = meta.get("cached_at", 0)
            content_type = meta.get("content_type", "image/jpeg")
            etag = meta.get("etag", "")

            ttl = get_settings().immich_thumbnail_cache_ttl_seconds
            if time.time() - cached_at < ttl:
                logger.info("Immich thumbnail cache hit for asset_id=%s, size=%s", asset_id, size)
                return CachedThumbnail(
                    path=img_path, content=None, content_type=content_type, etag=etag, cache_hit=True
                )
        except Exception as e:
            logger.warning("Error reading cache metadata for asset_id=%s, size=%s: %s", asset_id, size, e)

    # 2. Cache miss or expired: serialize concurrent requests for the same asset+size
    cache_key = f"{asset_id}:{size}"

    # Get or create Lock
    if cache_key not in _locks:
        _locks[cache_key] = (asyncio.Lock(), 1)
    else:
        lock, ref = _locks[cache_key]
        _locks[cache_key] = (lock, ref + 1)

    lock = _locks[cache_key][0]

    try:
        async with lock:
            # 3. Double-check: check if a concurrent request already updated the cache while we waited
            if img_path.is_file() and meta_path.is_file():
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)

                    cached_at = meta.get("cached_at", 0)
                    content_type = meta.get("content_type", "image/jpeg")
                    etag = meta.get("etag", "")

                    ttl = get_settings().immich_thumbnail_cache_ttl_seconds
                    if time.time() - cached_at < ttl:
                        logger.info("Immich thumbnail cache hit after lock for asset_id=%s, size=%s", asset_id, size)
                        return CachedThumbnail(
                            path=img_path, content=None, content_type=content_type, etag=etag, cache_hit=True
                        )
                except Exception as e:
                    logger.warning(
                        "Error reading cache metadata after lock for asset_id=%s, size=%s: %s", asset_id, size, e
                    )

            # 4. Fetch from Immich
            logger.info("Immich thumbnail cache miss/expired for asset_id=%s, size=%s", asset_id, size)
            content, content_type_opt = await fetch_from_immich(settings, asset_id, size=size)
            content_type = content_type_opt or "image/jpeg"

            # Calculate stable etag (SHA-256 of content)
            content_hash = hashlib.sha256(content).hexdigest()
            etag = f'"{content_hash}"'

            # Try to write to cache, but don't let failures block returning the image
            if content and len(content) > 0:
                try:
                    cache_dir = _get_cache_dir()
                    cache_dir.mkdir(parents=True, exist_ok=True)

                    # Atomic write for image
                    temp_img = cache_dir / f"{img_path.name}.tmp_{uuid.uuid4().hex}"
                    temp_img.write_bytes(content)
                    temp_img.replace(img_path)

                    # Atomic write for metadata
                    meta_data = {
                        "asset_id": asset_id,
                        "size": size,
                        "content_type": content_type,
                        "etag": etag,
                        "cached_at": time.time(),
                    }
                    temp_meta = cache_dir / f"{meta_path.name}.tmp_{uuid.uuid4().hex}"
                    with open(temp_meta, "w", encoding="utf-8") as f:
                        json.dump(meta_data, f)
                    temp_meta.replace(meta_path)

                    logger.info("Immich thumbnail cache updated for asset_id=%s, size=%s", asset_id, size)
                except Exception as e:
                    logger.error("Failed to write to immich thumbnail cache: %s", e)

            return CachedThumbnail(path=None, content=content, content_type=content_type, etag=etag, cache_hit=False)
    finally:
        # Decrement ref count and clean up the lock from dictionary
        try:
            lock_item = _locks.get(cache_key)
            if lock_item:
                lock_obj, ref = lock_item
                if ref <= 1:
                    _locks.pop(cache_key, None)
                else:
                    _locks[cache_key] = (lock_obj, ref - 1)
        except Exception as e:
            logger.error("Error cleaning up cache lock for asset_id=%s, size=%s: %s", asset_id, size, e)
