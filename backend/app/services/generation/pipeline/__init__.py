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

# Temporarily delegate to pipeline_old for stage implementation and remaining helpers
from ..pipeline_old import (
    FINAL_AI_VISION_PROMPT,
    _build_metadata_provenance,
    _format_duration,
    _validate_module_config,
    _is_ai_module,
    _inject_ai_tags,
    _ai_tag_injections,
    _resolve_schedule_ai_settings,
    _select_generation_module,
    _search_assets_for_generation,
    _search_filters_for_module,
    _select_page_items,
    _dedupe_page_items,
    _prepare_page_items_for_module,
    _parse_ranking_payload,
    rank_source_assets_for_effect,
    _initial_artifact_state,
    _select_generation_page_items,
    _resolve_generation_source_context,
    _generation_output_paths,
    _run_selected_module,
    _persist_generation_outputs,
    _apply_source_vision,
    _apply_final_vision,
    _build_generation_artifacts,
    _pipeline_setup_and_planning,
    _pipeline_retrieve_and_select_assets,
    _pipeline_execute_module,
    _pipeline_enrich_metadata,
    _pipeline_persist_result,
    _pipeline_dispatch_notifications,
    run_generation_pipeline,
    _failed_history_provider,
    _merge_module_defaults,
)
