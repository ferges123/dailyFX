import json
import logging
import time

from sqlalchemy.orm import Session

from app.models.settings import SettingsModel
from app.services.generation.history import upsert_history_entry
from app.utils.debug_logger import debug_log, set_debug_mode

from .shared import (
    GenerationModuleSelection,
    GenerationPipelineContext,
    _trace_stage,
)

logger = logging.getLogger(__name__)


def _resolve_schedule_ai_settings(db: Session, settings: SettingsModel, schedule_id: int | None) -> None:
    try:
        from app.models.schedule import ScheduleModel

        schedule = None
        if schedule_id:
            schedule = db.get(ScheduleModel, schedule_id)
        if not schedule:
            schedule = db.query(ScheduleModel).filter(ScheduleModel.enabled).first()
            if not schedule:
                schedule = db.query(ScheduleModel).first()

        if schedule:
            settings.default_ai_provider = getattr(schedule, "ai_vision_provider", "none")
            settings.default_ai_model = getattr(schedule, "ai_vision_model", "")
            settings.ai_image_provider = getattr(schedule, "ai_image_provider", "none")
            settings.ai_image_model = getattr(schedule, "ai_image_model", "")
            settings.ai_prompt_enrichment = getattr(schedule, "ai_prompt_enrichment", False)
            settings.ai_photo_selection_enabled = getattr(schedule, "ai_photo_selection_enabled", False)
        else:
            settings.default_ai_provider = "none"
            settings.default_ai_model = ""
            settings.ai_image_provider = "none"
            settings.ai_image_model = ""
            settings.ai_prompt_enrichment = False
            settings.ai_photo_selection_enabled = False
    except Exception:
        if not hasattr(settings, "default_ai_provider"):
            settings.default_ai_provider = "none"
        if not hasattr(settings, "default_ai_model"):
            settings.default_ai_model = ""
        if not hasattr(settings, "ai_image_provider"):
            settings.ai_image_provider = "none"
        if not hasattr(settings, "ai_image_model"):
            settings.ai_image_model = ""
        if not hasattr(settings, "ai_prompt_enrichment"):
            settings.ai_prompt_enrichment = False
        if not hasattr(settings, "ai_photo_selection_enabled"):
            settings.ai_photo_selection_enabled = False


def _merge_module_defaults(groups_config: dict) -> dict:
    from app.services.generation import engine as engine_module

    modules = getattr(engine_module, "MODULES", {}) or {}
    merged = {}
    for name, module in modules.items():
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


def _select_generation_module(effects_config: dict) -> GenerationModuleSelection | None:
    from app.services.generation import engine as engine_module

    groups_config = _merge_module_defaults(effects_config)
    modules = getattr(engine_module, "MODULES", {}) or {}
    active_groups = []
    for name, data in groups_config.items():
        if data.get("enabled", False):
            mod = modules.get(name)
            if mod is not None and getattr(mod, "enabled", True):
                active_groups.append((name, data))
    debug_log(
        "Active modules",
        active=[f"{n}(w={d['weight']})" for n, d in active_groups],
        total_in_preset=len(effects_config),
    )
    if not active_groups:
        return None

    weights = [data.get("weight", 1) for _, data in active_groups]
    group_name, group_config = engine_module.random.choices(active_groups, weights=weights, k=1)[0]
    module = modules.get(group_name)
    if module is None:
        raise ValueError(f"Unknown generation group: {group_name}")
    return GenerationModuleSelection(name=group_name, module=module, config=group_config)


def _pipeline_setup_and_planning(ctx: GenerationPipelineContext) -> GenerationModuleSelection | None:
    ctx.source = "MANUAL" if ctx.force else "AUTOMATION"
    logger.info(f"🔵 run_generation_cycle START - task_id={ctx.task_id}, source={ctx.source}")
    ctx.pipeline_start_time = time.time()

    _resolve_schedule_ai_settings(ctx.db, ctx.settings, ctx.schedule_id)
    set_debug_mode(ctx.settings.debug_mode)

    ctx.selected_group_name = ctx.source.lower()
    ctx.task_update(status="running", step="running", progress=0.0)

    upsert_history_entry(
        ctx.db,
        ctx.task_id,
        generation_type=ctx.selected_group_name,
        status="RUNNING",
        title=f"{ctx.source.title()} generation running",
        summary="Generation is in progress",
        source_asset_ids="[]",
        config_json=json.dumps({"state": "running"}),
        task_step=ctx.current_step,
        schedule_id=ctx.schedule_id,
        album_name=ctx.album_name,
    )
    _trace_stage(
        ctx.db, ctx.task_id, stage="start", message="Generation started", step="running", status="running", progress=0.0
    )
    debug_log(
        "Generation cycle started",
        task_id=ctx.task_id,
        source=ctx.source,
        schedule_id=ctx.schedule_id,
        album_name=ctx.album_name,
        ai_provider=ctx.settings.default_ai_provider,
        ai_model=ctx.settings.default_ai_model,
        ai_image_provider=ctx.settings.ai_image_provider,
        ai_image_model=ctx.settings.ai_image_model,
        debug_mode=ctx.settings.debug_mode,
    )

    if ctx.effects_config is None:
        debug_log("Skipping: no effects_config provided", task_id=ctx.task_id)
        logger.warning("No effects_config provided, skipping.")
        ctx.task_update(status="failed", step="failed", error="No effects_config provided")
        return None

    try:
        module_selection = _select_generation_module(ctx.effects_config)
    except ValueError as exc:
        debug_log("ERROR: unknown module", task_id=ctx.task_id, module=str(exc))
        logger.error("%s", exc)
        ctx.task_update(status="failed", step="failed", error=str(exc))
        return None

    if module_selection is None:
        debug_log("Skipping: no active modules", task_id=ctx.task_id)
        logger.info("No active modification groups, skipping.")
        ctx.task_update(status="failed", step="failed", error="No active modification groups")
        return None

    ctx.selected_group_name = module_selection.name
    debug_log("Module selected", task_id=ctx.task_id, module=ctx.selected_group_name, config=module_selection.config.get("config", {}))
    logger.info(f"🎯 Selected generation group: {ctx.selected_group_name} (task_id={ctx.task_id})")
    _trace_stage(
        ctx.db,
        ctx.task_id,
        stage="module_selected",
        message=f"Selected generation group {ctx.selected_group_name}",
        step=ctx.current_step,
        status="running",
        progress=ctx.current_progress,
        details={"group": ctx.selected_group_name, "label": getattr(module_selection.module, "label", ctx.selected_group_name)},
    )
    return module_selection
