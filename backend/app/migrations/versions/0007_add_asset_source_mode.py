"""Add asset source mode to settings

Revision ID: 0007_add_asset_source_mode
Revises: 0006_add_person_filter_strategy
Create Date: 2026-05-13 16:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0007_add_asset_source_mode"
down_revision = "0006_add_person_filter_strategy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("settings", sa.Column("asset_source_mode", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("settings", "asset_source_mode")
