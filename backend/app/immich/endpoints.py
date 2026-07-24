from __future__ import annotations

import hashlib
from datetime import date, datetime, time, timezone
from itertools import combinations
from typing import Any

from app.immich.models import (
    ImmichAlbumSummary,
    ImmichAssetSummary,
    ImmichFaceSummary,
    ImmichPersonSummary,
    ImmichSearchFilters,
    ImmichTagSummary,
)


def checksum(content: bytes) -> str:
    return hashlib.sha1(content).hexdigest()


def to_iso_utc_start(value: date) -> str:
    return datetime.combine(value, time.min, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def to_iso_utc_end(value: date) -> str:
    return datetime.combine(value, time.max, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def coerce_face_summary(
    payload: dict[str, Any],
    *,
    person_id: str | None = None,
    person_name: str | None = None,
) -> ImmichFaceSummary | None:
    face_id = payload.get("id") if isinstance(payload.get("id"), str) else payload.get("faceId")
    image_width = payload.get("imageWidth")
    if image_width is None:
        image_width = payload.get("image_width")
    image_height = payload.get("imageHeight")
    if image_height is None:
        image_height = payload.get("image_height")
    source_type = payload.get("sourceType")
    if source_type is None:
        source_type = payload.get("source_type")

    x1 = payload.get("boundingBoxX1")
    if x1 is None:
        x1 = payload.get("bounding_box_x1")
    y1 = payload.get("boundingBoxY1")
    if y1 is None:
        y1 = payload.get("bounding_box_y1")
    x2 = payload.get("boundingBoxX2")
    if x2 is None:
        x2 = payload.get("bounding_box_x2")
    y2 = payload.get("boundingBoxY2")
    if y2 is None:
        y2 = payload.get("bounding_box_y2")

    if x1 is None or y1 is None or x2 is None or y2 is None:
        x = payload.get("x")
        y = payload.get("y")
        width = payload.get("width")
        height = payload.get("height")
        if None not in (x, y, width, height):
            x1 = x
            y1 = y
            x2 = x + width
            y2 = y + height

    if x1 is None or y1 is None or x2 is None or y2 is None:
        return None

    return ImmichFaceSummary(
        id=face_id if isinstance(face_id, str) else None,
        person_id=person_id,
        person_name=person_name,
        image_width=image_width if isinstance(image_width, int) else None,
        image_height=image_height if isinstance(image_height, int) else None,
        bounding_box_x1=float(x1) if isinstance(x1, (int, float)) else None,
        bounding_box_y1=float(y1) if isinstance(y1, (int, float)) else None,
        bounding_box_x2=float(x2) if isinstance(x2, (int, float)) else None,
        bounding_box_y2=float(y2) if isinstance(y2, (int, float)) else None,
        source_type=source_type if isinstance(source_type, str) else None,
    )


def coerce_person_summary(payload: dict[str, Any]) -> ImmichPersonSummary | None:
    person_id = payload.get("id")
    name = payload.get("name")
    if not isinstance(person_id, str) or not isinstance(name, str):
        return None
    raw_faces = payload.get("faces") or payload.get("faceList") or payload.get("face")
    faces = []
    if isinstance(raw_faces, list):
        faces = [
            face
            for item in raw_faces
            if isinstance(item, dict)
            and (face := coerce_face_summary(item, person_id=person_id, person_name=name)) is not None
        ]
    elif isinstance(raw_faces, dict):
        face = coerce_face_summary(raw_faces, person_id=person_id, person_name=name)
        if face is not None:
            faces = [face]
    count = payload.get("count", 0)
    return ImmichPersonSummary(
        id=person_id,
        name=name,
        is_hidden=bool(payload.get("isHidden", False)),
        asset_count=count if isinstance(count, int) else 0,
        faces=faces,
    )


def coerce_asset_summary(payload: dict[str, Any]) -> ImmichAssetSummary | None:
    asset_id = payload.get("id")
    if not isinstance(asset_id, str) or not asset_id.strip():
        return None
    original_file_name = payload.get("originalFileName") or payload.get("original_file_name")
    created_at = payload.get("fileCreatedAt") or payload.get("createdAt") or payload.get("created_at")
    updated_at = payload.get("fileModifiedAt") or payload.get("updatedAt") or payload.get("updated_at")
    mime_type = payload.get("mimeType") or payload.get("mime_type")
    asset_type = payload.get("type") or payload.get("assetType") or payload.get("asset_type")
    raw_people = payload.get("people", [])
    people = (
        [
            person
            for item in raw_people
            if isinstance(item, dict) and (person := coerce_person_summary(item)) is not None
        ]
        if isinstance(raw_people, list)
        else []
    )
    return ImmichAssetSummary(
        id=asset_id,
        original_file_name=original_file_name if isinstance(original_file_name, str) else None,
        created_at=created_at if isinstance(created_at, str) else None,
        updated_at=updated_at if isinstance(updated_at, str) else None,
        mime_type=mime_type if isinstance(mime_type, str) else None,
        asset_type=asset_type if isinstance(asset_type, str) else None,
        people=people,
    )


def coerce_album_summary(payload: dict[str, Any]) -> ImmichAlbumSummary | None:
    album_id = payload.get("id")
    album_name = payload.get("albumName")
    if not isinstance(album_id, str) or not isinstance(album_name, str):
        return None
    asset_count = payload.get("assetCount")
    thumbnail_asset_id = payload.get("albumThumbnailAssetId")
    created_at = payload.get("createdAt")
    last_modified = payload.get("lastModifiedAssetTimestamp")
    return ImmichAlbumSummary(
        id=album_id,
        album_name=album_name,
        asset_count=asset_count if isinstance(asset_count, int) else 0,
        thumbnail_asset_id=thumbnail_asset_id if isinstance(thumbnail_asset_id, str) else None,
        created_at=created_at if isinstance(created_at, str) else None,
        last_modified_asset_timestamp=last_modified if isinstance(last_modified, str) else None,
    )


def coerce_tag_summary(payload: dict[str, Any]) -> ImmichTagSummary | None:
    tag_id = payload.get("id")
    name = payload.get("name")
    if not isinstance(tag_id, str) or not isinstance(name, str):
        return None
    value = payload.get("value")
    parent_id = payload.get("parentId")
    return ImmichTagSummary(
        id=tag_id,
        name=name,
        value=value if isinstance(value, str) else None,
        parent_id=parent_id if isinstance(parent_id, str) else None,
    )


def build_person_request_sets(filters: ImmichSearchFilters) -> list[list[str]]:
    if filters.person_ids:
        return [list(dict.fromkeys(filters.person_ids))]

    obligatory_ids = list(dict.fromkeys(f.person_id for f in filters.person_filters if f.mode == "obligatory"))
    optional_ids = list(dict.fromkeys(f.person_id for f in filters.person_filters if f.mode == "optional"))

    request_sets: list[list[str]] = []
    if obligatory_ids:
        for count in range(0, len(optional_ids) + 1):
            for optional_combo in combinations(optional_ids, count):
                request_sets.append([*obligatory_ids, *optional_combo])
    else:
        for count in range(1, len(optional_ids) + 1):
            for optional_combo in combinations(optional_ids, count):
                request_sets.append(list(optional_combo))

    return request_sets or [[]]


def build_random_search_body(
    filters: ImmichSearchFilters,
    person_ids: list[str],
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "size": max(1, min(100, int(getattr(filters, "random_size", 1) or 1))),
        "withDeleted": False,
        "withExif": False,
        "withPeople": True,
        "withStacked": False,
    }
    if filters.album_ids:
        body["albumIds"] = filters.album_ids
    if person_ids:
        body["personIds"] = person_ids
    if filters.taken_after is not None:
        body["takenAfter"] = to_iso_utc_start(filters.taken_after)
    if filters.taken_before is not None:
        body["takenBefore"] = to_iso_utc_end(filters.taken_before)
    if filters.media_type == "photo":
        body["type"] = "IMAGE"
    elif filters.media_type == "video":
        body["type"] = "VIDEO"
    return body


def dedupe_assets(items: list[ImmichAssetSummary]) -> list[ImmichAssetSummary]:
    deduped: dict[str, ImmichAssetSummary] = {}
    for item in items:
        deduped.setdefault(item.id, item)
    return list(deduped.values())
