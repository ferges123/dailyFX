import logging
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.immich.errors import handle_immich_errors
from app.immich.models import ImmichPersonFilter, ImmichSearchFilters
from app.schemas.immich import (
    ImmichAlbumPageResponse,
    ImmichAssetPageResponse,
    ImmichExifResponse,
    ImmichFilterOptionsResponse,
)
from app.security import require_auth
from app.services.immich import build_immich_client as _build_immich_client
from app.services.immich import get_asset_thumbnail as _get_asset_thumbnail
from app.services.immich import get_or_create_settings as _get_or_create_settings
from app.services.immich import list_filter_options as _list_filter_options
from app.utils.query_params import query_date

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/immich", tags=["immich"])


@router.get("/options", response_model=ImmichFilterOptionsResponse)
async def list_filter_options(
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
) -> ImmichFilterOptionsResponse:
    row = _get_or_create_settings(db)
    with handle_immich_errors():
        albums, people = await _list_filter_options(row)

    return ImmichFilterOptionsResponse.from_domain(albums=albums, people=people)


@router.get("/albums", response_model=ImmichAlbumPageResponse)
async def list_albums(
    page: int = 1,
    size: int = 12,
    sort_by: str = "name",
    sort_order: str = "asc",
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
) -> ImmichAlbumPageResponse:
    if page < 1:
        page = 1
    if size < 1:
        size = 12

    if sort_by not in {"name", "count", "created", "modified"}:
        sort_by = "name"
    if sort_order not in {"asc", "desc"}:
        sort_order = "asc"

    row = _get_or_create_settings(db)
    with handle_immich_errors():
        client = _build_immich_client(row)
        all_albums = await client.list_albums()

    reverse = sort_order == "desc"

    if sort_by == "count":
        all_albums.sort(key=lambda a: a.asset_count, reverse=reverse)
    elif sort_by == "created":
        all_albums.sort(key=lambda a: a.created_at or "", reverse=reverse)
    elif sort_by == "modified":
        all_albums.sort(key=lambda a: a.last_modified_asset_timestamp or "", reverse=reverse)
    else:  # name
        all_albums.sort(key=lambda a: (a.album_name or "").lower(), reverse=reverse)

    total = len(all_albums)
    pages = (total + size - 1) // size if total > 0 else 1

    start = (page - 1) * size
    end = start + size
    sliced_albums = all_albums[start:end]

    return ImmichAlbumPageResponse(
        items=sliced_albums,
        total=total,
        count=len(sliced_albums),
        pages=pages,
        current_page=page,
    )


@router.get("/assets", response_model=ImmichAssetPageResponse)
async def list_assets(
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
) -> ImmichAssetPageResponse:
    params = request.query_params
    logger.info("list_assets endpoint called. Query params: %s", dict(params))
    media_type = _query_media_type(params.get("media_type"))
    album_ids = params.getlist("album_ids")
    person_ids = params.getlist("person_ids")
    person_modes = params.getlist("person_modes")
    person_mode = _query_person_mode(params.get("person_mode"))
    start_date = query_date(params.get("start_date"))
    end_date = query_date(params.get("end_date"))
    person_filters = _query_person_filters(person_ids, person_modes, person_mode)

    try:
        page = int(params.get("page", "1"))
    except ValueError:
        page = 1

    try:
        size = int(params.get("size", "24"))
    except ValueError:
        size = 24

    row = _get_or_create_settings(db)
    with handle_immich_errors():
        client = _build_immich_client(row)
        result = await client.get_assets(
            page=page,
            size=size,
            filters=ImmichSearchFilters(
                album_ids=album_ids,
                person_filters=person_filters,
                taken_after=start_date,
                taken_before=end_date,
                media_type=media_type,
            ),
        )

    return ImmichAssetPageResponse.from_domain(result)


@router.get("/assets/{asset_id}/thumbnail")
async def get_asset_thumbnail(
    asset_id: str,
    size: str = "preview",
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
) -> Response:
    row = _get_or_create_settings(db)
    with handle_immich_errors():
        content, content_type = await _get_asset_thumbnail(row, asset_id, size=size)

    return Response(content=content, media_type=content_type or "image/jpeg")


@router.get("/assets/{asset_id}/exif", response_model=ImmichExifResponse)
async def get_asset_exif(
    asset_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
) -> ImmichExifResponse:
    row = _get_or_create_settings(db)
    with handle_immich_errors():
        client = _build_immich_client(row)
        return ImmichExifResponse.from_domain(await client.get_asset_exif(asset_id))


def _query_person_mode(value: Any) -> str:
    if isinstance(value, str) and value.strip() in {"optional", "obligatory", "exclude"}:
        return value.strip()
    return "optional"


def _query_media_type(value: Any) -> str:
    if isinstance(value, str) and value.strip() in {"photo", "video", "all"}:
        return value.strip()
    return "all"


def _query_person_filters(
    person_ids: list[str],
    person_modes: list[str],
    fallback_mode: str,
) -> list[ImmichPersonFilter]:
    filters: list[ImmichPersonFilter] = []
    for index, person_id in enumerate(person_ids):
        if not isinstance(person_id, str) or not person_id.strip():
            continue
        mode = person_modes[index] if index < len(person_modes) else fallback_mode
        if mode not in {"optional", "obligatory", "exclude"}:
            mode = fallback_mode
        filters.append(ImmichPersonFilter(person_id=person_id, mode=mode))
    return filters
