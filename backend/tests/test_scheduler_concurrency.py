import asyncio
import os
from datetime import datetime, timezone
from unittest.mock import patch

from _contract_helpers import configure_contract_test_db

from app.database import SessionLocal, init_db
from app.models.generation_task import GenerationTaskModel
from app.models.schedule import ScheduleModel, schedule_notification_preset_association
from app.models.settings import SettingsModel
from app.services.immich import get_or_create_settings
from app.workers.scheduler import _perform_tick, _run_queued_task_in_background, _running_task_ids

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

        # Mock process supervision to avoid spawning real image workers.
        called_tasks = []

        async def fake_run_queued_task_in_background(task_id):
            called_tasks.append(task_id)
            try:
                await asyncio.sleep(0.1)
            finally:
                _running_task_ids.discard(task_id)

        monkeypatch.setattr(
            "app.workers.scheduler._run_queued_task_in_background",
            fake_run_queued_task_in_background,
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


def test_scheduler_terminates_generation_worker_after_timeout(monkeypatch):
    """A stuck child must release its concurrency slot without a scheduler restart."""

    class FakeQueue:
        def close(self):
            pass

        def join_thread(self):
            pass

    class FakeProcess:
        def __init__(self):
            self.alive = True
            self.exitcode = None
            self.join_timeouts: list[int | None] = []
            self.terminated = False
            self.killed = False
            self.closed = False

        def start(self):
            pass

        def join(self, timeout=None):
            self.join_timeouts.append(timeout)
            if self.terminated or self.killed:
                self.alive = False
                self.exitcode = -15

        def is_alive(self):
            return self.alive

        def terminate(self):
            self.terminated = True

        def kill(self):
            self.killed = True

        def close(self):
            self.closed = True

    process = FakeProcess()

    class FakeContext:
        def Queue(self, maxsize):
            assert maxsize == 1
            return FakeQueue()

        def Process(self, target, args):
            return process

    failures: list[tuple[str, str]] = []
    monkeypatch.setattr("app.workers.scheduler.GENERATION_WORKER_TIMEOUT_SECONDS", 0)
    monkeypatch.setattr(
        "app.workers.scheduler._record_worker_failure", lambda task_id, error: failures.append((task_id, error))
    )
    monkeypatch.setattr("app.workers.scheduler._update_schedule_after_queued_task", lambda *args: None)
    _running_task_ids.clear()

    with patch("app.workers.scheduler.multiprocessing.get_context", return_value=FakeContext()):
        asyncio.run(_run_queued_task_in_background("stuck-task"))

    assert process.join_timeouts == [0, 5]
    assert process.terminated is True
    assert process.killed is False
    assert process.closed is True
    assert failures == [("stuck-task", "Generation worker exceeded 0s timeout")]
    assert "stuck-task" not in _running_task_ids
