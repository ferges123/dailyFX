from __future__ import annotations

import json
from typing import Literal

from fastapi import HTTPException
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.immich.errors import (
    ImmichAuthenticationError,
    ImmichConfigurationError,
    ImmichConnectionError,
    ImmichPermissionError,
    ImmichUnexpectedResponseError,
)
from app.immich.models import ImmichPersonFilter, ImmichSearchFilters
from app.services.generation.history import upsert_history_entry
from app.services.generation.tasks import update_task
from app.utils.date_utils import parse_date


class RunNowPersonFilterPayload(BaseModel):
    person_id: str = Field(validation_alias=AliasChoices("person_id", "personId"))
    mode: Literal["optional", "obligatory", "exclude"] = "optional"


class RunNowSearchFiltersPayload(BaseModel):
    album_ids: list[str] | None = None
    person_filters: list[RunNowPersonFilterPayload] = Field(default_factory=list)
    taken_after: str | None = None
    taken_before: str | None = None
    media_type: Literal["photo", "video", "all"] = "photo"

    model_config = ConfigDict(populate_by_name=True)

    def to_search_filters(self) -> ImmichSearchFilters:
        return ImmichSearchFilters(
            album_ids=self.album_ids or None,
            person_filters=[
                ImmichPersonFilter(person_id=item.person_id, mode=item.mode) for item in self.person_filters
            ],
            taken_after=parse_date(self.taken_after),
            taken_before=parse_date(self.taken_before),
            media_type=self.media_type,
        )

    @classmethod
    def from_search_filters(cls, filters: ImmichSearchFilters) -> "RunNowSearchFiltersPayload":
        return cls(
            album_ids=filters.album_ids or None,
            person_filters=[
                RunNowPersonFilterPayload(person_id=item.person_id, mode=item.mode) for item in filters.person_filters
            ],
            taken_after=filters.taken_after.isoformat() if filters.taken_after else None,
            taken_before=filters.taken_before.isoformat() if filters.taken_before else None,
            media_type=filters.media_type,
        )


class RunNowTaskPayload(BaseModel):
    filters: RunNowSearchFiltersPayload | None = None
    effects_config: dict[str, object] | None = None
    selected_asset_ids: list[str] | None = None
    schedule_id: int | None = None
    album_name: str | None = None
    notification_preset_ids: list[int] | None = None

    model_config = ConfigDict(populate_by_name=True)

    def to_json(self) -> str:
        return self.model_dump_json(exclude_none=True)

    def to_run_generation_kwargs(self, *, notification_presets: list[object] | None = None) -> dict[str, object]:
        return {
            "filters": self.filters.to_search_filters() if self.filters is not None else None,
            "effects_config": self.effects_config,
            "selected_asset_ids": self.selected_asset_ids,
            "schedule_id": self.schedule_id,
            "album_name": self.album_name,
            "notification_presets": notification_presets,
        }

    @classmethod
    def from_json(cls, payload_json: str) -> "RunNowTaskPayload":
        return cls.model_validate_json(payload_json)


def build_run_now_search_filters(
    *,
    album_ids: list[str] | None,
    person_filters: list[dict[str, object]] | None,
    start_date: str | None,
    end_date: str | None,
    media_type: Literal["photo", "video", "all"] = "photo",
) -> ImmichSearchFilters:
    payload = RunNowSearchFiltersPayload(
        album_ids=album_ids or None,
        person_filters=[RunNowPersonFilterPayload.model_validate(item) for item in person_filters or []],
        taken_after=start_date,
        taken_before=end_date,
        media_type=media_type,
    )
    return payload.to_search_filters()


def build_run_now_task_payload(
    *,
    filters: ImmichSearchFilters | None,
    effects_config: dict[str, object] | None,
    selected_asset_ids: list[str] | None = None,
    schedule_id: int | None = None,
    album_name: str | None = None,
    notification_preset_ids: list[int] | None = None,
) -> RunNowTaskPayload:
    return RunNowTaskPayload(
        filters=RunNowSearchFiltersPayload.from_search_filters(filters) if filters is not None else None,
        effects_config=effects_config,
        selected_asset_ids=selected_asset_ids or None,
        schedule_id=schedule_id,
        album_name=album_name,
        notification_preset_ids=notification_preset_ids or None,
    )


def parse_run_now_task_payload(payload_json: str) -> RunNowTaskPayload:
    return RunNowTaskPayload.from_json(payload_json)


def record_run_now_failure_history(
    db,
    task_id: str,
    *,
    generation_type: str,
    title: str,
    summary: str,
) -> None:
    upsert_history_entry(
        db,
        task_id,
        generation_type=generation_type,
        status="FAILED",
        title=title,
        summary=summary,
        source_asset_ids="[]",
        config_json=json.dumps({"error": summary}),
        task_step="failed",
    )


async def preview_run_now_assets(
    *,
    client,
    filters: ImmichSearchFilters,
    task_id: str,
    db,
    no_assets_message: str,
) -> object:
    try:
        preview = await client.search_assets(filters)
    except ImmichConfigurationError as exc:
        update_task(db, task_id, status="failed", step="failed", progress=0.0, error=str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ImmichAuthenticationError as exc:
        update_task(db, task_id, status="failed", step="failed", progress=0.0, error=str(exc))
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except ImmichPermissionError as exc:
        update_task(db, task_id, status="failed", step="failed", progress=0.0, error=str(exc))
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ImmichConnectionError as exc:
        update_task(db, task_id, status="failed", step="failed", progress=0.0, error=str(exc))
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ImmichUnexpectedResponseError as exc:
        update_task(db, task_id, status="failed", step="failed", progress=0.0, error=str(exc))
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        update_task(db, task_id, status="failed", step="failed", progress=0.0, error=str(exc))
        raise HTTPException(status_code=500, detail="Failed to preview assets") from exc

    if not preview.items:
        update_task(db, task_id, status="failed", step="failed", progress=0.0, error=no_assets_message)
        raise HTTPException(status_code=400, detail=no_assets_message)

    return preview
