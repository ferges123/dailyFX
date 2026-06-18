from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import TypedDict


class ImmichExifInfo(TypedDict, total=False):
    make: str
    model: str
    lensModel: str
    fNumber: float | int | str
    exposureTime: float | int | str
    focalLength: float | int | str
    iso: int | str
    latitude: float | int | str
    longitude: float | int | str
    dateTimeOriginal: str


@dataclass(frozen=True)
class ImmichConnectionResult:
    ok: bool
    server_url: str
    user_email: str | None = None
    user_id: str | None = None
    server_version: str | None = None


@dataclass(frozen=True)
class ImmichFaceSummary:
    id: str | None = None
    person_id: str | None = None
    person_name: str | None = None
    image_width: int | None = None
    image_height: int | None = None
    bounding_box_x1: float | None = None
    bounding_box_y1: float | None = None
    bounding_box_x2: float | None = None
    bounding_box_y2: float | None = None
    source_type: str | None = None


@dataclass(frozen=True)
class ImmichPersonSummary:
    id: str
    name: str
    is_hidden: bool = False
    asset_count: int = 0
    faces: list[ImmichFaceSummary] = field(default_factory=list)


@dataclass(frozen=True)
class ImmichAssetSummary:
    id: str
    original_file_name: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    mime_type: str | None = None
    asset_type: str | None = None
    people: list[ImmichPersonSummary] = field(default_factory=list)


@dataclass(frozen=True)
class ImmichAssetPage:
    items: list[ImmichAssetSummary]
    total: int | None
    count: int | None
    next_page: str | None


@dataclass(frozen=True)
class ImmichAlbumSummary:
    id: str
    album_name: str
    asset_count: int
    thumbnail_asset_id: str | None = None


@dataclass(frozen=True)
class ImmichTagSummary:
    id: str
    name: str
    value: str | None = None
    parent_id: str | None = None


@dataclass(frozen=True)
class ImmichPersonFilter:
    person_id: str
    mode: str = "optional"


@dataclass(frozen=True)
class ImmichSearchFilters:
    album_ids: list[str] | None = None
    person_ids: list[str] | None = None  # Direct request body filter for the search endpoint.
    person_filters: list[ImmichPersonFilter] = field(default_factory=list)
    taken_after: date | None = None
    taken_before: date | None = None
    media_type: str = "all"
    random_size: int = 1


@dataclass(frozen=True)
class ImmichUploadResult:
    id: str
    status: str | None = None


@dataclass(frozen=True)
class ImmichUploadMetadata:
    filename: str
    device_asset_id: str
    device_id: str
    file_created_at: str
    file_modified_at: str
    checksum: str | None = None
    content_type: str = "image/png"

    def as_request_data(self) -> dict[str, str]:
        return {
            "filename": self.filename,
            "fileCreatedAt": self.file_created_at,
            "fileModifiedAt": self.file_modified_at,
        }
