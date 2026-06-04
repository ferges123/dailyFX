"""Add automation tick columns and accept_notes

Revision ID: 0014_add_automation_tick_and_accept_notes
Revises: 0013_add_push_subscription_metadata
Create Date: 2026-05-20
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0014_add_automation_tick_and_accept_notes"
down_revision = "0013_add_push_subscription_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    settings_cols = {c["name"] for c in inspector.get_columns("settings")}
    with op.batch_alter_table("settings") as batch_op:
        if "automation_last_tick_at" not in settings_cols:
            batch_op.add_column(sa.Column("automation_last_tick_at", sa.DateTime(timezone=True), nullable=True))
        if "automation_last_tick_status" not in settings_cols:
            batch_op.add_column(sa.Column("automation_last_tick_status", sa.String(length=50), nullable=True))
        if "automation_last_tick_reason" not in settings_cols:
            batch_op.add_column(sa.Column("automation_last_tick_reason", sa.Text(), nullable=True))
        if "automation_last_tick_task_id" not in settings_cols:
            batch_op.add_column(sa.Column("automation_last_tick_task_id", sa.String(length=64), nullable=True))
        if "automation_next_run_at" not in settings_cols:
            batch_op.add_column(sa.Column("automation_next_run_at", sa.DateTime(timezone=True), nullable=True))

    history_cols = {c["name"] for c in inspector.get_columns("generation_history")}
    with op.batch_alter_table("generation_history") as batch_op:
        if "accept_notes" not in history_cols:
            batch_op.add_column(sa.Column("accept_notes", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("generation_history") as batch_op:
        batch_op.drop_column("accept_notes")
    with op.batch_alter_table("settings") as batch_op:
        batch_op.drop_column("automation_next_run_at")
        batch_op.drop_column("automation_last_tick_task_id")
        batch_op.drop_column("automation_last_tick_reason")
        batch_op.drop_column("automation_last_tick_status")
        batch_op.drop_column("automation_last_tick_at")
