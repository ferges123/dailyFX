"""add tags_json to generation_history

Revision ID: 0018_add_tags_json
Revises: 0017_add_automation_filters_json
Create Date: 2026-05-25
"""

import sqlalchemy as sa
from alembic import op

revision = "0018_add_tags_json"
down_revision = "d531a46572af"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("generation_history", sa.Column("tags_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("generation_history", "tags_json")
