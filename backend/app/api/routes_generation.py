import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Request, Security
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal, get_db
from app.immich.errors import ImmichError
from app.models.generation_history import GenerationHistoryModel
from app.models.settings import SettingsModel
from app.schemas.generation import (
    EffectStatsResponse,
    GenerationAcceptRequest,
    GenerationExampleResponse,
    GenerationHistoryPage,
    GenerationHistoryResponse,
    GenerationModuleResponse,
    GenerationTaskStatusResponse,
)
from app.security import authorize_review_access, require_auth
from app.services.generation.ai_effects import get_seed_hidden_map
from app.services.generation.examples import ensure_example_preview, list_example_previews
from app.services.generation.history import get_or_create_thumbnail
from app.services.generation.history_api import build_generation_history_page
from app.services.generation.modules import LOCAL_MODULE_GROUPS, MODULES
from app.services.generation.stream import (
    load_events_after,
    record_history_snapshot,
    replay_gap_requires_resync,
)
from app.services.generation.tasks import get_task
from app.services.generation.upload_metadata import build_immich_upload_metadata
from app.services.immich import build_immich_client, get_or_create_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/generation", tags=["generation"])
_review_bearer = HTTPBearer(auto_error=False)


def _stream_event_message(event_type: str, payload: dict | None = None, event_id: int | None = None) -> str:
    lines: list[str] = []
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event_type}")
    data = json.dumps(payload or {}, separators=(",", ":"), ensure_ascii=False)
    for line in data.splitlines() or ["{}"]:
        lines.append(f"data: {line}")
    return "\n".join(lines) + "\n\n"


@router.get("/task/{task_id}/status")
async def get_task_status(
    task_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
) -> GenerationTaskStatusResponse:
    row = get_task(db, task_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Task not found")
    done = row.status in ("succeeded", "failed", "cancelled")
    return GenerationTaskStatusResponse.from_model(row, done=done)


@router.get("/stream")
async def stream_generation_events(request: Request, _: None = Depends(require_auth)):
    """SSE endpoint for real-time generation status updates.

    Polling design: we create a short-lived DB session per iteration to avoid
    holding a transaction open for the entire stream lifetime. The poll interval
    is 5 seconds (not 1s) to limit DB load when many clients are connected.
    Duplicate payloads are suppressed so the client receives only state changes.
    """
    last_event_id_header = request.headers.get("last-event-id")
    try:
        last_event_id = int(last_event_id_header) if last_event_id_header else 0
    except ValueError:
        last_event_id = 0

    async def event_stream():
        cursor = last_event_id
        heartbeat_at = time.monotonic()

        try:
            while True:
                if await request.is_disconnected():
                    break

                # Open a short-lived session only for this read, then close it.
                # This avoids holding a transaction open across the sleep and
                # prevents unbounded session/connection churn under load.
                session = SessionLocal()
                try:
                    if cursor > 0 and replay_gap_requires_resync(session, cursor):
                        yield _stream_event_message(
                            "resync-required",
                            {"reason": "stream_gap", "last_event_id": cursor},
                        )
                        return

                    rows = load_events_after(session, cursor)
                    if rows:
                        for row in rows:
                            payload = json.loads(row.payload_json)
                            yield _stream_event_message(row.event_type, payload, row.id)
                            cursor = row.id
                        heartbeat_at = time.monotonic()
                finally:
                    session.close()

                now = time.monotonic()
                if now - heartbeat_at >= 15:
                    yield _stream_event_message("heartbeat", {"ts": datetime.now(timezone.utc).isoformat()})
                    heartbeat_at = now
                await asyncio.sleep(5)

        except asyncio.CancelledError:
            # Client disconnected or server shutting down — clean exit.
            return

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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


@router.get("/modules", response_model=list[GenerationModuleResponse])
async def list_generation_modules(_: None = Depends(require_auth)) -> list[GenerationModuleResponse]:
    hidden_map = get_seed_hidden_map()
    return [
        GenerationModuleResponse(
            name=item.name,
            label=item.label,
            description=item.description,
            display_group=getattr(item, "display_group", None) or LOCAL_MODULE_GROUPS.get(item.name),
            default_weight=item.default_weight,
            default_config=item.default_config or {},
            config_schema=item.config_schema or [],
        )
        for item in MODULES.values()
        if not (getattr(item, "source", None) == "builtin" and hidden_map.get(item.name, False))
    ]


@router.get("/examples", response_model=list[GenerationExampleResponse])
async def list_generation_examples(
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
) -> list[GenerationExampleResponse]:
    settings = get_or_create_settings(db)
    return await list_example_previews(settings)


@router.get("/examples/{module_name}")
async def get_generation_example(module_name: str, db: Session = Depends(get_db), _: None = Depends(require_auth)):
    settings = get_or_create_settings(db)
    preview = await ensure_example_preview(module_name, settings)
    path = preview.image_path
    if not path.exists():
        raise HTTPException(status_code=404, detail="Example image not found")
    return FileResponse(path, media_type="image/png")


@router.get("/review/{task_id}", response_class=FileResponse)
async def get_review_page(task_id: str) -> FileResponse:
    """Serve the standalone review page for a generation."""
    html_path = Path(__file__).resolve().parent.parent / "static" / "review.html"
    return FileResponse(html_path, media_type="text/html")


@router.get("/review/{task_id}/thumbnail")
async def get_review_thumbnail(
    task_id: str,
    review_token: str | None = None,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Security(_review_bearer),
) -> FileResponse:
    """Public thumbnail for push notification image previews."""
    authorize_review_access(task_id, review_token=review_token, credentials=credentials)
    row = db.query(GenerationHistoryModel).filter(GenerationHistoryModel.task_id == task_id).first()
    if not row or not row.output_path:
        raise HTTPException(status_code=404, detail="Not found")
    path = Path(row.output_path).resolve()
    data_dir = get_settings().data_dir.resolve()
    if not path.is_relative_to(data_dir):
        raise HTTPException(status_code=400, detail="Invalid path")
    if not path.exists():
        raise HTTPException(status_code=404, detail="Not found")

    thumb_path = get_or_create_thumbnail(path).resolve()
    if not thumb_path.is_relative_to(data_dir):
        raise HTTPException(status_code=400, detail="Invalid path")
    if thumb_path != path and thumb_path.exists():
        return FileResponse(thumb_path, media_type="image/jpeg")

    from app.services.generation.output_format import output_mime_type

    return FileResponse(path, media_type=output_mime_type(row.output_format))


@router.get("/history/{task_id}", response_model=GenerationHistoryResponse)
async def get_generation_history_entry(
    task_id: str,
    review_token: str | None = None,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Security(_review_bearer),
):
    """Get a single generation history entry by task_id. No auth required (used by review page)."""
    authorize_review_access(task_id, review_token=review_token, credentials=credentials)
    row = db.query(GenerationHistoryModel).filter(GenerationHistoryModel.task_id == task_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    return GenerationHistoryResponse.from_model(row)


@router.get("/history", response_model=GenerationHistoryPage)
async def get_generation_history(
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
    status: str | None = None,
    search: str | None = None,
    offset: int = 0,
    limit: int = 10,
):
    """Get history of all generations. Optional ?status=, ?search=, ?offset=, and ?limit= for pagination."""
    return build_generation_history_page(db, status=status, search=search, offset=offset, limit=limit)


@router.get("/history/{task_id}/image")
def get_generation_image(
    task_id: str,
    thumbnail: bool = False,
    review_token: str | None = None,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Security(_review_bearer),
):
    """Serve the generated image file or its thumbnail preview."""
    authorize_review_access(task_id, review_token=review_token, credentials=credentials)
    row = db.query(GenerationHistoryModel).filter(GenerationHistoryModel.task_id == task_id).first()
    if not row or not row.output_path:
        raise HTTPException(status_code=404, detail="Image not found")
    path = Path(row.output_path).resolve()
    data_dir = get_settings().data_dir.resolve()
    if not path.is_relative_to(data_dir):
        raise HTTPException(status_code=400, detail="Invalid path")
    if not path.exists():
        raise HTTPException(status_code=404, detail="Image file not found on disk")

    headers = {"Cache-Control": "private, max-age=604800"}
    if thumbnail:
        thumb_path = get_or_create_thumbnail(path).resolve()
        if not thumb_path.is_relative_to(data_dir):
            raise HTTPException(status_code=400, detail="Invalid path")
        if thumb_path != path and thumb_path.exists():
            return FileResponse(thumb_path, media_type="image/jpeg", headers=headers)

    from app.services.generation.output_format import output_mime_type

    return FileResponse(path, media_type=output_mime_type(row.output_format), headers=headers)


@router.post("/history/{task_id}/accept", response_model=GenerationHistoryResponse)
async def accept_generation(
    task_id: str,
    request: GenerationAcceptRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    """Accept and upload a generated image to Immich."""
    row = db.query(GenerationHistoryModel).filter(GenerationHistoryModel.task_id == task_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Generation history entry not found")

    if not row.output_path:
        raise HTTPException(status_code=404, detail="Output path not available in history")

    image_path = Path(row.output_path)
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
        record_history_snapshot(db, row)
        return row
    except Exception as exc:
        row.status = "FAILED"
        row.accept_notes = "Upload failed"
        db.commit()
        db.refresh(row)
        record_history_snapshot(db, row)
        logger.exception("Failed to upload image to Immich: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to upload image to Immich") from exc


@router.post("/history/{task_id}/retry", response_model=GenerationHistoryResponse)
async def retry_acceptance(
    task_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
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
            image_path = Path(row.output_path)
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
        record_history_snapshot(db, row)
        return row
    except Exception as exc:
        row.status = "FAILED"
        row.accept_notes = "Retry failed"
        db.commit()
        db.refresh(row)
        record_history_snapshot(db, row)
        logger.exception("Retry failed for task %s", task_id)
        raise HTTPException(status_code=500, detail="Retry failed") from exc


@router.post("/history/{task_id}/reject", response_model=GenerationHistoryResponse)
async def reject_generation(task_id: str, db: Session = Depends(get_db), _: None = Depends(require_auth)):
    """Reject generated image and keep it in history as reviewed."""
    row = db.query(GenerationHistoryModel).filter(GenerationHistoryModel.task_id == task_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Generation history entry not found")

    if row.accepted_at:
        raise HTTPException(status_code=409, detail="Cannot reject already uploaded generation")

    row.status = "REJECTED"
    db.commit()
    db.refresh(row)
    record_history_snapshot(db, row)
    return row


def _delete_history_records_and_files(db: Session, status: str | None = None) -> None:
    """Helper to physically delete generated files/thumbnails and purge database history records."""
    from app.models.generation_stream_event import GenerationStreamEventModel
    from app.models.generation_task import GenerationTaskModel

    query = db.query(GenerationHistoryModel)
    if status is not None:
        query = query.filter(GenerationHistoryModel.status == status)

    rows = query.all()
    task_ids = [row.task_id for row in rows]

    for row in rows:
        if row.output_path:
            path = Path(row.output_path)
            if path.exists():
                path.unlink(missing_ok=True)
            thumb = path.with_suffix(path.suffix + ".thumb_400.jpg")
            if thumb.exists():
                thumb.unlink(missing_ok=True)

    query.delete(synchronize_session=False)
    if task_ids:
        db.query(GenerationTaskModel).filter(GenerationTaskModel.task_id.in_(task_ids)).delete(
            synchronize_session=False
        )
        db.query(GenerationStreamEventModel).filter(GenerationStreamEventModel.task_id.in_(task_ids)).delete(
            synchronize_session=False
        )


@router.delete("/history/rejected", status_code=204)
async def delete_rejected_cache(db: Session = Depends(get_db), _: None = Depends(require_auth)):
    """Delete all rejected generations (files + DB records)."""
    _delete_history_records_and_files(db, "REJECTED")
    db.commit()


@router.delete("/history/status/{status}", status_code=204)
async def delete_history_by_status(status: str, db: Session = Depends(get_db), _: None = Depends(require_auth)):
    """Delete all generations of a specific status (files + DB records)."""
    status_map = {
        "rejected": "REJECTED",
        "failed": "FAILED",
        "pending": "PENDING_REVIEW",
        "accepted": "UPLOADED",
    }
    db_status = status_map.get(status.lower())
    if not db_status:
        raise HTTPException(status_code=400, detail=f"Invalid or unsupported status: {status}")

    _delete_history_records_and_files(db, db_status)
    db.commit()


@router.delete("/history/cache", status_code=204)
async def clear_generation_cache(db: Session = Depends(get_db), _: None = Depends(require_auth)):
    """Delete all generation history (files + DB records)."""
    _delete_history_records_and_files(db)
    db.commit()


@router.post("/history/{task_id}/like", response_model=GenerationHistoryResponse)
async def like_generation(
    task_id: str,
    review_token: str | None = None,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Security(_review_bearer),
):
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
    return row


@router.post("/history/{task_id}/dislike", response_model=GenerationHistoryResponse)
async def dislike_generation(
    task_id: str,
    review_token: str | None = None,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Security(_review_bearer),
):
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
    return row


def _quality_label_for_rate(rating_count: int, like_rate: int | None) -> str:
    if rating_count < 3 or like_rate is None:
        return "insufficient_data"
    if like_rate >= 80:
        return "excellent"
    if like_rate >= 60:
        return "good"
    if like_rate >= 40:
        return "mixed"
    return "poor"


def _effect_stats_response(
    *,
    effect_id: str,
    title: str,
    total_runs: int,
    likes: int,
    dislikes: int,
    pending_review_runs: int,
    uploaded_runs: int,
    rejected_runs: int,
    failed_runs: int,
    last_run_at: datetime | None,
) -> EffectStatsResponse:
    rating_count = likes + dislikes
    unrated_count = max(0, total_runs - rating_count)
    like_rate = round((likes / rating_count) * 100) if rating_count else None
    quality_label = _quality_label_for_rate(rating_count, like_rate)
    quality_score = like_rate if quality_label != "insufficient_data" and like_rate is not None else 0
    return EffectStatsResponse(
        effect_id=effect_id,
        title=title,
        total_runs=total_runs,
        likes=likes,
        dislikes=dislikes,
        rating_count=rating_count,
        unrated_count=unrated_count,
        like_rate=like_rate,
        quality_score=quality_score,
        quality_label=quality_label,
        pending_review_runs=pending_review_runs,
        uploaded_runs=uploaded_runs,
        rejected_runs=rejected_runs,
        failed_runs=failed_runs,
        last_run_at=last_run_at,
    )


@router.get("/stats/effects", response_model=list[EffectStatsResponse])
def get_effect_stats(db: Session = Depends(get_db), _: None = Depends(require_auth)):
    from app.models.effect_statistics_log import EffectStatisticsLogModel
    from app.models.generation_history import GenerationHistoryModel
    from app.services.generation.modules import MODULES

    # Backfill missing statistics logs from generation history
    missing_tasks = (
        db.query(GenerationHistoryModel.task_id, GenerationHistoryModel.generation_type)
        .outerjoin(EffectStatisticsLogModel, GenerationHistoryModel.task_id == EffectStatisticsLogModel.task_id)
        .filter(EffectStatisticsLogModel.id.is_(None))
        .all()
    )
    if missing_tasks:
        for task_id, gen_type in missing_tasks:
            db.add(EffectStatisticsLogModel(effect_id=gen_type, task_id=task_id))
        db.commit()

    # Query stats grouped by effect_id
    stats = (
        db.query(
            EffectStatisticsLogModel.effect_id,
            sa.func.count(EffectStatisticsLogModel.id).label("total_runs"),
            sa.func.sum(sa.case((EffectStatisticsLogModel.liked.is_(True), 1), else_=0)).label("likes"),
            sa.func.sum(sa.case((EffectStatisticsLogModel.liked.is_(False), 1), else_=0)).label("dislikes"),
            sa.func.sum(sa.case((GenerationHistoryModel.status == "PENDING_REVIEW", 1), else_=0)).label(
                "pending_review_runs"
            ),
            sa.func.sum(sa.case((GenerationHistoryModel.status == "UPLOADED", 1), else_=0)).label("uploaded_runs"),
            sa.func.sum(sa.case((GenerationHistoryModel.status == "REJECTED", 1), else_=0)).label("rejected_runs"),
            sa.func.sum(sa.case((GenerationHistoryModel.status == "FAILED", 1), else_=0)).label("failed_runs"),
            sa.func.max(GenerationHistoryModel.created_at).label("last_run_at"),
        )
        .outerjoin(GenerationHistoryModel, GenerationHistoryModel.task_id == EffectStatisticsLogModel.task_id)
        .group_by(EffectStatisticsLogModel.effect_id)
        .all()
    )

    results = []
    # Merge titles from MODULES registry
    for (
        effect_id,
        total,
        likes,
        dislikes,
        pending_review_runs,
        uploaded_runs,
        rejected_runs,
        failed_runs,
        last_run_at,
    ) in stats:
        module = MODULES.get(effect_id)
        title = getattr(module, "label", effect_id) if module else effect_id
        results.append(
            _effect_stats_response(
                effect_id=effect_id,
                title=title,
                total_runs=total or 0,
                likes=likes or 0,
                dislikes=dislikes or 0,
                pending_review_runs=pending_review_runs or 0,
                uploaded_runs=uploaded_runs or 0,
                rejected_runs=rejected_runs or 0,
                failed_runs=failed_runs or 0,
                last_run_at=last_run_at,
            )
        )

    # Also add any built-in/AI effects that have 0 runs yet
    seen_effects = {row[0] for row in stats}
    for key, module in MODULES.items():
        if key not in seen_effects:
            title = getattr(module, "label", key)
            results.append(
                _effect_stats_response(
                    effect_id=key,
                    title=title,
                    total_runs=0,
                    likes=0,
                    dislikes=0,
                    pending_review_runs=0,
                    uploaded_runs=0,
                    rejected_runs=0,
                    failed_runs=0,
                    last_run_at=None,
                )
            )

    return results
