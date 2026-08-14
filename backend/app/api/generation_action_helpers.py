import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal
from app.models.generation_history import GenerationHistoryModel
from app.models.settings import SettingsModel
from app.schemas.generation import GenerationAcceptRequest
from app.security import ActorContext, resolve_actor_context
from app.services.audit import record_audit_event
from app.services.generation.stream import record_history_snapshot

logger = logging.getLogger(__name__)


@dataclass
class _RowProxy:
    task_id: str
    title: str | None = None
    summary: str | None = None
    tags_json: str | None = None
    config_json: str | None = None
    source_asset_ids: str | None = None
    generation_type: str | None = None
    provider: str | None = None
    model: str | None = None
    created_at: datetime | None = None
    upload_status: str | None = None
    accepted_at: datetime | None = None


_AI_VISION_HISTORY_STATUSES = {"PENDING_REVIEW", "REJECTED", "UPLOADED"}


def _load_history_config(config_json: str | None) -> dict:
    if not config_json:
        return {}
    try:
        loaded = json.loads(config_json)
    except (TypeError, ValueError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _merge_history_ai_tags(vision_tags: list[str], tag_injections: object) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    injected_tags = tag_injections if isinstance(tag_injections, list) else []
    for tag in [*vision_tags, *injected_tags]:
        if not isinstance(tag, str):
            continue
        normalized = tag.strip()
        key = normalized.casefold()
        if normalized and key not in seen:
            seen.add(key)
            merged.append(normalized)
    return merged


def _prepare_history_ai_vision_data(task_id: str) -> tuple[bytes, SettingsModel]:
    session = SessionLocal()
    try:
        row = session.query(GenerationHistoryModel).filter(GenerationHistoryModel.task_id == task_id).first()
        if not row:
            raise HTTPException(status_code=404, detail="Generation history entry not found")
        if row.status not in _AI_VISION_HISTORY_STATUSES:
            raise HTTPException(status_code=409, detail="AI Vision is available only for completed generations")
        if getattr(row, "local_file_status", "available") == "deleted_by_retention":
            raise HTTPException(status_code=410, detail="Local image was deleted by retention")
        if not row.output_path:
            raise HTTPException(status_code=404, detail="Output path not available in history")

        image_path = Path(row.output_path).resolve()
        data_dir = get_settings().data_dir.resolve()
        if not image_path.is_relative_to(data_dir):
            raise HTTPException(status_code=400, detail="Invalid path")
        if not image_path.exists():
            raise HTTPException(status_code=404, detail="Generated image not found on disk")

        settings = session.query(SettingsModel).first()
        if not settings:
            raise HTTPException(status_code=500, detail="Settings not found")
        from app.services.generation.pipeline.planning import _resolve_schedule_ai_settings

        _resolve_schedule_ai_settings(session, settings, row.schedule_id)
        if (getattr(settings, "default_ai_provider", "none") or "none").strip().lower() == "none":
            raise HTTPException(status_code=422, detail="AI Vision provider is not configured")

        return image_path.read_bytes(), settings
    finally:
        session.close()


def _save_history_ai_vision_result(task_id: str, analysis, actor_ctx: ActorContext) -> GenerationHistoryModel:
    session = SessionLocal()
    session.expire_on_commit = False
    try:
        row = session.query(GenerationHistoryModel).filter(GenerationHistoryModel.task_id == task_id).first()
        if not row:
            raise HTTPException(status_code=404, detail="Generation history entry not found")
        if row.status not in _AI_VISION_HISTORY_STATUSES:
            raise HTTPException(status_code=409, detail="Generation is no longer eligible for AI Vision")

        config = _load_history_config(row.config_json)
        provenance = config.get("metadata_provenance")
        if not isinstance(provenance, dict):
            provenance = {}
            config["metadata_provenance"] = provenance
        final_vision = provenance.get("final_vision")
        if not isinstance(final_vision, dict):
            final_vision = {}
            provenance["final_vision"] = final_vision

        row.title = analysis.title or row.title
        row.summary = analysis.summary
        row.tags_json = json.dumps(
            _merge_history_ai_tags(analysis.tags, provenance.get("tag_injections")),
            ensure_ascii=False,
        )
        if analysis.token_count is not None:
            row.total_token_count = (row.total_token_count or 0) + analysis.token_count

        run_at = datetime.now(timezone.utc).isoformat()
        final_vision.update(
            attempted=True,
            succeeded=True,
            provider=analysis.provider,
            model=analysis.model,
            error=None,
            last_run_at=run_at,
        )
        provenance["title_source"] = "history_final_vision"
        provenance["summary_source"] = "history_final_vision"
        provenance["tags_source"] = "history_final_vision"
        provenance["history_final_vision"] = {
            "last_run_at": run_at,
            "provider": analysis.provider,
            "model": analysis.model,
        }
        row.config_json = json.dumps(config, ensure_ascii=False)
        session.commit()
        session.refresh(row)
        record_history_snapshot(session, row)
        record_audit_event(
            db=session,
            action="generation.history_ai_vision",
            category="generation",
            outcome="success",
            actor_type=actor_ctx.actor_type,
            request_id=actor_ctx.request_id,
            source_ip_hash=actor_ctx.source_ip_hash,
            target_type="generation",
            target_id=task_id,
            task_id=task_id,
            summary="AI Vision metadata added to generation history",
            metadata={"provider": analysis.provider, "model": analysis.model, "tags_count": len(analysis.tags)},
        )
        return row
    finally:
        session.close()


def _record_history_ai_vision_failure(
    db: Session,
    task_id: str,
    actor_ctx: ActorContext,
    exc: Exception,
) -> None:
    record_audit_event(
        db=db,
        action="generation.history_ai_vision",
        category="generation",
        outcome="failure",
        actor_type=actor_ctx.actor_type,
        request_id=actor_ctx.request_id,
        source_ip_hash=actor_ctx.source_ip_hash,
        target_type="generation",
        target_id=task_id,
        task_id=task_id,
        summary=f"AI Vision metadata update failed: {str(exc)}",
        error_code=exc.__class__.__name__,
        metadata={"error": str(exc)},
    )


def _prepare_accept_data(
    task_id: str, request: GenerationAcceptRequest
) -> tuple[Path, str | None, SettingsModel, _RowProxy]:
    session = SessionLocal()
    try:
        row = session.query(GenerationHistoryModel).filter(GenerationHistoryModel.task_id == task_id).first()
        if not row:
            raise HTTPException(status_code=404, detail="Generation history entry not found")

        if not row.output_path:
            raise HTTPException(status_code=404, detail="Output path not available in history")

        image_path = Path(row.output_path).resolve()
        data_dir = get_settings().data_dir.resolve()
        if not image_path.is_relative_to(data_dir):
            raise HTTPException(status_code=400, detail="Invalid path")
        if not image_path.exists():
            raise HTTPException(status_code=404, detail="Generated image not found on disk")

        settings = session.query(SettingsModel).first()
        if not settings:
            raise HTTPException(status_code=500, detail="Settings not found")

        album_name = request.album_name or row.album_name or None
        proxy = _RowProxy(
            task_id=row.task_id,
            title=row.title,
            summary=row.summary,
            tags_json=row.tags_json,
            config_json=row.config_json,
            source_asset_ids=row.source_asset_ids,
            generation_type=row.generation_type,
            provider=row.provider,
            model=row.model,
            created_at=row.created_at,
        )
        return image_path, album_name, settings, proxy
    finally:
        session.close()


def _finalize_accept_success(
    task_id: str,
    upload_result_id: str,
    upload_result_status: str,
    album_id: str | None,
    album_name: str | None,
    album_created: bool,
    album_updated: bool,
    accept_notes: list[str],
    actor_ctx: ActorContext,
) -> GenerationHistoryModel:
    session = SessionLocal()
    session.expire_on_commit = False
    try:
        row = session.query(GenerationHistoryModel).filter(GenerationHistoryModel.task_id == task_id).first()
        if not row:
            raise HTTPException(status_code=404, detail="Generation history entry not found")

        row.uploaded_asset_id = upload_result_id
        row.upload_status = upload_result_status
        row.status = "UPLOADED"
        row.album_id = album_id
        row.album_name = album_name
        row.album_created = album_created
        row.album_updated = album_updated
        row.accept_notes = "\n".join(accept_notes) if accept_notes else None
        row.accepted_at = datetime.now(timezone.utc)

        session.commit()

        try:
            from app.services.generation.asset_usage import accept_task_assets

            accept_task_assets(session, task_id)
        except Exception as registry_exc:
            logger.exception("Failed to accept assets in registry for task %s: %s", task_id, registry_exc)

        record_history_snapshot(session, row)

        record_audit_event(
            db=session,
            action="generation.accepted",
            category="generation",
            outcome="success",
            actor_type=actor_ctx.actor_type,
            request_id=actor_ctx.request_id,
            source_ip_hash=actor_ctx.source_ip_hash,
            target_type="generation",
            target_id=task_id,
            task_id=task_id,
            summary=f"Generation accepted and uploaded to Immich (Asset ID: {upload_result_id})",
            metadata={
                "uploaded_asset_id": upload_result_id,
                "album_name": album_name,
                "album_id": album_id,
            },
        )
        return row
    finally:
        session.close()


def _finalize_accept_failure(task_id: str, exc: Exception, actor_ctx: ActorContext) -> None:
    session = SessionLocal()
    session.expire_on_commit = False
    try:
        row = session.query(GenerationHistoryModel).filter(GenerationHistoryModel.task_id == task_id).first()
        if row:
            row.status = "FAILED"
            row.accept_notes = "Upload failed"
            session.commit()
            record_history_snapshot(session, row)

            record_audit_event(
                db=session,
                action="generation.accepted",
                category="generation",
                outcome="failure",
                actor_type=actor_ctx.actor_type,
                request_id=actor_ctx.request_id,
                source_ip_hash=actor_ctx.source_ip_hash,
                target_type="generation",
                target_id=task_id,
                task_id=task_id,
                summary=f"Failed to accept generation: {str(exc)}",
                error_code=exc.__class__.__name__,
                metadata={"error": str(exc)},
            )
    finally:
        session.close()


def _prepare_retry_data(
    task_id: str,
) -> tuple[str | None, Path | None, str | None, str | None, SettingsModel, _RowProxy]:
    session = SessionLocal()
    try:
        row = session.query(GenerationHistoryModel).filter(GenerationHistoryModel.task_id == task_id).first()
        if not row:
            raise HTTPException(status_code=404, detail="Generation history entry not found")

        settings = session.query(SettingsModel).first()
        if not settings:
            raise HTTPException(status_code=500, detail="Settings not found")

        uploaded_asset_id = row.uploaded_asset_id
        image_path = None
        if not uploaded_asset_id:
            if not row.output_path:
                raise HTTPException(status_code=400, detail="No output image file path in history")
            image_path = Path(row.output_path).resolve()
            data_dir = get_settings().data_dir.resolve()
            if not image_path.is_relative_to(data_dir):
                raise HTTPException(status_code=400, detail="Invalid path")
            if not image_path.exists():
                raise HTTPException(status_code=400, detail="Generated image file not found on disk")

        album_name = (row.album_name or "").strip() or None
        row_album_id = row.album_id
        proxy = _RowProxy(
            task_id=row.task_id,
            title=row.title,
            summary=row.summary,
            tags_json=row.tags_json,
            config_json=row.config_json,
            source_asset_ids=row.source_asset_ids,
            generation_type=row.generation_type,
            provider=row.provider,
            model=row.model,
            created_at=row.created_at,
            upload_status=row.upload_status,
            accepted_at=row.accepted_at,
        )
        return uploaded_asset_id, image_path, album_name, row_album_id, settings, proxy
    finally:
        session.close()


def _finalize_retry_success(
    task_id: str,
    new_uploaded_asset_id: str,
    upload_status: str,
    accepted_at: datetime | None,
    album_id: str | None,
    album_name: str | None,
    album_created: bool,
    album_updated: bool,
    accept_notes: list[str],
    actor_ctx: ActorContext,
) -> GenerationHistoryModel:
    session = SessionLocal()
    session.expire_on_commit = False
    try:
        row = session.query(GenerationHistoryModel).filter(GenerationHistoryModel.task_id == task_id).first()
        if not row:
            raise HTTPException(status_code=404, detail="Generation history entry not found")

        row.uploaded_asset_id = new_uploaded_asset_id
        row.upload_status = upload_status
        if accepted_at:
            row.accepted_at = accepted_at
        row.album_id = album_id
        row.album_name = album_name
        row.album_created = album_created
        row.album_updated = album_updated
        row.accept_notes = "\n".join(accept_notes) if accept_notes else None
        row.status = "UPLOADED"
        session.commit()

        try:
            from app.services.generation.asset_usage import accept_task_assets

            accept_task_assets(session, task_id)
        except Exception as registry_exc:
            logger.exception("Failed to accept assets in registry during retry for task %s: %s", task_id, registry_exc)

        record_history_snapshot(session, row)

        record_audit_event(
            db=session,
            action="generation.retried",
            category="generation",
            outcome="success",
            actor_type=actor_ctx.actor_type,
            request_id=actor_ctx.request_id,
            source_ip_hash=actor_ctx.source_ip_hash,
            target_type="generation",
            target_id=task_id,
            task_id=task_id,
            summary="Generation retry succeeded",
            metadata={
                "uploaded_asset_id": row.uploaded_asset_id,
                "album_name": album_name,
                "album_id": album_id,
            },
        )
        return row
    finally:
        session.close()


def _finalize_retry_failure(task_id: str, exc: Exception, actor_ctx: ActorContext) -> None:
    session = SessionLocal()
    session.expire_on_commit = False
    try:
        row = session.query(GenerationHistoryModel).filter(GenerationHistoryModel.task_id == task_id).first()
        if row:
            row.status = "FAILED"
            row.accept_notes = "Retry failed"
            session.commit()
            record_history_snapshot(session, row)

            record_audit_event(
                db=session,
                action="generation.retried",
                category="generation",
                outcome="failure",
                actor_type=actor_ctx.actor_type,
                request_id=actor_ctx.request_id,
                source_ip_hash=actor_ctx.source_ip_hash,
                target_type="generation",
                target_id=task_id,
                task_id=task_id,
                summary=f"Generation retry failed: {str(exc)}",
                error_code=exc.__class__.__name__,
                metadata={"error": str(exc)},
            )
    finally:
        session.close()


def _delete_history_records_and_files(
    db: Session, status: str | None = None, actor_ctx: ActorContext | None = None
) -> None:
    actor_ctx = resolve_actor_context(actor_ctx)
    """Helper to physically delete generated files/thumbnails and purge database history records."""
    from app.models.generation_stream_event import GenerationStreamEventModel
    from app.models.generation_task import GenerationTaskModel

    query = db.query(GenerationHistoryModel)
    if status is not None:
        query = query.filter(GenerationHistoryModel.status == status)

    rows = query.all()
    count = len(rows)
    task_ids = [row.task_id for row in rows]

    from app.services.file_deletion import queue_file_deletion

    data_dir = get_settings().data_dir.resolve()
    for row in rows:
        if row.output_path:
            path = Path(row.output_path).resolve()
            if not path.is_relative_to(data_dir):
                logger.warning("Attempted to delete file outside data_dir: %s", path)
                continue
            thumb = path.with_suffix(path.suffix + ".thumb_400.jpg")
            queue_file_deletion(
                db,
                path=path,
                thumbnail_path=thumb,
                task_id=row.task_id,
                reason="history_delete",
            )

    if task_ids:
        try:
            from app.services.generation.asset_usage import release_task_assets

            for tid in task_ids:
                release_task_assets(db, tid, reason="deleted")
        except Exception as registry_exc:
            logger.exception("Failed to release assets in registry for deleted tasks: %s", registry_exc)

    query.delete(synchronize_session=False)
    if task_ids:
        db.query(GenerationTaskModel).filter(GenerationTaskModel.task_id.in_(task_ids)).delete(
            synchronize_session=False
        )
        db.query(GenerationStreamEventModel).filter(GenerationStreamEventModel.task_id.in_(task_ids)).delete(
            synchronize_session=False
        )

    if actor_ctx and count > 0:
        record_audit_event(
            db=db,
            action="generation.deleted",
            category="generation",
            outcome="success",
            actor_type=actor_ctx.actor_type,
            request_id=actor_ctx.request_id,
            source_ip_hash=actor_ctx.source_ip_hash,
            summary=f"Deleted {count} generation history records (status filter: {status or 'all'})",
            metadata={
                "status_filter": status,
                "deleted_count": count,
                "deleted_task_ids": task_ids,
            },
        )
