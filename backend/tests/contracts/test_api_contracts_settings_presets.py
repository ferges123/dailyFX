from datetime import datetime, timezone

from _contract_helpers import configure_contract_test_db

from app.api.routes_presets import (
    create_effect_preset,
    create_notification_preset,
    create_people_preset,
    list_effect_presets,
    list_notification_presets,
    list_people_presets,
)
from app.api.routes_settings import read_settings, update_settings
from app.database import SessionLocal, init_db
from app.models.effect_preset import EffectPresetModel
from app.models.notification_preset import NotificationPresetModel
from app.models.people_preset import PeoplePresetModel
from app.models.settings import SettingsModel
from app.schemas.presets import EffectPresetCreate, NotificationPresetCreate, PeoplePresetCreate
from app.schemas.settings import SettingsUpdate

test_db = configure_contract_test_db("api_contracts_settings_presets")


def test_settings_contract():
    init_db()
    db = SessionLocal()
    try:
        db.query(SettingsModel).delete()
        db.commit()

        response = update_settings(
            SettingsUpdate(
                immich_url="https://immich.example.test",
                immich_api_key="immich-secret-1234",
                openai_api_key="sk-openai-9876",
                gemini_api_key="gemini-4567",
                openrouter_api_key="openrouter-1357",
                byteplus_api_key="byteplus-2468",
                xiaomi_api_key="mimo-8642",
                local_ai_base_url="https://local-ai.example.test/v1",
                local_ai_api_key="local-3141",
                ai_vision_hourly_limit=25,
                ai_image_hourly_limit=7,
                debug_mode=True,
                favorite_albums_json='["albums-a", "albums-b"]',
                ai_custom_prompt="Focus on faces",
            ),
            db,
        )

        assert response.model_dump(mode="json") == {
            "immich_url": "https://immich.example.test",
            "ai_vision_hourly_limit": 25,
            "ai_image_hourly_limit": 7,
            "debug_mode": True,
            "favorite_albums_json": '["albums-a", "albums-b"]',
            "ai_custom_prompt": "Focus on faces",
            "immich_api_key_masked": "********",
            "openai_api_key_masked": "********",
            "gemini_api_key_masked": "********",
            "openrouter_api_key_masked": "********",
            "byteplus_api_key_masked": "********",
            "xiaomi_api_key_masked": "********",
            "local_ai_base_url": "https://local-ai.example.test/v1",
            "local_ai_api_key_masked": "********",
            "retention_enabled": True,
            "retention_rejected_files_days": 7,
            "retention_rejected_metadata_days": 90,
            "retention_failed_files_days": 7,
            "retention_failed_metadata_days": 90,
            "retention_uploaded_files_days": 30,
            "retention_uploaded_metadata_days": 30,
            "retention_task_days": 30,
            "retention_audit_days": 180,
            "retention_backup_count": 7,
        }

        read_response = read_settings(db)
        assert read_response.model_dump(mode="json") == response.model_dump(mode="json")
    finally:
        db.close()


def test_people_presets_contract():
    init_db()
    db = SessionLocal()
    try:
        db.query(PeoplePresetModel).delete()
        db.commit()

        response = create_people_preset(
            PeoplePresetCreate(
                name="Contract Filter",
                album_ids=["album-1", "album-2"],
                person_filters=[
                    {"personId": "person-1", "mode": "obligatory"},
                    {"personId": "person-2", "mode": "exclude"},
                ],
                start_date="2026-05-01",
                end_date="2026-05-31",
                media_type="video",
            ),
            db,
        )
        row = db.get(PeoplePresetModel, response.id)
        row.created_at = datetime(2026, 5, 12, 10, 15, tzinfo=timezone.utc)
        db.commit()
        db.refresh(row)
        response.created_at = row.created_at

        response_dict = response.model_dump(mode="json")
        assert response_dict == {
            "id": response.id,
            "name": "Contract Filter",
            "album_ids": ["album-1", "album-2"],
            "person_filters": [
                {"personId": "person-1", "mode": "obligatory"},
                {"personId": "person-2", "mode": "exclude"},
            ],
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
            "media_type": "video",
            "created_at": "2026-05-12T10:15:00Z",
        }

        listed = list_people_presets(db)
        assert [item.model_dump(mode="json") for item in listed] == [response_dict]
    finally:
        db.close()


def test_effect_presets_contract():
    init_db()
    db = SessionLocal()
    try:
        db.query(EffectPresetModel).delete()
        db.commit()

        response = create_effect_preset(
            EffectPresetCreate(
                name="Contract Effect",
                groups={"collage": {"enabled": True, "weight": 1, "config": {"border": 8}}},
            ),
            db,
        )
        row = db.get(EffectPresetModel, response.id)
        row.created_at = datetime(2026, 5, 12, 10, 20, tzinfo=timezone.utc)
        db.commit()
        db.refresh(row)
        response.created_at = row.created_at

        response_dict = response.model_dump(mode="json")
        assert response_dict == {
            "id": response.id,
            "name": "Contract Effect",
            "groups": {"collage": {"enabled": True, "weight": 1, "config": {"border": 8}}},
            "created_at": "2026-05-12T10:20:00Z",
        }

        listed = list_effect_presets(db)
        assert [item.model_dump(mode="json") for item in listed] == [response_dict]
    finally:
        db.close()


def test_notification_presets_contract():
    init_db()
    db = SessionLocal()
    try:
        db.query(NotificationPresetModel).delete()
        db.commit()

        response = create_notification_preset(
            NotificationPresetCreate(
                name="Contract Notification",
                provider="telegram",
                url=None,
                topic="-123456789",
                token="telegram-secret-1234",
                webhook_url=None,
            ),
            db,
        )
        row = db.get(NotificationPresetModel, response.id)
        row.created_at = datetime(2026, 5, 12, 10, 25, tzinfo=timezone.utc)
        db.commit()
        db.refresh(row)
        response.created_at = row.created_at

        response_dict = response.model_dump(mode="json")
        assert response_dict == {
            "id": response.id,
            "name": "Contract Notification",
            "provider": "telegram",
            "url": None,
            "topic": "-123456789",
            "has_token": True,
            "token_masked": "tel...1234",
            "webhook_url": None,
            "created_at": "2026-05-12T10:25:00Z",
            "push_subscription_ids": [],
        }

        listed = list_notification_presets(db)
        assert [item.model_dump(mode="json") for item in listed] == [response_dict]
    finally:
        db.close()
