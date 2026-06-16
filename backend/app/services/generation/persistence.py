from __future__ import annotations

import json
import logging

from app.models.generation_history import GenerationHistoryModel

logger = logging.getLogger(__name__)


def _load_existing_history_config(existing: GenerationHistoryModel | None) -> dict:
    if not existing or not existing.config_json:
        return {}

    try:
        parsed = json.loads(existing.config_json)
    except Exception:
        return {}

    return parsed if isinstance(parsed, dict) else {}


def _build_generation_history_config(*, existing_config: dict, result, artifacts) -> dict:
    return {
        **existing_config,
        **result.config,
        "metadata_provenance": artifacts.metadata_provenance,
        **(
            {"source_created_at": artifacts.source_asset.created_at}
            if artifacts.source_asset and artifacts.source_asset.created_at
            else {}
        ),
        **(
            {"source_original_file_name": artifacts.source_asset.original_file_name}
            if artifacts.source_asset and artifacts.source_asset.original_file_name
            else {}
        ),
        **({"exif": artifacts.exif_info} if artifacts.exif_info else {}),
    }


def _save_generation_output(output_path, final_bytes: bytes) -> None:
    output_path.write_bytes(final_bytes)


def _prime_generation_thumbnail(output_path) -> None:
    from app.services.generation.history import get_or_create_thumbnail

    try:
        get_or_create_thumbnail(output_path)
    except Exception as thumb_err:
        logger.warning(f"Failed to pre-generate thumbnail during generation cycle: {thumb_err}")


def persist_generation_result(
    *,
    db,
    task_id: str,
    result,
    artifacts,
    output_path,
    image_url: str,
    schedule_id: int | None,
    album_name: str | None,
) -> None:
    from app.services.generation.history import upsert_history_entry

    existing = db.query(GenerationHistoryModel).filter(GenerationHistoryModel.task_id == task_id).first()
    existing_config = _load_existing_history_config(existing)

    _save_generation_output(output_path, artifacts.final_bytes)
    _prime_generation_thumbnail(output_path)
    logger.info(f"💾 Saved result to {output_path} (task_id={task_id})")

    upsert_history_entry(
        db,
        task_id,
        generation_type=result.generation_type,
        status="PENDING_REVIEW",
        title=artifacts.ai_title,
        summary=artifacts.ai_summary,
        source_asset_ids=json.dumps(result.source_asset_ids),
        output_path=str(output_path),
        image_url=image_url,
        provider=artifacts.ai_provider,
        model=artifacts.ai_model,
        total_token_count=artifacts.ai_token_count,
        tags_json=json.dumps(artifacts.ai_tags) if artifacts.ai_tags else None,
        schedule_id=schedule_id,
        album_name=album_name,
        output_format=getattr(result, "output_format", "png")
        if isinstance(getattr(result, "output_format", None), str)
        else "png",
        frame_count=getattr(result, "frame_count", None)
        if isinstance(getattr(result, "frame_count", None), int)
        else None,
        config_json=json.dumps(
            _build_generation_history_config(existing_config=existing_config, result=result, artifacts=artifacts)
        ),
        task_step="review_ready",
    )
