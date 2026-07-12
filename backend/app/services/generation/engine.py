from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.orm import Session

from app.immich.models import ImmichSearchFilters


async def run_generation_cycle(
    db: Session,
    settings,
    task_id: str,
    force: bool = False,
    filters: ImmichSearchFilters | None = None,
    effects_config: dict | None = None,
    schedule_id: int | None = None,
    album_name: str | None = None,
    notification_presets: list = None,
    webhook_url: str | None = None,
    selected_asset_ids: list[str] | None = None,
    on_progress: "Callable[[str], None] | None" = None,
) -> dict | None:
    from app.services.generation.pipeline import run_generation_pipeline

    return await run_generation_pipeline(
        db,
        settings,
        task_id,
        force=force,
        filters=filters,
        effects_config=effects_config,
        schedule_id=schedule_id,
        album_name=album_name,
        notification_presets=notification_presets,
        webhook_url=webhook_url,
        selected_asset_ids=selected_asset_ids,
        on_progress=on_progress,
    )
