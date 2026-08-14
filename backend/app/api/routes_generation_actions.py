"""Generation action endpoints (accept, retry, reject, ai-vision, like, dislike, delete).

Architectural Note on Database Session Lifecycle:
------------------------------------------------
Endpoints in this module (such as accept, retry, and ai-vision) intentionally use a
three-phase execution pattern:

  Phase 1 (DB Read): Open a brief SessionLocal() to read required state and project
          it into an in-memory `_RowProxy` dataclass, then close the session.
  Phase 2 (Async I/O): Perform long-running async HTTP operations (e.g., uploading assets
          to Immich or making AI vision API calls) without holding a database connection.
  Phase 3 (DB Finalize): Open a new brief SessionLocal() to re-verify state, persist
          results, update history status, and record audit events.

This design prevents pool starvation and thread blockages during external network I/O.
The potential Time-Of-Check-Time-Of-Use (TOCTOU) window between Phase 1 and Phase 3 is
mitigated by re-querying the database row in Phase 3 and enforcing status preconditions
before committing updates.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.api.generation_action_helpers import (
    _delete_history_records_and_files,
    _finalize_accept_failure,
    _finalize_accept_success,
    _finalize_retry_failure,
    _finalize_retry_success,
    _prepare_accept_data,
    _prepare_history_ai_vision_data,
    _prepare_retry_data,
    _record_history_ai_vision_failure,
    _save_history_ai_vision_result,
)
from app.api.generation_upload_helpers import (
    _apply_album_and_tag,
    _apply_uploaded_asset_caption_and_tags,
    _upload_generation_asset,
)
from app.config import get_settings
from app.database import get_db
from app.models.generation_history import GenerationHistoryModel
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


@router.post("/history/{task_id}/ai-vision", response_model=GenerationHistoryResponse)
async def run_history_ai_vision(
    task_id: str,
    review_token: str | None = None,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Security(_review_bearer),
    actor_ctx: ActorContext = Depends(get_actor_context_dependency),
):
    """Generate AI Vision summary and tags for a completed history item."""
    actor_ctx = resolve_actor_context(actor_ctx)
    authorize_review_access(task_id, review_token=review_token, credentials=credentials)
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


@router.post("/history/{task_id}/accept", response_model=GenerationHistoryResponse)
async def accept_generation(
    task_id: str,
    request: GenerationAcceptRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
    actor_ctx: ActorContext = Depends(get_actor_context_dependency),
):
    """Accept and upload a generated image to Immich."""
    actor_ctx = resolve_actor_context(actor_ctx)
    image_path, album_name, settings, row_proxy = _prepare_accept_data(task_id, request)

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


@router.post("/history/{task_id}/retry", response_model=GenerationHistoryResponse)
async def retry_acceptance(
    task_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
    actor_ctx: ActorContext = Depends(get_actor_context_dependency),
):
    """Retry album/tag steps or the entire upload for a generation."""
    actor_ctx = resolve_actor_context(actor_ctx)
    uploaded_asset_id, image_path, album_name, row_album_id, settings, row_proxy = _prepare_retry_data(task_id)

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
    """Reject generated image and keep it in history as reviewed."""
    actor_ctx = resolve_actor_context(actor_ctx)
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
