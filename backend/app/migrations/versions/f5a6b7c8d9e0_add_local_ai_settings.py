"""add_local_ai_settings

Revision ID: f5a6b7c8d9e0
Revises: d531a46572af
Create Date: 2026-05-30 13:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "f5a6b7c8d9e0"
down_revision = "d531a46572af"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("settings", schema=None) as batch_op:
        batch_op.add_column(sa.Column("encrypted_local_ai_api_key", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("local_ai_base_url", sa.String(length=2048), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("settings", schema=None) as batch_op:
        batch_op.drop_column("local_ai_base_url")
        batch_op.drop_column("encrypted_local_ai_api_key")
