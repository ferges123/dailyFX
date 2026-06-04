from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.models.generation_history import GenerationHistoryModel
from app.services.generation.stream import record_history_snapshot

_PLACEHOLDER_VALUES: dict[str, Any] = {
    "generation_type": "manual",
    "status": "RUNNING",
    "title": "Generation running",
    "summary": "Generation is in progress",
    "source_asset_ids": "[]",
    "config_json": "{}",
}


def history_status_for_task_status(status: str | None) -> str | None:
    if status in {"queued", "running"}:
        return "RUNNING"
    if status == "failed":
        return "FAILED"
    return None


def upsert_history_entry(db: Session, task_id: str, **fields: Any) -> GenerationHistoryModel:
    row = db.query(GenerationHistoryModel).filter(GenerationHistoryModel.task_id == task_id).first()
    normalized_fields = {key: value for key, value in fields.items() if value is not None}

    if row is None:
        payload = {**_PLACEHOLDER_VALUES, **normalized_fields}
        row = GenerationHistoryModel(task_id=task_id, **payload)
        db.add(row)
    else:
        for key, value in normalized_fields.items():
            setattr(row, key, value)

    db.commit()
    db.refresh(row)
    record_history_snapshot(db, row)
    return row


def append_history_trace(
    db: Session,
    task_id: str,
    *,
    stage: str,
    message: str,
    step: str | None = None,
    status: str | None = None,
    progress: float | None = None,
    details: dict[str, Any] | None = None,
    max_entries: int = 24,
) -> GenerationHistoryModel:
    row = db.query(GenerationHistoryModel).filter(GenerationHistoryModel.task_id == task_id).first()
    config: dict[str, Any] = {}
    if row and row.config_json:
        try:
            parsed = json.loads(row.config_json)
            if isinstance(parsed, dict):
                config = parsed
        except Exception:
            config = {}

    trace = config.get("task_trace")
    if not isinstance(trace, list):
        trace = []
    trace.append(
        {
            "stage": stage,
            "message": message,
            "step": step,
            "status": status,
            "progress": progress,
            "details": details or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )
    config["task_trace"] = trace[-max_entries:]
    if details:
        config["task_trace_last"] = details

    return upsert_history_entry(
        db,
        task_id,
        config_json=json.dumps(config),
        task_step=step if step is not None else (row.task_step if row else None),
    )


def get_or_create_thumbnail(original_path: Path, max_size: int = 400) -> Path:
    from PIL import Image

    thumb_path = original_path.with_suffix(original_path.suffix + f".thumb_{max_size}.jpg")
    if thumb_path.exists():
        try:
            if thumb_path.stat().st_mtime >= original_path.stat().st_mtime:
                return thumb_path
        except Exception:
            pass
    try:
        with Image.open(original_path) as img:
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.thumbnail((max_size, max_size))
            thumb_path.parent.mkdir(parents=True, exist_ok=True)
            img.save(thumb_path, "JPEG", quality=85)
        return thumb_path
    except Exception as e:
        logging.getLogger("dailyfx").error(f"Failed to generate thumbnail for {original_path}: {e}")
        return original_path
