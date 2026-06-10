from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.effect_preset import EffectPresetModel
from app.models.filter_preset import FilterPresetModel
from app.models.notification_preset import NotificationPresetModel
from app.models.schedule import ScheduleModel
from app.schemas.schedules import ScheduleCreate, ScheduleResponse, ScheduleRunNowResponse, ScheduleUpdate
from app.security import require_auth
from app.services.generation.task_flow import trigger_schedule_run_now
from app.workers.scheduler import _compute_next_run

router = APIRouter(prefix="/api/schedules", tags=["schedules"])


def _to_response(row: ScheduleModel, db: Session) -> ScheduleResponse:
    fp = db.get(FilterPresetModel, row.filter_preset_id)
    ep = db.get(EffectPresetModel, row.effect_preset_id)
    return ScheduleResponse.from_model(
        row,
        filter_preset_name=fp.name if fp else None,
        effect_preset_name=ep.name if ep else None,
    )


def _validate_presets(body: ScheduleCreate, db: Session) -> None:
    if not db.get(FilterPresetModel, body.filter_preset_id):
        raise HTTPException(status_code=404, detail="Filter preset not found")
    if not db.get(EffectPresetModel, body.effect_preset_id):
        raise HTTPException(status_code=404, detail="Effect preset not found")
    if body.ai_photo_selection_enabled and body.ai_vision_provider == "none":
        raise HTTPException(status_code=422, detail="AI photo selection requires an AI Vision provider")


# ── CRUD ──────────────────────────────────────────────────────────────────────


@router.get("", response_model=list[ScheduleResponse])
def list_schedules(db: Session = Depends(get_db), _: None = Depends(require_auth)):
    rows = db.query(ScheduleModel).order_by(ScheduleModel.name).all()
    return [_to_response(r, db) for r in rows]


@router.post("", response_model=ScheduleResponse, status_code=201)
def create_schedule(body: ScheduleCreate, db: Session = Depends(get_db), _: None = Depends(require_auth)):
    _validate_presets(body, db)

    # Resolve and validate notification presets
    notifs = []
    if body.notification_preset_ids:
        notifs = (
            db.query(NotificationPresetModel).filter(NotificationPresetModel.id.in_(body.notification_preset_ids)).all()
        )
        if len(notifs) != len(body.notification_preset_ids):
            raise HTTPException(status_code=404, detail="One or more notification presets not found")

    row = ScheduleModel(
        name=body.name,
        enabled=body.enabled,
        schedule_expr=body.schedule_expr,
        filter_preset_id=body.filter_preset_id,
        effect_preset_id=body.effect_preset_id,
        notification_presets=notifs,
        album_name=body.album_name,
        ai_vision_provider=body.ai_vision_provider,
        ai_vision_model=body.ai_vision_model,
        ai_image_provider=body.ai_image_provider,
        ai_image_model=body.ai_image_model,
        ai_prompt_enrichment=body.ai_prompt_enrichment,
        ai_photo_selection_enabled=body.ai_photo_selection_enabled,
    )
    if body.enabled:
        row.next_run_at = _compute_next_run(body.schedule_expr, None)
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_response(row, db)


@router.put("/{schedule_id}", response_model=ScheduleResponse)
def update_schedule(
    schedule_id: int,
    body: ScheduleUpdate,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    row = db.get(ScheduleModel, schedule_id)
    if not row:
        raise HTTPException(status_code=404, detail="Schedule not found")
    _validate_presets(body, db)

    # Resolve and validate notification presets
    notifs = []
    if body.notification_preset_ids:
        notifs = (
            db.query(NotificationPresetModel).filter(NotificationPresetModel.id.in_(body.notification_preset_ids)).all()
        )
        if len(notifs) != len(body.notification_preset_ids):
            raise HTTPException(status_code=404, detail="One or more notification presets not found")

    row.name = body.name
    row.enabled = body.enabled
    row.schedule_expr = body.schedule_expr
    row.filter_preset_id = body.filter_preset_id
    row.effect_preset_id = body.effect_preset_id
    row.notification_presets = notifs
    row.album_name = body.album_name
    row.ai_vision_provider = body.ai_vision_provider
    row.ai_vision_model = body.ai_vision_model
    row.ai_image_provider = body.ai_image_provider
    row.ai_image_model = body.ai_image_model
    row.ai_prompt_enrichment = body.ai_prompt_enrichment
    row.ai_photo_selection_enabled = body.ai_photo_selection_enabled
    row.next_run_at = _compute_next_run(body.schedule_expr, row.last_run_at) if body.enabled else None
    db.commit()
    db.refresh(row)
    return _to_response(row, db)


@router.delete("/{schedule_id}", status_code=204)
def delete_schedule(schedule_id: int, db: Session = Depends(get_db), _: None = Depends(require_auth)):
    row = db.get(ScheduleModel, schedule_id)
    if not row:
        raise HTTPException(status_code=404, detail="Schedule not found")
    # Clean up many-to-many relationship
    row.notification_presets = []
    db.delete(row)
    db.commit()


# ── Run Now ───────────────────────────────────────────────────────────────────


@router.post("/{schedule_id}/run-now", response_model=ScheduleRunNowResponse)
async def trigger_schedule_now(
    schedule_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    return await trigger_schedule_run_now(db, schedule_id)
