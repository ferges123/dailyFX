from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.file_deletion_job import FileDeletionJobModel

logger = logging.getLogger(__name__)

_MAX_ATTEMPTS = 10


def queue_file_deletion(
    db: Session,
    *,
    path: Path,
    thumbnail_path: Path | None = None,
    task_id: str | None = None,
    reason: str,
) -> FileDeletionJobModel:
    """Add an idempotent deletion request to the current DB transaction."""
    normalized_path = str(path.resolve())
    existing = (
        db.query(FileDeletionJobModel)
        .filter(
            FileDeletionJobModel.path == normalized_path,
            FileDeletionJobModel.status.in_(('pending', 'processing', 'failed')),
        )
        .order_by(FileDeletionJobModel.id.desc())
        .first()
    )
    if existing is not None:
        if existing.status == "failed":
            existing.status = "pending"
            existing.next_attempt_at = datetime.now(timezone.utc)
            existing.last_error = None
        return existing

    job = FileDeletionJobModel(
        task_id=task_id,
        path=normalized_path,
        thumbnail_path=str(thumbnail_path.resolve()) if thumbnail_path else None,
        reason=reason,
    )
    db.add(job)
    return job


def _unlink(path_value: str | None) -> None:
    if not path_value:
        return
    Path(path_value).unlink(missing_ok=True)


def process_file_deletion_jobs(
    db: Session,
    *,
    data_dir: Path,
    now: datetime | None = None,
    batch_size: int = 100,
) -> tuple[int, int]:
    """Process committed deletion jobs; failed jobs remain durable for retry."""
    now = now or datetime.now(timezone.utc)
    data_dir = data_dir.resolve()
    jobs = (
        db.query(FileDeletionJobModel)
        .filter(
            (
                (FileDeletionJobModel.status == "pending")
                | (
                    (FileDeletionJobModel.status == "failed")
                    & (FileDeletionJobModel.attempts < _MAX_ATTEMPTS)
                )
            ),
            FileDeletionJobModel.next_attempt_at <= now,
        )
        .order_by(FileDeletionJobModel.id.asc())
        .limit(batch_size)
        .all()
    )
    deleted = failed = 0
    for job in jobs:
        try:
            for value in (job.path, job.thumbnail_path):
                if value is None:
                    continue
                path = Path(value).resolve()
                if not path.is_relative_to(data_dir):
                    raise ValueError("file deletion path is outside DATA_DIR")
            job.status = "processing"
            job.attempts += 1
            db.flush()
            _unlink(job.path)
            _unlink(job.thumbnail_path)
            job.status = "completed"
            job.last_error = None
            deleted += 1
        except Exception as exc:
            job.status = "failed"
            job.last_error = str(exc)[:2000]
            delay = min(3600, 2 ** min(job.attempts, 10))
            job.next_attempt_at = now + timedelta(seconds=delay)
            failed += 1
            logger.exception("File deletion job %s failed", job.id)
    if jobs:
        db.commit()
    return deleted, failed
