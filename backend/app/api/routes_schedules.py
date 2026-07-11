from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.limiter import limiter
from app.models.effect_preset import EffectPresetModel
from app.models.filter_preset import FilterPresetModel
from app.models.notification_preset import NotificationPresetModel
from app.models.schedule import ScheduleModel
from app.schemas.schedules import (
    ScheduleCreate,
    ScheduleDiagnosticsResponse,
    ScheduleResponse,
    ScheduleRunNowResponse,
    ScheduleUpdate,
)
from app.security import ActorContext, get_actor_context, require_auth, resolve_actor_context
from app.services.audit import record_audit_event
from app.services.generation.task_flow import trigger_schedule_run_now
from app.workers.scheduler import _compute_next_run

router = APIRouter(prefix="/api/schedules", tags=["schedules"])


def build_schedule_diff(old_dict: dict, new_dict: dict) -> dict:
    diff = {}
    for k in old_dict.keys() | new_dict.keys():
        old_val = old_dict.get(k)
        new_val = new_dict.get(k)
        if old_val != new_val:
            diff[k] = {"from": old_val, "to": new_val}
    return diff


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
def create_schedule(
    body: ScheduleCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
    actor_ctx: ActorContext = Depends(get_actor_context),
):
    actor_ctx = resolve_actor_context(actor_ctx)
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

    record_audit_event(
        db=db,
        action="schedule.created",
        category="schedule",
        outcome="success",
        actor_type=actor_ctx.actor_type,
        request_id=actor_ctx.request_id,
        source_ip_hash=actor_ctx.source_ip_hash,
        target_type="schedule",
        target_id=row.id,
        summary=f"Schedule '{row.name}' created",
        metadata={"name": row.name},
    )

    return _to_response(row, db)


@router.put("/{schedule_id}", response_model=ScheduleResponse)
def update_schedule(
    schedule_id: int,
    body: ScheduleUpdate,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
    actor_ctx: ActorContext = Depends(get_actor_context),
):
    actor_ctx = resolve_actor_context(actor_ctx)
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

    old_dict = {
        "name": row.name,
        "enabled": row.enabled,
        "schedule_expr": row.schedule_expr,
        "filter_preset_id": row.filter_preset_id,
        "effect_preset_id": row.effect_preset_id,
        "album_name": row.album_name,
        "ai_vision_provider": row.ai_vision_provider,
        "ai_vision_model": row.ai_vision_model,
        "ai_image_provider": row.ai_image_provider,
        "ai_image_model": row.ai_image_model,
        "ai_prompt_enrichment": row.ai_prompt_enrichment,
        "ai_photo_selection_enabled": row.ai_photo_selection_enabled,
        "notification_preset_ids": [np.id for np in row.notification_presets],
    }

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

    new_dict = {
        "name": body.name,
        "enabled": body.enabled,
        "schedule_expr": body.schedule_expr,
        "filter_preset_id": body.filter_preset_id,
        "effect_preset_id": body.effect_preset_id,
        "album_name": body.album_name,
        "ai_vision_provider": body.ai_vision_provider,
        "ai_vision_model": body.ai_vision_model,
        "ai_image_provider": body.ai_image_provider,
        "ai_image_model": body.ai_image_model,
        "ai_prompt_enrichment": body.ai_prompt_enrichment,
        "ai_photo_selection_enabled": body.ai_photo_selection_enabled,
        "notification_preset_ids": body.notification_preset_ids,
    }

    diff = build_schedule_diff(old_dict, new_dict)
    if diff:
        record_audit_event(
            db=db,
            action="schedule.updated",
            category="schedule",
            outcome="success",
            actor_type=actor_ctx.actor_type,
            request_id=actor_ctx.request_id,
            source_ip_hash=actor_ctx.source_ip_hash,
            target_type="schedule",
            target_id=schedule_id,
            summary=f"Schedule '{row.name}' updated",
            changes=diff,
            metadata={"name": row.name},
        )

    return _to_response(row, db)


@router.delete("/{schedule_id}", status_code=204)
def delete_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
    actor_ctx: ActorContext = Depends(get_actor_context),
):
    actor_ctx = resolve_actor_context(actor_ctx)
    row = db.get(ScheduleModel, schedule_id)
    if not row:
        raise HTTPException(status_code=404, detail="Schedule not found")

    schedule_name = row.name
    # Clean up many-to-many relationship
    row.notification_presets = []
    db.delete(row)
    db.commit()

    record_audit_event(
        db=db,
        action="schedule.deleted",
        category="schedule",
        outcome="success",
        actor_type=actor_ctx.actor_type,
        request_id=actor_ctx.request_id,
        source_ip_hash=actor_ctx.source_ip_hash,
        target_type="schedule",
        target_id=schedule_id,
        summary=f"Schedule '{schedule_name}' deleted",
        metadata={"name": schedule_name},
    )


# ── Run Now ───────────────────────────────────────────────────────────────────


@router.post("/{schedule_id}/run-now", response_model=ScheduleRunNowResponse)
@limiter.limit("10/minute")
async def trigger_schedule_now(
    schedule_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
    request: Request = None,
    actor_ctx: ActorContext = Depends(get_actor_context),
):
    actor_ctx = resolve_actor_context(actor_ctx)
    row = db.get(ScheduleModel, schedule_id)
    if not row:
        raise HTTPException(status_code=404, detail="Schedule not found")

    res = await trigger_schedule_run_now(db, schedule_id)

    record_audit_event(
        db=db,
        action="schedule.run_now",
        category="schedule",
        outcome="success",
        actor_type=actor_ctx.actor_type,
        request_id=actor_ctx.request_id,
        source_ip_hash=actor_ctx.source_ip_hash,
        target_type="schedule",
        target_id=schedule_id,
        summary=f"Schedule '{row.name}' triggered manually",
        metadata={"name": row.name},
    )

    return res


@router.get("/{schedule_id}/diagnostics", response_model=ScheduleDiagnosticsResponse)
async def get_schedule_diagnostics(
    schedule_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    from datetime import datetime, timezone

    from app.models.effect_preset import EffectPresetModel
    from app.models.filter_preset import FilterPresetModel
    from app.schemas.schedules import DiagnosticAssetDetail, ScheduleDiagnosticsResponse
    from app.services.generation.asset_usage import get_assets_usage_status
    from app.services.generation.schedule_runs import build_scheduled_run_context
    from app.services.immich import build_immich_client, get_or_create_settings

    schedule = db.get(ScheduleModel, schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    fp = db.get(FilterPresetModel, schedule.filter_preset_id)
    ep = db.get(EffectPresetModel, schedule.effect_preset_id)
    if not fp or not ep:
        raise HTTPException(status_code=400, detail="Schedule has missing presets")

    run_context = build_scheduled_run_context(
        schedule_id=schedule_id,
        album_name=schedule.album_name,
        filter_preset=fp,
        effect_preset=ep,
    )

    settings = get_or_create_settings(db)
    client = build_immich_client(settings)

    try:
        # Fetch matching assets using paginated metadata search (size=1000)
        page = await client.get_assets(page=1, size=1000, filters=run_context.filters)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to query Immich assets: {exc}")

    collected_items = page.items
    collected_ids = [item.id for item in collected_items]

    usage_statuses = get_assets_usage_status(db, collected_ids)

    never_used_candidates = []
    released_candidates = []
    accepted_candidates = []
    pending_candidates = []

    for item in collected_items:
        status = usage_statuses.get(item.id, {})
        if status.get("has_pending"):
            pending_candidates.append(item)
        elif status.get("ever_accepted"):
            accepted_candidates.append(item)
        elif status.get("returned_to_pool"):
            released_candidates.append(item)
        else:
            never_used_candidates.append(item)

    # Sort never_used: newest first
    never_used_sorted = sorted(never_used_candidates, key=lambda x: x.created_at or "", reverse=True)

    # Sort released: most recently released first
    def released_sort_key(x):
        st = usage_statuses.get(x.id, {})
        dt = st.get("last_released_at")
        if dt and dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt or datetime.min.replace(tzinfo=timezone.utc)

    released_sorted = sorted(released_candidates, key=released_sort_key, reverse=True)

    # Sort accepted: oldest accepted first
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)

    def accepted_sort_key(x):
        st = usage_statuses.get(x.id, {})
        dt = st.get("last_accepted_at") or epoch
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (dt, x.id)

    accepted_sorted = sorted(accepted_candidates, key=accepted_sort_key)

    priority_list = never_used_sorted + released_sorted + accepted_sorted

    # Construct details for first 10
    selection_order_details = []
    for x in priority_list[:10]:
        st = usage_statuses.get(x.id, {})
        # Map last action time
        last_action_at = None
        if x in accepted_sorted:
            last_action_at = st.get("last_accepted_at")
            status_val = "accepted"
        elif x in released_sorted:
            last_action_at = st.get("last_released_at")
            status_val = "released"
        else:
            status_val = "never_used"

        selection_order_details.append(
            DiagnosticAssetDetail(
                id=x.id,
                original_file_name=x.original_file_name,
                created_at=x.created_at,
                status=status_val,
                last_action_at=last_action_at,
            )
        )

    return ScheduleDiagnosticsResponse(
        total_candidates=page.total,
        never_used_count=len(never_used_candidates),
        released_count=len(released_candidates),
        accepted_count=len(accepted_candidates),
        pending_count=len(pending_candidates),
        selection_order=selection_order_details,
    )
