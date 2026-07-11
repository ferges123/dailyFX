import logging
import time

logger = logging.getLogger(__name__)

from app.services.audit import record_audit_event
from app.utils.debug_logger import debug_log

from .shared import (
    GenerationArtifacts,
    GenerationPipelineContext,
    _format_duration,
    _trace_stage,
    resolve_pipeline_actor,
)


def _generation_output_paths(task_id: str, output_format: str | None = None) -> tuple[object, str]:
    from app.services.generation import engine as engine_module
    from app.services.generation.output_format import output_extension

    output_dir = engine_module.get_settings().data_dir / "results"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{task_id}.{output_extension(output_format)}"
    image_url = f"/api/generation/history/{task_id}/image"
    return output_path, image_url


async def _pipeline_persist_result(
    ctx: GenerationPipelineContext,
    result: object,
    artifacts: GenerationArtifacts,
    output_path: str,
    image_url: str,
) -> dict:
    from app.services.generation import engine as engine_module

    ctx.task_update(step="saving_result", progress=0.95)
    ctx.progress_msg("Saving result…")
    _trace_stage(
        ctx.db,
        ctx.task_id,
        stage="saving_result",
        message="Saving result and writing history entry",
        step="saving_result",
        status="running",
        progress=0.95,
    )
    engine_module._persist_generation_result(
        db=ctx.db,
        task_id=ctx.task_id,
        result=result,
        artifacts=artifacts,
        output_path=output_path,
        image_url=image_url,
        schedule_id=ctx.schedule_id,
        album_name=ctx.album_name,
    )
    debug_log(
        "History entry saved",
        task_id=ctx.task_id,
        status="PENDING_REVIEW",
        generation_type=result.generation_type,
        album_name=ctx.album_name,
        ai_title=artifacts.ai_title,
        tags_count=len(artifacts.ai_tags),
    )

    ctx.task_update(status="succeeded", step="succeeded", progress=1.0, error=None)
    total_elapsed = max(0.0, time.time() - ctx.pipeline_start_time)
    duration_label = _format_duration(total_elapsed)
    _trace_stage(
        ctx.db,
        ctx.task_id,
        stage="completed",
        message=f"Generation completed successfully in {duration_label}"
        if duration_label
        else "Generation completed successfully",
        step="succeeded",
        status="succeeded",
        progress=1.0,
        details={"elapsed_seconds": round(total_elapsed, 2), "generation_type": result.generation_type},
    )

    try:
        actor = resolve_pipeline_actor(ctx.task_id, ctx.schedule_id)
        record_audit_event(
            db=ctx.db,
            action="generation.completed",
            category="generation",
            outcome="success",
            actor_type=actor,
            task_id=ctx.task_id,
            schedule_id=ctx.schedule_id,
            summary=f"Generation completed successfully for task {ctx.task_id}",
            metadata={
                "generation_type": result.generation_type,
                "title": artifacts.ai_title,
                "provider": artifacts.ai_provider,
                "model": artifacts.ai_model,
            },
        )
    except Exception:
        logger.exception("Could not save successful generation audit event for task %s", ctx.task_id)

    return {"task_id": ctx.task_id, "type": result.generation_type, **result.config}
