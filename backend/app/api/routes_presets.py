import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.effect_preset import EffectPresetModel
from app.models.notification_preset import NotificationPresetModel
from app.models.people_preset import PeoplePresetModel
from app.models.push import PushSubscriptionModel
from app.models.schedule import ScheduleModel
from app.schemas.presets import (
    EffectPresetCreate,
    EffectPresetResponse,
    NotificationPresetCreate,
    NotificationPresetResponse,
    NotificationPresetTestResponse,
    PeoplePresetCreate,
    PeoplePresetResponse,
)
from app.security import (
    ActorContext,
    decrypt_secret,
    encrypt_secret,
    get_actor_context,
    mask_secret,
    require_auth,
    resolve_actor_context,
)
from app.services.audit import record_audit_event
from app.services.notifications import run_notification_preset_test

router = APIRouter(prefix="/api/presets", tags=["presets"])


def build_preset_diff(old_dict: dict, new_dict: dict) -> dict:
    diff = {}
    for k in old_dict.keys() | new_dict.keys():
        old_val = old_dict.get(k)
        new_val = new_dict.get(k)
        if old_val != new_val:
            if "token" in k.lower() or "secret" in k.lower() or "encrypted" in k.lower() or "password" in k.lower():
                diff[k] = {"changed": True}
            else:
                diff[k] = {"from": old_val, "to": new_val}
    return diff


def _load_push_subscriptions_or_400(db: Session, ids: list[int]) -> list[PushSubscriptionModel]:
    if not ids:
        return []
    rows = db.query(PushSubscriptionModel).filter(PushSubscriptionModel.id.in_(ids)).all()
    found_ids = {row.id for row in rows}
    missing_ids = [item for item in ids if item not in found_ids]
    if missing_ids:
        raise HTTPException(status_code=400, detail=f"Unknown push subscription id(s): {missing_ids}")
    rows_by_id = {row.id: row for row in rows}
    return [rows_by_id[item] for item in ids]


def _preset_in_use(db: Session, preset_id: int, fk_field: str) -> bool:
    return db.query(ScheduleModel).filter(getattr(ScheduleModel, fk_field) == preset_id).first() is not None


# People Presets


@router.get("/people", response_model=list[PeoplePresetResponse])
def list_people_presets(db: Session = Depends(get_db), _: None = Depends(require_auth)):
    rows = db.query(PeoplePresetModel).order_by(PeoplePresetModel.name).all()
    return [PeoplePresetResponse.from_model(row) for row in rows]


@router.post("/people", response_model=PeoplePresetResponse, status_code=201)
def create_people_preset(
    body: PeoplePresetCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
    actor_ctx: ActorContext = Depends(get_actor_context),
):
    actor_ctx = resolve_actor_context(actor_ctx)
    if db.query(PeoplePresetModel).filter_by(name=body.name).first():
        raise HTTPException(status_code=409, detail="People preset with this name already exists")
    row = PeoplePresetModel(
        name=body.name,
        album_ids_json=json.dumps(body.album_ids),
        person_filters_json=json.dumps([p.model_dump() for p in body.person_filters]),
        start_date=body.start_date,
        end_date=body.end_date,
        media_type=body.media_type,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    record_audit_event(
        db=db,
        action="preset.created",
        category="preset",
        outcome="success",
        actor_type=actor_ctx.actor_type,
        request_id=actor_ctx.request_id,
        source_ip_hash=actor_ctx.source_ip_hash,
        target_type="preset",
        target_id=row.id,
        summary=f"People preset '{row.name}' created",
        metadata={"type": "people", "name": row.name},
    )

    return PeoplePresetResponse.from_model(row)


@router.put("/people/{preset_id}", response_model=PeoplePresetResponse)
def update_people_preset(
    preset_id: int,
    body: PeoplePresetCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
    actor_ctx: ActorContext = Depends(get_actor_context),
):
    actor_ctx = resolve_actor_context(actor_ctx)
    row = db.query(PeoplePresetModel).filter_by(id=preset_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="People preset not found")
    existing = (
        db.query(PeoplePresetModel)
        .filter(PeoplePresetModel.name == body.name, PeoplePresetModel.id != preset_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="People preset with this name already exists")

    old_dict = {
        "name": row.name,
        "album_ids": json.loads(row.album_ids_json) if row.album_ids_json else [],
        "person_filters": json.loads(row.person_filters_json) if row.person_filters_json else [],
        "start_date": row.start_date.isoformat() if row.start_date else None,
        "end_date": row.end_date.isoformat() if row.end_date else None,
        "media_type": row.media_type,
    }

    row.name = body.name
    row.album_ids_json = json.dumps(body.album_ids)
    row.person_filters_json = json.dumps([p.model_dump() for p in body.person_filters])
    row.start_date = body.start_date
    row.end_date = body.end_date
    row.media_type = body.media_type
    db.commit()
    db.refresh(row)

    new_dict = {
        "name": body.name,
        "album_ids": body.album_ids,
        "person_filters": [p.model_dump() for p in body.person_filters],
        "start_date": body.start_date.isoformat() if body.start_date else None,
        "end_date": body.end_date.isoformat() if body.end_date else None,
        "media_type": body.media_type,
    }

    diff = build_preset_diff(old_dict, new_dict)
    if diff:
        record_audit_event(
            db=db,
            action="preset.updated",
            category="preset",
            outcome="success",
            actor_type=actor_ctx.actor_type,
            request_id=actor_ctx.request_id,
            source_ip_hash=actor_ctx.source_ip_hash,
            target_type="preset",
            target_id=preset_id,
            summary=f"People preset '{row.name}' updated",
            changes=diff,
            metadata={"type": "people", "name": row.name},
        )

    return PeoplePresetResponse.from_model(row)


@router.delete("/people/{preset_id}", status_code=204)
def delete_people_preset(
    preset_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
    actor_ctx: ActorContext = Depends(get_actor_context),
):
    actor_ctx = resolve_actor_context(actor_ctx)
    row = db.query(PeoplePresetModel).filter_by(id=preset_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="People preset not found")
    if _preset_in_use(db, preset_id, "people_preset_id"):
        raise HTTPException(status_code=409, detail="Preset is used by one or more schedules")

    preset_name = row.name
    db.delete(row)
    db.commit()

    record_audit_event(
        db=db,
        action="preset.deleted",
        category="preset",
        outcome="success",
        actor_type=actor_ctx.actor_type,
        request_id=actor_ctx.request_id,
        source_ip_hash=actor_ctx.source_ip_hash,
        target_type="preset",
        target_id=preset_id,
        summary=f"People preset '{preset_name}' deleted",
        metadata={"type": "people", "name": preset_name},
    )


# Effect Presets


@router.get("/effects", response_model=list[EffectPresetResponse])
def list_effect_presets(db: Session = Depends(get_db), _: None = Depends(require_auth)):
    rows = db.query(EffectPresetModel).order_by(EffectPresetModel.name).all()
    return [EffectPresetResponse.from_model(row) for row in rows]


@router.post("/effects", response_model=EffectPresetResponse, status_code=201)
def create_effect_preset(
    body: EffectPresetCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
    actor_ctx: ActorContext = Depends(get_actor_context),
):
    actor_ctx = resolve_actor_context(actor_ctx)
    from app.services.generation.config_validation import validate_effects_config

    validate_effects_config(body.groups)

    if db.query(EffectPresetModel).filter_by(name=body.name).first():
        raise HTTPException(status_code=409, detail="Effect preset with this name already exists")
    row = EffectPresetModel(name=body.name, groups_json=json.dumps(body.groups))
    db.add(row)
    db.commit()
    db.refresh(row)

    record_audit_event(
        db=db,
        action="preset.created",
        category="preset",
        outcome="success",
        actor_type=actor_ctx.actor_type,
        request_id=actor_ctx.request_id,
        source_ip_hash=actor_ctx.source_ip_hash,
        target_type="preset",
        target_id=row.id,
        summary=f"Effect preset '{row.name}' created",
        metadata={"type": "effect", "name": row.name},
    )

    return EffectPresetResponse.from_model(row)


@router.put("/effects/{preset_id}", response_model=EffectPresetResponse)
def update_effect_preset(
    preset_id: int,
    body: EffectPresetCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
    actor_ctx: ActorContext = Depends(get_actor_context),
):
    actor_ctx = resolve_actor_context(actor_ctx)
    from app.services.generation.config_validation import validate_effects_config

    validate_effects_config(body.groups)

    row = db.query(EffectPresetModel).filter_by(id=preset_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Effect preset not found")
    existing = (
        db.query(EffectPresetModel)
        .filter(EffectPresetModel.name == body.name, EffectPresetModel.id != preset_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Effect preset with this name already exists")

    old_dict = {
        "name": row.name,
        "groups": json.loads(row.groups_json) if row.groups_json else {},
    }

    row.name = body.name
    row.groups_json = json.dumps(body.groups)
    db.commit()
    db.refresh(row)

    new_dict = {
        "name": body.name,
        "groups": body.groups,
    }

    diff = build_preset_diff(old_dict, new_dict)
    if diff:
        record_audit_event(
            db=db,
            action="preset.updated",
            category="preset",
            outcome="success",
            actor_type=actor_ctx.actor_type,
            request_id=actor_ctx.request_id,
            source_ip_hash=actor_ctx.source_ip_hash,
            target_type="preset",
            target_id=preset_id,
            summary=f"Effect preset '{row.name}' updated",
            changes=diff,
            metadata={"type": "effect", "name": row.name},
        )

    return EffectPresetResponse.from_model(row)


@router.delete("/effects/{preset_id}", status_code=204)
def delete_effect_preset(
    preset_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
    actor_ctx: ActorContext = Depends(get_actor_context),
):
    actor_ctx = resolve_actor_context(actor_ctx)
    row = db.query(EffectPresetModel).filter_by(id=preset_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Effect preset not found")
    if _preset_in_use(db, preset_id, "effect_preset_id"):
        raise HTTPException(status_code=409, detail="Preset is used by one or more schedules")

    preset_name = row.name
    db.delete(row)
    db.commit()

    record_audit_event(
        db=db,
        action="preset.deleted",
        category="preset",
        outcome="success",
        actor_type=actor_ctx.actor_type,
        request_id=actor_ctx.request_id,
        source_ip_hash=actor_ctx.source_ip_hash,
        target_type="preset",
        target_id=preset_id,
        summary=f"Effect preset '{preset_name}' deleted",
        metadata={"type": "effect", "name": preset_name},
    )


# Notification Presets


@router.get("/notifications", response_model=list[NotificationPresetResponse])
def list_notification_presets(db: Session = Depends(get_db), _: None = Depends(require_auth)):
    rows = db.query(NotificationPresetModel).order_by(NotificationPresetModel.name).all()
    return [NotificationPresetResponse.from_model(row, token_masked=_masked_token(row)) for row in rows]


@router.post("/notifications", response_model=NotificationPresetResponse, status_code=201)
def create_notification_preset(
    body: NotificationPresetCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
    actor_ctx: ActorContext = Depends(get_actor_context),
):
    actor_ctx = resolve_actor_context(actor_ctx)
    if db.query(NotificationPresetModel).filter_by(name=body.name).first():
        raise HTTPException(status_code=409, detail="Notification preset with this name already exists")
    row = NotificationPresetModel(
        name=body.name,
        provider=body.provider,
        url=body.url,
        topic=body.topic,
        encrypted_token=encrypt_secret(body.token) if body.token else None,
        webhook_url=body.webhook_url,
    )
    row.push_subscriptions = _load_push_subscriptions_or_400(db, body.push_subscription_ids)
    db.add(row)
    db.commit()
    db.refresh(row)

    record_audit_event(
        db=db,
        action="preset.created",
        category="preset",
        outcome="success",
        actor_type=actor_ctx.actor_type,
        request_id=actor_ctx.request_id,
        source_ip_hash=actor_ctx.source_ip_hash,
        target_type="preset",
        target_id=row.id,
        summary=f"Notification preset '{row.name}' created",
        metadata={"type": "notification", "name": row.name},
    )

    return NotificationPresetResponse.from_model(row, token_masked=_masked_token(row))


@router.put("/notifications/{preset_id}", response_model=NotificationPresetResponse)
def update_notification_preset(
    preset_id: int,
    body: NotificationPresetCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
    actor_ctx: ActorContext = Depends(get_actor_context),
):
    actor_ctx = resolve_actor_context(actor_ctx)
    row = db.query(NotificationPresetModel).filter_by(id=preset_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Notification preset not found")
    existing = (
        db.query(NotificationPresetModel)
        .filter(NotificationPresetModel.name == body.name, NotificationPresetModel.id != preset_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Notification preset with this name already exists")

    old_dict = {
        "name": row.name,
        "provider": row.provider,
        "url": row.url,
        "topic": row.topic,
        "webhook_url": row.webhook_url,
        "token": decrypt_secret(row.encrypted_token) if row.encrypted_token else None,
        "push_subscription_ids": [ps.id for ps in row.push_subscriptions],
    }

    row.name = body.name
    row.provider = body.provider
    row.url = body.url
    row.topic = body.topic
    if body.token is not None:
        existing_decrypted = decrypt_secret(row.encrypted_token) if row.encrypted_token else None
        existing_masked = mask_secret(existing_decrypted) if existing_decrypted else None
        if body.token != existing_masked:
            row.encrypted_token = encrypt_secret(body.token)
    row.webhook_url = body.webhook_url
    row.push_subscriptions = _load_push_subscriptions_or_400(db, body.push_subscription_ids)
    db.commit()
    db.refresh(row)

    new_dict = {
        "name": body.name,
        "provider": body.provider,
        "url": body.url,
        "topic": body.topic,
        "webhook_url": body.webhook_url,
        "token": old_dict["token"]
        if body.token == (mask_secret(old_dict["token"]) if old_dict["token"] else None)
        else body.token,
        "push_subscription_ids": body.push_subscription_ids,
    }

    diff = build_preset_diff(old_dict, new_dict)
    if diff:
        record_audit_event(
            db=db,
            action="preset.updated",
            category="preset",
            outcome="success",
            actor_type=actor_ctx.actor_type,
            request_id=actor_ctx.request_id,
            source_ip_hash=actor_ctx.source_ip_hash,
            target_type="preset",
            target_id=preset_id,
            summary=f"Notification preset '{row.name}' updated",
            changes=diff,
            metadata={"type": "notification", "name": row.name},
        )

    return NotificationPresetResponse.from_model(row, token_masked=_masked_token(row))


@router.delete("/notifications/{preset_id}", status_code=204)
def delete_notification_preset(
    preset_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
    actor_ctx: ActorContext = Depends(get_actor_context),
):
    actor_ctx = resolve_actor_context(actor_ctx)
    row = db.query(NotificationPresetModel).filter_by(id=preset_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Notification preset not found")

    from app.models.schedule import schedule_notification_preset_association

    in_use = (
        db.query(schedule_notification_preset_association).filter_by(notification_preset_id=preset_id).first()
        is not None
    )
    if in_use:
        raise HTTPException(status_code=409, detail="Preset is used by one or more schedules")

    preset_name = row.name
    db.delete(row)
    db.commit()

    record_audit_event(
        db=db,
        action="preset.deleted",
        category="preset",
        outcome="success",
        actor_type=actor_ctx.actor_type,
        request_id=actor_ctx.request_id,
        source_ip_hash=actor_ctx.source_ip_hash,
        target_type="preset",
        target_id=preset_id,
        summary=f"Notification preset '{preset_name}' deleted",
        metadata={"type": "notification", "name": preset_name},
    )


@router.post("/notifications/{preset_id}/test", response_model=NotificationPresetTestResponse)
async def test_notification_preset(
    preset_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    row = db.query(NotificationPresetModel).filter_by(id=preset_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Notification preset not found")
    results, errors = await run_notification_preset_test(row)
    if not results and errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    return NotificationPresetTestResponse(ok=True, sent=results, errors=errors)


def _masked_token(row: NotificationPresetModel) -> str | None:
    token_decrypted = decrypt_secret(row.encrypted_token) if row.encrypted_token else None
    return mask_secret(token_decrypted) if token_decrypted else None
