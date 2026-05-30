"""add generation_tasks table

Revision ID: 0023_add_generation_tasks_table
Revises: 0022_drop_filter_preset_sample_count
Create Date: 2026-05-26 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0023_add_generation_tasks_table"
down_revision = "0022_drop_filter_preset_sample_count"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "generation_tasks",
        sa.Column("task_id", sa.String(length=64), primary_key=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("step", sa.String(length=64), nullable=True),
        sa.Column("progress", sa.Float(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade():
    op.drop_table("generation_tasks")
