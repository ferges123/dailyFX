"""add is_deleted column to schedules table

Revision ID: 0041_add_is_deleted_to_schedules
Revises: 0040_add_index_generation_history_type_created_at
Create Date: 2026-07-26 11:23:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "0041_add_is_deleted_to_schedules"
down_revision = "0040_add_index_generation_history_type_created_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("schedules", sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="0"))
    op.create_index("ix_schedules_is_deleted", "schedules", ["is_deleted"])


def downgrade() -> None:
    op.drop_index("ix_schedules_is_deleted", table_name="schedules")
    op.drop_column("schedules", "is_deleted")
