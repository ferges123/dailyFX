"""add_task_step_to_generation_history

Revision ID: a1b2c3d4e5f6
Revises: 104dd93b730f
Create Date: 2026-05-23 15:40:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "a1b2c3d4e5f6"
down_revision = "104dd93b730f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("generation_history", sa.Column("task_step", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("generation_history", "task_step")
