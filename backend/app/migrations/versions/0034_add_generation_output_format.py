"""add generation output format

Revision ID: 0034
Revises: 0033
Create Date: 2026-06-12 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("generation_history") as batch_op:
        batch_op.add_column(sa.Column("output_format", sa.String(length=10), nullable=False, server_default="png"))
        batch_op.add_column(sa.Column("frame_count", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("generation_history") as batch_op:
        batch_op.drop_column("frame_count")
        batch_op.drop_column("output_format")
