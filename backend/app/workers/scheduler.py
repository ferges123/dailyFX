from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.generation.engine import run_generation_cycle
from app.services.generation.history import upsert_history_entry
from app.services.generation.run_now import parse_run_now_task_payload
from app.services.generation.schedule_runs import build_scheduled_run_context
from app.services.generation.task_flow import run_queued_generation_task
from app.services.generation.tasks import ensure_task, update_task
from app.services.immich import get_or_create_settings

_running_task_ids: set[str] = set()
_background_tasks: set[asyncio.Task] = set()

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = int(os.environ.get("AUTOMATION_POLL_INTERVAL_SECONDS", "10"))
from app.workers.schedule_parser import (
    _compute_next_run,
    _local_now,
    should_run_automation,
)


async def _run_queued_task_in_background(task_id: str) -> None:
    _running_task_ids.add(task_id)
    logger.info("Starting background task: %s", task_id)
    session = SessionLocal()
    try:
        settings = get_or_create_settings(session)
        from app.models.generation_task import GenerationTaskModel

        queued_task = session.get(GenerationTaskModel, task_id)
        if not queued_task:
            logger.warning("Queued background task %s not found in database", task_id)
            return

        result = await run_queued_generation_task(
            session,
            settings,
            queued_task,
            run_generation_cycle_fn=run_generation_cycle,
        )
        if result["status"] == "failed":
            logger.warning("Background task %s failed: %s", task_id, result.get("error"))

        if task_id.startswith("auto-s") or task_id.startswith("man-"):
            payload = parse_run_now_task_payload(queued_task.payload_json)
            if payload.schedule_id:
                from app.models.schedule import ScheduleModel

                schedule = session.get(ScheduleModel, payload.schedule_id)
                if schedule:
                    if result["status"] == "completed":
                        schedule.last_tick_status = "completed"
                        schedule.last_tick_reason = "generation completed"
                    else:
                        schedule.last_tick_status = "error"
                        schedule.last_tick_reason = str(result.get("error") or "generation failed")
                    session.add(schedule)
                    session.commit()
    except Exception as exc:
        logger.exception("Exception in background task execution %s: %s", task_id, exc)
    finally:
        session.close()
        _running_task_ids.discard(task_id)
        logger.info(
            "Background task finished and cleaned up: %s. Current running count: %d", task_id, len(_running_task_ids)
        )


def _reset_stuck_tasks_at_runtime(session: Session, current: datetime) -> None:
    from app.models.generation_history import GenerationHistoryModel
    from app.models.generation_task import GenerationTaskModel

    # 5 minutes timeout
    cutoff = current.astimezone(timezone.utc) - timedelta(minutes=5)

    # 1. Reset stuck running history entries
    try:
        stuck_history = (
            session.query(GenerationHistoryModel)
            .filter(GenerationHistoryModel.status == "RUNNING")
            .filter(GenerationHistoryModel.updated_at < cutoff)
            .all()
        )
        if stuck_history:
            for task in stuck_history:
                error = "Task timed out (stuck in RUNNING for more than 15 minutes)"
                upsert_history_entry(
                    session,
                    task.task_id,
                    status="FAILED",
                    task_step="failed",
                    summary=error,
                )
                # Keep the legacy in-memory error attribute for callers that inspect
                # the queried row directly; the persisted diagnostic is in summary.
                task.error = error
                logger.warning("Reset stuck RUNNING task %s to FAILED (timed out)", task.task_id)
    except Exception as exc:
        logger.exception("Failed to reset stuck RUNNING history tasks: %s", exc)
        session.rollback()

    # 2. Reset stuck running tasks
    try:
        stuck_tasks = (
            session.query(GenerationTaskModel)
            .filter(GenerationTaskModel.status == "running")
            .filter(GenerationTaskModel.updated_at < cutoff)
            .all()
        )
        if stuck_tasks:
            for task in stuck_tasks:
                error = "Task timed out (stuck in running for more than 15 minutes)"
                update_task(
                    session,
                    task.task_id,
                    status="failed",
                    step="failed",
                    progress=0.0,
                    error=error,
                )
                logger.warning("Reset stuck running queued task %s to failed (timed out)", task.task_id)
    except Exception as exc:
        logger.exception("Failed to reset stuck running queued tasks: %s", exc)
        session.rollback()


async def _perform_tick(session: Session, now: datetime | None = None, async_mode: bool = True) -> dict[str, object]:
    """Core tick logic — iterates over all enabled schedules."""
    import uuid

    from app.models.effect_preset import EffectPresetModel
    from app.models.generation_task import GenerationTaskModel
    from app.models.people_preset import PeoplePresetModel
    from app.models.schedule import ScheduleModel

    current = now or _local_now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=_local_now().tzinfo)

    # Reset stuck tasks older than 15 minutes
    _reset_stuck_tasks_at_runtime(session, current)

    settings = get_or_create_settings(session)
    MAX_CONCURRENT_TASKS = int(os.environ.get("CONCURRENCY_LIMIT", "2"))

    if not async_mode:
        # --- SYNCHRONOUS MODE (For tests) ---
        queued_task = (
            session.query(GenerationTaskModel)
            .filter(GenerationTaskModel.status == "queued")
            .order_by(GenerationTaskModel.created_at.asc())
            .first()
        )

        if queued_task:
            logger.info("[Sync Mode] Found queued manual task: %s", queued_task.task_id)
            result = await run_queued_generation_task(
                session,
                settings,
                queued_task,
                run_generation_cycle_fn=run_generation_cycle,
            )
            if result["status"] == "failed":
                logger.warning("[Sync Mode] Queued manual task %s failed: %s", queued_task.task_id, result.get("error"))
            return result

        schedules = session.query(ScheduleModel).filter(ScheduleModel.enabled.is_(True)).all()
        if not schedules:
            return {"status": "skipped", "reason": "no enabled schedules"}

        results = []
        for schedule in schedules:
            if not should_run_automation(schedule.schedule_expr, schedule.last_run_at, current):
                results.append({"schedule_id": schedule.id, "status": "not_due"})
                continue

            fp = session.get(PeoplePresetModel, schedule.people_preset_id)
            ep = session.get(EffectPresetModel, schedule.effect_preset_id)
            if not fp or not ep:
                logger.warning("[Sync Mode] Schedule %d missing presets, skipping", schedule.id)
                results.append({"schedule_id": schedule.id, "status": "skipped", "reason": "missing presets"})
                continue

            run_context = build_scheduled_run_context(
                schedule_id=schedule.id,
                album_name=schedule.album_name,
                people_preset=fp,
                effect_preset=ep,
                notification_presets=list(schedule.notification_presets),
            )
            payload = run_context.to_run_now_task_payload()

            schedule.last_run_at = current
            schedule.last_tick_status = "started"
            schedule.last_tick_reason = "generation queued"
            task_id = f"auto-s{schedule.id}-{uuid.uuid4().hex[:8]}"
            schedule.last_task_id = task_id
            schedule.next_run_at = _compute_next_run(schedule.schedule_expr, current, current)
            session.add(schedule)
            session.commit()

            try:
                result = await run_generation_cycle(
                    session,
                    settings,
                    task_id,
                    **payload.to_run_generation_kwargs(notification_presets=run_context.notification_presets),
                )
                schedule.last_tick_status = "completed"
                schedule.last_tick_reason = "generation completed" if result else "generation completed with no result"
            except Exception as exc:
                logger.exception("[Sync Mode] Schedule %d generation failed: %s", schedule.id, exc)
                schedule.last_tick_status = "error"
                schedule.last_tick_reason = str(exc)

            session.add(schedule)
            session.commit()
            results.append({"schedule_id": schedule.id, "status": schedule.last_tick_status, "task_id": task_id})

        due = [r for r in results if r["status"] != "not_due"]
        return {"status": "completed", "schedules_checked": len(results), "schedules_run": len(due), "results": results}

    else:
        # --- ASYNCHRONOUS CONCURRENT MODE (For production) ---
        schedules = session.query(ScheduleModel).filter(ScheduleModel.enabled.is_(True)).all()
        schedules_enqueued = 0
        for schedule in schedules:
            if not should_run_automation(schedule.schedule_expr, schedule.last_run_at, current):
                continue

            fp = session.get(PeoplePresetModel, schedule.people_preset_id)
            ep = session.get(EffectPresetModel, schedule.effect_preset_id)
            if not fp or not ep:
                logger.warning("Schedule %d missing presets, skipping auto-queue", schedule.id)
                continue

            run_context = build_scheduled_run_context(
                schedule_id=schedule.id,
                album_name=schedule.album_name,
                people_preset=fp,
                effect_preset=ep,
                notification_presets=list(schedule.notification_presets),
            )
            payload = run_context.to_run_now_task_payload()

            task_id = f"auto-s{schedule.id}-{uuid.uuid4().hex[:8]}"
            ensure_task(
                session,
                task_id,
                status="queued",
                step="queued",
                progress=0.0,
                payload_json=payload.to_json(),
                schedule_id=schedule.id,
            )

            schedule.last_run_at = current
            schedule.last_task_id = task_id
            schedule.last_tick_status = "queued"
            schedule.last_tick_reason = "Enqueued in background task runner"
            schedule.next_run_at = _compute_next_run(schedule.schedule_expr, current, current)
            session.add(schedule)
            session.commit()
            schedules_enqueued += 1
            logger.info("Enqueued scheduled run task: %s for schedule: %s", task_id, schedule.name)

        queued_tasks = (
            session.query(GenerationTaskModel)
            .filter(GenerationTaskModel.status == "queued")
            .order_by(GenerationTaskModel.created_at.asc())
            .all()
        )

        spawned_count = 0
        for task in queued_tasks:
            if task.task_id in _running_task_ids:
                continue
            if len(_running_task_ids) >= MAX_CONCURRENT_TASKS:
                logger.info(
                    "Concurrency limit reached (%d/%d). Skipping further queue processing.",
                    len(_running_task_ids),
                    MAX_CONCURRENT_TASKS,
                )
                break

            _running_task_ids.add(task.task_id)
            task_obj = asyncio.create_task(_run_queued_task_in_background(task.task_id))
            _background_tasks.add(task_obj)
            task_obj.add_done_callback(_background_tasks.discard)
            spawned_count += 1

        return {
            "status": "completed",
            "schedules_checked": len(schedules),
            "schedules_enqueued": schedules_enqueued,
            "active_tasks_count": len(_running_task_ids),
            "tasks_spawned_this_tick": spawned_count,
        }


def run_scheduler_tick(db: Session | None = None, now: datetime | None = None) -> dict[str, object]:
    """Synchronous wrapper — used by tests."""
    owns_db = db is None
    session = db or SessionLocal()
    try:
        return asyncio.run(_perform_tick(session, now, async_mode=False))
    finally:
        if owns_db:
            session.close()


async def run_scheduler_tick_async(now: datetime | None = None) -> dict[str, object]:
    """Async version used by the production scheduler loop."""
    session = SessionLocal()
    try:
        return await _perform_tick(session, now, async_mode=True)
    finally:
        session.close()


def main() -> None:
    logging.basicConfig(level=os.environ.get("AUTOMATION_LOG_LEVEL", "INFO"))
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logger.info("Automation scheduler started (poll interval: %ss)", POLL_INTERVAL_SECONDS)
    # Migrations are run by the api container; scheduler only needs the engine ready.
    from app.database import _ensure_engine

    _ensure_engine()
    import app.models  # noqa: F401 — register models with Base

    asyncio.run(_async_main())


async def _async_main() -> None:
    from app.config import get_settings as _get_settings

    # Reset any stuck RUNNING tasks to FAILED
    from app.database import SessionLocal
    from app.models.generation_history import GenerationHistoryModel
    from app.workers.telegram_bot import start_telegram_bot_listener

    session = SessionLocal()
    try:
        stuck_tasks = session.query(GenerationHistoryModel).filter(GenerationHistoryModel.status == "RUNNING").all()
        if stuck_tasks:
            for task in stuck_tasks:
                task.status = "FAILED"
                task.error = "Interrupted by scheduler restart"
            session.commit()
            logger.info("Reset %d stuck RUNNING tasks to FAILED", len(stuck_tasks))

        from app.models.generation_task import GenerationTaskModel

        stuck_queued_tasks = session.query(GenerationTaskModel).filter(GenerationTaskModel.status == "running").all()
        if stuck_queued_tasks:
            for task in stuck_queued_tasks:
                task.status = "failed"
                task.error = "Interrupted by scheduler restart"
            session.commit()
            logger.info("Reset %d stuck running queued tasks to failed", len(stuck_queued_tasks))
    except Exception as exc:
        logger.exception("Failed to reset stuck tasks: %s", exc)
        session.rollback()
    finally:
        session.close()

    # Start Telegram bot long polling listener in background
    asyncio.create_task(start_telegram_bot_listener())

    health_path = _get_settings().data_dir / "scheduler.health"
    results_dir = _get_settings().data_dir / "results"
    tick_count = 0
    while True:
        try:
            outcome = await run_scheduler_tick_async()
            logger.info("Scheduler tick outcome: %s", outcome)
        except Exception:
            logger.exception("Scheduler tick failed")
        health_path.touch()
        tick_count += 1
        ticks_per_hour = max(1, 3600 // POLL_INTERVAL_SECONDS)
        # Clean up result files once per day
        if tick_count % (ticks_per_hour * 24) == 0:
            _cleanup_old_results(results_dir)
        # DB backup once per day
        if tick_count % (ticks_per_hour * 24) == 0:
            _backup_database()
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


from app.workers.scheduler_tasks import _backup_database, _cleanup_old_results

if __name__ == "__main__":
    main()
