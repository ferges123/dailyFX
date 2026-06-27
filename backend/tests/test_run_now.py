import asyncio
from types import SimpleNamespace

from _contract_helpers import configure_contract_test_db, make_effect_preset_row
from fastapi import BackgroundTasks

from app.api.routes_schedules import trigger_schedule_now
from app.database import SessionLocal, init_db
from app.models.filter_preset import FilterPresetModel
from app.models.generation_history import GenerationHistoryModel
from app.models.generation_task import GenerationTaskModel
from app.models.schedule import ScheduleModel

test_db = configure_contract_test_db("run_now")


def _setup_run_now_db():
    init_db()
    db = SessionLocal()
    db.query(ScheduleModel).delete()
    db.query(FilterPresetModel).delete()
    db.query(GenerationHistoryModel).delete()
    db.query(GenerationTaskModel).delete()
    from app.models.effect_preset import EffectPresetModel

    db.query(EffectPresetModel).delete()
    db.commit()

    fp = FilterPresetModel(name="test-fp", album_ids_json="[]", person_filters_json="[]", media_type="photo")
    db.add(fp)
    ep = make_effect_preset_row(name="test-ep", groups_json="{}")
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


def test_trigger_schedule_now_enqueues_even_when_a_generation_is_running(monkeypatch):
    db, schedule = _setup_run_now_db()
    try:
        # Simulate an active running task in DB. This should not block queueing another run-now request.
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

        monkeypatch.setattr(
            "app.services.generation.task_flow.get_or_create_settings",
            lambda _db: SimpleNamespace(),
        )
        monkeypatch.setattr(
            "app.services.generation.task_flow.build_immich_client",
            lambda _settings: SimpleNamespace(),
        )

        async def fake_preview_run_now_assets(**_kwargs):
            return SimpleNamespace(items=[object()])

        monkeypatch.setattr("app.services.generation.task_flow.preview_run_now_assets", fake_preview_run_now_assets)

        bg_tasks = BackgroundTasks()

        async def run_once():
            return await trigger_schedule_now(schedule_id=schedule.id, background_tasks=bg_tasks, db=db)

        first = asyncio.run(run_once())
        second = asyncio.run(run_once())

        assert first.task_id != second.task_id
        assert first.task_id.startswith("man-")
        assert second.task_id.startswith("man-")

        queued_history = (
            db.query(GenerationHistoryModel)
            .filter(GenerationHistoryModel.status == "QUEUED")
            .order_by(GenerationHistoryModel.created_at.asc())
            .all()
        )
        assert len(queued_history) == 2
        assert [entry.task_id for entry in queued_history] == [first.task_id, second.task_id]
        assert all(entry.title.startswith("Queued:") for entry in queued_history)

        queued_tasks = db.query(GenerationTaskModel).order_by(GenerationTaskModel.created_at.asc()).all()
        assert len(queued_tasks) == 2
        assert [task.status for task in queued_tasks] == ["queued", "queued"]
        assert [task.task_id for task in queued_tasks] == [first.task_id, second.task_id]

    finally:
        db.close()
        test_db.unlink(missing_ok=True)


def test_trigger_schedule_now_updates_schedule_fields(monkeypatch):
    db, schedule = _setup_run_now_db()
    try:
        monkeypatch.setattr(
            "app.services.generation.task_flow.get_or_create_settings",
            lambda _db: SimpleNamespace(),
        )
        monkeypatch.setattr(
            "app.services.generation.task_flow.build_immich_client",
            lambda _settings: SimpleNamespace(),
        )

        async def fake_preview_run_now_assets(**_kwargs):
            return SimpleNamespace(items=[object()])

        monkeypatch.setattr("app.services.generation.task_flow.preview_run_now_assets", fake_preview_run_now_assets)

        bg_tasks = BackgroundTasks()

        async def run_once():
            return await trigger_schedule_now(schedule_id=schedule.id, background_tasks=bg_tasks, db=db)

        assert schedule.last_run_at is None
        assert schedule.next_run_at is None

        res = asyncio.run(run_once())

        db.refresh(schedule)
        assert schedule.last_run_at is not None
        assert schedule.next_run_at is not None
        assert schedule.last_task_id == res.task_id
        assert schedule.last_tick_status == "queued"
        assert schedule.last_tick_reason == "generation triggered manually"
    finally:
        db.close()
        test_db.unlink(missing_ok=True)
