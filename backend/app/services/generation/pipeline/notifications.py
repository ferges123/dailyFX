from app.services.generation.output import dispatch_generation_outputs
from app.utils.debug_logger import debug_log

from .shared import (
    GenerationArtifacts,
    GenerationPipelineContext,
)


async def _pipeline_dispatch_notifications(
    ctx: GenerationPipelineContext,
    result: object,
    image_url: str,
    artifacts: GenerationArtifacts,
) -> None:
    await dispatch_generation_outputs(
        notification_presets=ctx.notification_presets,
        webhook_url=ctx.webhook_url,
        result=result,
        task_id=ctx.task_id,
        image_url=image_url,
        title=artifacts.ai_title,
        summary=artifacts.ai_summary,
    )
    debug_log("Generation cycle completed", task_id=ctx.task_id)
