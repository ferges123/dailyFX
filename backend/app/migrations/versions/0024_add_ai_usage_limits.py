"""add ai usage limits and usage tracking

Revision ID: 0024_add_ai_usage_limits
Revises: 0023_add_generation_tasks_table
Create Date: 2026-05-26 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0024_add_ai_usage_limits"
down_revision = "0023_add_generation_tasks_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("settings", schema=None) as batch_op:
        batch_op.add_column(sa.Column("ai_vision_hourly_limit", sa.Integer(), nullable=False, server_default="30"))
        batch_op.add_column(sa.Column("ai_image_hourly_limit", sa.Integer(), nullable=False, server_default="10"))

    op.create_table(
        "ai_usage_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("usage_type", sa.String(length=20), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("task_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ai_usage_events_usage_type", "ai_usage_events", ["usage_type"])
    op.create_index("ix_ai_usage_events_task_id", "ai_usage_events", ["task_id"])
    op.create_index("ix_ai_usage_events_created_at", "ai_usage_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_ai_usage_events_created_at", table_name="ai_usage_events")
    op.drop_index("ix_ai_usage_events_task_id", table_name="ai_usage_events")
    op.drop_index("ix_ai_usage_events_usage_type", table_name="ai_usage_events")
    op.drop_table("ai_usage_events")

    with op.batch_alter_table("settings", schema=None) as batch_op:
        batch_op.drop_column("ai_image_hourly_limit")
        batch_op.drop_column("ai_vision_hourly_limit")
