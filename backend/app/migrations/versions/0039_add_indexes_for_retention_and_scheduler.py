"""add indexes for retention created_at and scheduler enabled

Revision ID: 0039_add_indexes_for_retention_and_scheduler
Revises: 0038_add_file_deletion_jobs
Create Date: 2026-07-24 21:40:00.000000
"""

from alembic import op

revision = "0039_add_indexes_for_retention_and_scheduler"
down_revision = "0038_add_file_deletion_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_generation_history_created_at", "generation_history", ["created_at"])
    op.create_index("ix_schedules_enabled", "schedules", ["enabled"])


def downgrade() -> None:
    op.drop_index("ix_schedules_enabled", table_name="schedules")
    op.drop_index("ix_generation_history_created_at", table_name="generation_history")
