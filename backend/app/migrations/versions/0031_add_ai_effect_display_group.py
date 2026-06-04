"""add ai effect display group

Revision ID: 0031_add_ai_effect_display_group
Revises: 0030_add_ai_effects_table
Create Date: 2026-06-01
"""

from alembic import op
import sqlalchemy as sa

revision = "0031_add_ai_effect_display_group"
down_revision = "0030_add_ai_effects_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ai_effects", sa.Column("display_group", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("ai_effects", "display_group")
