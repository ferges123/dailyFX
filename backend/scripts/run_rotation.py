#!/usr/bin/env python3
import os
import secrets
import shutil
import sys
from pathlib import Path

# Add backend directory to Python path
backend_dir = Path(__file__).resolve().parents[1]
sys.path.append(str(backend_dir))

# If database points to container path /data/app.db, map to the host path /opt/dailyFX/data/app.db
if os.environ.get("DATABASE_URL") == "sqlite:////data/app.db":
    os.environ["DATABASE_URL"] = "sqlite:////opt/dailyFX/data/app.db"

from app.config import get_settings

settings = get_settings()
if settings.database_url == "sqlite:////data/app.db":
    os.environ["DATABASE_URL"] = "sqlite:////opt/dailyFX/data/app.db"
    get_settings.cache_clear()
    settings = get_settings()

from app.database import SessionLocal, init_db
from app.models.notification_preset import NotificationPresetModel
from app.models.settings import SettingsModel
from scripts.rotate_secret_key import decrypt_with_key, encrypt_with_key


def main():
    env_path = backend_dir.parent / ".env"
    if not env_path.exists():
        print(f"Error: .env file not found at {env_path}")
        sys.exit(1)

    # Read current env contents
    env_content = env_path.read_text()

    # Extract current APP_SECRET_KEY
    old_key = None
    for line in env_content.splitlines():
        if line.startswith("APP_SECRET_KEY="):
            old_key = line.split("=", 1)[1].strip()
            break

    if not old_key:
        print("Error: APP_SECRET_KEY not found in .env file.")
        sys.exit(1)

    # Generate new secure key
    new_key = secrets.token_hex(32)
    print(f"Old key: {old_key}")
    print(f"Generated new key: {new_key}")

    # Set up database backup
    db_url = settings.database_url
    print(f"Database URL to use: {db_url}")

    if db_url.startswith("sqlite:///"):
        db_path = Path(db_url.replace("sqlite:///", ""))
        if not db_path.is_absolute():
            db_path = (backend_dir / db_path).resolve()
            if not db_path.exists():
                db_path = Path(db_url.replace("sqlite:///", "")).resolve()

        if db_path.exists():
            backup_path = db_path.with_suffix(db_path.suffix + ".manual_rotation_backup")
            print(f"Creating manual database backup at: {backup_path}")
            shutil.copy2(db_path, backup_path)
        else:
            print(f"Warning: Database path {db_path} not found. Backup skipped.")

    # Initialize the database engine and SessionLocal bind
    init_db()

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
                    except Exception as e:
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
                except Exception as e:
                    print(f"Error decrypting notification preset '{preset.name}': {e}")
                    raise

        db.commit()
        print(f"Successfully migrated {settings_updated} settings records and {presets_updated} notification presets.")

        # Update .env file
        new_lines = []
        for line in env_content.splitlines():
            if line.startswith("APP_SECRET_KEY="):
                new_lines.append(f"APP_SECRET_KEY={new_key}")
            else:
                new_lines.append(line)

        # Ensure trailing newline
        env_path.write_text("\n".join(new_lines) + "\n")
        print("Successfully updated APP_SECRET_KEY in .env file.")
        print("ROTATION_SUCCESS")

    except Exception as e:
        db.rollback()
        print(f"Error during rotation: {e}")
        print("Database changes have been rolled back and .env was NOT modified.")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
