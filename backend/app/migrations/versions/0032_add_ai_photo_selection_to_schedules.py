"""add ai photo selection to schedules

Revision ID: 0032_add_ai_photo_selection_to_schedules
Revises: 0031_add_ai_effect_display_group
Create Date: 2026-06-09
"""

import sqlalchemy as sa
from alembic import op

revision = "0032_add_ai_photo_selection_to_schedules"
down_revision = "0031_add_ai_effect_display_group"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("schedules", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("ai_photo_selection_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0"))
        )


def downgrade() -> None:
    with op.batch_alter_table("schedules", schema=None) as batch_op:
        batch_op.drop_column("ai_photo_selection_enabled")
