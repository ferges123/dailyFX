"""add durable locks for AI usage reservations

Revision ID: 0042_add_ai_usage_locks
Revises: 0041_add_is_deleted_to_schedules
Create Date: 2026-09-16 12:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "0042_add_ai_usage_locks"
down_revision = "0041_add_is_deleted_to_schedules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_usage_locks",
        sa.Column("usage_type", sa.String(length=20), primary_key=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.bulk_insert(
        sa.table("ai_usage_locks", sa.column("usage_type", sa.String)),
        [{"usage_type": "vision"}, {"usage_type": "image"}],
    )


def downgrade() -> None:
    op.drop_table("ai_usage_locks")
