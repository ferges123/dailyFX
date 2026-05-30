"""drop legacy automation fields from settings

Revision ID: 0021_drop_legacy_automation_fields
Revises: 0020_migrate_legacy_to_presets
Create Date: 2026-05-25
"""
import sqlalchemy as sa
from alembic import op

revision = "0021_drop_legacy_automation_fields"
down_revision = "0020_migrate_legacy_to_presets"
branch_labels = None
depends_on = None

_LEGACY_COLS = [
    "automation_enabled",
    "automation_schedule",
    "automation_person_ids_json",
    "automation_filters_json",
    "modification_groups_json",
    "automation_last_run_at",
    "automation_last_tick_at",
    "automation_last_tick_status",
    "automation_last_tick_reason",
    "automation_last_tick_task_id",
    "automation_next_run_at",
    "notification_provider",
    "notification_url",
    "notification_topic",
    "encrypted_notification_token",
    "webhook_url",
]


def upgrade() -> None:
    with op.batch_alter_table("settings") as batch_op:
        existing = [col["name"] for col in sa.inspect(op.get_bind()).get_columns("settings")]
        for col in _LEGACY_COLS:
            if col in existing:
                batch_op.drop_column(col)


def downgrade() -> None:
    with op.batch_alter_table("settings") as batch_op:
        batch_op.add_column(sa.Column("automation_enabled", sa.Boolean(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("automation_schedule", sa.String(50), nullable=False, server_default="weekly"))
        batch_op.add_column(sa.Column("automation_person_ids_json", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("automation_filters_json", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("modification_groups_json", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("automation_last_run_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("automation_last_tick_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("automation_last_tick_status", sa.String(50), nullable=True))
        batch_op.add_column(sa.Column("automation_last_tick_reason", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("automation_last_tick_task_id", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("automation_next_run_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("notification_provider", sa.String(50), nullable=False, server_default="web"))
        batch_op.add_column(sa.Column("notification_url", sa.String(2048), nullable=True))
        batch_op.add_column(sa.Column("notification_topic", sa.String(255), nullable=True))
        batch_op.add_column(sa.Column("encrypted_notification_token", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("webhook_url", sa.String(2048), nullable=True))
