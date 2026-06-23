"""add_effect_statistics_log

Revision ID: 0036
Revises: 0035
Create Date: 2026-06-23 16:20:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "effect_statistics_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("effect_id", sa.String(length=255), nullable=False),
        sa.Column("task_id", sa.String(length=64), nullable=True),
        sa.Column("liked", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_effect_statistics_log_effect_id", "effect_statistics_log", ["effect_id"])
    op.create_index("ix_effect_statistics_log_task_id", "effect_statistics_log", ["task_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_effect_statistics_log_task_id", table_name="effect_statistics_log")
    op.drop_index("ix_effect_statistics_log_effect_id", table_name="effect_statistics_log")
    op.drop_table("effect_statistics_log")
