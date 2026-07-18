"""add durable file deletion outbox

Revision ID: 0038_add_file_deletion_jobs
Revises: 0037_rename_filter_presets_to_people_presets
Create Date: 2026-07-17 12:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "0038_add_file_deletion_jobs"
down_revision = "0037_rename_filter_presets_to_people_presets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "file_deletion_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.String(length=64), nullable=True),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("thumbnail_path", sa.Text(), nullable=True),
        sa.Column("reason", sa.String(length=50), nullable=False, server_default="retention"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_file_deletion_jobs_task_id", "file_deletion_jobs", ["task_id"])
    op.create_index("ix_file_deletion_jobs_status", "file_deletion_jobs", ["status"])
    op.create_index("ix_file_deletion_jobs_next_attempt_at", "file_deletion_jobs", ["next_attempt_at"])


def downgrade() -> None:
    op.drop_index("ix_file_deletion_jobs_next_attempt_at", table_name="file_deletion_jobs")
    op.drop_index("ix_file_deletion_jobs_status", table_name="file_deletion_jobs")
    op.drop_index("ix_file_deletion_jobs_task_id", table_name="file_deletion_jobs")
    op.drop_table("file_deletion_jobs")
