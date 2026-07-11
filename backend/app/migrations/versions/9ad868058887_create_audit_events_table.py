"""create_audit_events_table

Revision ID: 9ad868058887
Revises: a2c7f4e1b9d0
Create Date: 2026-07-11 12:13:17.288324
"""

import sqlalchemy as sa
from alembic import op

revision = "9ad868058887"
down_revision = "a2c7f4e1b9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("outcome", sa.String(length=50), nullable=False),
        sa.Column("actor_type", sa.String(length=50), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("source_ip_hash", sa.String(length=64), nullable=True),
        sa.Column("target_type", sa.String(length=50), nullable=True),
        sa.Column("target_id", sa.String(length=64), nullable=True),
        sa.Column("task_id", sa.String(length=64), nullable=True),
        sa.Column("schedule_id", sa.Integer(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("changes_json", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_events_event_id", "audit_events", ["event_id"], unique=True)
    op.create_index("ix_audit_events_occurred_at", "audit_events", ["occurred_at"], unique=False)
    op.create_index("ix_audit_events_action", "audit_events", ["action"], unique=False)
    op.create_index("ix_audit_events_category", "audit_events", ["category"], unique=False)
    op.create_index("ix_audit_events_outcome", "audit_events", ["outcome"], unique=False)
    op.create_index("ix_audit_events_task_id", "audit_events", ["task_id"], unique=False)
    op.create_index("ix_audit_events_schedule_id", "audit_events", ["schedule_id"], unique=False)
    op.create_index("ix_audit_events_target", "audit_events", ["target_type", "target_id"], unique=False)


def downgrade() -> None:
    op.drop_table("audit_events")
