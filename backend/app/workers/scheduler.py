from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from datetime import time as time_of_day

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.generation.engine import run_generation_cycle
from app.services.generation.schedule_runs import build_scheduled_run_context
from app.services.generation.task_flow import run_queued_generation_task
from app.services.immich import get_or_create_settings

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = int(os.environ.get("AUTOMATION_POLL_INTERVAL_SECONDS", "10"))
WEEKDAY_CODES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
WEEKDAY_TO_INDEX = {code: index for index, code in enumerate(WEEKDAY_CODES)}
WEEKDAY_PRESETS = {
    "weekdays": (0, 1, 2, 3, 4),
    "weekends": (5, 6),
}
TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


@dataclass(frozen=True)
class ParsedAutomationSchedule:
    kind: str
    days: tuple[int, ...]
    run_time: time_of_day | None
    valid: bool


def _local_now() -> datetime:
    return datetime.now().astimezone()


def _normalize_datetime(value: datetime | None, tzinfo) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=tzinfo)
    return value.astimezone(tzinfo)


def _parse_time_of_day(value: str | None) -> time_of_day | None:
    if not value:
        return None
    normalized = value.strip()
    if not TIME_RE.match(normalized):
        return None
    hour, minute = normalized.split(":")
    return time_of_day(hour=int(hour), minute=int(minute))


def _parse_weekdays(value: str | None) -> tuple[int, ...]:
    if not value:
        return ()
    days: list[int] = []
    seen: set[int] = set()
    for raw_token in value.split(","):
        token = raw_token.strip().lower()
        if not token:
            continue
        index = WEEKDAY_TO_INDEX.get(token)
        if index is None or index in seen:
            return ()
        seen.add(index)
        days.append(index)
    return tuple(days)


def _parse_automation_schedule(schedule: str) -> ParsedAutomationSchedule:
    normalized = (schedule or "weekly").strip().lower()
    if normalized in {"daily", "weekly"}:
        return ParsedAutomationSchedule(kind=normalized, days=(), run_time=None, valid=True)

    parts = [part.strip() for part in normalized.split("@") if part.strip()]
    if not parts:
        return ParsedAutomationSchedule(kind="weekly", days=(), run_time=None, valid=False)

    kind = parts[0]
    if kind not in {"daily", "weekly", "weekdays", "weekends"}:
        return ParsedAutomationSchedule(kind="weekly", days=(), run_time=None, valid=False)

    days: tuple[int, ...] = ()
    run_time: time_of_day | None = None

    if kind in WEEKDAY_PRESETS:
        days = WEEKDAY_PRESETS[kind]
        if len(parts) >= 2:
            parsed_time = _parse_time_of_day(parts[1])
            if parsed_time is None:
                return ParsedAutomationSchedule(kind="weekly", days=(), run_time=None, valid=False)
            run_time = parsed_time
        if len(parts) > 2:
            return ParsedAutomationSchedule(kind="weekly", days=(), run_time=None, valid=False)
        return ParsedAutomationSchedule(kind=kind, days=days, run_time=run_time, valid=True)

    if len(parts) >= 2:
        parsed_time = _parse_time_of_day(parts[1])
        if parsed_time is not None:
            run_time = parsed_time
        else:
            days = _parse_weekdays(parts[1])
            if not days:
                return ParsedAutomationSchedule(kind="weekly", days=(), run_time=None, valid=False)

    if len(parts) >= 3:
        parsed_time = _parse_time_of_day(parts[2])
        if parsed_time is None:
            return ParsedAutomationSchedule(kind="weekly", days=(), run_time=None, valid=False)
        run_time = parsed_time

    if len(parts) > 3:
        return ParsedAutomationSchedule(kind="weekly", days=(), run_time=None, valid=False)

    return ParsedAutomationSchedule(kind=kind, days=days, run_time=run_time, valid=True)


def _scheduled_moment(current: datetime, run_time: time_of_day) -> datetime:
    return datetime.combine(current.date(), run_time).replace(tzinfo=current.tzinfo)


def _compute_next_run(schedule: str, last_run_at: datetime | None, now: datetime | None = None) -> datetime | None:
    current = now or _local_now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=_local_now().tzinfo)

    last = _normalize_datetime(last_run_at, current.tzinfo)
    parsed = _parse_automation_schedule(schedule)
    if not parsed.valid:
        return None

    if parsed.kind == "daily":
        scheduled = _scheduled_moment(current, parsed.run_time or time_of_day(0, 0))
        if current < scheduled and (last is None or last < scheduled):
            return scheduled
        return scheduled + timedelta(days=1)

    if parsed.days:
        for offset in range(0, 15):
            candidate_date = current.date() + timedelta(days=offset)
            if candidate_date.weekday() not in parsed.days:
                continue
            scheduled = datetime.combine(
                candidate_date,
                parsed.run_time or time_of_day(0, 0),
            ).replace(tzinfo=current.tzinfo)
            if scheduled > current and (last is None or last < scheduled):
                return scheduled
        return None

    if parsed.kind == "weekly":
        if last is None:
            return current + timedelta(days=7)
        return _scheduled_moment(current + timedelta(days=7), parsed.run_time or time_of_day(0, 0))

    return None


def should_run_automation(schedule: str, last_run_at: datetime | None, now: datetime | None = None) -> bool:
    current = now or _local_now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=_local_now().tzinfo)

    last = _normalize_datetime(last_run_at, current.tzinfo)
    parsed = _parse_automation_schedule(schedule)

    if last is None:
        return True

    if parsed.kind == "daily":
        if parsed.run_time is None:
            return last.date() < current.date()
        scheduled = _scheduled_moment(current, parsed.run_time)
        return current >= scheduled and last < scheduled

    if parsed.days:
        if current.weekday() not in parsed.days:
            return False
        scheduled = _scheduled_moment(current, parsed.run_time or time_of_day(0, 0))
        return current >= scheduled and last < scheduled

    if parsed.valid:
        if parsed.run_time is not None:
            logger.debug("Weekly schedule has a time but no weekdays; using legacy weekly semantics.")
        return last.isocalendar()[:2] < current.isocalendar()[:2]

    logger.warning("Unknown automation schedule '%s', defaulting to weekly semantics.", schedule)
    return last.isocalendar()[:2] < current.isocalendar()[:2]


async def _perform_tick(session: Session, now: datetime | None = None) -> dict[str, object]:
    """Core tick logic — iterates over all enabled schedules."""
    from app.models.effect_preset import EffectPresetModel
    from app.models.filter_preset import FilterPresetModel
    from app.models.schedule import ScheduleModel

    current = now or _local_now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=_local_now().tzinfo)

    settings = get_or_create_settings(session)

    # 1. Check for queued manual/ad-hoc tasks first
    from app.models.generation_task import GenerationTaskModel

    queued_task = (
        session.query(GenerationTaskModel)
        .filter(GenerationTaskModel.status == "queued")
        .order_by(GenerationTaskModel.created_at.asc())
        .first()
    )

    if queued_task:
        logger.info("Found queued manual task: %s", queued_task.task_id)
        result = await run_queued_generation_task(
            session,
            settings,
            queued_task,
            run_generation_cycle_fn=run_generation_cycle,
        )
        if result["status"] == "failed":
            logger.warning("Queued manual task %s failed: %s", queued_task.task_id, result.get("error"))
        return result

    schedules = session.query(ScheduleModel).filter(ScheduleModel.enabled.is_(True)).all()

    if not schedules:
        return {"status": "skipped", "reason": "no enabled schedules"}

    results = []
    for schedule in schedules:
        if not should_run_automation(schedule.schedule_expr, schedule.last_run_at, current):
            results.append({"schedule_id": schedule.id, "status": "not_due"})
            continue

        fp = session.get(FilterPresetModel, schedule.filter_preset_id)
        ep = session.get(EffectPresetModel, schedule.effect_preset_id)
        if not fp or not ep:
            logger.warning("Schedule %d missing presets, skipping", schedule.id)
            results.append({"schedule_id": schedule.id, "status": "skipped", "reason": "missing presets"})
            continue

        run_context = build_scheduled_run_context(
            schedule_id=schedule.id,
            album_name=schedule.album_name,
            filter_preset=fp,
            effect_preset=ep,
            notification_presets=list(schedule.notification_presets),
        )
        payload = run_context.to_run_now_task_payload()

        schedule.last_run_at = current
        schedule.last_tick_status = "started"
        schedule.last_tick_reason = "generation queued"
        import uuid

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
            logger.exception("Schedule %d generation failed: %s", schedule.id, exc)
            schedule.last_tick_status = "error"
            schedule.last_tick_reason = str(exc)

        session.add(schedule)
        session.commit()
        results.append({"schedule_id": schedule.id, "status": schedule.last_tick_status, "task_id": task_id})

    due = [r for r in results if r["status"] != "not_due"]
    return {"status": "completed", "schedules_checked": len(results), "schedules_run": len(due), "results": results}


def run_scheduler_tick(db: Session | None = None, now: datetime | None = None) -> dict[str, object]:
    """Synchronous wrapper — used by tests."""
    owns_db = db is None
    session = db or SessionLocal()
    try:
        return asyncio.run(_perform_tick(session, now))
    finally:
        if owns_db:
            session.close()


async def run_scheduler_tick_async(now: datetime | None = None) -> dict[str, object]:
    """Async version used by the production scheduler loop."""
    session = SessionLocal()
    try:
        return await _perform_tick(session, now)
    finally:
        session.close()


def main() -> None:
    logging.basicConfig(level=os.environ.get("AUTOMATION_LOG_LEVEL", "INFO"))
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
        # Clean up result files once per hour
        if tick_count % ticks_per_hour == 0:
            _cleanup_old_results(results_dir)
        # DB backup once per day
        if tick_count % (ticks_per_hour * 24) == 0:
            _backup_database()
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


def _backup_database() -> None:
    try:
        import shutil

        from app.config import get_settings as _get_settings

        data_dir = _get_settings().data_dir
        src = data_dir / "app.db"
        if not src.exists():
            return
        backup_dir = data_dir / "backups"
        backup_dir.mkdir(exist_ok=True)
        dst = backup_dir / f"app_{datetime.now().strftime('%Y%m%d')}.db"
        shutil.copy2(src, dst)
        # Keep last 7 backups
        backups = sorted(backup_dir.glob("app_*.db"))
        for old in backups[:-7]:
            old.unlink(missing_ok=True)
        logger.info("DB backup created: %s", dst.name)
    except Exception:
        logger.exception("DB backup failed")


def _cleanup_old_results(results_dir) -> None:
    try:
        from datetime import timedelta

        from app.database import SessionLocal
        from app.models.generation_history import GenerationHistoryModel

        session = SessionLocal()
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=7)

            # 1. Delete REJECTED entries older than 7 days (and their files)
            old_rejected = (
                session.query(GenerationHistoryModel)
                .filter(
                    GenerationHistoryModel.status == "REJECTED",
                    GenerationHistoryModel.created_at < cutoff,
                )
                .all()
            )
            if old_rejected:
                for row in old_rejected:
                    if row.output_path:
                        from pathlib import Path as _Path

                        _Path(row.output_path).unlink(missing_ok=True)
                    session.delete(row)
                session.commit()
                logger.info("Pruned %d old REJECTED entries (>7 days)", len(old_rejected))

            # 2. Keep 50 most recent non-REJECTED entries
            keep_ids = [
                row.id
                for row in session.query(GenerationHistoryModel.id)
                .filter(GenerationHistoryModel.status != "REJECTED")
                .order_by(GenerationHistoryModel.id.desc())
                .limit(50)
                .all()
            ]
            old_rows = (
                session.query(GenerationHistoryModel.task_id)
                .filter(
                    GenerationHistoryModel.status != "REJECTED",
                    GenerationHistoryModel.id.notin_(keep_ids) if keep_ids else True,
                )
                .all()
            )
            old_task_ids = {row.task_id for row in old_rows}
            if old_task_ids:
                session.query(GenerationHistoryModel).filter(GenerationHistoryModel.task_id.in_(old_task_ids)).delete(
                    synchronize_session=False
                )
                session.commit()
                logger.info("Pruned %d old history entries", len(old_task_ids))
                for task_id in old_task_ids:
                    for f in results_dir.glob(f"{task_id}.*"):
                        f.unlink(missing_ok=True)
        finally:
            session.close()
    except Exception:
        logger.exception("History/result cleanup failed")


if __name__ == "__main__":
    main()
