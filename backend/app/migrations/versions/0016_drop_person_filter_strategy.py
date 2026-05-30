"""drop person_filter_strategy

Revision ID: 0016_drop_person_filter_strategy
Revises: 1fcc0b6b1f18
Create Date: 2026-05-22
"""
import sqlalchemy as sa
from alembic import op

revision = "0016_drop_person_filter_strategy"
down_revision = "1fcc0b6b1f18"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("settings") as batch_op:
        batch_op.drop_column("person_filter_strategy")


def downgrade() -> None:
    with op.batch_alter_table("settings") as batch_op:
        batch_op.add_column(sa.Column("person_filter_strategy", sa.String(20), nullable=True))
