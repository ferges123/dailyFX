from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models.generation_history import GenerationHistoryModel
from app.security import require_auth
from app.services.immich import get_or_create_settings
from app.services.generation.modules import MODULES
from app.services.generation.stream import record_history_snapshot
from app.services.studio.local_asset import StudioLocalAssetClient, build_studio_asset
from app.services.studio.validation import (
    StudioUploadValidationError,
    create_studio_session_dir,
    validate_studio_image_upload,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/studio", tags=["studio"])


class StudioAssetSummary:
    def __init__(self, *, id: str, original_file_name: str, created_at: str, mime_type: str) -> None:
        self.id = id
        self.original_file_name = original_file_name
        self.created_at = created_at
        self.updated_at = created_at
        self.mime_type = mime_type
        self.asset_type = "IMAGE"
        self.people = []


def _parse_config(raw: str) -> dict:
    try:
        parsed = json.loads(raw or "{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail="Studio config must be valid JSON") from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=422, detail="Studio config must be a JSON object")
    return parsed


def _get_supported_module(effect_id: str):
    module = MODULES.get(effect_id)
    if module is None:
        raise HTTPException(status_code=404, detail="Studio effect not found")
    if getattr(module, "source_asset_count", 1) != 1:
        raise HTTPException(status_code=400, detail="This effect is not supported in Studio yet")
    return module


@router.post("/preview")
async def create_studio_preview(
    file: UploadFile = File(...),
    effect_id: str = Form(...),
    config: str = Form("{}"),
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    settings = get_or_create_settings(db)

    module = _get_supported_module(effect_id)
    module_config = {
        **(getattr(module, "default_config", None) or {}),
        **_parse_config(config),
    }

    content = await file.read()
    try:
        validated = validate_studio_image_upload(
            filename=file.filename or "upload",
            content_type=file.content_type,
            content=content,
        )
    except StudioUploadValidationError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc

    temp_root = get_settings().data_dir / "temp" / "studio"
    session_id, session_dir = create_studio_session_dir(temp_root)
    source_path = session_dir / f"source{validated.extension}"
    source_path.write_bytes(content)

    asset = build_studio_asset(
        session_id=session_id,
        path=source_path,
        original_file_name=file.filename or source_path.name,
        mime_type=validated.mime_type,
    )
    asset_summary = StudioAssetSummary(
        id=asset.id,
        original_file_name=asset.original_file_name,
        created_at=asset.created_at,
        mime_type=asset.mime_type,
    )
    local_client = StudioLocalAssetClient(temp_root=temp_root, assets={asset.id: asset})

    try:
        result = await module.run([asset_summary], module_config, local_client, settings)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Studio preview failed for effect %s: %s", effect_id, exc)
        raise HTTPException(status_code=500, detail=f"Studio preview failed: {exc}") from exc

    task_id = f"studio-{uuid.uuid4().hex}"
    output_dir = get_settings().data_dir / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{task_id}.png"
    output_path.write_bytes(result.image_bytes)

    row = GenerationHistoryModel(
        task_id=task_id,
        generation_type=result.generation_type or effect_id,
        status="PENDING_REVIEW",
        title=result.title,
        summary=result.summary,
        source_asset_ids=json.dumps(result.source_asset_ids or [asset.id]),
        output_path=str(output_path),
        image_url=f"/api/generation/history/{task_id}/image",
        provider=result.provider,
        model=result.model,
        config_json=json.dumps(result.config or module_config),
        tags_json=json.dumps([]),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    record_history_snapshot(db, row)

    return {
        "task_id": task_id,
        "history_url": f"/history/{task_id}",
        "image_url": row.image_url,
        "module_name": effect_id,
        "title": row.title,
        "summary": row.summary,
    }
