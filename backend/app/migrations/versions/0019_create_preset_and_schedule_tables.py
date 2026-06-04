"""create preset and schedule tables

Revision ID: 0019_create_preset_and_schedule_tables
Revises: 0018_add_tags_json
Create Date: 2026-05-25
"""

import sqlalchemy as sa
from alembic import op

revision = "0019_create_preset_and_schedule_tables"
down_revision = "0018_add_tags_json"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "filter_presets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("album_ids_json", sa.Text(), nullable=True),
        sa.Column("person_filters_json", sa.Text(), nullable=True),
        sa.Column("asset_source_mode", sa.String(20), nullable=False, server_default="random"),
        sa.Column("start_date", sa.String(20), nullable=True),
        sa.Column("end_date", sa.String(20), nullable=True),
        sa.Column("media_type", sa.String(20), nullable=False, server_default="photo"),
        sa.Column("sample_count", sa.Integer(), nullable=False, server_default="24"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "effect_presets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("groups_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "notification_presets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("provider", sa.String(100), nullable=False, server_default="web"),
        sa.Column("url", sa.String(2048), nullable=True),
        sa.Column("topic", sa.String(255), nullable=True),
        sa.Column("encrypted_token", sa.Text(), nullable=True),
        sa.Column("webhook_url", sa.String(2048), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "schedules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("schedule_expr", sa.String(100), nullable=False, server_default="weekly"),
        sa.Column("filter_preset_id", sa.Integer(), nullable=False),
        sa.Column("effect_preset_id", sa.Integer(), nullable=False),
        sa.Column("notification_preset_id", sa.Integer(), nullable=True),
        sa.Column("album_name", sa.String(255), nullable=False, server_default="AI Photos"),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_tick_status", sa.String(50), nullable=True),
        sa.Column("last_tick_reason", sa.Text(), nullable=True),
        sa.Column("last_task_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["filter_preset_id"], ["filter_presets.id"]),
        sa.ForeignKeyConstraint(["effect_preset_id"], ["effect_presets.id"]),
        sa.ForeignKeyConstraint(["notification_preset_id"], ["notification_presets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.add_column("generation_history", sa.Column("schedule_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("generation_history", "schedule_id")
    op.drop_table("schedules")
    op.drop_table("notification_presets")
    op.drop_table("effect_presets")
    op.drop_table("filter_presets")
