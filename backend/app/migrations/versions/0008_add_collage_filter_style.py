"""Add collage filter style to settings

Revision ID: 0008_add_collage_filter_style
Revises: 0007_add_asset_source_mode
Create Date: 2026-05-14 12:45:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "0008_add_collage_filter_style"
down_revision = "0007_add_asset_source_mode"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("settings", sa.Column("collage_filter_style", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("settings", "collage_filter_style")
