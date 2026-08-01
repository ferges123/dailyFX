from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


def run_generation_task_process(task_id: str, result_queue: Any) -> None:
    """Run one queued generation in a short-lived process.

    Image libraries keep native allocations after a job completes. Running the
    complete pipeline in this process guarantees the operating system releases
    those allocations when the job exits.
    """
    asyncio.run(_run_generation_task(task_id, result_queue))


async def _run_generation_task(task_id: str, result_queue: Any) -> None:
    from app.database import SessionLocal, _ensure_engine
    from app.models.generation_task import GenerationTaskModel
    from app.services.generation.engine import run_generation_cycle
    from app.services.generation.task_flow import run_queued_generation_task
    from app.services.immich import get_or_create_settings

    # Spawn starts a new interpreter, so it does not inherit the scheduler's
    # SQLAlchemy engine or model registration.
    _ensure_engine()
    import app.models  # noqa: F401

    session = SessionLocal()
    try:
        settings = get_or_create_settings(session)
        queued_task = session.get(GenerationTaskModel, task_id)
        if not queued_task:
            result_queue.put({"status": "failed", "error": "Queued task was not found"})
            return

        result = await run_queued_generation_task(
            session,
            settings,
            queued_task,
            run_generation_cycle_fn=run_generation_cycle,
        )
        result_queue.put(result)
    except BaseException as exc:
        logger.exception("Generation worker crashed for task %s", task_id)
        result_queue.put({"status": "failed", "error": f"Worker process crashed: {exc}"})
        raise
    finally:
        session.close()
