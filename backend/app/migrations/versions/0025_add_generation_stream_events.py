"""add generation stream events

Revision ID: 0025_add_generation_stream_events
Revises: 0024_add_ai_usage_limits
Create Date: 2026-05-27 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "0025_add_generation_stream_events"
down_revision = "0024_add_ai_usage_limits"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "generation_stream_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("task_id", sa.String(length=64), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_generation_stream_events_event_type", "generation_stream_events", ["event_type"])
    op.create_index("ix_generation_stream_events_task_id", "generation_stream_events", ["task_id"])


def downgrade():
    op.drop_index("ix_generation_stream_events_task_id", table_name="generation_stream_events")
    op.drop_index("ix_generation_stream_events_event_type", table_name="generation_stream_events")
    op.drop_table("generation_stream_events")
