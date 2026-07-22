import os
from datetime import datetime, timezone

import pytest
from _contract_helpers import configure_contract_test_db, make_effect_preset_row, make_notification_preset_row

from app.database import SessionLocal, init_db
from app.models.settings import SettingsModel
from app.schemas.schedules import ScheduleCreate
from app.services.immich import get_or_create_settings
from app.workers.scheduler import run_scheduler_tick, should_run_automation

test_db = configure_contract_test_db("scheduler")


def _setup_scheduler_db():
    os.environ["APP_SECRET_KEY"] = "test-api-secret"
    import app.config

    app.config.get_settings.cache_clear()
    init_db()
    db = SessionLocal()
    from app.models.asset_usage import AssetUsageModel
    from app.models.effect_preset import EffectPresetModel
    from app.models.generation_history import GenerationHistoryModel
    from app.models.generation_task import GenerationTaskModel
    from app.models.notification_preset import NotificationPresetModel
    from app.models.people_preset import PeoplePresetModel
    from app.models.schedule import ScheduleModel

    db.query(GenerationTaskModel).delete()
    db.query(GenerationHistoryModel).delete()
    db.query(AssetUsageModel).delete()
    db.query(NotificationPresetModel).delete()
    db.query(ScheduleModel).delete()
    db.query(PeoplePresetModel).delete()
    db.query(EffectPresetModel).delete()
    db.query(SettingsModel).delete()
    db.commit()

    get_or_create_settings(db)
    db.commit()
    return db


def _create_scheduler_schedule(
    db,
    *,
    name: str,
    schedule_expr: str,
    filter_name: str,
    effect_name: str,
    groups_json: str,
    album_name: str,
    media_type: str = "photo",
):
    from app.models.people_preset import PeoplePresetModel
    from app.models.schedule import ScheduleModel

    people_preset = PeoplePresetModel(
        name=filter_name,
        album_ids_json='["album1"]',
        person_filters_json="[]",
        media_type=media_type,
    )
    effect_preset = make_effect_preset_row(
        name=effect_name,
        groups_json=groups_json,
    )
    db.add(people_preset)
    db.add(effect_preset)
    db.commit()

    schedule = ScheduleModel(
        name=name,
        enabled=True,
        schedule_expr=schedule_expr,
        people_preset_id=people_preset.id,
        effect_preset_id=effect_preset.id,
        album_name=album_name,
    )
    db.add(schedule)
    db.commit()
    return schedule


def test_should_run_automation_daily_and_weekly():
    now = datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc)
    assert should_run_automation("daily", None, now)
    assert should_run_automation("weekly", None, now)
    assert not should_run_automation("daily", datetime(2026, 5, 14, 8, 0, tzinfo=timezone.utc), now)
    assert not should_run_automation("weekly", datetime(2026, 5, 12, 8, 0, tzinfo=timezone.utc), now)
    assert should_run_automation("weekly", datetime(2026, 5, 1, 8, 0, tzinfo=timezone.utc), now)


def test_should_run_automation_daily_at_specific_time():
    before_time = datetime(2026, 5, 14, 7, 59, tzinfo=timezone.utc)
    after_time = datetime(2026, 5, 14, 8, 1, tzinfo=timezone.utc)

    assert not should_run_automation("daily@08:00", datetime(2026, 5, 13, 9, 0, tzinfo=timezone.utc), before_time)
    assert should_run_automation("daily@08:00", datetime(2026, 5, 13, 9, 0, tzinfo=timezone.utc), after_time)


def test_should_run_automation_weekly_on_selected_days_and_time():
    wednesday_before = datetime(2026, 5, 13, 7, 59, tzinfo=timezone.utc)
    wednesday_after = datetime(2026, 5, 13, 8, 1, tzinfo=timezone.utc)
    thursday_after = datetime(2026, 5, 14, 8, 1, tzinfo=timezone.utc)

    assert not should_run_automation(
        "weekly@wed@08:00",
        datetime(2026, 5, 12, 9, 0, tzinfo=timezone.utc),
        wednesday_before,
    )
    assert should_run_automation(
        "weekly@wed@08:00",
        datetime(2026, 5, 12, 9, 0, tzinfo=timezone.utc),
        wednesday_after,
    )
    assert not should_run_automation(
        "weekly@wed@08:00",
        datetime(2026, 5, 13, 9, 0, tzinfo=timezone.utc),
        thursday_after,
    )


def test_should_run_automation_weekdays_and_weekends_presets():
    thursday_after = datetime(2026, 5, 14, 8, 1, tzinfo=timezone.utc)
    saturday_after = datetime(2026, 5, 16, 8, 1, tzinfo=timezone.utc)

    assert should_run_automation("weekdays@08:00", datetime(2026, 5, 13, 9, 0, tzinfo=timezone.utc), thursday_after)
    assert not should_run_automation("weekdays@08:00", datetime(2026, 5, 14, 9, 0, tzinfo=timezone.utc), saturday_after)
    assert should_run_automation("weekends@08:00", datetime(2026, 5, 15, 9, 0, tzinfo=timezone.utc), saturday_after)


def test_scheduler_tick_updates_last_run_and_dispatches(monkeypatch):
    db = _setup_scheduler_db()
    try:
        schedule = _create_scheduler_schedule(
            db,
            name="Test Schedule",
            schedule_expr="daily",
            filter_name="Test Filter Preset",
            effect_name="Test Effect Preset",
            groups_json='{"collage": {"enabled": true, "weight": 1, "config": {"asset_count": 4}}}',
            album_name="Test Album",
        )

        called: dict[str, str] = {}

        async def fake_run_generation_cycle(session, settings, task_id, *args, **kwargs):
            called["task_id"] = task_id
            called["settings_id"] = str(settings.id)
            called["schedule_id"] = kwargs.get("schedule_id")
            return {"ok": True}

        monkeypatch.setattr("app.workers.scheduler.run_generation_cycle", fake_run_generation_cycle)

        outcome = run_scheduler_tick(db=db, now=datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc))

        db.refresh(schedule)
        assert outcome["status"] == "completed"
        assert outcome["schedules_checked"] == 1
        assert outcome["schedules_run"] == 1
        assert called["settings_id"] == "1"
        assert called["schedule_id"] == schedule.id
        assert called["task_id"].startswith(f"auto-s{schedule.id}-")
        assert schedule.last_run_at is not None
        assert schedule.last_tick_status == "completed"
        assert schedule.last_tick_reason == "generation completed"
        assert schedule.next_run_at is not None
    finally:
        db.close()


def test_scheduler_tick_consumes_queued_manual_payload(monkeypatch):
    from app.immich.client import ImmichPersonFilter, ImmichSearchFilters
    from app.models.generation_task import GenerationTaskModel
    from app.services.generation.run_now import build_run_now_task_payload

    db = _setup_scheduler_db()
    try:
        notif_one = make_notification_preset_row(name="Notif One", provider="web")
        notif_two = make_notification_preset_row(name="Notif Two", provider="web")
        db.add_all([notif_one, notif_two])
        db.commit()

        payload_json = build_run_now_task_payload(
            filters=ImmichSearchFilters(
                album_ids=["album-1"],
                person_filters=[ImmichPersonFilter(person_id="person-1", mode="exclude")],
                taken_after=None,
                taken_before=None,
                media_type="video",
            ),
            effects_config={"instafilter": {"enabled": True, "weight": 1, "config": {}}},
            selected_asset_ids=["asset-1"],
            schedule_id=11,
            album_name="Queue Album",
            notification_preset_ids=[notif_one.id, notif_two.id],
        ).to_json()

        db.add(
            GenerationTaskModel(
                task_id="queued-manual-1",
                status="queued",
                step="queued",
                progress=0.0,
                payload_json=payload_json,
            )
        )
        db.commit()

        called: dict[str, object] = {}

        async def fake_run_generation_cycle(session, settings, task_id, *args, **kwargs):
            called["task_id"] = task_id
            called["filters"] = kwargs.get("filters")
            called["effects_config"] = kwargs.get("effects_config")
            called["selected_asset_ids"] = kwargs.get("selected_asset_ids")
            called["schedule_id"] = kwargs.get("schedule_id")
            called["album_name"] = kwargs.get("album_name")
            called["notification_presets"] = kwargs.get("notification_presets")
            return {"ok": True}

        monkeypatch.setattr("app.workers.scheduler.run_generation_cycle", fake_run_generation_cycle)

        outcome = run_scheduler_tick(db=db, now=datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc))

        assert outcome["status"] == "completed"
        assert outcome["manual_run"] == "queued-manual-1"
        assert called["task_id"] == "queued-manual-1"
        assert called["schedule_id"] == 11
        assert called["album_name"] == "Queue Album"
        assert called["selected_asset_ids"] == ["asset-1"]
        assert called["effects_config"] == {"instafilter": {"enabled": True, "weight": 1, "config": {}}}
        assert [preset.id for preset in called["notification_presets"]] == [notif_one.id, notif_two.id]
        filters = called["filters"]
        assert isinstance(filters, ImmichSearchFilters)
        assert filters.album_ids == ["album-1"]
        assert filters.person_filters == [ImmichPersonFilter(person_id="person-1", mode="exclude")]
        assert filters.media_type == "video"
    finally:
        db.close()


def test_scheduler_tick_starts_without_automation_filter(monkeypatch):
    db = _setup_scheduler_db()
    try:
        schedule = _create_scheduler_schedule(
            db,
            name="Test Schedule 2",
            schedule_expr="daily",
            filter_name="Test Filter Preset 2",
            effect_name="Test Effect Preset 2",
            groups_json='{"instafilter": {"enabled": true, "weight": 1, "config": {"styles": ["random"]}}}',
            album_name="Test Album",
        )

        called: dict[str, str] = {}

        async def fake_run_generation_cycle(session, settings, task_id, *args, **kwargs):
            called["task_id"] = task_id
            called["settings_id"] = str(settings.id)
            return {"ok": True}

        monkeypatch.setattr("app.workers.scheduler.run_generation_cycle", fake_run_generation_cycle)

        outcome = run_scheduler_tick(db=db, now=datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc))

        db.refresh(schedule)
        assert outcome["status"] == "completed"
        assert called["settings_id"] == "1"
        assert called["task_id"].startswith(f"auto-s{schedule.id}-")
        assert schedule.last_run_at is not None
        assert schedule.last_tick_status == "completed"
    finally:
        db.close()


def test_scheduler_tick_records_not_due_state():
    db = _setup_scheduler_db()
    try:
        schedule = _create_scheduler_schedule(
            db,
            name="Test Schedule 3",
            schedule_expr="weekdays@08:00",
            filter_name="Test Filter Preset 3",
            effect_name="Test Effect Preset 3",
            groups_json='{"collage": {"enabled": true, "weight": 1, "config": {"asset_count": 4}}}',
            album_name="Test Album",
        )
        schedule.last_run_at = datetime(2026, 5, 14, 9, 0, tzinfo=timezone.utc)
        db.commit()

        outcome = run_scheduler_tick(db=db, now=datetime(2026, 5, 14, 12, 0, tzinfo=timezone.utc))

        db.refresh(schedule)
        assert outcome["status"] == "completed"
        assert outcome["schedules_checked"] == 1
        assert outcome["schedules_run"] == 0
        assert outcome["results"][0]["status"] == "not_due"
    finally:
        db.close()


def test_schedule_create_enforces_text_limits():
    with pytest.raises(ValueError, match="String should have at most 255 characters"):
        ScheduleCreate(
            name="x" * 256,
            enabled=False,
            schedule_expr="weekly",
            people_preset_id=1,
            effect_preset_id=1,
        )

    with pytest.raises(ValueError, match="at most 20 items"):
        ScheduleCreate(
            name="Valid schedule",
            enabled=False,
            schedule_expr="weekly",
            people_preset_id=1,
            effect_preset_id=1,
            notification_preset_ids=list(range(21)),
        )


def test_schedule_create_rejects_invalid_provider_values():
    with pytest.raises(
        ValueError,
        match="Input should be 'none', 'openai', 'gemini', 'xiaomi', 'openrouter' or 'local'",
    ):
        ScheduleCreate(
            name="Valid schedule",
            enabled=False,
            schedule_expr="weekly",
            people_preset_id=1,
            effect_preset_id=1,
            ai_vision_provider="anthropic",
        )

    with pytest.raises(
        ValueError,
        match="Input should be 'none', 'openai', 'gemini', 'openrouter', 'byteplus' or 'local'",
    ):
        ScheduleCreate(
            name="Valid schedule",
            enabled=False,
            schedule_expr="weekly",
            people_preset_id=1,
            effect_preset_id=1,
            ai_image_provider="flux",
        )

    with pytest.raises(ValueError, match="String should have at most 100 characters"):
        ScheduleCreate(
            name="Valid schedule",
            enabled=False,
            schedule_expr="x" * 101,
            people_preset_id=1,
            effect_preset_id=1,
        )


def test_reset_stuck_tasks_at_runtime():
    from datetime import timedelta

    from app.models.generation_history import GenerationHistoryModel
    from app.models.generation_task import GenerationTaskModel
    from app.workers.scheduler import _reset_stuck_tasks_at_runtime

    db = _setup_scheduler_db()
    try:
        now = datetime.now(timezone.utc)

        # 1. Create a task that is "running" but updated recently (should NOT be reset)
        recent_task = GenerationTaskModel(
            task_id="recent-task-1", status="running", step="selecting_asset", updated_at=now - timedelta(minutes=5)
        )
        recent_history = GenerationHistoryModel(
            task_id="recent-task-1",
            generation_type="collage",
            status="RUNNING",
            title="Recent Task",
            summary="Testing",
            source_asset_ids="[]",
            config_json="{}",
            updated_at=now - timedelta(minutes=5),
        )

        # 2. Create a task that is "running" and updated long ago (should be reset)
        stuck_task = GenerationTaskModel(
            task_id="stuck-task-1", status="running", step="selecting_asset", updated_at=now - timedelta(minutes=20)
        )
        stuck_history = GenerationHistoryModel(
            task_id="stuck-task-1",
            generation_type="collage",
            status="RUNNING",
            title="Stuck Task",
            summary="Testing",
            source_asset_ids="[]",
            config_json="{}",
            updated_at=now - timedelta(minutes=20),
        )

        db.add(recent_task)
        db.add(recent_history)
        db.add(stuck_task)
        db.add(stuck_history)
        db.commit()

        # Run cleanup
        _reset_stuck_tasks_at_runtime(db, now)

        # Verify results
        db.refresh(recent_task)
        db.refresh(recent_history)
        db.refresh(stuck_task)
        db.refresh(stuck_history)

        assert recent_task.status == "running"
        assert recent_history.status == "RUNNING"

        assert stuck_task.status == "failed"
        assert stuck_task.error == "Task timed out (stuck in running for more than 15 minutes)"
        assert stuck_history.status == "FAILED"
        assert stuck_history.error == "Task timed out (stuck in RUNNING for more than 15 minutes)"
    finally:
        db.close()


def test_cleanup_old_results_retention(tmp_path):
    from datetime import timedelta

    from app.models.generation_history import GenerationHistoryModel
    from app.workers.scheduler import _cleanup_old_results

    db = _setup_scheduler_db()
    settings = get_or_create_settings(db)
    settings.retention_rejected_metadata_days = 7
    settings.retention_uploaded_files_days = 7
    db.commit()
    try:
        now = datetime.now(timezone.utc)

        # 1. Create a recent non-REJECTED entry (5 days ago, should be kept)
        recent_non_rejected = GenerationHistoryModel(
            task_id="recent-non-rejected",
            generation_type="collage",
            status="UPLOADED",
            title="Recent Non-Rejected",
            summary="Testing",
            source_asset_ids="[]",
            config_json="{}",
            created_at=now - timedelta(days=5),
            output_path=str(tmp_path / "results" / "recent-non-rejected.png"),
        )

        # 2. Create an old non-REJECTED entry (31 days ago, should be pruned)
        old_non_rejected = GenerationHistoryModel(
            task_id="old-non-rejected",
            generation_type="collage",
            status="UPLOADED",
            title="Old Non-Rejected",
            summary="Testing",
            source_asset_ids="[]",
            config_json="{}",
            created_at=now - timedelta(days=31),
            output_path=str(tmp_path / "results" / "old-non-rejected.png"),
        )

        # 3. Create a recent REJECTED entry (3 days ago, should be kept)
        recent_rejected = GenerationHistoryModel(
            task_id="recent-rejected",
            generation_type="collage",
            status="REJECTED",
            title="Recent Rejected",
            summary="Testing",
            source_asset_ids="[]",
            config_json="{}",
            created_at=now - timedelta(days=3),
            output_path=str(tmp_path / "results" / "recent-rejected.png"),
        )

        # 4. Create an old REJECTED entry (8 days ago, should be pruned)
        old_rejected = GenerationHistoryModel(
            task_id="old-rejected",
            generation_type="collage",
            status="REJECTED",
            title="Old Rejected",
            summary="Testing",
            source_asset_ids="[]",
            config_json="{}",
            created_at=now - timedelta(days=8),
            output_path=str(tmp_path / "results" / "old-rejected.png"),
        )

        # 5. Create 60 recent non-REJECTED entries (to verify 50 entry limit is removed)
        many_recent = []
        for i in range(60):
            many_recent.append(
                GenerationHistoryModel(
                    task_id=f"many-recent-{i}",
                    generation_type="collage",
                    status="UPLOADED",
                    title=f"Many Recent {i}",
                    summary="Testing",
                    source_asset_ids="[]",
                    config_json="{}",
                    created_at=now - timedelta(days=1),
                    output_path=str(tmp_path / "results" / f"many-recent-{i}.png"),
                )
            )

        db.add(recent_non_rejected)
        db.add(old_non_rejected)
        db.add(recent_rejected)
        db.add(old_rejected)
        for row in many_recent:
            db.add(row)
        db.commit()

        # Create dummy result files in tmp_path
        results_dir = tmp_path / "results"
        results_dir.mkdir()
        orphan = results_dir / "orphan.png"
        orphan.write_bytes(b"orphan")
        os.utime(orphan, (now.timestamp() - 8 * 86400, now.timestamp() - 8 * 86400))
        recent_orphan = results_dir / "recent-orphan.png"
        recent_orphan.write_bytes(b"keep")
        for suffix in [".png", ".png.thumb_400.jpg"]:
            (results_dir / f"recent-non-rejected{suffix}").touch()
            (results_dir / f"old-non-rejected{suffix}").touch()
            (results_dir / f"recent-rejected{suffix}").touch()
            (results_dir / f"old-rejected{suffix}").touch()
            for i in range(60):
                (results_dir / f"many-recent-{i}{suffix}").touch()

        # Run cleanup
        _cleanup_old_results(results_dir)

        # Check DB entries
        kept_tasks = [row.task_id for row in db.query(GenerationHistoryModel.task_id).all()]
        assert "recent-non-rejected" in kept_tasks
        assert "recent-rejected" in kept_tasks
        assert "old-non-rejected" not in kept_tasks
        assert "old-rejected" not in kept_tasks

        # Verify the 60 recent entries are all kept (no 50 entry limit)
        for i in range(60):
            assert f"many-recent-{i}" in kept_tasks

        # Check files
        assert (results_dir / "recent-non-rejected.png").exists()
        assert (results_dir / "recent-rejected.png").exists()
        assert not (results_dir / "old-non-rejected.png").exists()
        # Old REJECTED deletes output_path:
        assert not (results_dir / "old-rejected.png").exists()
        assert not orphan.exists()
        assert recent_orphan.exists()
    finally:
        db.close()
