from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.schedule import ScheduleModel


class ScheduleCreate(BaseModel):
    name: str = Field(max_length=255)
    enabled: bool = False
    schedule_expr: str = Field(default="weekly", max_length=100)
    filter_preset_id: int
    effect_preset_id: int
    notification_preset_ids: list[int] = Field(default_factory=list, max_length=20)
    album_name: str = Field(default="AI Photos", max_length=255)
    ai_vision_provider: Literal["none", "openai", "gemini", "xiaomi", "openrouter", "local"] = "none"
    ai_vision_model: str = Field(default="gpt-4o-mini", max_length=100)
    ai_image_provider: Literal["none", "openai", "gemini", "openrouter", "byteplus", "local"] = "none"
    ai_image_model: str = Field(default="gpt-image-1", max_length=100)
    ai_prompt_enrichment: bool = False


class ScheduleUpdate(ScheduleCreate):
    pass


class ScheduleResponse(BaseModel):
    id: int
    name: str
    enabled: bool
    schedule_expr: str
    filter_preset_id: int
    effect_preset_id: int
    notification_preset_ids: list[int]
    album_name: str
    ai_vision_provider: str
    ai_vision_model: str
    ai_image_provider: str
    ai_image_model: str
    ai_prompt_enrichment: bool
    last_run_at: datetime | None
    next_run_at: datetime | None
    last_tick_status: str | None
    last_tick_reason: str | None
    last_task_id: str | None
    created_at: datetime
    # Preset names for UI display (populated manually in routes)
    filter_preset_name: str | None = None
    effect_preset_name: str | None = None
    notification_preset_names: list[str] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_model(
        cls,
        row: "ScheduleModel",
        *,
        filter_preset_name: str | None = None,
        effect_preset_name: str | None = None,
        notification_preset_names: list[str] | None = None,
    ) -> "ScheduleResponse":
        return cls(
            id=row.id,
            name=row.name,
            enabled=row.enabled,
            schedule_expr=row.schedule_expr,
            filter_preset_id=row.filter_preset_id,
            effect_preset_id=row.effect_preset_id,
            notification_preset_ids=[preset.id for preset in row.notification_presets],
            album_name=row.album_name,
            ai_vision_provider=row.ai_vision_provider,
            ai_vision_model=row.ai_vision_model,
            ai_image_provider=row.ai_image_provider,
            ai_image_model=row.ai_image_model,
            ai_prompt_enrichment=row.ai_prompt_enrichment,
            last_run_at=row.last_run_at,
            next_run_at=row.next_run_at,
            last_tick_status=row.last_tick_status,
            last_tick_reason=row.last_tick_reason,
            last_task_id=row.last_task_id,
            created_at=row.created_at,
            filter_preset_name=filter_preset_name,
            effect_preset_name=effect_preset_name,
            notification_preset_names=notification_preset_names or [preset.name for preset in row.notification_presets],
        )


class ScheduleRunNowResponse(BaseModel):
    message: str
    task_id: str
