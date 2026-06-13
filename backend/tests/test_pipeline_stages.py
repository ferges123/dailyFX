from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.generation.pipeline import (
    GenerationPipelineContext,
    _pipeline_setup_and_planning,
)


def test_pipeline_setup_and_planning_basic():
    db = MagicMock()
    settings = SimpleNamespace(
        default_ai_provider="xiaomi",
        default_ai_model="mimo-v2.5",
        ai_vision_hourly_limit=3,
        encrypted_xiaomi_api_key="secret",
        ai_image_provider="none",
        ai_image_model="none",
        debug_mode=True,
    )
    ctx = GenerationPipelineContext(
        db=db,
        settings=settings,
        task_id="test-task",
        force=True,
        effects_config={"pencil_sketch": {"enabled": True}}
    )

    with (
        patch("app.services.generation.pipeline.planning._resolve_schedule_ai_settings"),
        patch("app.services.generation.pipeline.planning.set_debug_mode"),
        patch("app.services.generation.pipeline.planning.upsert_history_entry"),
        patch("app.services.generation.pipeline.shared.upsert_history_entry"),
        patch("app.services.generation.pipeline.planning._trace_stage"),
        patch("app.services.generation.pipeline.planning.debug_log"),
        patch("app.services.generation.pipeline.shared.update_task"),
        patch("app.services.generation.ai_effects_repository.list_ai_effect_rows", return_value=[]),
    ):
        module_selection = _pipeline_setup_and_planning(ctx)

    assert module_selection is not None
    assert module_selection.name == "pencil_sketch"
    assert ctx.source == "MANUAL"
    assert ctx.selected_group_name == "pencil_sketch"
