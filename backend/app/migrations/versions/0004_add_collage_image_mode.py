"""add collage image mode

Revision ID: 0004_add_collage_image_mode
Revises: 0003_add_gemini_output_size
Create Date: 2026-05-13
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_add_collage_image_mode"
down_revision = "0003_add_gemini_output_size"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("settings", sa.Column("collage_image_mode", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("settings", "collage_image_mode")
