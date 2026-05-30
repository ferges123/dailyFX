import asyncio

import pytest
from _contract_helpers import configure_contract_test_db, make_effect_preset_row
from fastapi import BackgroundTasks, HTTPException

from app.api.routes_schedules import trigger_schedule_now
from app.database import SessionLocal, init_db
from app.models.filter_preset import FilterPresetModel
from app.models.generation_history import GenerationHistoryModel
from app.models.schedule import ScheduleModel

test_db = configure_contract_test_db("run_now")


def _setup_run_now_db():
    init_db()
    db = SessionLocal()
    fp = FilterPresetModel(name="test-fp", album_ids_json="[]", person_filters_json="[]", media_type="photo")
    db.add(fp)
    ep = make_effect_preset_row(name="test-ep", groups_json="[]")
    db.add(ep)
    db.commit()

    schedule = ScheduleModel(
        name="Test Schedule",
        enabled=True,
        schedule_expr="daily",
        filter_preset_id=fp.id,
        effect_preset_id=ep.id,
    )
    db.add(schedule)
    db.commit()
    return db, schedule


def test_trigger_schedule_now_concurrency_lock():
    db, schedule = _setup_run_now_db()
    try:
        # 1. Simulate an active running task in DB
        running_task = GenerationHistoryModel(
            task_id="active-task-123",
            status="RUNNING",
            generation_type="collage",
            title="Active Task",
            summary="",
            source_asset_ids="[]",
            config_json="{}",
        )
        db.add(running_task)
        db.commit()

        # 2. Try to call trigger_schedule_now and verify it raises 409
        bg_tasks = BackgroundTasks()

        async def run_failing():
            await trigger_schedule_now(schedule_id=schedule.id, background_tasks=bg_tasks, db=db)

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(run_failing())

        assert exc_info.value.status_code == 409
        assert "already running" in exc_info.value.detail

        # 3. Mark task as COMPLETED and verify it doesn't raise 409 anymore
        running_task.status = "COMPLETED"
        db.commit()

        async def run_succeeding():
            # This should not throw 409. It may still fail on Immich config/connectivity, which is expected.
            await trigger_schedule_now(schedule_id=schedule.id, background_tasks=bg_tasks, db=db)

        try:
            asyncio.run(run_succeeding())
        except HTTPException as e:
            assert e.status_code != 409
        except Exception:
            # Bypassing configuration or connection errors since Immich client is not configured
            pass

    finally:
        db.close()
        test_db.unlink(missing_ok=True)
