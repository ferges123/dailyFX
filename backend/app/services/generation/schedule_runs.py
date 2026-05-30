from __future__ import annotations

import json
from dataclasses import dataclass

from app.immich.models import ImmichSearchFilters
from app.models.effect_preset import EffectPresetModel
from app.models.filter_preset import FilterPresetModel
from app.models.notification_preset import NotificationPresetModel
from app.services.generation.run_now import (
    RunNowTaskPayload,
    build_run_now_search_filters,
    build_run_now_task_payload,
)


@dataclass(frozen=True)
class ScheduledRunContext:
    filters: ImmichSearchFilters
    effects_config: dict[str, object]
    notification_presets: list[NotificationPresetModel]
    schedule_id: int
    album_name: str | None

    def to_run_now_task_payload(self) -> RunNowTaskPayload:
        notification_preset_ids = [preset.id for preset in self.notification_presets if preset.id is not None]
        return build_run_now_task_payload(
            filters=self.filters,
            effects_config=self.effects_config,
            schedule_id=self.schedule_id,
            album_name=self.album_name,
            notification_preset_ids=notification_preset_ids or None,
        )


def build_scheduled_run_context(
    *,
    schedule_id: int,
    album_name: str | None,
    filter_preset: FilterPresetModel,
    effect_preset: EffectPresetModel,
    notification_presets: list[NotificationPresetModel] | None = None,
) -> ScheduledRunContext:
    return ScheduledRunContext(
        filters=build_run_now_search_filters(
            album_ids=json.loads(filter_preset.album_ids_json or "[]") or None,
            person_filters=json.loads(filter_preset.person_filters_json or "[]"),
            start_date=filter_preset.start_date,
            end_date=filter_preset.end_date,
            media_type=filter_preset.media_type,
        ),
        effects_config=json.loads(effect_preset.groups_json or "{}"),
        notification_presets=list(notification_presets or []),
        schedule_id=schedule_id,
        album_name=album_name,
    )
