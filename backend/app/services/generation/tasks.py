from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.generation_task import GenerationTaskModel
from app.services.generation.stream import record_task_snapshot

FINAL_TASK_STATUSES = {"succeeded", "failed", "cancelled"}


def get_task(db: Session, task_id: str) -> GenerationTaskModel | None:
    return db.get(GenerationTaskModel, task_id)


def ensure_task(
    db: Session,
    task_id: str,
    *,
    status: str = "queued",
    step: str | None = "queued",
    progress: float | None = 0.0,
    error: str | None = None,
    payload_json: str | None = None,
) -> GenerationTaskModel:
    row = db.get(GenerationTaskModel, task_id)
    if row is None:
        row = GenerationTaskModel(
            task_id=task_id,
            status=status,
            step=step,
            progress=progress,
            error=error,
            payload_json=payload_json,
        )
        db.add(row)
    else:
        row.status = status
        row.step = step
        row.progress = progress
        row.error = error
        if payload_json is not None:
            row.payload_json = payload_json
    db.commit()
    db.refresh(row)
    record_task_snapshot(db, row)
    return row


def update_task(
    db: Session,
    task_id: str,
    *,
    status: str | None = None,
    step: str | None = None,
    progress: float | None = None,
    error: str | None = None,
    payload_json: str | None = None,
) -> GenerationTaskModel:
    row = db.get(GenerationTaskModel, task_id)
    if row is None:
        row = GenerationTaskModel(task_id=task_id, status=status or "queued", payload_json=payload_json)
        db.add(row)
    if status is not None:
        row.status = status
    if step is not None:
        row.step = step
    if progress is not None:
        row.progress = progress
    if error is not None or status == "failed":
        row.error = error
    if payload_json is not None:
        row.payload_json = payload_json
    db.commit()
    db.refresh(row)
    record_task_snapshot(db, row)
    return row
