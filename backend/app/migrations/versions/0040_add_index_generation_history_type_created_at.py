"""add composite index for generation_type and created_at on generation_history

Revision ID: 0040_add_index_generation_history_type_created_at
Revises: 0039_add_indexes_for_retention_and_scheduler
Create Date: 2026-07-25 23:30:00.000000
"""

from alembic import op

revision = "0040_add_index_generation_history_type_created_at"
down_revision = "0039_add_indexes_for_retention_and_scheduler"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_generation_history_type_created_at",
        "generation_history",
        ["generation_type", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_generation_history_type_created_at", table_name="generation_history")
