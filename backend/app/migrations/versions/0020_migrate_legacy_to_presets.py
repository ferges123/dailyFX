"""migrate legacy settings to presets and schedules

Revision ID: 0020_migrate_legacy_to_presets
Revises: 0019_create_preset_and_schedule_tables
Create Date: 2026-05-25
"""

from alembic import op
from sqlalchemy.sql import text

revision = "0020_migrate_legacy_to_presets"
down_revision = "0019_create_preset_and_schedule_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    row = conn.execute(
        text(
            "SELECT automation_enabled, automation_schedule, automation_filters_json, "
            "modification_groups_json, notification_provider, notification_url, "
            "notification_topic, encrypted_notification_token, webhook_url, "
            "automation_last_run_at, default_album_name FROM settings LIMIT 1"
        )
    ).fetchone()

    if row is None:
        return  # No settings yet — nothing to migrate

    (
        automation_enabled,
        automation_schedule,
        automation_filters_json,
        modification_groups_json,
        notification_provider,
        notification_url,
        notification_topic,
        encrypted_notification_token,
        webhook_url,
        automation_last_run_at,
        default_album_name,
    ) = row

    # Skip if default schedule already exists
    existing = conn.execute(text("SELECT id FROM schedules LIMIT 1")).fetchone()
    if existing:
        return

    # 1. Filter preset
    conn.execute(
        text(
            "INSERT INTO filter_presets (name, album_ids_json, person_filters_json, "
            "asset_source_mode, media_type, sample_count) "
            "VALUES (:name, :album_ids, :person_filters, :mode, :media_type, :sample_count)"
        ),
        {
            "name": "Default Filters",
            "album_ids": _extract_album_ids(automation_filters_json),
            "person_filters": _extract_person_filters(automation_filters_json),
            "mode": _extract_field(automation_filters_json, "assetSourceMode", "random"),
            "media_type": _extract_field(automation_filters_json, "mediaType", "photo"),
            "sample_count": int(_extract_field(automation_filters_json, "sampleCount", "24")),
        },
    )
    filter_preset_id = conn.execute(text("SELECT last_insert_rowid()")).scalar()

    # 2. Effect preset
    groups = modification_groups_json or "{}"
    conn.execute(
        text("INSERT INTO effect_presets (name, groups_json) VALUES (:name, :groups)"),
        {"name": "Default Effects", "groups": groups},
    )
    effect_preset_id = conn.execute(text("SELECT last_insert_rowid()")).scalar()

    # 3. Notification preset
    conn.execute(
        text(
            "INSERT INTO notification_presets (name, provider, url, topic, encrypted_token, webhook_url) "
            "VALUES (:name, :provider, :url, :topic, :token, :webhook)"
        ),
        {
            "name": "Default Notifications",
            "provider": notification_provider or "web",
            "url": notification_url,
            "topic": notification_topic,
            "token": encrypted_notification_token,
            "webhook": webhook_url,
        },
    )
    notification_preset_id = conn.execute(text("SELECT last_insert_rowid()")).scalar()

    # 4. Schedule
    conn.execute(
        text(
            "INSERT INTO schedules (name, enabled, schedule_expr, filter_preset_id, "
            "effect_preset_id, notification_preset_id, album_name, last_run_at) "
            "VALUES (:name, :enabled, :expr, :fp, :ep, :np, :album, :last_run)"
        ),
        {
            "name": "Default Schedule",
            "enabled": 1 if automation_enabled else 0,
            "expr": automation_schedule or "weekly",
            "fp": filter_preset_id,
            "ep": effect_preset_id,
            "np": notification_preset_id,
            "album": default_album_name or "AI Photos",
            "last_run": automation_last_run_at,
        },
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("DELETE FROM schedules WHERE name = 'Default Schedule'"))
    conn.execute(text("DELETE FROM filter_presets WHERE name = 'Default Filters'"))
    conn.execute(text("DELETE FROM effect_presets WHERE name = 'Default Effects'"))
    conn.execute(text("DELETE FROM notification_presets WHERE name = 'Default Notifications'"))


# ── Helpers ───────────────────────────────────────────────────────────────────


def _parse_json(value):
    if not value:
        return {}
    try:
        import json

        return json.loads(value)
    except Exception:
        return {}


def _extract_album_ids(filters_json: str | None) -> str:
    import json

    data = _parse_json(filters_json)
    ids = data.get("albumIds") or []
    return json.dumps(ids)


def _extract_person_filters(filters_json: str | None) -> str:
    import json

    data = _parse_json(filters_json)
    pf = data.get("personFilters") or []
    return json.dumps(pf)


def _extract_field(filters_json: str | None, key: str, default: str) -> str:
    data = _parse_json(filters_json)
    val = data.get(key)
    return str(val) if val is not None else default
