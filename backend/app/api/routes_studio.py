
import json
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.limiter import limiter
from app.models.generation_history import GenerationHistoryModel
from app.security import require_auth

from app.services.immich import get_or_create_settings
from app.services.generation.modules import MODULES
from app.services.generation.stream import record_history_snapshot
from app.services.generation.ai_vision import analyze_image
from app.schemas.generation import GenerationModuleResponse
from app.services.generation.ai_effects import get_seed_hidden_map
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


def _parse_bool_form(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_supported_module(effect_id: str):
    module = MODULES.get(effect_id)
    if module is None:
        raise HTTPException(status_code=404, detail="Studio effect not found")
    if getattr(module, "source_asset_count", 1) != 1:
        raise HTTPException(status_code=400, detail="This effect is not supported in Studio yet")
    return module


@router.post("/preview")
@limiter.limit("5/minute")
async def create_studio_preview(
    request: Request,


    file: UploadFile = File(...),
    effect_id: str = Form(...),
    config: str = Form("{}"),
    ai_vision_enabled: str | None = Form(None),
    prompt_enrichment_enabled: str | None = Form(None),
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    settings = get_or_create_settings(db)

    module = _get_supported_module(effect_id)
    parsed_config = _parse_config(config)
    from app.services.generation.config_validation import validate_module_config
    try:
        validate_module_config(effect_id, {"config": parsed_config})
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    module_config = {
        **(getattr(module, "default_config", None) or {}),
        **parsed_config,
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

    original_prompt_enrichment = getattr(settings, "ai_prompt_enrichment", False)
    prompt_enrichment_requested = _parse_bool_form(prompt_enrichment_enabled)
    settings.ai_prompt_enrichment = prompt_enrichment_requested and effect_id.startswith("ai_")

    try:
        result = await module.run([asset_summary], module_config, local_client, settings)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Studio preview failed for effect %s: %s", effect_id, exc)
        raise HTTPException(status_code=500, detail=f"Studio preview failed: {exc}") from exc
    finally:
        settings.ai_prompt_enrichment = original_prompt_enrichment

    task_id = f"studio-{uuid.uuid4().hex}"
    output_dir = get_settings().data_dir / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{task_id}.png"
    output_path.write_bytes(result.image_bytes)

    vision_result = None
    if _parse_bool_form(ai_vision_enabled):
        vision_result = await analyze_image(settings, result.image_bytes)

    title = vision_result.title if vision_result else result.title
    summary = vision_result.summary if vision_result else result.summary
    tags = vision_result.tags if vision_result else []
    total_token_count = vision_result.token_count if vision_result else None
    provider = vision_result.provider if vision_result and vision_result.provider else result.provider
    model = vision_result.model if vision_result and vision_result.model else result.model

    row = GenerationHistoryModel(
        task_id=task_id,
        generation_type=result.generation_type or effect_id,
        status="PENDING_REVIEW",
        title=title,
        summary=summary,
        source_asset_ids=json.dumps(result.source_asset_ids or [asset.id]),
        output_path=str(output_path),
        image_url=f"/api/generation/history/{task_id}/image",
        provider=provider,
        model=model,
        total_token_count=total_token_count,
        config_json=json.dumps(result.config or module_config),
        tags_json=json.dumps(tags),
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


@router.get("/modules", response_model=list[GenerationModuleResponse])
async def list_studio_modules(_: None = Depends(require_auth)) -> list[GenerationModuleResponse]:
    hidden_map = get_seed_hidden_map()
    modules = []
    for module in MODULES.values():
        if getattr(module, "source_asset_count", 1) != 1:
            continue
        if getattr(module, "source", None) == "builtin" and hidden_map.get(module.name, False):
            continue
        modules.append(
            GenerationModuleResponse(
                name=module.name,
                label=module.label,
                description=module.description,
                default_weight=module.default_weight,
                default_config=module.default_config or {},
                config_schema=getattr(module, "config_schema", None) or [],
            )
        )
    return modules
