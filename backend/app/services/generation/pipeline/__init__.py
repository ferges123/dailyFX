from .shared import (
    GenerationPipelineContext,
    GenerationModuleSelection,
    GenerationArtifacts,
    _trace_stage,
    _record_generation_failure,
)

# Expose standard modules/functions imported in pipeline for test patching compatibility
from app.services.generation.ai_vision import analyze_image, analyze_images
from app.utils.debug_logger import debug_log, set_debug_mode
from app.services.generation.history import upsert_history_entry
from app.services.generation.tasks import update_task

# Import Stage 1 (planning)
from .planning import (
    _pipeline_setup_and_planning,
    _select_generation_module,
    _resolve_schedule_ai_settings,
    _merge_module_defaults,
)

# Import Stage 2 (assets)
from .assets import (
    _pipeline_retrieve_and_select_assets,
    _search_assets_for_generation,
    _search_filters_for_module,
    _select_page_items,
    _dedupe_page_items,
    _prepare_page_items_for_module,
    _parse_ranking_payload,
    rank_source_assets_for_effect,
)

# Import Stage 3 (execution)
from .execution import (
    _pipeline_execute_module,
    _run_selected_module,
    _validate_module_config,
)

# Import Stage 4 (metadata)
from .metadata import (
    _pipeline_enrich_metadata,
    _resolve_generation_source_context,
    _initial_artifact_state,
    _build_generation_artifacts,
    _apply_source_vision,
    _apply_final_vision,
    FINAL_AI_VISION_PROMPT,
)

# Temporarily delegate remaining functions to pipeline_old
from ..pipeline_old import (
    _format_duration,
    _generation_output_paths,
    _persist_generation_outputs,
    _pipeline_persist_result,
    _pipeline_dispatch_notifications,
    run_generation_pipeline,
    _failed_history_provider,
)
