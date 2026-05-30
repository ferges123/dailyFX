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
    from app.models.effect_preset import EffectPresetModel
    from app.models.filter_preset import FilterPresetModel
    from app.models.generation_task import GenerationTaskModel
    from app.models.notification_preset import NotificationPresetModel
    from app.models.schedule import ScheduleModel

    db.query(GenerationTaskModel).delete()
    db.query(NotificationPresetModel).delete()
    db.query(ScheduleModel).delete()
    db.query(FilterPresetModel).delete()
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
    from app.models.filter_preset import FilterPresetModel
    from app.models.schedule import ScheduleModel

    filter_preset = FilterPresetModel(
        name=filter_name,
        album_ids_json='["album1"]',
        person_filters_json="[]",
        media_type=media_type,
    )
    effect_preset = make_effect_preset_row(
        name=effect_name,
        groups_json=groups_json,
    )
    db.add(filter_preset)
    db.add(effect_preset)
    db.commit()

    schedule = ScheduleModel(
        name=name,
        enabled=True,
        schedule_expr=schedule_expr,
        filter_preset_id=filter_preset.id,
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
            filter_preset_id=1,
            effect_preset_id=1,
        )

    with pytest.raises(ValueError, match="at most 20 items"):
        ScheduleCreate(
            name="Valid schedule",
            enabled=False,
            schedule_expr="weekly",
            filter_preset_id=1,
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
            filter_preset_id=1,
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
            filter_preset_id=1,
            effect_preset_id=1,
            ai_image_provider="flux",
        )

    with pytest.raises(ValueError, match="String should have at most 100 characters"):
        ScheduleCreate(
            name="Valid schedule",
            enabled=False,
            schedule_expr="x" * 101,
            filter_preset_id=1,
            effect_preset_id=1,
        )
