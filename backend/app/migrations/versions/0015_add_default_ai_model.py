"""add default_ai_model

Revision ID: 0015_add_default_ai_model
Revises: 0014_add_automation_tick_and_accept_notes
Create Date: 2026-05-20 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "0015_add_default_ai_model"
down_revision = "0014_add_automation_tick_and_accept_notes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "settings",
        sa.Column("default_ai_model", sa.String(length=100), nullable=False, server_default="gpt-image-1"),
    )


def downgrade() -> None:
    op.drop_column("settings", "default_ai_model")
