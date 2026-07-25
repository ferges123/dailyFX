from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.generation_history import GenerationHistoryModel
from app.models.generation_stream_event import GenerationStreamEventModel
from app.models.generation_task import GenerationTaskModel

logger = logging.getLogger(__name__)


def _serialize_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def serialize_history_row(row: GenerationHistoryModel) -> dict[str, Any]:
    liked_val = row.stats_log.liked if getattr(row, "stats_log", None) else None
    return {
        "id": row.id,
        "task_id": row.task_id,
        "generation_type": row.generation_type,
        "status": row.status,
        "title": row.title,
        "summary": row.summary,
        "local_file_status": getattr(row, "local_file_status", "available"),
        "image_url": row.image_url,
        "provider": row.provider,
        "model": row.model,
        "task_step": row.task_step,
        "output_format": row.output_format,
        "frame_count": row.frame_count,
        "album_name": row.album_name,
        "liked": liked_val,
        "created_at": _serialize_datetime(row.created_at),
        "updated_at": _serialize_datetime(row.updated_at),
    }


def serialize_task_row(row: GenerationTaskModel) -> dict[str, Any]:
    return {
        "task_id": row.task_id,
        "status": row.status,
        "step": row.step,
        "progress": row.progress,
        "error": row.error,
        "created_at": _serialize_datetime(row.created_at),
        "updated_at": _serialize_datetime(row.updated_at),
    }


def append_stream_event(db: Session, event_type: str, payload: dict[str, Any], task_id: str | None = None) -> None:
    try:
        db.add(
            GenerationStreamEventModel(
                event_type=event_type,
                task_id=task_id,
                payload_json=json.dumps(payload, separators=(",", ":"), ensure_ascii=False),
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to append generation stream event %s", event_type)


def record_history_snapshot(db: Session, row: GenerationHistoryModel) -> None:
    append_stream_event(db, "history-upsert", serialize_history_row(row), task_id=row.task_id)


def record_task_snapshot(db: Session, row: GenerationTaskModel) -> None:
    append_stream_event(db, "task-upsert", serialize_task_row(row), task_id=row.task_id)


STREAM_EVENT_MAX_ROWS = 5_000
STREAM_REPLAY_BATCH_SIZE = 500


def get_latest_event_id(db: Session) -> int:
    return db.query(func.max(GenerationStreamEventModel.id)).scalar() or 0


def load_events_after(
    db: Session, after_id: int, limit: int = STREAM_REPLAY_BATCH_SIZE
) -> list[GenerationStreamEventModel]:
    return (
        db.query(GenerationStreamEventModel)
        .filter(GenerationStreamEventModel.id > after_id)
        .order_by(GenerationStreamEventModel.id.asc())
        .limit(limit)
        .all()
    )


def prune_generation_stream_events(
    db: Session,
    *,
    max_rows: int = STREAM_EVENT_MAX_ROWS,
) -> int:
    if max_rows < 1:
        raise ValueError("max_rows must be at least 1")

    cutoff_id = (
        db.query(GenerationStreamEventModel.id)
        .order_by(GenerationStreamEventModel.id.desc())
        .offset(max_rows)
        .limit(1)
        .scalar()
    )
    if cutoff_id is None:
        return 0

    deleted_count = (
        db.query(GenerationStreamEventModel)
        .filter(GenerationStreamEventModel.id <= cutoff_id)
        .delete(synchronize_session=False)
    )
    return deleted_count


def replay_gap_requires_resync(db: Session, after_id: int) -> bool:
    if after_id <= 0:
        return False
    oldest_event_id = db.query(func.min(GenerationStreamEventModel.id)).scalar()
    if oldest_event_id is None:
        return False
    return after_id < oldest_event_id - 1
