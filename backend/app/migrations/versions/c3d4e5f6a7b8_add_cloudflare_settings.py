"""add_cloudflare_settings

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-05-24 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("settings", sa.Column("encrypted_cloudflare_api_key", sa.String(), nullable=True))
    op.add_column("settings", sa.Column("cloudflare_account_id", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("settings", "cloudflare_account_id")
    op.drop_column("settings", "encrypted_cloudflare_api_key")
