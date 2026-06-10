import os
from pathlib import Path

from _contract_helpers import make_effect_preset_row, make_notification_preset_row

import pytest
from fastapi import HTTPException

from app.api.routes_schedules import create_schedule, list_schedules, update_schedule
from app.database import SessionLocal, init_db
from app.models.effect_preset import EffectPresetModel
from app.models.filter_preset import FilterPresetModel
from app.models.notification_preset import NotificationPresetModel
from app.models.schedule import ScheduleModel, schedule_notification_preset_association
from app.schemas.schedules import ScheduleCreate, ScheduleResponse, ScheduleRunNowResponse, ScheduleUpdate

os.environ["APP_ENV"] = "development"
os.environ["APP_SECRET_KEY"] = "test-api-secret"
test_db = Path("/tmp/immich_ai_creator_test_schedule_contracts.db")
test_db.unlink(missing_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{test_db}"


def test_schedule_response_adapter_preserves_preset_names_and_ids():
    init_db()
    db = SessionLocal()
    try:
        db.execute(schedule_notification_preset_association.delete())
        db.query(ScheduleModel).delete()
        db.query(NotificationPresetModel).delete()
        db.query(FilterPresetModel).delete()
        db.query(EffectPresetModel).delete()
        db.commit()

        filter_preset = FilterPresetModel(
            name="Filter A",
            album_ids_json='["album-1"]',
            person_filters_json="[]",
            media_type="photo",
        )
        effect_preset = make_effect_preset_row(
            name="Effect A",
            groups_json='{"collage": {"enabled": true, "weight": 1, "config": {}}}',
        )
        notif_one = make_notification_preset_row(name="Notify One", provider="web")
        notif_two = make_notification_preset_row(name="Notify Two", provider="telegram")
        db.add_all([filter_preset, effect_preset, notif_one, notif_two])
        db.commit()

        schedule = ScheduleModel(
            name="Schedule A",
            enabled=True,
            schedule_expr="daily",
            filter_preset_id=filter_preset.id,
            effect_preset_id=effect_preset.id,
            album_name="Album A",
            ai_vision_provider="local",
            ai_vision_model="qwen2.5-vl",
            ai_image_provider="local",
            ai_image_model="flux.1",
        )
        schedule.notification_presets = [notif_one, notif_two]
        db.add(schedule)
        db.commit()
        db.refresh(schedule)

        response = ScheduleResponse.from_model(
            schedule,
            filter_preset_name=filter_preset.name,
            effect_preset_name=effect_preset.name,
        )

        assert response.model_dump() == {
            "id": schedule.id,
            "name": "Schedule A",
            "enabled": True,
            "schedule_expr": "daily",
            "filter_preset_id": filter_preset.id,
            "effect_preset_id": effect_preset.id,
            "notification_preset_ids": [notif_one.id, notif_two.id],
            "album_name": "Album A",
            "ai_vision_provider": "local",
            "ai_vision_model": "qwen2.5-vl",
            "ai_image_provider": "local",
            "ai_image_model": "flux.1",
            "ai_prompt_enrichment": False,
            "ai_photo_selection_enabled": False,
            "last_run_at": None,
            "next_run_at": None,
            "last_tick_status": None,
            "last_tick_reason": None,
            "last_task_id": None,
            "created_at": schedule.created_at,
            "filter_preset_name": "Filter A",
            "effect_preset_name": "Effect A",
            "notification_preset_names": ["Notify One", "Notify Two"],
        }
    finally:
        db.close()
        test_db.unlink(missing_ok=True)


def test_schedule_run_now_response_contract():
    payload = ScheduleRunNowResponse(message="Generation triggered", task_id="man-abc123")
    assert payload.model_dump() == {
        "message": "Generation triggered",
        "task_id": "man-abc123",
    }


def test_list_schedules_returns_adapter_values():
    init_db()
    db = SessionLocal()
    try:
        db.execute(schedule_notification_preset_association.delete())
        db.query(ScheduleModel).delete()
        db.query(NotificationPresetModel).delete()
        db.query(FilterPresetModel).delete()
        db.query(EffectPresetModel).delete()
        db.commit()

        filter_preset = FilterPresetModel(
            name="Filter B",
            album_ids_json='["album-2"]',
            person_filters_json="[]",
            media_type="video",
        )
        effect_preset = make_effect_preset_row(
            name="Effect B",
            groups_json='{"instafilter": {"enabled": true, "weight": 1, "config": {}}}',
        )
        notif = make_notification_preset_row(name="Notify B", provider="web")
        db.add_all([filter_preset, effect_preset, notif])
        db.commit()

        schedule = ScheduleModel(
            name="Schedule B",
            enabled=False,
            schedule_expr="weekly",
            filter_preset_id=filter_preset.id,
            effect_preset_id=effect_preset.id,
            album_name="Album B",
            ai_vision_provider="local",
            ai_vision_model="qwen2.5-vl",
            ai_image_provider="local",
            ai_image_model="flux.1",
        )
        db.add(schedule)
        db.commit()
        db.execute(
            schedule_notification_preset_association.insert().values(
                schedule_id=schedule.id,
                notification_preset_id=notif.id,
            )
        )
        db.commit()

        rows = list_schedules(db)

        assert len(rows) == 1
        response = rows[0]
        assert isinstance(response, ScheduleResponse)
        assert response.filter_preset_name == "Filter B"
        assert response.effect_preset_name == "Effect B"
        assert response.notification_preset_names == ["Notify B"]
        assert response.notification_preset_ids == [notif.id]
    finally:
        db.close()
        test_db.unlink(missing_ok=True)


def test_schedule_response_includes_ai_photo_selection_flag():
    init_db()
    db = SessionLocal()
    try:
        filter_preset = FilterPresetModel(name="Filter validation create", album_ids_json="[]", person_filters_json="[]")
        effect_preset = make_effect_preset_row(
            name="Effect validation create", groups_json='{"instafilter": {"enabled": true}}'
        )
        db.add_all([filter_preset, effect_preset])
        db.commit()
        schedule = ScheduleModel(
            name="Schedule validation create",
            enabled=False,
            schedule_expr="weekly",
            filter_preset_id=filter_preset.id,
            effect_preset_id=effect_preset.id,
            album_name="Album C",
            ai_vision_provider="local",
            ai_vision_model="qwen2.5-vl",
            ai_image_provider="none",
            ai_image_model="gpt-image-1",
            ai_photo_selection_enabled=True,
        )
        db.add(schedule)
        db.commit()
        db.refresh(schedule)

        response = ScheduleResponse.from_model(schedule)

        assert response.ai_photo_selection_enabled is True
    finally:
        db.close()
        test_db.unlink(missing_ok=True)


def test_create_schedule_rejects_ai_photo_selection_without_vision_provider():
    init_db()
    db = SessionLocal()
    try:
        filter_preset = FilterPresetModel(name="Filter C", album_ids_json="[]", person_filters_json="[]")
        effect_preset = make_effect_preset_row(name="Effect C", groups_json='{"instafilter": {"enabled": true}}')
        db.add_all([filter_preset, effect_preset])
        db.commit()

        body = ScheduleCreate(
            name="Schedule C",
            filter_preset_id=filter_preset.id,
            effect_preset_id=effect_preset.id,
            ai_vision_provider="none",
            ai_photo_selection_enabled=True,
        )

        with pytest.raises(HTTPException) as exc:
            create_schedule(body, db)

        assert exc.value.status_code == 422
        assert "AI photo selection requires an AI Vision provider" in str(exc.value.detail)
    finally:
        db.close()
        test_db.unlink(missing_ok=True)


def test_update_schedule_rejects_ai_photo_selection_without_vision_provider():
    init_db()
    db = SessionLocal()
    try:
        filter_preset = FilterPresetModel(name="Filter validation update", album_ids_json="[]", person_filters_json="[]")
        effect_preset = make_effect_preset_row(
            name="Effect validation update", groups_json='{"instafilter": {"enabled": true}}'
        )
        db.add_all([filter_preset, effect_preset])
        db.commit()

        schedule = ScheduleModel(
            name="Schedule D",
            enabled=False,
            schedule_expr="weekly",
            filter_preset_id=filter_preset.id,
            effect_preset_id=effect_preset.id,
        )
        db.add(schedule)
        db.commit()

        body = ScheduleUpdate(
            name="Schedule D",
            filter_preset_id=filter_preset.id,
            effect_preset_id=effect_preset.id,
            ai_vision_provider="none",
            ai_photo_selection_enabled=True,
        )

        with pytest.raises(HTTPException) as exc:
            update_schedule(schedule.id, body, db)

        assert exc.value.status_code == 422
        assert "AI photo selection requires an AI Vision provider" in str(exc.value.detail)
    finally:
        db.close()
        test_db.unlink(missing_ok=True)
