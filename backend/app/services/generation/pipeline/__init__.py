import logging
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.immich.models import ImmichSearchFilters
from app.models.settings import SettingsModel
from app.services.generation.ai_budget import AIUsageLimitExceededError

# Expose standard modules/functions imported in pipeline for test patching compatibility
from app.services.generation.ai_vision import analyze_image, analyze_images  # noqa: F401
from app.services.generation.history import upsert_history_entry  # noqa: F401
from app.services.generation.tasks import update_task  # noqa: F401
from app.utils.debug_logger import debug_log, set_debug_mode  # noqa: F401

# Import Stage 2 (assets)
from .assets import (  # noqa: F401
    _dedupe_page_items,
    _parse_ranking_payload,
    _pipeline_retrieve_and_select_assets,
    _prepare_page_items_for_module,
    _search_assets_for_generation,
    _search_filters_for_module,
    _select_page_items,
    rank_source_assets_for_effect,
)

# Import Stage 3 (execution)
from .execution import (  # noqa: F401
    _pipeline_execute_module,
    _run_selected_module,
    _validate_module_config,
)

# Import Stage 4 (metadata)
from .metadata import (  # noqa: F401
    FINAL_AI_VISION_PROMPT,
    _apply_final_vision,
    _apply_source_vision,
    _build_generation_artifacts,
    _initial_artifact_state,
    _pipeline_enrich_metadata,
    _resolve_generation_source_context,
)

# Import Stage 6 (notifications)
from .notifications import (
    _pipeline_dispatch_notifications,
)

# Import Stage 5 (persistence)
from .persistence import (
    _generation_output_paths,
    _pipeline_persist_result,
)

# Import Stage 1 (planning)
from .planning import (  # noqa: F401
    _merge_module_defaults,
    _pipeline_setup_and_planning,
    _resolve_schedule_ai_settings,
    _select_generation_module,
)
from .shared import (  # noqa: F401
    GenerationArtifacts,
    GenerationModuleSelection,
    GenerationPipelineContext,
    _failed_history_provider,
    _record_generation_failure,
    _trace_stage,
)

logger = logging.getLogger(__name__)


async def run_generation_pipeline(
    db: Session,
    settings: SettingsModel,
    task_id: str,
    force: bool = False,
    filters: ImmichSearchFilters | None = None,
    effects_config: dict | None = None,
    schedule_id: int | None = None,
    album_name: str | None = None,
    notification_presets: list = None,
    webhook_url: str | None = None,
    selected_asset_ids: list[str] | None = None,
    on_progress: Callable[[str], None] | None = None,
) -> dict | None:
    ctx = GenerationPipelineContext(
        db=db,
        settings=settings,
        task_id=task_id,
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

    module_selection = _pipeline_setup_and_planning(ctx)
    if module_selection is None:
        return None

    try:
        # Faza 2: Pobieranie i selekcja zdjęć
        assets_res = await _pipeline_retrieve_and_select_assets(ctx, module_selection)
        if assets_res is None:
            return None
        client, page, page_items, photo_selection_trace = assets_res

        # Faza 3: Wykonanie modułu generowania
        result = await _pipeline_execute_module(ctx, module_selection, page_items, client)

        # Faza 4: Wzbogacanie metadanych i analiza wizyjna
        source_asset, artifacts = await _pipeline_enrich_metadata(
            ctx, module_selection, result, page, client, photo_selection_trace
        )

        output_path, image_url = _generation_output_paths(ctx.task_id)

        # Faza 5: Zapisanie wyników w bazie danych i na dysku
        persist_res = await _pipeline_persist_result(ctx, result, artifacts, output_path, image_url)

        # Faza 6: Powiadomienia (Telegram / Webhook)
        await _pipeline_dispatch_notifications(ctx, result, image_url, artifacts)

        return persist_res

    except AIUsageLimitExceededError as exc:
        debug_log(
            "Generation blocked by AI usage limit", task_id=ctx.task_id, module=ctx.selected_group_name, error=str(exc)
        )
        logger.warning("Generation blocked for task %s: %s", ctx.task_id, exc)
        _record_generation_failure(
            db=db,
            task_id=ctx.task_id,
            group_name=ctx.selected_group_name,
            settings=settings,
            exc=exc,
            current_progress=ctx.current_progress,
            _task_update=ctx.task_update,
        )
        return None
    except Exception as exc:
        debug_log("Generation cycle FAILED", task_id=ctx.task_id, module=ctx.selected_group_name, error=str(exc))
        logger.exception("Generation cycle failed for task %s: %s", ctx.task_id, exc)
        _record_generation_failure(
            db=db,
            task_id=ctx.task_id,
            group_name=ctx.selected_group_name,
            settings=settings,
            exc=exc,
            current_progress=ctx.current_progress,
            _task_update=ctx.task_update,
        )
        return None
