from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.immich.errors import ImmichError
from app.models.generation_history import GenerationHistoryModel
from app.schemas.generation import GenerationAcceptRequest
from app.services.generation.upload_metadata import build_immich_upload_metadata

logger = logging.getLogger(__name__)


async def _apply_album_and_tag(
    *,
    client: Any,
    upload_asset_id: str,
    album_name: str,
    request: GenerationAcceptRequest | None = None,
) -> tuple[str | None, bool, bool, list[str]]:
    album_id = request.album_id if request and request.album_id is not None else None
    album_created = False
    album_updated = False
    accept_notes: list[str] = []

    create_album = request.create_album if request is not None else True
    if create_album or album_name:
        try:
            albums = await client.list_albums()
            existing_album = next((album for album in albums if album.album_name.lower() == album_name.lower()), None)
            if existing_album is not None:
                await client.add_assets_to_album(existing_album.id, [upload_asset_id])
                album_id = existing_album.id
                album_updated = True
            else:
                connection = await client.test_connection()
                if connection.user_id:
                    created_album = await client.create_album(album_name, [upload_asset_id], user_id=connection.user_id)
                    if created_album is not None:
                        album_id = created_album.id
                        album_created = True
        except ImmichError as exc:
            message = f"Album update failed: {exc}"
            logger.warning("Uploaded to Immich but %s", message)
            accept_notes.append(message)

    tag_name = "dailyFX"
    try:
        tag = await client.ensure_tag(tag_name)
        await client.tag_assets(tag.id, [upload_asset_id])
    except ImmichError as exc:
        message = f"Tagging failed: {exc}"
        logger.warning("Uploaded to Immich but %s", message)
        accept_notes.append(message)

    return album_id, album_created, album_updated, accept_notes


async def _upload_generation_asset(
    *,
    client: Any,
    row: GenerationHistoryModel,
    task_id: str,
    image_path: Path,
):
    content = image_path.read_bytes()
    metadata = build_immich_upload_metadata(row=row, task_id=task_id, image_path=image_path)
    return await client.upload_asset(content=content, metadata=metadata)


async def _apply_uploaded_asset_caption_and_tags(
    *, client: Any, upload_asset_id: str, row: GenerationHistoryModel
) -> None:
    if row.summary:
        try:
            await client.update_asset(upload_asset_id, description=row.summary)
        except Exception as update_exc:
            logger.warning("Failed to update asset description in Immich: %s", update_exc)

    if row.tags_json:
        try:
            tag_names = json.loads(row.tags_json)
            if tag_names:
                tags = await client.upsert_tags(tag_names)
                for tag in tags:
                    await client.tag_assets(tag.id, [upload_asset_id])
        except Exception as tag_exc:
            logger.warning("Failed to apply AI tags in Immich: %s", tag_exc)
