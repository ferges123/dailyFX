from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class GenerationModuleConfigOption(BaseModel):
    label: str
    value: str


class GenerationModuleConfigField(BaseModel):
    key: str
    label: str
    type: Literal["select", "multiselect", "number", "text", "boolean"]
    description: str | None = None
    default: object | None = None
    options: list[GenerationModuleConfigOption] = Field(default_factory=list)
    min: int | float | None = None
    max: int | float | None = None
    step: int | float | None = None
    placeholder: str | None = None


class GenerationHistoryBase(BaseModel):
    task_id: str
    generation_type: str
    status: Literal["QUEUED", "RUNNING", "PENDING_REVIEW", "UPLOADED", "REJECTED", "FAILED"] = "PENDING_REVIEW"
    title: str
    summary: str
    source_asset_ids: str
    output_path: str | None = None
    image_url: str | None = None
    provider: str | None = None
    model: str | None = None
    total_token_count: int | None = None
    config_json: str
    tags_json: str | None = None
    task_step: str | None = None
    output_format: Literal["png", "gif", "webp"] = "png"
    frame_count: int | None = None
    uploaded_asset_id: str | None = None
    upload_status: str | None = None
    album_id: str | None = None
    album_name: str | None = None
    album_created: bool = False
    album_updated: bool = False
    accept_notes: str | None = None
    accepted_at: datetime | None = None
    liked: bool | None = None


class GenerationHistoryCreate(GenerationHistoryBase):
    pass


class GenerationHistoryResponse(GenerationHistoryBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_model(cls, row: object) -> "GenerationHistoryResponse":
        return cls.model_validate(row)


class GenerationHistoryPage(BaseModel):
    items: list[GenerationHistoryResponse]
    total: int
    latest_event_id: int = 0

    @classmethod
    def from_rows(
        cls,
        rows: list[object],
        *,
        total: int,
        latest_event_id: int,
    ) -> "GenerationHistoryPage":
        return cls(
            items=[GenerationHistoryResponse.from_model(row) for row in rows],
            total=total,
            latest_event_id=latest_event_id,
        )


class GenerationModuleResponse(BaseModel):
    name: str
    label: str
    description: str
    display_group: str | None = None
    default_weight: int = 1
    default_config: dict = Field(default_factory=dict)
    config_schema: list[GenerationModuleConfigField] = Field(default_factory=list)


class GenerationExampleResponse(BaseModel):
    module_name: str
    label: str
    title: str
    summary: str
    source_asset_id: str
    image_url: str


class GenerationAcceptRequest(BaseModel):
    create_album: bool = False
    album_name: str | None = Field(default=None, max_length=255)
    album_id: str | None = None


class PersonFilterRequest(BaseModel):
    person_id: str
    mode: Literal["optional", "obligatory", "exclude"] = "optional"


class GenerationTaskStatusResponse(BaseModel):
    task_id: str
    status: Literal["queued", "running", "succeeded", "failed", "cancelled"]
    step: str | None = None
    progress: float | None = None
    done: bool
    error: str | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, row: object, *, done: bool) -> "GenerationTaskStatusResponse":
        return cls(
            task_id=row.task_id,
            status=row.status,
            step=row.step,
            progress=row.progress,
            done=done,
            error=row.error if row.status == "failed" else None,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )


class EffectStatsResponse(BaseModel):
    effect_id: str
    title: str
    total_runs: int
    likes: int
    dislikes: int
    rating_count: int
    unrated_count: int
    like_rate: int | None = None
    quality_score: int
    quality_label: Literal["insufficient_data", "excellent", "good", "mixed", "poor"]
    pending_review_runs: int
    uploaded_runs: int
    rejected_runs: int
    failed_runs: int
    last_run_at: datetime | None = None
