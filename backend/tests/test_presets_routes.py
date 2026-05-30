
import pytest
from _contract_helpers import configure_contract_test_db

from app.api.routes_presets import (
    create_notification_preset,
    list_notification_presets,
    update_notification_preset,
)
from app.database import SessionLocal, init_db
from app.models.notification_preset import NotificationPresetModel
from app.schemas.presets import FilterPresetCreate, NotificationPresetCreate, PersonFilterItem
from app.security import decrypt_secret

test_db = configure_contract_test_db("presets")


def test_notification_presets_masking_and_updating():
    import app.config

    app.config.get_settings.cache_clear()

    init_db()
    db = SessionLocal()
    try:
        db.query(NotificationPresetModel).delete()
        db.commit()

        # 1. Create a notification preset
        body = NotificationPresetCreate(
            name="Test Preset",
            provider="telegram",
            url=None,
            topic="-123456789",
            token="telegram-bot-token-1234567890",
            webhook_url=None,
        )

        response = create_notification_preset(body, db)

        # Verify response masking
        assert response.name == "Test Preset"
        assert response.provider == "telegram"
        assert response.has_token is True
        assert response.token_masked == "tel...7890"  # telegram-bot-token-1234567890 -> tel...7890

        # Verify DB is encrypted
        row = db.query(NotificationPresetModel).filter_by(id=response.id).first()
        assert row is not None
        assert row.encrypted_token != "telegram-bot-token-1234567890"
        assert decrypt_secret(row.encrypted_token) == "telegram-bot-token-1234567890"

        # 2. Update with the same name, but body has the masked token
        update_body = NotificationPresetCreate(
            name="Test Preset Updated",
            provider="telegram",
            url=None,
            topic="-123456789",
            token="tel...7890",  # masked token sent
            webhook_url=None,
        )

        update_response = update_notification_preset(response.id, update_body, db)

        # The token should NOT change in the database
        row_updated = db.query(NotificationPresetModel).filter_by(id=response.id).first()
        assert row_updated.name == "Test Preset Updated"
        assert decrypt_secret(row_updated.encrypted_token) == "telegram-bot-token-1234567890"
        assert update_response.token_masked == "tel...7890"

        # 3. Update with a new token
        update_body_new = NotificationPresetCreate(
            name="Test Preset Updated Again",
            provider="telegram",
            url=None,
            topic="-123456789",
            token="new-telegram-token-555555",
            webhook_url=None,
        )

        update_response_new = update_notification_preset(response.id, update_body_new, db)

        # Token should be updated in the database
        row_updated_new = db.query(NotificationPresetModel).filter_by(id=response.id).first()
        assert decrypt_secret(row_updated_new.encrypted_token) == "new-telegram-token-555555"
        assert update_response_new.token_masked == "new...5555"

        # 4. List notification presets and verify the masked token is returned
        all_presets = list_notification_presets(db)
        assert len(all_presets) >= 1
        listed = [p for p in all_presets if p.id == response.id][0]
        assert listed.token_masked == "new...5555"
        assert listed.has_token is True

    finally:
        db.close()
        test_db.unlink(missing_ok=True)


def test_notification_preset_rejects_non_http_urls():
    with pytest.raises(ValueError, match="Server URL must be an absolute http:// or https:// URL"):
        NotificationPresetCreate(
            name="Bad preset",
            provider="ntfy",
            url="ftp://example.com",
            topic="dailyfx",
            token=None,
            webhook_url=None,
        )

    with pytest.raises(ValueError, match="Webhook URL must be an absolute http:// or https:// URL"):
        NotificationPresetCreate(
            name="Bad webhook",
            provider="web",
            url=None,
            topic=None,
            token=None,
            webhook_url="javascript:alert(1)",
        )


def test_filter_preset_rejects_invalid_dates_and_long_names():
    with pytest.raises(ValueError, match="String should have at most 255 characters"):
        FilterPresetCreate(
            name="x" * 256,
            album_ids=[],
            person_filters=[],
            start_date=None,
            end_date=None,
            media_type="photo",
        )

    with pytest.raises(ValueError, match="must be a valid YYYY-MM-DD date"):
        FilterPresetCreate(
            name="Valid name",
            album_ids=[],
            person_filters=[],
            start_date="2026-13-01",
            end_date=None,
            media_type="photo",
        )

    with pytest.raises(ValueError, match="start_date must be on or before end_date"):
        FilterPresetCreate(
            name="Valid name",
            album_ids=[],
            person_filters=[],
            start_date="2026-06-02",
            end_date="2026-06-01",
            media_type="photo",
        )

    with pytest.raises(ValueError, match="at most 100 items"):
        FilterPresetCreate(
            name="Valid name",
            album_ids=[f"album-{index}" for index in range(101)],
            person_filters=[],
            start_date=None,
            end_date=None,
            media_type="photo",
        )

    with pytest.raises(ValueError, match="at most 100 items"):
        FilterPresetCreate(
            name="Valid name",
            album_ids=[],
            person_filters=[PersonFilterItem(personId=f"person-{index}") for index in range(101)],
            start_date=None,
            end_date=None,
            media_type="photo",
        )


def test_person_filter_mode_rejects_invalid_value():
    with pytest.raises(ValueError, match="Input should be 'optional', 'obligatory' or 'exclude'"):
        PersonFilterItem(personId="person-1", mode="maybe")
