from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field

from app.immich.models import (
    ImmichAlbumSummary as ImmichAlbumSummaryModel,
)
from app.immich.models import (
    ImmichAssetPage as ImmichAssetPageModel,
)
from app.immich.models import (
    ImmichPersonSummary as ImmichPersonSummaryModel,
)


class _ImmichResponseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_domain(cls, value: object) -> Self:
        return cls.model_validate(value)


class ImmichPersonSummary(_ImmichResponseModel):
    id: str
    name: str
    is_hidden: bool = False
    asset_count: int = 0


class ImmichAssetSummary(_ImmichResponseModel):
    id: str
    original_file_name: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    mime_type: str | None = None
    asset_type: str | None = None
    people: list[ImmichPersonSummary] = Field(default_factory=list)


class ImmichAssetPageResponse(_ImmichResponseModel):
    items: list[ImmichAssetSummary]
    total: int | None = None
    count: int | None = None
    next_page: str | None = None

    @classmethod
    def from_domain(cls, value: ImmichAssetPageModel) -> Self:
        return cls.model_validate(value)


class ImmichExifResponse(_ImmichResponseModel):
    make: str | None = None
    model: str | None = None
    lensModel: str | None = None
    fNumber: float | int | str | None = None
    exposureTime: float | int | str | None = None
    focalLength: float | int | str | None = None
    iso: int | str | None = None
    latitude: float | int | str | None = None
    longitude: float | int | str | None = None
    dateTimeOriginal: str | None = None

    @classmethod
    def from_domain(cls, value: object) -> Self:
        return cls.model_validate(value)


class ImmichAlbumSummary(_ImmichResponseModel):
    id: str
    album_name: str
    asset_count: int
    thumbnail_asset_id: str | None = None
    created_at: str | None = None
    last_modified_asset_timestamp: str | None = None

    @classmethod
    def from_domain(cls, value: ImmichAlbumSummaryModel) -> Self:
        return cls.model_validate(value)


class ImmichFilterOptionsResponse(_ImmichResponseModel):
    albums: list[ImmichAlbumSummary]
    people: list[ImmichPersonSummary]

    @classmethod
    def from_domain(
        cls,
        *,
        albums: list[ImmichAlbumSummaryModel],
        people: list[ImmichPersonSummaryModel],
    ) -> Self:
        return cls.model_validate({"albums": albums, "people": people})


class ImmichAlbumPageResponse(_ImmichResponseModel):
    items: list[ImmichAlbumSummary]
    total: int
    count: int
    pages: int
    current_page: int
