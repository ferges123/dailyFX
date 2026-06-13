import asyncio
import os
from datetime import datetime, timezone

from _contract_helpers import configure_contract_test_db

from app.database import SessionLocal, init_db
from app.models.generation_task import GenerationTaskModel
from app.models.schedule import ScheduleModel, schedule_notification_preset_association
from app.models.settings import SettingsModel
from app.services.immich import get_or_create_settings
from app.workers.scheduler import _perform_tick, _running_task_ids

test_db = configure_contract_test_db("scheduler_concurrency")


def _setup_concurrency_db():
    os.environ["APP_SECRET_KEY"] = "test-api-secret"
    os.environ["CONCURRENCY_LIMIT"] = "2"
    import app.config

    app.config.get_settings.cache_clear()
    init_db()
    db = SessionLocal()

    db.execute(schedule_notification_preset_association.delete())
    db.query(ScheduleModel).delete()
    db.query(GenerationTaskModel).delete()
    db.query(SettingsModel).delete()
    db.commit()

    get_or_create_settings(db)
    db.commit()
    return db


def test_scheduler_async_concurrency_limit(monkeypatch):
    db = _setup_concurrency_db()
    _running_task_ids.clear()
    try:
        # Enqueue 3 manual tasks
        for i in range(3):
            db.add(
                GenerationTaskModel(
                    task_id=f"queued-task-{i}",
                    status="queued",
                    step="queued",
                    progress=0.0,
                    payload_json='{"schedule_id": 123, "notification_preset_ids": []}',
                )
            )
        db.commit()

        # Mock run_queued_generation_task to do a small sleep to simulate execution
        called_tasks = []
        async def fake_run_queued_generation_task(session, settings, queued_task, *args, **kwargs):
            called_tasks.append(queued_task.task_id)
            await asyncio.sleep(0.1)
            return {"status": "completed"}

        monkeypatch.setattr(
            "app.workers.scheduler.run_queued_generation_task",
            fake_run_queued_generation_task,
        )

        async def run_test_logic():
            now = datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc)
            outcome = await _perform_tick(db, now=now, async_mode=True)

            assert outcome["status"] == "completed"
            assert outcome["schedules_enqueued"] == 0
            assert outcome["tasks_spawned_this_tick"] == 2
            assert outcome["active_tasks_count"] == 2
            assert len(_running_task_ids) == 2
            assert "queued-task-0" in _running_task_ids
            assert "queued-task-1" in _running_task_ids
            assert "queued-task-2" not in _running_task_ids

            # Wait for the background tasks to finish
            await asyncio.sleep(0.3)
            assert len(_running_task_ids) == 0

        asyncio.run(run_test_logic())

    finally:
        db.close()
        test_db.unlink(missing_ok=True)
