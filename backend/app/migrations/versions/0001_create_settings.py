"""create settings table

Revision ID: 0001_create_settings
Revises:
Create Date: 2026-05-12
"""

import sqlalchemy as sa
from alembic import op

revision = "0001_create_settings"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("immich_url", sa.String(length=2048), nullable=True),
        sa.Column("encrypted_immich_api_key", sa.String(), nullable=True),
        sa.Column("default_album_name", sa.String(length=255), nullable=False),
        sa.Column("encrypted_openai_api_key", sa.String(), nullable=True),
        sa.Column("encrypted_gemini_api_key", sa.String(), nullable=True),
        sa.Column("default_ai_provider", sa.String(length=50), nullable=False),
        sa.Column("notification_provider", sa.String(length=50), nullable=False),
        sa.Column("encrypted_notification_token", sa.String(), nullable=True),
        sa.Column("auto_suggestions_enabled", sa.Boolean(), nullable=False),
        sa.Column("auto_suggestions_schedule", sa.String(length=50), nullable=False),
        sa.Column("auto_suggestions_max_per_run", sa.Integer(), nullable=False),
        sa.Column("auto_suggestions_lookback_days", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("settings")
