#!/usr/bin/env python3
import base64
import hashlib
import os
import shutil
import sys
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

# Add backend directory to Python path
backend_dir = Path(__file__).resolve().parents[1]
sys.path.append(str(backend_dir))

from app.database import SessionLocal, get_settings
from app.models.notification_preset import NotificationPresetModel
from app.models.settings import SettingsModel


def get_fernet(secret_key: str) -> Fernet:
    digest = hashlib.sha256(secret_key.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def decrypt_with_key(value: str | None, secret_key: str) -> str | None:
    if not value:
        return None
    f = get_fernet(secret_key)
    try:
        return f.decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        raise ValueError("Decryption failed. Please check if the old secret key is correct.")


def encrypt_with_key(value: str | None, secret_key: str) -> str | None:
    if not value:
        return None
    f = get_fernet(secret_key)
    return f.encrypt(value.encode("utf-8")).decode("utf-8")


def main():
    # Read keys from env or command line
    old_key = os.environ.get("OLD_SECRET_KEY")
    new_key = os.environ.get("NEW_SECRET_KEY")

    if not old_key or not new_key:
        if len(sys.argv) == 3:
            old_key = sys.argv[1]
            new_key = sys.argv[2]
        else:
            print("Error: Missing old or new secret key.")
            print("Usage: python rotate_secret_key.py <old_key> <new_key>")
            print("Or set OLD_SECRET_KEY and NEW_SECRET_KEY environment variables.")
            sys.exit(1)

    if old_key == new_key:
        print("Old and new secret keys are identical. No rotation needed.")
        sys.exit(0)

    settings = get_settings()
    db_url = settings.database_url

    # Perform backup if SQLite
    if db_url.startswith("sqlite:///"):
        db_path = Path(db_url.replace("sqlite:///", ""))
        if not db_path.is_absolute():
            db_path = (backend_dir / db_path).resolve()
            if not db_path.exists():
                db_path = Path(db_url.replace("sqlite:///", "")).resolve()

        if db_path.exists():
            backup_path = db_path.with_suffix(db_path.suffix + ".backup")
            print(f"Creating database backup at: {backup_path}")
            shutil.copy2(db_path, backup_path)
        else:
            print(f"Warning: Database path {db_path} not found. Backup skipped.")

    db = SessionLocal()
    try:
        print("Re-encrypting database settings...")

        # 1. Update settings
        settings_records = db.query(SettingsModel).all()
        settings_fields = [
            "encrypted_immich_api_key",
            "encrypted_openai_api_key",
            "encrypted_gemini_api_key",
            "encrypted_openrouter_api_key",
            "encrypted_byteplus_api_key",
            "encrypted_xiaomi_api_key",
            "encrypted_local_ai_api_key",
        ]

        settings_updated = 0
        for record in settings_records:
            updated = False
            for field in settings_fields:
                val = getattr(record, field)
                if val:
                    try:
                        decrypted = decrypt_with_key(val, old_key)
                        re_encrypted = encrypt_with_key(decrypted, new_key)
                        setattr(record, field, re_encrypted)
                        updated = True
                    except ValueError as e:
                        print(f"Error decrypting settings field '{field}' for record ID {record.id}: {e}")
                        raise
            if updated:
                settings_updated += 1

        # 2. Update notification presets
        presets = db.query(NotificationPresetModel).all()
        presets_updated = 0
        for preset in presets:
            if preset.encrypted_token:
                try:
                    decrypted = decrypt_with_key(preset.encrypted_token, old_key)
                    re_encrypted = encrypt_with_key(decrypted, new_key)
                    preset.encrypted_token = re_encrypted
                    presets_updated += 1
                except ValueError as e:
                    print(f"Error decrypting notification preset '{preset.name}': {e}")
                    raise

        db.commit()
        print(f"Successfully migrated {settings_updated} settings records and {presets_updated} notification presets.")
        print("You can now safely update APP_SECRET_KEY in your .env file.")

    except Exception as e:
        db.rollback()
        print(f"Error during rotation: {e}")
        print("Database changes have been rolled back.")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
