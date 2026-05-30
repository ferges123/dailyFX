"""Create push_subscriptions and vapid_keys tables

Revision ID: 0013a_create_push_tables
Revises: 0012_rename_collage_output_size
Create Date: 2026-05-20
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0013a_create_push_tables"
down_revision = "0012_rename_collage_output_size"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "push_subscriptions" not in tables:
        op.create_table(
            "push_subscriptions",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("endpoint", sa.Text(), nullable=False, unique=True),
            sa.Column("p256dh", sa.String(length=512), nullable=False),
            sa.Column("auth", sa.String(length=256), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    if "vapid_keys" not in tables:
        op.create_table(
            "vapid_keys",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("private_key", sa.Text(), nullable=False),
            sa.Column("public_key", sa.Text(), nullable=False),
        )


def downgrade() -> None:
    op.drop_table("vapid_keys")
    op.drop_table("push_subscriptions")
