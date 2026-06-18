"""add indexes for status and schedule

Revision ID: 0035
Revises: 0034
Create Date: 2026-06-18 12:55:00.000000
"""

from alembic import op

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_generation_history_status", "generation_history", ["status"])
    op.create_index("ix_generation_history_schedule_id", "generation_history", ["schedule_id"])
    op.create_index("ix_generation_tasks_status", "generation_tasks", ["status"])


def downgrade() -> None:
    op.drop_index("ix_generation_tasks_status", table_name="generation_tasks")
    op.drop_index("ix_generation_history_schedule_id", table_name="generation_history")
    op.drop_index("ix_generation_history_status", table_name="generation_history")
