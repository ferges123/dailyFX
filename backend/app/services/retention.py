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


def _file_policy(row: GenerationHistoryModel, settings: SettingsModel, now: datetime) -> datetime | None:
    if row.status == "REJECTED":
        return _cutoff(getattr(settings, "retention_rejected_files_days", 7), now)
    if row.status == "FAILED":
        return _cutoff(getattr(settings, "retention_failed_files_days", 7), now)
    if row.status == "UPLOADED":
        return _cutoff(getattr(settings, "retention_uploaded_files_days", 30), now)
    return None


def _metadata_policy(row: GenerationHistoryModel, settings: SettingsModel, now: datetime) -> datetime | None:
    if row.status == "REJECTED":
        return _cutoff(getattr(settings, "retention_rejected_metadata_days", 90), now)
    if row.status == "FAILED":
        return _cutoff(getattr(settings, "retention_failed_metadata_days", 90), now)
    if row.status == "UPLOADED":
        return _cutoff(getattr(settings, "retention_uploaded_metadata_days", 30), now)
    return None


def plan_retention(
    db: Session, settings: SettingsModel, *, now: datetime | None = None, data_dir: Path | None = None
) -> RetentionPreview:
    now = now or datetime.now(timezone.utc)
    data_dir = (data_dir or get_app_settings().data_dir).resolve()
    files = metadata = tasks = total_bytes = missing = audits = 0
    warnings: list[str] = []
    rows = db.query(GenerationHistoryModel).all()
    known_paths: set[Path] = set()
    for row in rows:
        path = _safe_path(row.output_path, data_dir)
        if path:
            known_paths.add(path)
            if not path.exists():
                missing += 1
            cutoff = _file_policy(row, settings, now)
            if cutoff and row.created_at and row.created_at < cutoff and path.exists():
                files += 1
                total_bytes += path.stat().st_size
                thumb = path.with_suffix(path.suffix + ".thumb_400.jpg")
                if thumb.exists():
                    total_bytes += thumb.stat().st_size
        metadata_cutoff = _metadata_policy(row, settings, now)
        if metadata_cutoff and row.created_at and row.created_at < metadata_cutoff:
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
    if results_dir.exists():
        for path in results_dir.iterdir():
            if (
                path.is_file()
                and path not in known_paths
                and path.stat().st_mtime < (now - timedelta(days=7)).timestamp()
            ):
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
    preview = plan_retention(db, settings, now=now, data_dir=data_dir)
    if dry_run or not getattr(settings, "retention_enabled", True):
        return preview
    now = now or datetime.now(timezone.utc)
    data_dir = (data_dir or get_app_settings().data_dir).resolve()
    rows = db.query(GenerationHistoryModel).all()
    metadata_cutoffs: list[GenerationHistoryModel] = []
    for row in rows:
        path = _safe_path(row.output_path, data_dir)
        if path and not path.exists() and getattr(row, "local_file_status", "available") == "available":
            row.local_file_status = "missing"
        cutoff = _file_policy(row, settings, now)
        if path and cutoff and row.created_at and row.created_at < cutoff:
            try:
                path.unlink(missing_ok=True)
                thumb = path.with_suffix(path.suffix + ".thumb_400.jpg")
                thumb.unlink(missing_ok=True)
                row.local_file_status = "deleted_by_retention"
                row.local_file_deleted_at = now
                row.local_file_delete_reason = "retention"
                row.output_path = None
            except OSError:
                logger.exception("Retention failed to delete %s", path)
        metadata_cutoff = _metadata_policy(row, settings, now)
        if metadata_cutoff and row.created_at and row.created_at < metadata_cutoff:
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

    # Perform audit logs retention (Task 7)
    audit_cutoff = _cutoff(getattr(settings, "retention_audit_days", 90), now)
    if audit_cutoff:
        from app.models.audit_event import AuditEventModel

        db.query(AuditEventModel).filter(AuditEventModel.created_at < audit_cutoff).delete(synchronize_session=False)

    db.commit()

    # Record audit event for retention completion (Task 5)
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
            summary=f"Retention executed: deleted {preview.files} files, {preview.metadata} metadata rows, {preview.tasks} tasks, {preview.audits} audit logs",
            metadata={
                "deleted_files": preview.files,
                "deleted_metadata_rows": preview.metadata,
                "deleted_tasks": preview.tasks,
                "deleted_audit_logs": preview.audits,
                "released_bytes": preview.bytes,
            },
        )
    except Exception:
        logger.exception("Failed to record retention.completed audit event")

    return preview
