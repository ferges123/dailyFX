import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Security
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal, get_db
from app.models.generation_history import GenerationHistoryModel
from app.schemas.generation import (
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
from app.services.generation.stream import load_events_after, replay_gap_requires_resync
from app.services.generation.tasks import get_task
from app.services.immich import get_or_create_settings

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
    if row and getattr(row, "local_file_status", "available") == "deleted_by_retention":
        raise HTTPException(status_code=410, detail="Local image was deleted by retention")
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
    effect: str | None = None,
    liked: bool | None = None,
    sort: str = "newest",
    offset: int = 0,
    limit: int = 10,
):
    """Get history of all generations with optional filters and pagination."""
    return build_generation_history_page(
        db,
        status=status,
        search=search,
        effect=effect,
        liked=liked,
        sort=sort,
        offset=offset,
        limit=limit,
    )


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
    if row and getattr(row, "local_file_status", "available") == "deleted_by_retention":
        raise HTTPException(status_code=410, detail="Local image was deleted by retention")
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
