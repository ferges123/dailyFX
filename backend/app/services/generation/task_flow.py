from __future__ import annotations

import uuid
from typing import Awaitable, Callable

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.effect_preset import EffectPresetModel
from app.models.filter_preset import FilterPresetModel
from app.models.generation_task import GenerationTaskModel
from app.models.notification_preset import NotificationPresetModel
from app.models.schedule import ScheduleModel
from app.schemas.schedules import ScheduleRunNowResponse
from app.services.generation.engine import run_generation_cycle
from app.services.generation.history import upsert_history_entry
from app.services.generation.run_now import (
    parse_run_now_task_payload,
    preview_run_now_assets,
    record_run_now_failure_history,
)
from app.services.generation.schedule_runs import build_scheduled_run_context
from app.services.generation.tasks import ensure_task, update_task
from app.services.immich import build_immich_client, get_or_create_settings


async def trigger_schedule_run_now(db: Session, schedule_id: int) -> ScheduleRunNowResponse:
    row = db.get(ScheduleModel, schedule_id)
    if not row:
        raise HTTPException(status_code=404, detail="Schedule not found")

    fp = db.get(FilterPresetModel, row.filter_preset_id)
    ep = db.get(EffectPresetModel, row.effect_preset_id)
    if not fp or not ep:
        raise HTTPException(status_code=400, detail="Schedule has missing presets")

    settings = get_or_create_settings(db)
    run_context = build_scheduled_run_context(
        schedule_id=schedule_id,
        album_name=row.album_name,
        filter_preset=fp,
        effect_preset=ep,
        notification_presets=list(row.notification_presets),
    )

    client = build_immich_client(settings)
    task_id = f"man-{uuid.uuid4().hex[:8]}"
    ensure_task(db, task_id, status="queued", step="queued", progress=0.0)

    try:
        # Preview happens before enqueueing so invalid filters fail fast.
        await preview_run_now_assets(
            client=client,
            filters=run_context.filters,
            task_id=task_id,
            db=db,
            no_assets_message="No assets matched the filter preset",
        )
    except HTTPException as exc:
        record_run_now_failure_history(
            db,
            task_id,
            generation_type="schedule_run",
            title="Failed: schedule run",
            summary=str(exc.detail) if isinstance(exc.detail, str) else "Failed to preview assets",
        )
        raise

    payload_json = run_context.to_run_now_task_payload().to_json()
    update_task(db, task_id, status="queued", step="queued", progress=0.0, payload_json=payload_json)
    upsert_history_entry(
        db,
        task_id,
        generation_type="schedule_run",
        status="QUEUED",
        title=f"Queued: {row.name}",
        summary="Waiting for the worker to start this scheduled run.",
        source_asset_ids="[]",
        config_json=payload_json,
        task_step="queued",
        schedule_id=schedule_id,
        album_name=row.album_name,
    )
    return ScheduleRunNowResponse(message="Generation triggered", task_id=task_id)


async def run_queued_generation_task(
    db: Session,
    settings,
    queued_task: GenerationTaskModel,
    *,
    run_generation_cycle_fn: Callable[..., Awaitable[object]] = run_generation_cycle,
) -> dict[str, object]:
    if not queued_task.payload_json:
        queued_task.status = "failed"
        queued_task.step = "failed"
        queued_task.progress = 0.0
        queued_task.error = "No payload"
        db.add(queued_task)
        db.commit()
        return {"status": "failed", "manual_run": queued_task.task_id, "error": "No payload"}

    try:
        payload = parse_run_now_task_payload(queued_task.payload_json)
        notification_presets = None
        if payload.notification_preset_ids:
            notification_presets = (
                db.query(NotificationPresetModel)
                .filter(NotificationPresetModel.id.in_(payload.notification_preset_ids))
                .all()
            )

        queued_task.status = "running"
        queued_task.step = "running"
        queued_task.progress = 0.0
        db.add(queued_task)
        db.commit()

        await run_generation_cycle_fn(
            db,
            settings,
            queued_task.task_id,
            force=True,
            **payload.to_run_generation_kwargs(notification_presets=notification_presets),
        )
        return {"status": "completed", "manual_run": queued_task.task_id}
    except Exception as exc:  # noqa: BLE001
        queued_task.status = "failed"
        queued_task.step = "failed"
        queued_task.progress = 0.0
        queued_task.error = str(exc)
        db.add(queued_task)
        db.commit()
        upsert_history_entry(
            db,
            queued_task.task_id,
            status="FAILED",
            summary=f"Queue execution failed: {exc}",
            task_step="failed",
        )
        return {"status": "failed", "manual_run": queued_task.task_id, "error": str(exc)}
