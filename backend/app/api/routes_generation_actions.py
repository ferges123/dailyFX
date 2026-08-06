import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.api.generation_upload_helpers import (
    _apply_album_and_tag,
    _apply_uploaded_asset_caption_and_tags,
    _upload_generation_asset,
)
from app.config import get_settings
from app.database import SessionLocal, get_db
from app.models.generation_history import GenerationHistoryModel
from app.models.settings import SettingsModel
from app.schemas.generation import GenerationAcceptRequest, GenerationHistoryResponse
from app.security import (
    ActorContext,
    authorize_review_access,
    get_actor_context_dependency,
    require_auth,
    resolve_actor_context,
)
from app.services.audit import record_audit_event
from app.services.generation.ai_budget import AIUsageLimitExceededError
from app.services.generation.ai_vision import (
    FINAL_GENERATION_VISION_PROMPT,
    AIVisionError,
    analyze_image,
)
from app.services.generation.stream import record_history_snapshot
from app.services.immich import build_immich_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/generation", tags=["generation"])
_review_bearer = HTTPBearer(auto_error=False)


class _RowProxy:
    pass


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


@router.post("/history/{task_id}/ai-vision", response_model=GenerationHistoryResponse)
async def run_history_ai_vision(
    task_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
    actor_ctx: ActorContext = Depends(get_actor_context_dependency),
):
    """Generate AI Vision summary and tags for a completed history item."""
    actor_ctx = resolve_actor_context(actor_ctx)
    image_bytes, settings = _prepare_history_ai_vision_data(task_id)
    try:
        analysis = await analyze_image(
            settings,
            image_bytes,
            prompt=FINAL_GENERATION_VISION_PROMPT,
        )
        return _save_history_ai_vision_result(task_id, analysis, actor_ctx)
    except AIUsageLimitExceededError as exc:
        _record_history_ai_vision_failure(db, task_id, actor_ctx, exc)
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except (AIVisionError, OSError, ValueError) as exc:
        _record_history_ai_vision_failure(db, task_id, actor_ctx, exc)
        logger.warning("AI Vision update failed for task %s: %s", task_id, exc)
        raise HTTPException(status_code=502, detail="AI Vision analysis failed") from exc
    except Exception as exc:
        _record_history_ai_vision_failure(db, task_id, actor_ctx, exc)
        logger.exception("Unexpected AI Vision update failure for task %s", task_id)
        raise HTTPException(status_code=502, detail="AI Vision analysis failed") from exc


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
        proxy = _RowProxy()
        proxy.task_id = row.task_id
        proxy.title = row.title
        proxy.summary = row.summary
        proxy.tags_json = row.tags_json
        proxy.config_json = row.config_json
        proxy.source_asset_ids = row.source_asset_ids
        proxy.generation_type = row.generation_type
        proxy.provider = row.provider
        proxy.model = row.model
        proxy.created_at = row.created_at
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


@router.post("/history/{task_id}/accept", response_model=GenerationHistoryResponse)
async def accept_generation(
    task_id: str,
    request: GenerationAcceptRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
    actor_ctx: ActorContext = Depends(get_actor_context_dependency),
):
    actor_ctx = resolve_actor_context(actor_ctx)
    """Accept and upload a generated image to Immich."""
    # Phase 1: Short DB session read
    image_path, album_name, settings, row_proxy = _prepare_accept_data(task_id, request)

    # Phase 2: Async Immich HTTP calls without DB session
    client = build_immich_client(settings)
    try:
        upload_result = await _upload_generation_asset(
            client=client, row=row_proxy, task_id=task_id, image_path=image_path
        )
        await _apply_uploaded_asset_caption_and_tags(client=client, upload_asset_id=upload_result.id, row=row_proxy)

        if album_name:
            album_id, album_created, album_updated, accept_notes = await _apply_album_and_tag(
                client=client,
                upload_asset_id=upload_result.id,
                album_name=album_name,
                request=request,
            )
        else:
            album_id, album_created, album_updated, accept_notes = None, False, False, []
    except Exception as exc:
        _finalize_accept_failure(task_id, exc, actor_ctx)
        logger.exception("Failed to upload image to Immich: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to upload image to Immich") from exc

    # Phase 3: Short DB session update
    return _finalize_accept_success(
        task_id=task_id,
        upload_result_id=upload_result.id,
        upload_result_status=upload_result.status,
        album_id=album_id,
        album_name=album_name,
        album_created=album_created,
        album_updated=album_updated,
        accept_notes=accept_notes,
        actor_ctx=actor_ctx,
    )


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
        proxy = _RowProxy()
        proxy.task_id = row.task_id
        proxy.title = row.title
        proxy.summary = row.summary
        proxy.tags_json = row.tags_json
        proxy.config_json = row.config_json
        proxy.source_asset_ids = row.source_asset_ids
        proxy.generation_type = row.generation_type
        proxy.provider = row.provider
        proxy.model = row.model
        proxy.created_at = row.created_at
        proxy.upload_status = row.upload_status
        proxy.accepted_at = row.accepted_at
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


@router.post("/history/{task_id}/retry", response_model=GenerationHistoryResponse)
async def retry_acceptance(
    task_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
    actor_ctx: ActorContext = Depends(get_actor_context_dependency),
):
    actor_ctx = resolve_actor_context(actor_ctx)
    """Retry album/tag steps or the entire upload for a generation."""
    # Phase 1: Short DB session read
    uploaded_asset_id, image_path, album_name, row_album_id, settings, row_proxy = _prepare_retry_data(task_id)

    # Phase 2: Async Immich HTTP calls without DB session
    client = build_immich_client(settings)
    try:
        new_uploaded_asset_id = uploaded_asset_id
        upload_status = row_proxy.upload_status
        accepted_at = row_proxy.accepted_at

        if not new_uploaded_asset_id and image_path:
            upload_result = await _upload_generation_asset(
                client=client,
                row=row_proxy,
                task_id=task_id,
                image_path=image_path,
            )
            new_uploaded_asset_id = upload_result.id
            upload_status = upload_result.status
            accepted_at = datetime.now(timezone.utc)
            await _apply_uploaded_asset_caption_and_tags(
                client=client, upload_asset_id=new_uploaded_asset_id, row=row_proxy
            )

        if album_name and new_uploaded_asset_id:
            album_id, album_created, album_updated, accept_notes = await _apply_album_and_tag(
                client=client,
                upload_asset_id=new_uploaded_asset_id,
                album_name=album_name,
                request=GenerationAcceptRequest(
                    create_album=True,
                    album_name=album_name,
                    album_id=row_album_id,
                ),
            )
        else:
            album_id, album_created, album_updated, accept_notes = row_album_id, False, False, []
    except Exception as exc:
        _finalize_retry_failure(task_id, exc, actor_ctx)
        logger.exception("Retry failed for task %s", task_id)
        raise HTTPException(status_code=500, detail="Retry failed") from exc

    # Phase 3: Short DB session update
    return _finalize_retry_success(
        task_id=task_id,
        new_uploaded_asset_id=new_uploaded_asset_id,
        upload_status=upload_status,
        accepted_at=accepted_at,
        album_id=album_id,
        album_name=album_name,
        album_created=album_created,
        album_updated=album_updated,
        accept_notes=accept_notes,
        actor_ctx=actor_ctx,
    )


@router.post("/history/{task_id}/reject", response_model=GenerationHistoryResponse)
def reject_generation(
    task_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
    actor_ctx: ActorContext = Depends(get_actor_context_dependency),
):
    actor_ctx = resolve_actor_context(actor_ctx)
    """Reject generated image and keep it in history as reviewed."""
    row = db.query(GenerationHistoryModel).filter(GenerationHistoryModel.task_id == task_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Generation history entry not found")

    if row.accepted_at:
        raise HTTPException(status_code=409, detail="Cannot reject already uploaded generation")

    try:
        row.status = "REJECTED"
        db.commit()
        db.refresh(row)

        try:
            from app.services.generation.asset_usage import release_task_assets

            release_task_assets(db, task_id, reason="rejected")
        except Exception as registry_exc:
            logger.exception("Failed to release assets in registry for task %s: %s", task_id, registry_exc)

        record_history_snapshot(db, row)

        record_audit_event(
            db=db,
            action="generation.rejected",
            category="generation",
            outcome="success",
            actor_type=actor_ctx.actor_type,
            request_id=actor_ctx.request_id,
            source_ip_hash=actor_ctx.source_ip_hash,
            target_type="generation",
            target_id=task_id,
            task_id=task_id,
            summary="Generation rejected",
        )

        return row
    except Exception as exc:
        try:
            db.rollback()
        except Exception:
            pass
        record_audit_event(
            db=db,
            action="generation.rejected",
            category="generation",
            outcome="failure",
            actor_type=actor_ctx.actor_type,
            request_id=actor_ctx.request_id,
            source_ip_hash=actor_ctx.source_ip_hash,
            target_type="generation",
            target_id=task_id,
            task_id=task_id,
            summary=f"Failed to reject generation: {str(exc)}",
            error_code=exc.__class__.__name__,
            metadata={"error": str(exc)},
        )
        raise


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


@router.delete("/history/rejected", status_code=204)
def delete_rejected_cache(
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
    actor_ctx: ActorContext = Depends(get_actor_context_dependency),
):
    """Delete all rejected generations (files + DB records)."""
    _delete_history_records_and_files(db, "REJECTED", actor_ctx)
    db.commit()
    from app.services.file_deletion import process_file_deletion_jobs

    process_file_deletion_jobs(db, data_dir=get_settings().data_dir)


@router.delete("/history/status/{status}", status_code=204)
def delete_history_by_status(
    status: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
    actor_ctx: ActorContext = Depends(get_actor_context_dependency),
):
    """Delete all generations of a specific status (files + DB records)."""
    status_map = {
        "rejected": "REJECTED",
        "failed": "FAILED",
        "pending": "PENDING_REVIEW",
        "accepted": "UPLOADED",
        "running": "RUNNING",
    }
    db_status = status_map.get(status.lower())
    if not db_status:
        raise HTTPException(status_code=400, detail=f"Invalid or unsupported status: {status}")

    _delete_history_records_and_files(db, db_status, actor_ctx)
    db.commit()
    from app.services.file_deletion import process_file_deletion_jobs

    process_file_deletion_jobs(db, data_dir=get_settings().data_dir)


@router.delete("/history/cache", status_code=204)
def clear_generation_cache(
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
    actor_ctx: ActorContext = Depends(get_actor_context_dependency),
):
    """Delete all generation history (files + DB records)."""
    _delete_history_records_and_files(db, None, actor_ctx)
    db.commit()
    from app.services.file_deletion import process_file_deletion_jobs

    process_file_deletion_jobs(db, data_dir=get_settings().data_dir)


@router.post("/history/{task_id}/like", response_model=GenerationHistoryResponse)
def like_generation(
    task_id: str,
    review_token: str | None = None,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Security(_review_bearer),
    actor_ctx: ActorContext = Depends(get_actor_context_dependency),
):
    actor_ctx = resolve_actor_context(actor_ctx)
    authorize_review_access(task_id, review_token=review_token, credentials=credentials)
    row = db.query(GenerationHistoryModel).filter_by(task_id=task_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Entry not found")

    from app.models.effect_statistics_log import EffectStatisticsLogModel

    log = db.query(EffectStatisticsLogModel).filter_by(task_id=task_id).first()
    if not log:
        log = EffectStatisticsLogModel(effect_id=row.generation_type, task_id=task_id)
        db.add(log)

    log.liked = None if log.liked is True else True
    db.commit()
    db.refresh(row)
    record_history_snapshot(db, row)

    action = "generation.liked" if log.liked is True else "generation.rating_reset"
    summary = "Generation liked" if log.liked is True else "Generation rating reset"
    record_audit_event(
        db=db,
        action=action,
        category="generation",
        outcome="success",
        actor_type=actor_ctx.actor_type,
        request_id=actor_ctx.request_id,
        source_ip_hash=actor_ctx.source_ip_hash,
        target_type="generation",
        target_id=task_id,
        task_id=task_id,
        summary=summary,
    )

    return row


@router.post("/history/{task_id}/dislike", response_model=GenerationHistoryResponse)
def dislike_generation(
    task_id: str,
    review_token: str | None = None,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Security(_review_bearer),
    actor_ctx: ActorContext = Depends(get_actor_context_dependency),
):
    actor_ctx = resolve_actor_context(actor_ctx)
    authorize_review_access(task_id, review_token=review_token, credentials=credentials)
    row = db.query(GenerationHistoryModel).filter_by(task_id=task_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Entry not found")

    from app.models.effect_statistics_log import EffectStatisticsLogModel

    log = db.query(EffectStatisticsLogModel).filter_by(task_id=task_id).first()
    if not log:
        log = EffectStatisticsLogModel(effect_id=row.generation_type, task_id=task_id)
        db.add(log)

    log.liked = None if log.liked is False else False
    db.commit()
    db.refresh(row)
    record_history_snapshot(db, row)

    action = "generation.unliked" if log.liked is False else "generation.rating_reset"
    summary = "Generation unliked" if log.liked is False else "Generation rating reset"
    record_audit_event(
        db=db,
        action=action,
        category="generation",
        outcome="success",
        actor_type=actor_ctx.actor_type,
        request_id=actor_ctx.request_id,
        source_ip_hash=actor_ctx.source_ip_hash,
        target_type="generation",
        target_id=task_id,
        task_id=task_id,
        summary=summary,
    )

    return row
