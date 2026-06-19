import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.effect_preset import EffectPresetModel
from app.models.filter_preset import FilterPresetModel
from app.models.notification_preset import NotificationPresetModel
from app.models.push import PushSubscriptionModel
from app.models.schedule import ScheduleModel
from app.schemas.presets import (
    EffectPresetCreate,
    EffectPresetResponse,
    FilterPresetCreate,
    FilterPresetResponse,
    NotificationPresetCreate,
    NotificationPresetResponse,
    NotificationPresetTestResponse,
)
from app.security import decrypt_secret, encrypt_secret, mask_secret, require_auth
from app.services.notifications import run_notification_preset_test

router = APIRouter(prefix="/api/presets", tags=["presets"])


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


# Filter Presets


@router.get("/filters", response_model=list[FilterPresetResponse])
def list_filter_presets(db: Session = Depends(get_db), _: None = Depends(require_auth)):
    rows = db.query(FilterPresetModel).order_by(FilterPresetModel.name).all()
    return [FilterPresetResponse.from_model(row) for row in rows]


@router.post("/filters", response_model=FilterPresetResponse, status_code=201)
def create_filter_preset(body: FilterPresetCreate, db: Session = Depends(get_db), _: None = Depends(require_auth)):
    if db.query(FilterPresetModel).filter_by(name=body.name).first():
        raise HTTPException(status_code=409, detail="Filter preset with this name already exists")
    row = FilterPresetModel(
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
    return FilterPresetResponse.from_model(row)


@router.put("/filters/{preset_id}", response_model=FilterPresetResponse)
def update_filter_preset(
    preset_id: int,
    body: FilterPresetCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    row = db.query(FilterPresetModel).filter_by(id=preset_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Filter preset not found")
    existing = (
        db.query(FilterPresetModel)
        .filter(FilterPresetModel.name == body.name, FilterPresetModel.id != preset_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Filter preset with this name already exists")
    row.name = body.name
    row.album_ids_json = json.dumps(body.album_ids)
    row.person_filters_json = json.dumps([p.model_dump() for p in body.person_filters])
    row.start_date = body.start_date
    row.end_date = body.end_date
    row.media_type = body.media_type
    db.commit()
    db.refresh(row)
    return FilterPresetResponse.from_model(row)


@router.delete("/filters/{preset_id}", status_code=204)
def delete_filter_preset(preset_id: int, db: Session = Depends(get_db), _: None = Depends(require_auth)):
    row = db.query(FilterPresetModel).filter_by(id=preset_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Filter preset not found")
    if _preset_in_use(db, preset_id, "filter_preset_id"):
        raise HTTPException(status_code=409, detail="Preset is used by one or more schedules")
    db.delete(row)
    db.commit()


# Effect Presets


@router.get("/effects", response_model=list[EffectPresetResponse])
def list_effect_presets(db: Session = Depends(get_db), _: None = Depends(require_auth)):
    rows = db.query(EffectPresetModel).order_by(EffectPresetModel.name).all()
    return [EffectPresetResponse.from_model(row) for row in rows]


@router.post("/effects", response_model=EffectPresetResponse, status_code=201)
def create_effect_preset(body: EffectPresetCreate, db: Session = Depends(get_db), _: None = Depends(require_auth)):
    from app.services.generation.config_validation import validate_effects_config

    validate_effects_config(body.groups)

    if db.query(EffectPresetModel).filter_by(name=body.name).first():
        raise HTTPException(status_code=409, detail="Effect preset with this name already exists")
    row = EffectPresetModel(name=body.name, groups_json=json.dumps(body.groups))
    db.add(row)
    db.commit()
    db.refresh(row)
    return EffectPresetResponse.from_model(row)


@router.put("/effects/{preset_id}", response_model=EffectPresetResponse)
def update_effect_preset(
    preset_id: int,
    body: EffectPresetCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
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
    row.name = body.name
    row.groups_json = json.dumps(body.groups)
    db.commit()
    db.refresh(row)
    return EffectPresetResponse.from_model(row)


@router.delete("/effects/{preset_id}", status_code=204)
def delete_effect_preset(preset_id: int, db: Session = Depends(get_db), _: None = Depends(require_auth)):
    row = db.query(EffectPresetModel).filter_by(id=preset_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Effect preset not found")
    if _preset_in_use(db, preset_id, "effect_preset_id"):
        raise HTTPException(status_code=409, detail="Preset is used by one or more schedules")
    db.delete(row)
    db.commit()


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
):
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
    return NotificationPresetResponse.from_model(row, token_masked=_masked_token(row))


@router.put("/notifications/{preset_id}", response_model=NotificationPresetResponse)
def update_notification_preset(
    preset_id: int,
    body: NotificationPresetCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
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
    return NotificationPresetResponse.from_model(row, token_masked=_masked_token(row))


@router.delete("/notifications/{preset_id}", status_code=204)
def delete_notification_preset(preset_id: int, db: Session = Depends(get_db), _: None = Depends(require_auth)):
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
    db.delete(row)
    db.commit()


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
