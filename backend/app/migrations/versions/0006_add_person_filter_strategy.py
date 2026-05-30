"""Add person filter strategy to settings

Revision ID: 0006_add_person_filter_strategy
Revises: 0005_create_collage_history
Create Date: 2026-05-13 15:40:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0006_add_person_filter_strategy"
down_revision = "0005_create_collage_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("settings", sa.Column("person_filter_strategy", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("settings", "person_filter_strategy")
