"""add gemini output size

Revision ID: 0003_add_gemini_output_size
Revises: 0002_add_notification_fields
Create Date: 2026-05-13
"""

import sqlalchemy as sa
from alembic import op

revision = "0003_add_gemini_output_size"
down_revision = "0002_add_notification_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("settings", sa.Column("gemini_output_size", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("settings", "gemini_output_size")
