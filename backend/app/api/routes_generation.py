import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.immich.errors import ImmichError
from app.models.generation_history import GenerationHistoryModel
from app.models.settings import SettingsModel
from app.schemas.generation import (
    GenerationAcceptRequest,
    GenerationExampleResponse,
    GenerationHistoryPage,
    GenerationHistoryResponse,
    GenerationModuleResponse,
    GenerationTaskStatusResponse,
)
from app.security import require_auth
from app.services.generation.examples import ensure_example_preview, list_example_previews
from app.services.generation.ai_effects import get_seed_hidden_map
from app.services.generation.history import get_or_create_thumbnail
from app.services.generation.history_api import build_generation_history_page
from app.services.generation.modules import MODULES
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
    last_event_id_header = request.headers.get("last-event-id")
    try:
        last_event_id = int(last_event_id_header) if last_event_id_header else 0
    except ValueError:
        last_event_id = 0

    async def event_stream():
        cursor = last_event_id
        heartbeat_at = time.monotonic()

        while True:
            if await request.is_disconnected():
                break

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
                    continue
            finally:
                session.close()

            now = time.monotonic()
            if now - heartbeat_at >= 15:
                yield _stream_event_message("heartbeat", {"ts": datetime.now(timezone.utc).isoformat()})
                heartbeat_at = now
            await asyncio.sleep(1)

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
                    await client.create_album(album_name, [upload_asset_id], user_id=connection.user_id)
                    refreshed_albums = await client.list_albums()
                    created_album = next(
                        (album for album in refreshed_albums if album.album_name.lower() == album_name.lower()),
                        None,
                    )
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
async def get_review_thumbnail(task_id: str, db: Session = Depends(get_db)) -> FileResponse:
    """Public thumbnail for push notification image previews."""
    row = db.query(GenerationHistoryModel).filter(GenerationHistoryModel.task_id == task_id).first()
    if not row or not row.output_path:
        raise HTTPException(status_code=404, detail="Not found")
    path = Path(row.output_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(path, media_type="image/png")


@router.get("/history/{task_id}", response_model=GenerationHistoryResponse)
async def get_generation_history_entry(task_id: str, db: Session = Depends(get_db)):
    """Get a single generation history entry by task_id. No auth required (used by review page)."""
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
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    """Serve the generated image file or its thumbnail preview."""
    row = db.query(GenerationHistoryModel).filter(GenerationHistoryModel.task_id == task_id).first()
    if not row or not row.output_path:
        raise HTTPException(status_code=404, detail="Image not found")
    path = Path(row.output_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Image file not found on disk")

    headers = {"Cache-Control": "private, max-age=604800"}
    if thumbnail:
        thumb_path = get_or_create_thumbnail(path)
        if thumb_path != path and thumb_path.exists():
            return FileResponse(thumb_path, media_type="image/jpeg", headers=headers)

    return FileResponse(path, media_type="image/png", headers=headers)


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
        row.accept_notes = f"Upload failed: {exc}"
        db.commit()
        db.refresh(row)
        record_history_snapshot(db, row)
        logger.exception("Failed to upload image to Immich: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


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
        row.accept_notes = f"Retry failed: {exc}"
        db.commit()
        db.refresh(row)
        record_history_snapshot(db, row)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


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
