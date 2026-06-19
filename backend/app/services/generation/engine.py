from __future__ import annotations

import random  # noqa: F401
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.config import get_settings  # noqa: F401
from app.immich.models import ImmichSearchFilters
from app.services.generation.ai_vision import analyze_image  # noqa: F401
from app.services.generation.modules import MODULES
from app.services.immich import build_immich_client  # noqa: F401


def _merge_module_defaults(groups_config: dict) -> dict:
    merged = {}
    for name, module in MODULES.items():
        current = groups_config.get(name) if isinstance(groups_config, dict) else None
        if not isinstance(current, dict):
            current = {}
        in_preset = isinstance(groups_config, dict) and name in groups_config
        merged[name] = {
            "enabled": current.get("enabled", False) if in_preset else False,
            "weight": current.get("weight", module.default_weight),
            "config": {
                **(module.default_config or {}),
                **(current.get("config") if isinstance(current.get("config"), dict) else {}),
            },
        }
    return merged


async def _send_gen_notification(notification_preset, title: str, summary: str, image_url: str, task_id: str):
    from app.services.generation.output import send_generation_notification

    return await send_generation_notification(notification_preset, title, summary, image_url, task_id)


async def _send_webhook(webhook_url: str | None, task_id: str, generation_type: str, title: str) -> None:
    from app.services.generation.output import send_webhook

    return await send_webhook(webhook_url, task_id, generation_type, title)


def _persist_generation_result(
    *,
    db: Session,
    task_id: str,
    result,
    artifacts,
    output_path,
    image_url: str,
    schedule_id: int | None,
    album_name: str | None,
) -> None:
    from app.services.generation.persistence import persist_generation_result

    return persist_generation_result(
        db=db,
        task_id=task_id,
        result=result,
        artifacts=artifacts,
        output_path=output_path,
        image_url=image_url,
        schedule_id=schedule_id,
        album_name=album_name,
    )


async def _dispatch_generation_outputs(
    *,
    notification_presets,
    webhook_url: str | None,
    result,
    task_id: str,
    image_url: str,
    title: str,
    summary: str,
) -> None:
    if notification_presets:
        for np_preset in notification_presets:
            await _send_gen_notification(np_preset, title, summary, image_url, task_id)
            if np_preset.webhook_url:
                await _send_webhook(np_preset.webhook_url, task_id, result.generation_type, title)
    elif webhook_url:
        await _send_webhook(webhook_url, task_id, result.generation_type, title)


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
