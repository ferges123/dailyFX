from app.utils.debug_logger import debug_log
from .shared import (
    GenerationPipelineContext,
    GenerationArtifacts,
)


async def _pipeline_dispatch_notifications(
    ctx: GenerationPipelineContext,
    result: object,
    image_url: str,
    artifacts: GenerationArtifacts,
) -> None:
    from app.services.generation import engine as engine_module

    await engine_module._dispatch_generation_outputs(
        notification_presets=ctx.notification_presets,
        webhook_url=ctx.webhook_url,
        result=result,
        task_id=ctx.task_id,
        image_url=image_url,
        title=artifacts.ai_title,
        summary=artifacts.ai_summary,
    )
    debug_log("Generation cycle completed", task_id=ctx.task_id)
