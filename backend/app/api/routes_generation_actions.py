import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.immich.errors import ImmichError
from app.models.generation_history import GenerationHistoryModel
from app.models.settings import SettingsModel
from app.schemas.generation import GenerationAcceptRequest, GenerationHistoryResponse
from app.security import ActorContext, authorize_review_access, get_actor_context, require_auth, resolve_actor_context
from app.services.audit import record_audit_event
from app.services.generation.stream import record_history_snapshot
from app.services.generation.upload_metadata import build_immich_upload_metadata
from app.services.immich import build_immich_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/generation", tags=["generation"])
_review_bearer = HTTPBearer(auto_error=False)


async def _apply_album_and_tag(
    *,
    client,
    upload_asset_id: str,
    album_name: str,
    request: GenerationAcceptRequest | None = None,
) -> tuple[str | None, bool, bool, list[str]]:
    album_id = request.album_id if request and request.album_id is not None else None
    album_created = False
    album_updated = False
    accept_notes: list[str] = []

    create_album = request.create_album if request is not None else True
    if create_album or album_name:
        try:
            albums = await client.list_albums()
            existing_album = next((album for album in albums if album.album_name.lower() == album_name.lower()), None)
            if existing_album is not None:
                await client.add_assets_to_album(existing_album.id, [upload_asset_id])
                album_id = existing_album.id
                album_updated = True
            else:
                connection = await client.test_connection()
                if connection.user_id:
                    created_album = await client.create_album(album_name, [upload_asset_id], user_id=connection.user_id)
                    if created_album is not None:
                        album_id = created_album.id
                        album_created = True
        except ImmichError as exc:
            message = f"Album update failed: {exc}"
            logger.warning("Uploaded to Immich but %s", message)
            accept_notes.append(message)

    tag_name = "dailyFX"
    try:
        tag = await client.ensure_tag(tag_name)
        await client.tag_assets(tag.id, [upload_asset_id])
    except ImmichError as exc:
        message = f"Tagging failed: {exc}"
        logger.warning("Uploaded to Immich but %s", message)
        accept_notes.append(message)

    return album_id, album_created, album_updated, accept_notes


async def _upload_generation_asset(
    *,
    client,
    row: GenerationHistoryModel,
    task_id: str,
    image_path: Path,
):
    content = image_path.read_bytes()
    metadata = build_immich_upload_metadata(row=row, task_id=task_id, image_path=image_path)
    return await client.upload_asset(content=content, metadata=metadata)


async def _apply_uploaded_asset_caption_and_tags(*, client, upload_asset_id: str, row: GenerationHistoryModel) -> None:
    if row.summary:
        try:
            await client.update_asset(upload_asset_id, description=row.summary)
        except Exception as update_exc:
            logger.warning("Failed to update asset description in Immich: %s", update_exc)

    if row.tags_json:
        try:
            tag_names = json.loads(row.tags_json)
            if tag_names:
                tags = await client.upsert_tags(tag_names)
                for tag in tags:
                    await client.tag_assets(tag.id, [upload_asset_id])
        except Exception as tag_exc:
            logger.warning("Failed to apply AI tags in Immich: %s", tag_exc)


@router.post("/history/{task_id}/accept", response_model=GenerationHistoryResponse)
async def accept_generation(
    task_id: str,
    request: GenerationAcceptRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
    actor_ctx: ActorContext = Depends(get_actor_context),
):
    actor_ctx = resolve_actor_context(actor_ctx)
    """Accept and upload a generated image to Immich."""
    row = db.query(GenerationHistoryModel).filter(GenerationHistoryModel.task_id == task_id).first()
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

    settings = db.query(SettingsModel).first()
    if not settings:
        raise HTTPException(status_code=500, detail="Settings not found")

    client = build_immich_client(settings)
    try:
        upload_result = await _upload_generation_asset(client=client, row=row, task_id=task_id, image_path=image_path)
        await _apply_uploaded_asset_caption_and_tags(client=client, upload_asset_id=upload_result.id, row=row)

        album_name = request.album_name or row.album_name or None
        if album_name:
            album_id, album_created, album_updated, accept_notes = await _apply_album_and_tag(
                client=client,
                upload_asset_id=upload_result.id,
                album_name=album_name,
                request=request,
            )
        else:
            album_id, album_created, album_updated, accept_notes = None, False, False, []

        row.uploaded_asset_id = upload_result.id
        row.upload_status = upload_result.status
        row.status = "UPLOADED"
        row.album_id = album_id
        row.album_name = album_name
        row.album_created = album_created
        row.album_updated = album_updated
        row.accept_notes = "\n".join(accept_notes) if accept_notes else None
        row.accepted_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(row)

        try:
            from app.services.generation.asset_usage import accept_task_assets

            accept_task_assets(db, task_id)
        except Exception as registry_exc:
            logger.exception("Failed to accept assets in registry for task %s: %s", task_id, registry_exc)

        record_history_snapshot(db, row)

        record_audit_event(
            db=db,
            action="generation.accepted",
            category="generation",
            outcome="success",
            actor_type=actor_ctx.actor_type,
            request_id=actor_ctx.request_id,
            source_ip_hash=actor_ctx.source_ip_hash,
            target_type="generation",
            target_id=task_id,
            task_id=task_id,
            summary=f"Generation accepted and uploaded to Immich (Asset ID: {upload_result.id})",
            metadata={
                "uploaded_asset_id": upload_result.id,
                "album_name": album_name,
                "album_id": album_id,
            },
        )

        return row
    except Exception as exc:
        row.status = "FAILED"
        row.accept_notes = "Upload failed"
        db.commit()
        db.refresh(row)
        record_history_snapshot(db, row)

        record_audit_event(
            db=db,
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

        logger.exception("Failed to upload image to Immich: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to upload image to Immich") from exc


@router.post("/history/{task_id}/retry", response_model=GenerationHistoryResponse)
async def retry_acceptance(
    task_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
    actor_ctx: ActorContext = Depends(get_actor_context),
):
    actor_ctx = resolve_actor_context(actor_ctx)
    """Retry album/tag steps or the entire upload for a generation."""
    row = db.query(GenerationHistoryModel).filter(GenerationHistoryModel.task_id == task_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Generation history entry not found")

    settings = db.query(SettingsModel).first()
    if not settings:
        raise HTTPException(status_code=500, detail="Settings not found")

    client = build_immich_client(settings)
    try:
        # If not uploaded yet, try uploading first
        if not row.uploaded_asset_id:
            if not row.output_path:
                raise HTTPException(status_code=400, detail="No output image file path in history")
            image_path = Path(row.output_path).resolve()
            data_dir = get_settings().data_dir.resolve()
            if not image_path.is_relative_to(data_dir):
                raise HTTPException(status_code=400, detail="Invalid path")
            if not image_path.exists():
                raise HTTPException(status_code=400, detail="Generated image file not found on disk")

            upload_result = await _upload_generation_asset(
                client=client,
                row=row,
                task_id=task_id,
                image_path=image_path,
            )
            row.uploaded_asset_id = upload_result.id
            row.upload_status = upload_result.status
            row.accepted_at = datetime.now(timezone.utc)
            await _apply_uploaded_asset_caption_and_tags(client=client, upload_asset_id=upload_result.id, row=row)

        # Now apply/retry album and tagging
        album_name = (row.album_name or "").strip() or None
        if album_name:
            album_id, album_created, album_updated, accept_notes = await _apply_album_and_tag(
                client=client,
                upload_asset_id=row.uploaded_asset_id,
                album_name=album_name,
                request=GenerationAcceptRequest(
                    create_album=True,
                    album_name=album_name,
                    album_id=row.album_id,
                ),
            )
        else:
            album_id, album_created, album_updated, accept_notes = row.album_id, False, False, []

        row.album_id = album_id
        row.album_name = album_name
        row.album_created = album_created
        row.album_updated = album_updated
        row.accept_notes = "\n".join(accept_notes) if accept_notes else None
        row.status = "UPLOADED"
        db.commit()
        db.refresh(row)

        try:
            from app.services.generation.asset_usage import accept_task_assets

            accept_task_assets(db, task_id)
        except Exception as registry_exc:
            logger.exception("Failed to accept assets in registry during retry for task %s: %s", task_id, registry_exc)

        record_history_snapshot(db, row)

        record_audit_event(
            db=db,
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
    except Exception as exc:
        row.status = "FAILED"
        row.accept_notes = "Retry failed"
        db.commit()
        db.refresh(row)
        record_history_snapshot(db, row)

        record_audit_event(
            db=db,
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

        logger.exception("Retry failed for task %s", task_id)
        raise HTTPException(status_code=500, detail="Retry failed") from exc


@router.post("/history/{task_id}/reject", response_model=GenerationHistoryResponse)
async def reject_generation(
    task_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
    actor_ctx: ActorContext = Depends(get_actor_context),
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

    data_dir = get_settings().data_dir.resolve()
    for row in rows:
        if row.output_path:
            path = Path(row.output_path).resolve()
            if not path.is_relative_to(data_dir):
                logger.warning("Attempted to delete file outside data_dir: %s", path)
                continue
            if path.exists():
                path.unlink(missing_ok=True)
            thumb = path.with_suffix(path.suffix + ".thumb_400.jpg")
            if thumb.exists():
                thumb.unlink(missing_ok=True)

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
async def delete_rejected_cache(
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
    actor_ctx: ActorContext = Depends(get_actor_context),
):
    """Delete all rejected generations (files + DB records)."""
    _delete_history_records_and_files(db, "REJECTED", actor_ctx)
    db.commit()


@router.delete("/history/status/{status}", status_code=204)
async def delete_history_by_status(
    status: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
    actor_ctx: ActorContext = Depends(get_actor_context),
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


@router.delete("/history/cache", status_code=204)
async def clear_generation_cache(
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
    actor_ctx: ActorContext = Depends(get_actor_context),
):
    """Delete all generation history (files + DB records)."""
    _delete_history_records_and_files(db, None, actor_ctx)
    db.commit()


@router.post("/history/{task_id}/like", response_model=GenerationHistoryResponse)
async def like_generation(
    task_id: str,
    review_token: str | None = None,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Security(_review_bearer),
    actor_ctx: ActorContext = Depends(get_actor_context),
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
async def dislike_generation(
    task_id: str,
    review_token: str | None = None,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Security(_review_bearer),
    actor_ctx: ActorContext = Depends(get_actor_context),
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
