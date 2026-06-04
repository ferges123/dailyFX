"""add ai_prompt_enrichment to schedules

Revision ID: 0029_add_ai_prompt_enrichment_to_schedules
Revises: 0028_many_to_many_schedules_notifications
Create Date: 2026-05-28
"""

import sqlalchemy as sa
from alembic import op

revision = "0029_add_ai_prompt_enrichment_to_schedules"
down_revision = "0028_many_to_many_schedules_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Use batch_alter_table for SQLite compatibility
    with op.batch_alter_table("schedules", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("ai_prompt_enrichment", sa.Boolean(), nullable=False, server_default=sa.text("0"))
        )


def downgrade() -> None:
    with op.batch_alter_table("schedules", schema=None) as batch_op:
        batch_op.drop_column("ai_prompt_enrichment")
