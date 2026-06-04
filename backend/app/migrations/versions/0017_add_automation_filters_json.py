"""add automation_filters_json

Revision ID: 0017_add_automation_filters_json
Revises: 0016_drop_person_filter_strategy
Create Date: 2026-05-22
"""

import sqlalchemy as sa
from alembic import op

revision = "0017_add_automation_filters_json"
down_revision = "0016_drop_person_filter_strategy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("settings") as batch_op:
        batch_op.add_column(sa.Column("automation_filters_json", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("settings") as batch_op:
        batch_op.drop_column("automation_filters_json")
