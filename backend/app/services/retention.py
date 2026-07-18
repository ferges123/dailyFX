from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import get_settings as get_app_settings
from app.models.generation_history import GenerationHistoryModel
from app.models.settings import SettingsModel

logger = logging.getLogger(__name__)

_RETAINABLE_STATUSES = ("REJECTED", "FAILED", "UPLOADED")


@dataclass(frozen=True)
class RetentionPreview:
    files: int = 0
    metadata: int = 0
    tasks: int = 0
    bytes: int = 0
    missing_files: int = 0
    orphan_files: int = 0
    audits: int = 0
    warnings: tuple[str, ...] = ()


def _cutoff(days: int | None, now: datetime) -> datetime | None:
    return None if days is None else now - timedelta(days=max(1, days))


def _min_retention_days(settings: SettingsModel) -> int:
    return min(
        getattr(settings, "retention_rejected_files_days", 7) or 7,
        getattr(settings, "retention_failed_files_days", 7) or 7,
        getattr(settings, "retention_uploaded_files_days", 30) or 30,
        getattr(settings, "retention_rejected_metadata_days", 90) or 90,
        getattr(settings, "retention_failed_metadata_days", 90) or 90,
        getattr(settings, "retention_uploaded_metadata_days", 30) or 30,
    )


def _safe_path(value: str | None, data_dir: Path) -> Path | None:
    if not value:
        return None
    path = Path(value).resolve()
    try:
        path.relative_to(data_dir.resolve())
    except ValueError:
        logger.warning("Retention skipped path outside data_dir: %s", path)
        return None
    return path


def _known_output_paths(db: Session, data_dir: Path) -> set[Path]:
    known: set[Path] = set()
    output_paths = (
        db.query(GenerationHistoryModel.output_path)
        .filter(GenerationHistoryModel.output_path.isnot(None))
        .all()
    )
    for (value,) in output_paths:
        path = _safe_path(value, data_dir)
        if path:
            known.add(path)
            known.add(path.with_suffix(path.suffix + ".thumb_400.jpg"))
    return known


def _find_orphan_paths(db: Session, data_dir: Path, now: datetime) -> list[Path]:
    results_dir = data_dir / "results"
    if not results_dir.exists():
        return []
    known_paths = _known_output_paths(db, data_dir)
    cutoff = (now - timedelta(days=7)).timestamp()
    return [
        path
        for path in results_dir.iterdir()
        if path.is_file() and path not in known_paths and path.stat().st_mtime < cutoff
    ]


def _file_cutoff(row_status: str, settings: SettingsModel, now: datetime) -> datetime | None:
    if row_status == "REJECTED":
        return _cutoff(getattr(settings, "retention_rejected_files_days", 7), now)
    if row_status == "FAILED":
        return _cutoff(getattr(settings, "retention_failed_files_days", 7), now)
    if row_status == "UPLOADED":
        return _cutoff(getattr(settings, "retention_uploaded_files_days", 30), now)
    return None


def _metadata_cutoff(row_status: str, settings: SettingsModel, now: datetime) -> datetime | None:
    if row_status == "REJECTED":
        return _cutoff(getattr(settings, "retention_rejected_metadata_days", 90), now)
    if row_status == "FAILED":
        return _cutoff(getattr(settings, "retention_failed_metadata_days", 90), now)
    if row_status == "UPLOADED":
        return _cutoff(getattr(settings, "retention_uploaded_metadata_days", 30), now)
    return None


def _query_retention_candidates(db: Session, settings: SettingsModel, now: datetime):
    """Query only rows eligible for any retention policy, using SQL WHERE filters."""
    min_days = _min_retention_days(settings)
    earliest_cutoff = now - timedelta(days=min_days)

    return (
        db.query(GenerationHistoryModel)
        .filter(
            GenerationHistoryModel.status.in_(_RETAINABLE_STATUSES),
            GenerationHistoryModel.created_at < earliest_cutoff,
        )
        .all()
    )


def plan_retention(
    db: Session, settings: SettingsModel, *, now: datetime | None = None, data_dir: Path | None = None
) -> RetentionPreview:
    now = now or datetime.now(timezone.utc)
    data_dir = (data_dir or get_app_settings().data_dir).resolve()
    files = metadata = tasks = total_bytes = missing = audits = 0
    warnings: list[str] = []
    known_paths = _known_output_paths(db, data_dir)

    rows = _query_retention_candidates(db, settings, now)
    for row in rows:
        path = _safe_path(row.output_path, data_dir)
        if path:
            known_paths.add(path)
            if not path.exists():
                missing += 1
            cutoff = _file_cutoff(row.status, settings, now)
            if cutoff and row.created_at and row.created_at < cutoff and path.exists():
                files += 1
                total_bytes += path.stat().st_size
                thumb = path.with_suffix(path.suffix + ".thumb_400.jpg")
                if thumb.exists():
                    total_bytes += thumb.stat().st_size
        meta_cutoff = _metadata_cutoff(row.status, settings, now)
        if meta_cutoff and row.created_at and row.created_at < meta_cutoff:
            metadata += 1

    task_cutoff = _cutoff(getattr(settings, "retention_task_days", 30), now)
    if task_cutoff:
        from app.models.generation_task import GenerationTaskModel

        tasks = (
            db.query(GenerationTaskModel)
            .filter(
                GenerationTaskModel.status.in_(("succeeded", "failed", "cancelled")),
                GenerationTaskModel.updated_at < task_cutoff,
            )
            .count()
        )

    audit_cutoff = _cutoff(getattr(settings, "retention_audit_days", 90), now)
    if audit_cutoff:
        from app.models.audit_event import AuditEventModel

        audits = db.query(AuditEventModel).filter(AuditEventModel.created_at < audit_cutoff).count()

    results_dir = data_dir / "results"
    for path in _find_orphan_paths(db, data_dir, now):
        warnings.append(f"orphan:{path.name}")
    return RetentionPreview(files, metadata, tasks, total_bytes, missing, len(warnings), audits, tuple(warnings))


def execute_retention(
    db: Session,
    settings: SettingsModel,
    *,
    now: datetime | None = None,
    dry_run: bool = False,
    data_dir: Path | None = None,
    actor_ctx: object | None = None,
) -> RetentionPreview:
    now = now or datetime.now(timezone.utc)
    data_dir = (data_dir or get_app_settings().data_dir).resolve()

    rows = _query_retention_candidates(db, settings, now)

    if dry_run or not getattr(settings, "retention_enabled", True):
        return plan_retention(db, settings, now=now, data_dir=data_dir)

    files = total_bytes = missing = 0
    metadata_cutoffs: list[GenerationHistoryModel] = []
    queued_file_jobs = 0
    orphan_paths = _find_orphan_paths(db, data_dir, now)
    for row in rows:
        path = _safe_path(row.output_path, data_dir)
        if path:
            if not path.exists() and getattr(row, "local_file_status", "available") == "available":
                row.local_file_status = "missing"
                missing += 1
            cutoff = _file_cutoff(row.status, settings, now)
            if cutoff and row.created_at and row.created_at < cutoff:
                from app.services.file_deletion import queue_file_deletion

                thumb = path.with_suffix(path.suffix + ".thumb_400.jpg")
                if path.exists():
                    total_bytes += path.stat().st_size
                    if thumb.exists():
                        total_bytes += thumb.stat().st_size
                    files += 1
                queue_file_deletion(
                    db,
                    path=path,
                    thumbnail_path=thumb,
                    task_id=row.task_id,
                    reason="retention",
                )
                queued_file_jobs += 1
                row.local_file_status = "deleted_by_retention"
                row.local_file_deleted_at = now
                row.local_file_delete_reason = "retention"
                row.output_path = None
        meta_cutoff = _metadata_cutoff(row.status, settings, now)
        if meta_cutoff and row.created_at and row.created_at < meta_cutoff:
            metadata_cutoffs.append(row)

    if metadata_cutoffs:
        from app.models.generation_stream_event import GenerationStreamEventModel
        from app.models.generation_task import GenerationTaskModel

        task_ids = [row.task_id for row in metadata_cutoffs]
        db.query(GenerationStreamEventModel).filter(GenerationStreamEventModel.task_id.in_(task_ids)).delete(
            synchronize_session=False
        )
        db.query(GenerationTaskModel).filter(GenerationTaskModel.task_id.in_(task_ids)).delete(
            synchronize_session=False
        )
        for row in metadata_cutoffs:
            db.delete(row)

    task_cutoff = _cutoff(getattr(settings, "retention_task_days", 30), now)
    if task_cutoff:
        from app.models.generation_task import GenerationTaskModel

        db.query(GenerationTaskModel).filter(
            GenerationTaskModel.status.in_(("succeeded", "failed", "cancelled")),
            GenerationTaskModel.updated_at < task_cutoff,
        ).delete(synchronize_session=False)

    audit_cutoff = _cutoff(getattr(settings, "retention_audit_days", 90), now)
    if audit_cutoff:
        from app.models.audit_event import AuditEventModel

        db.query(AuditEventModel).filter(AuditEventModel.created_at < audit_cutoff).delete(synchronize_session=False)

    from app.services.file_deletion import queue_file_deletion

    for path in orphan_paths:
        queue_file_deletion(db, path=path, reason="orphan_cleanup")
        queued_file_jobs += 1
        if path.exists():
            total_bytes += path.stat().st_size
        files += 1

    db.commit()

    from app.services.file_deletion import process_file_deletion_jobs

    deleted_jobs, failed_jobs = process_file_deletion_jobs(db, data_dir=data_dir, now=now)
    if failed_jobs:
        logger.warning(
            "Retention queued %d file deletion jobs; %d failed and will retry",
            queued_file_jobs,
            failed_jobs,
        )

    # Count orphans for preview
    orphan_count = len(orphan_paths)

    try:
        from app.services.audit import record_audit_event

        actor_type = getattr(actor_ctx, "actor_type", "scheduler")
        request_id = getattr(actor_ctx, "request_id", None)
        source_ip_hash = getattr(actor_ctx, "source_ip_hash", None)

        record_audit_event(
            db=db,
            action="retention.completed",
            category="retention",
            outcome="success",
            actor_type=actor_type,
            request_id=request_id,
            source_ip_hash=source_ip_hash,
            summary=(
                f"Retention executed: deleted {deleted_jobs} files, "
                f"{len(metadata_cutoffs)} metadata rows, tasks and audit logs"
            ),
            metadata={
                "deleted_files": deleted_jobs,
                "deleted_metadata_rows": len(metadata_cutoffs),
                "released_bytes": total_bytes,
            },
        )
    except Exception:
        logger.exception("Failed to record retention.completed audit event")

    return RetentionPreview(
        files=files,
        metadata=len(metadata_cutoffs),
        tasks=0,
        bytes=total_bytes,
        missing_files=missing,
        orphan_files=orphan_count,
        audits=0,
    )
