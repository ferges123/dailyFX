import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure app can be imported
project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root / "backend"))

from app.database import SessionLocal, init_db
from app.models.settings import SettingsModel
from app.models.notification_preset import NotificationPresetModel
from scripts.rotate_secret_key import decrypt_with_key, encrypt_with_key, main

def test_rotate_secret_key(monkeypatch):
    # Initialize the test DB
    init_db()
    db = SessionLocal()
    try:
        # Clear existing
        db.query(SettingsModel).delete()
        db.query(NotificationPresetModel).delete()
        db.commit()

        old_key = "my-old-secret-key-123"
        new_key = "my-new-secret-key-456"

        # Create settings encrypted with old key
        settings = SettingsModel(
            id=1,
            encrypted_immich_api_key=encrypt_with_key("immich-api-value", old_key),
            encrypted_openai_api_key=encrypt_with_key("openai-api-value", old_key),
            encrypted_gemini_api_key=None,
        )
        db.add(settings)

        # Create notification preset encrypted with old key
        preset = NotificationPresetModel(
            name="Test Preset for Rotation",
            provider="telegram",
            encrypted_token=encrypt_with_key("telegram-token-value", old_key),
        )
        db.add(preset)
        db.commit()

        # Run rotation script main using monkeypatch args
        monkeypatch.setenv("OLD_SECRET_KEY", old_key)
        monkeypatch.setenv("NEW_SECRET_KEY", new_key)

        main()

        # Fetch records and verify they were rotated
        db.expire_all()
        updated_settings = db.query(SettingsModel).filter_by(id=1).first()
        assert updated_settings is not None
        assert decrypt_with_key(updated_settings.encrypted_immich_api_key, new_key) == "immich-api-value"
        assert decrypt_with_key(updated_settings.encrypted_openai_api_key, new_key) == "openai-api-value"
        assert updated_settings.encrypted_gemini_api_key is None

        # Verify old key cannot decrypt them now
        with pytest.raises(ValueError, match="Decryption failed"):
            decrypt_with_key(updated_settings.encrypted_immich_api_key, old_key)

        updated_preset = db.query(NotificationPresetModel).filter_by(name="Test Preset for Rotation").first()
        assert updated_preset is not None
        assert decrypt_with_key(updated_preset.encrypted_token, new_key) == "telegram-token-value"

        with pytest.raises(ValueError, match="Decryption failed"):
            decrypt_with_key(updated_preset.encrypted_token, old_key)

    finally:
        db.close()
