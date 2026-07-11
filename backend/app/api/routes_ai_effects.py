from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.ai_effect import AIEffectModel
from app.models.effect_preset import EffectPresetModel
from app.schemas.ai_effects import (
    AIEffectCreate,
    AIEffectExportRequest,
    AIEffectImportRequest,
    AIEffectImportResult,
    AIEffectResponse,
    AIEffectUpdate,
)
from app.security import ActorContext, get_actor_context, require_auth, resolve_actor_context
from app.services.audit import record_audit_event
from app.services.generation.ai_effects import (
    get_seed_hidden_map,
    get_seed_manifest_entry_map,
    get_seed_order_map,
    load_seed_effect,
    seed_effect_hash,
)
from app.services.generation.modules import MODULES

router = APIRouter(prefix="/api/ai-effects", tags=["ai-effects"])


def build_effect_diff(old_dict: dict, new_dict: dict) -> dict:
    diff = {}
    for k in old_dict.keys() | new_dict.keys():
        old_val = old_dict.get(k)
        new_val = new_dict.get(k)
        if old_val != new_val:
            diff[k] = {"from": old_val, "to": new_val}
    return diff


def _effect_in_use(db: Session, effect_id: str) -> bool:
    pattern = f'%"{effect_id}"%'
    return db.query(EffectPresetModel).filter(EffectPresetModel.groups_json.like(pattern)).first() is not None


def _row_to_response(
    row: AIEffectModel,
    *,
    hidden_map: dict[str, bool] | None = None,
) -> AIEffectResponse:
    hidden_map = hidden_map or get_seed_hidden_map()
    response = AIEffectResponse.from_model(row)
    if row.source == "builtin":
        response.hidden = hidden_map.get(row.id, False)
    return response


def _get_row_or_404(db: Session, effect_id: str) -> AIEffectModel:
    row = db.get(AIEffectModel, effect_id)
    if row is None:
        raise HTTPException(status_code=404, detail="AI effect not found")
    return row


def _set_user_modified_if_needed(row: AIEffectModel, body: AIEffectCreate | AIEffectUpdate) -> None:
    if row.source != "builtin":
        return
    if (
        row.title != body.title
        or row.description != body.description
        or row.display_group != body.display_group
        or row.positive_prompt != body.positive_prompt
        or row.negative_prompt != body.negative_prompt
        or row.custom_prompt_placeholder != body.custom_prompt_placeholder
    ):
        row.user_modified_at = datetime.now(timezone.utc)


@router.get("", response_model=list[AIEffectResponse])
def list_ai_effects(db: Session = Depends(get_db), _: None = Depends(require_auth)):
    rows = db.query(AIEffectModel).all()
    hidden_map = get_seed_hidden_map()
    order_map = get_seed_order_map()
    rows = [row for row in rows if not (row.source == "builtin" and hidden_map.get(row.id, False))]
    rows.sort(
        key=lambda row: (
            0 if row.source == "builtin" else 1 if row.source == "custom" else 2,
            order_map.get(row.id, 10_000_000) if row.source == "builtin" else row.title.lower(),
            row.id,
        )
    )
    return [_row_to_response(row, hidden_map=hidden_map) for row in rows]


@router.post("", response_model=AIEffectResponse, status_code=201)
def create_ai_effect(
    body: AIEffectCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
    actor_ctx: ActorContext = Depends(get_actor_context),
):
    actor_ctx = resolve_actor_context(actor_ctx)
    if db.get(AIEffectModel, body.id) is not None:
        raise HTTPException(status_code=409, detail="AI effect with this id already exists")
    row = AIEffectModel(
        id=body.id,
        title=body.title,
        description=body.description,
        display_group=body.display_group,
        positive_prompt=body.positive_prompt,
        negative_prompt=body.negative_prompt,
        custom_prompt_placeholder=body.custom_prompt_placeholder,
        source="custom",
        enabled=body.enabled,
        weight=1,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    MODULES.invalidate()

    record_audit_event(
        db=db,
        action="effect.created",
        category="effect",
        outcome="success",
        actor_type=actor_ctx.actor_type,
        request_id=actor_ctx.request_id,
        source_ip_hash=actor_ctx.source_ip_hash,
        target_type="effect",
        target_id=row.id,
        summary=f"AI effect '{row.title}' created",
        metadata={"id": row.id, "title": row.title},
    )

    return _row_to_response(row)


@router.put("/{effect_id}", response_model=AIEffectResponse)
def update_ai_effect(
    effect_id: str,
    body: AIEffectUpdate,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
    actor_ctx: ActorContext = Depends(get_actor_context),
):
    actor_ctx = resolve_actor_context(actor_ctx)
    row = _get_row_or_404(db, effect_id)

    old_dict = {
        "title": row.title,
        "description": row.description,
        "display_group": row.display_group,
        "positive_prompt": row.positive_prompt,
        "negative_prompt": row.negative_prompt,
        "custom_prompt_placeholder": row.custom_prompt_placeholder,
        "enabled": row.enabled,
    }

    _set_user_modified_if_needed(row, body)
    row.title = body.title
    row.description = body.description
    row.display_group = body.display_group
    row.positive_prompt = body.positive_prompt
    row.negative_prompt = body.negative_prompt
    row.custom_prompt_placeholder = body.custom_prompt_placeholder
    row.enabled = body.enabled
    db.commit()
    db.refresh(row)
    MODULES.invalidate()

    new_dict = {
        "title": body.title,
        "description": body.description,
        "display_group": body.display_group,
        "positive_prompt": body.positive_prompt,
        "negative_prompt": body.negative_prompt,
        "custom_prompt_placeholder": body.custom_prompt_placeholder,
        "enabled": body.enabled,
    }

    diff = build_effect_diff(old_dict, new_dict)
    if diff:
        record_audit_event(
            db=db,
            action="effect.updated",
            category="effect",
            outcome="success",
            actor_type=actor_ctx.actor_type,
            request_id=actor_ctx.request_id,
            source_ip_hash=actor_ctx.source_ip_hash,
            target_type="effect",
            target_id=effect_id,
            summary=f"AI effect '{row.title}' updated",
            changes=diff,
            metadata={"id": effect_id, "title": row.title},
        )

    return _row_to_response(row)


@router.post("/{effect_id}/reset", response_model=AIEffectResponse)
def reset_ai_effect(
    effect_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
    actor_ctx: ActorContext = Depends(get_actor_context),
):
    actor_ctx = resolve_actor_context(actor_ctx)
    row = _get_row_or_404(db, effect_id)
    if row.source != "builtin":
        raise HTTPException(status_code=409, detail="Only built-in AI effects can be reset")
    seed = load_seed_effect(effect_id)
    if seed is None:
        raise HTTPException(status_code=404, detail="Built-in effect seed not found")
    manifest_entry = get_seed_manifest_entry_map().get(effect_id)
    display_group = manifest_entry.display_group if manifest_entry else None
    hidden = manifest_entry.hidden if manifest_entry else False
    effect_hash = seed_effect_hash(seed, display_group=display_group, hidden=hidden).value
    row.title = seed.title
    row.description = seed.description
    row.display_group = display_group
    row.positive_prompt = seed.positive_prompt
    row.negative_prompt = seed.negative_prompt
    row.custom_prompt_placeholder = seed.custom_prompt_placeholder
    row.builtin_hash = effect_hash
    row.latest_builtin_hash = effect_hash
    row.user_modified_at = None
    db.commit()
    db.refresh(row)
    MODULES.invalidate()

    record_audit_event(
        db=db,
        action="effect.reset",
        category="effect",
        outcome="success",
        actor_type=actor_ctx.actor_type,
        request_id=actor_ctx.request_id,
        source_ip_hash=actor_ctx.source_ip_hash,
        target_type="effect",
        target_id=effect_id,
        summary=f"Built-in AI effect '{row.title}' reset to factory defaults",
        metadata={"id": effect_id, "title": row.title},
    )

    return _row_to_response(row)


@router.post("/{effect_id}/duplicate", response_model=AIEffectResponse, status_code=201)
def duplicate_ai_effect(
    effect_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
    actor_ctx: ActorContext = Depends(get_actor_context),
):
    actor_ctx = resolve_actor_context(actor_ctx)
    row = _get_row_or_404(db, effect_id)
    suffix = 1
    while db.get(AIEffectModel, f"{effect_id}_copy{suffix if suffix > 1 else ''}") is not None:
        suffix += 1
    new_id = f"{effect_id}_copy{suffix if suffix > 1 else ''}"
    copy_row = AIEffectModel(
        id=new_id,
        title=f"{row.title} Copy",
        description=row.description,
        display_group=row.display_group,
        positive_prompt=row.positive_prompt,
        negative_prompt=row.negative_prompt,
        custom_prompt_placeholder=row.custom_prompt_placeholder,
        source="custom",
        enabled=row.enabled,
        weight=1,
    )
    db.add(copy_row)
    db.commit()
    db.refresh(copy_row)
    MODULES.invalidate()

    record_audit_event(
        db=db,
        action="effect.duplicated",
        category="effect",
        outcome="success",
        actor_type=actor_ctx.actor_type,
        request_id=actor_ctx.request_id,
        source_ip_hash=actor_ctx.source_ip_hash,
        target_type="effect",
        target_id=effect_id,
        summary=f"AI effect '{row.title}' duplicated to '{copy_row.title}'",
        metadata={"source_id": effect_id, "new_id": new_id, "new_title": copy_row.title},
    )

    return _row_to_response(copy_row)


@router.delete("/{effect_id}", response_model=AIEffectResponse)
def delete_ai_effect(
    effect_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
    actor_ctx: ActorContext = Depends(get_actor_context),
):
    actor_ctx = resolve_actor_context(actor_ctx)
    row = _get_row_or_404(db, effect_id)
    if row.source == "builtin":
        row.enabled = False
        db.commit()
        db.refresh(row)
        MODULES.invalidate()

        record_audit_event(
            db=db,
            action="effect.updated",
            category="effect",
            outcome="success",
            actor_type=actor_ctx.actor_type,
            request_id=actor_ctx.request_id,
            source_ip_hash=actor_ctx.source_ip_hash,
            target_type="effect",
            target_id=effect_id,
            summary=f"Built-in AI effect '{row.title}' disabled",
            metadata={"id": effect_id, "title": row.title},
        )

        return _row_to_response(row)
    if _effect_in_use(db, effect_id):
        raise HTTPException(status_code=409, detail="AI effect is used by one or more effect presets")
    payload = _row_to_response(row)
    db.delete(row)
    db.commit()
    MODULES.invalidate()

    record_audit_event(
        db=db,
        action="effect.deleted",
        category="effect",
        outcome="success",
        actor_type=actor_ctx.actor_type,
        request_id=actor_ctx.request_id,
        source_ip_hash=actor_ctx.source_ip_hash,
        target_type="effect",
        target_id=effect_id,
        summary=f"Custom AI effect '{payload.title}' deleted",
        metadata={"id": effect_id, "title": payload.title},
    )

    return payload


@router.post("/import", response_model=AIEffectImportResult)
def import_ai_effects(
    body: AIEffectImportRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
    actor_ctx: ActorContext = Depends(get_actor_context),
):
    actor_ctx = resolve_actor_context(actor_ctx)
    result = AIEffectImportResult()

    for item in body.effects:
        row = db.get(AIEffectModel, item.id)
        if row is None:
            row = AIEffectModel(
                id=item.id,
                title=item.title,
                description=item.description,
                display_group=item.display_group,
                positive_prompt=item.positive_prompt,
                negative_prompt=item.negative_prompt,
                custom_prompt_placeholder=item.custom_prompt_placeholder,
                source=item.source or "imported",
                enabled=item.enabled,
                weight=1,
            )
            db.add(row)
            result.added.append(item.id)
            continue

        if not body.overwrite_existing:
            result.conflicts.append(item.id)
            continue

        row.title = item.title
        row.description = item.description
        row.display_group = item.display_group
        row.positive_prompt = item.positive_prompt
        row.negative_prompt = item.negative_prompt
        row.custom_prompt_placeholder = item.custom_prompt_placeholder
        row.enabled = item.enabled
        if item.source is not None:
            row.source = item.source
        if row.source != "builtin":
            row.builtin_hash = None
            row.latest_builtin_hash = None
            row.user_modified_at = None
        else:
            row.user_modified_at = datetime.now(timezone.utc)
        result.updated.append(item.id)

    db.commit()
    MODULES.invalidate()

    if len(result.added) > 0 or len(result.updated) > 0:
        record_audit_event(
            db=db,
            action="effect.imported",
            category="effect",
            outcome="success",
            actor_type=actor_ctx.actor_type,
            request_id=actor_ctx.request_id,
            source_ip_hash=actor_ctx.source_ip_hash,
            summary=f"Imported AI effects: added {len(result.added)}, updated {len(result.updated)}",
            metadata={
                "added_count": len(result.added),
                "updated_count": len(result.updated),
                "added_ids": result.added,
                "updated_ids": result.updated,
            },
        )

    return result


@router.get("/export", response_model=AIEffectExportRequest)
def export_ai_effects(db: Session = Depends(get_db), _: None = Depends(require_auth)):
    rows = db.query(AIEffectModel).all()
    rows.sort(
        key=lambda row: (
            0 if row.source == "builtin" else 1 if row.source == "custom" else 2,
            row.title.lower(),
            row.id,
        )
    )
    return AIEffectExportRequest(schema_version=1, effects=[_row_to_response(row) for row in rows])
