from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.immich.models import ImmichExifInfo
from app.models.settings import SettingsModel
from app.services.generation.history import append_history_trace, history_status_for_task_status, upsert_history_entry
from app.services.generation.tasks import update_task

logger = logging.getLogger(__name__)

@dataclass
class GenerationPipelineContext:
    db: Session
    settings: SettingsModel
    task_id: str
    force: bool = False
    filters: object | None = None
    effects_config: dict | None = None
    schedule_id: int | None = None
    album_name: str | None = None
    notification_presets: list | None = None
    webhook_url: str | None = None
    selected_asset_ids: list[str] | None = None
    on_progress: Callable[[str], None] | None = None

    # Internal pipeline state
    source: str = "MANUAL"
    current_step: str = "running"
    current_progress: float = 0.0
    selected_group_name: str = "manual"
    pipeline_start_time: float = 0.0

    def task_update(
        self,
        *,
        status: str | None = None,
        step: str | None = None,
        progress: float | None = None,
        error: str | None = None
    ) -> None:
        if step is not None:
            self.current_step = step
        if progress is not None:
            self.current_progress = progress
        update_task(
            self.db,
            self.task_id,
            status=status or "running",
            step=self.current_step,
            progress=self.current_progress,
            error=error,
        )
        if status != "succeeded":
            history_status = history_status_for_task_status(status) or "RUNNING"
            upsert_history_entry(self.db, self.task_id, status=history_status, task_step=self.current_step)

    def progress_msg(self, msg: str) -> None:
        if self.on_progress:
            self.on_progress(msg)


@dataclass(frozen=True)
class GenerationModuleSelection:
    name: str
    module: object
    config: dict


@dataclass(frozen=True)
class GenerationArtifacts:
    ai_title: str
    ai_summary: str
    ai_tags: list[str]
    ai_token_count: int | None
    ai_provider: str | None
    ai_model: str | None
    exif_info: ImmichExifInfo | None
    metadata_provenance: dict
    final_bytes: bytes
    source_asset: object | None = None


def _build_metadata_provenance() -> dict:
    return {
        "title_source": "module_output",
        "summary_source": "module_output",
        "tags_source": "module_output",
        "people_context": {
            "attempted": False,
            "used": False,
            "names": [],
            "faces": [],
            "prompt_hint": "",
        },
        "source_vision": {
            "attempted": False,
            "succeeded": False,
            "provider": None,
            "model": None,
            "error": None,
        },
        "photo_selection": {
            "attempted": False,
            "succeeded": False,
            "provider": None,
            "model": None,
            "candidate_asset_ids": [],
            "selected_asset_id": None,
            "error": None,
            "fallback_reason": None,
        },
        "final_vision": {
            "attempted": False,
            "succeeded": False,
            "provider": None,
            "model": None,
            "error": None,
        },
        "tag_injections": [],
    }


def _trace_stage(
    db: Session,
    task_id: str,
    *,
    stage: str,
    message: str,
    step: str | None = None,
    status: str | None = None,
    progress: float | None = None,
    details: dict | None = None,
) -> None:
    append_history_trace(
        db,
        task_id,
        stage=stage,
        message=message,
        step=step,
        status=status,
        progress=progress,
        details=details,
    )


def _format_duration(seconds: float | int | None) -> str | None:
    if seconds is None:
        return None
    total_seconds = max(0, int(round(float(seconds))))
    minutes, secs = divmod(total_seconds, 60)
    if minutes and secs:
        return f"{minutes} min {secs} sec"
    if minutes:
        return f"{minutes} min"
    return f"{secs} sec"


def _failed_history_provider(group_name: str, settings: SettingsModel) -> tuple[str, str | None]:
    if group_name.startswith("ai_"):
        provider = (settings.ai_image_provider or "").strip().lower() or "unknown"
        model = (settings.ai_image_model or "").strip() or None
        return provider, model
    return "local", None


def _record_generation_failure(
    *,
    db: Session,
    task_id: str,
    group_name: str,
    settings: SettingsModel,
    exc: Exception,
    current_progress: float,
    _task_update: Callable[..., None],
) -> None:
    _task_update(status="failed", step="failed", progress=current_progress, error=str(exc))
    _trace_stage(
        db,
        task_id,
        stage="failed",
        message=str(exc),
        step="failed",
        status="failed",
        progress=current_progress,
        details={"error_type": exc.__class__.__name__},
    )
    try:
        failed_provider, failed_model = _failed_history_provider(group_name, settings)
        upsert_history_entry(
            db,
            task_id,
            generation_type=group_name,
            status="FAILED",
            title=f"Failed: {group_name}",
            summary=str(exc),
            source_asset_ids="[]",
            output_path=None,
            image_url=None,
            provider=failed_provider,
            model=failed_model,
            config_json=json.dumps({"error": str(exc)}),
            task_step="failed",
        )
    except Exception:
        logger.exception("Could not save FAILED history entry for task %s", task_id)
