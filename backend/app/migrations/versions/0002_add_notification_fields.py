"""add notification fields

Revision ID: 0002_add_notification_fields
Revises: 0001_create_settings
Create Date: 2026-05-12
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_add_notification_fields"
down_revision = "0001_create_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("settings", sa.Column("notification_url", sa.String(length=2048), nullable=True))
    op.add_column("settings", sa.Column("notification_topic", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("settings", "notification_topic")
    op.drop_column("settings", "notification_url")

