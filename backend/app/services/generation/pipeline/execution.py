import time
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.models.settings import SettingsModel
from app.utils.debug_logger import debug_log

from .shared import (
    GenerationModuleSelection,
    GenerationPipelineContext,
    _trace_stage,
)

_ALBUM_NAME_SENTINEL = object()


def _validate_module_config(module, config: dict) -> None:
    from app.services.generation.config_validation import validate_module_config
    validate_module_config(module.name, {"config": config})


async def _run_selected_module(
    *,
    db: Session,
    module,
    group_name: str,
    group_config: dict,
    page_items: list,
    client,
    settings: SettingsModel,
    task_id: str,
    _task_update: Callable[..., None],
    _progress: Callable[[str], None],
):
    _validate_module_config(module, group_config.get("config", {}))
    _task_update(step="applying_effect", progress=0.25)
    _progress(f"Applying effect: {module.label}…")

    debug_log(
        "Starting module execution",
        task_id=task_id,
        module=group_name,
        config=group_config.get("config", {}),
        assets_count=len(page_items),
    )
    start_time = time.time()
    result = await module.run(page_items, group_config.get("config", {}), client, settings)
    elapsed = time.time() - start_time
    debug_log(
        "Module execution completed",
        task_id=task_id,
        module=group_name,
        elapsed_seconds=f"{elapsed:.2f}",
        result_size=len(result.image_bytes) if result.image_bytes else 0,
        source_asset_ids=result.source_asset_ids,
        title=result.title,
    )
    _trace_stage(
        db,
        task_id,
        stage="module_complete",
        message=f"Module {group_name} completed in {elapsed:.2f}s",
        step="applying_effect",
        status="running",
        progress=0.25,
        details={"elapsed_seconds": round(elapsed, 2), "generation_type": result.generation_type},
    )
    return result


async def _pipeline_execute_module(
    ctx: GenerationPipelineContext,
    module_selection: GenerationModuleSelection,
    page_items: list[object],
    client: object,
) -> object:
    original_album_name = getattr(ctx.settings, "_generation_album_name", _ALBUM_NAME_SENTINEL)
    if ctx.album_name is not None:
        ctx.settings._generation_album_name = ctx.album_name
    elif hasattr(ctx.settings, "_generation_album_name"):
        delattr(ctx.settings, "_generation_album_name")

    try:
        result = await _run_selected_module(
            db=ctx.db,
            module=module_selection.module,
            group_name=module_selection.name,
            group_config=module_selection.config,
            page_items=page_items,
            client=client,
            settings=ctx.settings,
            task_id=ctx.task_id,
            _task_update=ctx.task_update,
            _progress=ctx.progress_msg,
        )
        return result
    finally:
        if original_album_name is _ALBUM_NAME_SENTINEL:
            if hasattr(ctx.settings, "_generation_album_name"):
                delattr(ctx.settings, "_generation_album_name")
        else:
            ctx.settings._generation_album_name = original_album_name
