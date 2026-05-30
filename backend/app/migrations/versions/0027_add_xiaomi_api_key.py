"""add_xiaomi_api_key

Revision ID: 0027_add_xiaomi_api_key
Revises: 0026_merge_generation_stream_heads
Create Date: 2026-05-27 14:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0027_add_xiaomi_api_key"
down_revision = "0026_merge_generation_stream_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("settings", schema=None) as batch_op:
        batch_op.add_column(sa.Column("encrypted_xiaomi_api_key", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("settings", schema=None) as batch_op:
        batch_op.drop_column("encrypted_xiaomi_api_key")
