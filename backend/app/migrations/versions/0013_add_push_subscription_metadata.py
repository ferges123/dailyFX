"""add push subscription metadata

Revision ID: 0013_add_push_subscription_metadata
Revises: 0012_rename_collage_output_size
Create Date: 2026-05-18
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0013_add_push_subscription_metadata"
down_revision = "0013a_create_push_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("push_subscriptions")}
    with op.batch_alter_table("push_subscriptions") as batch_op:
        if "device_label" not in columns:
            batch_op.add_column(sa.Column("device_label", sa.String(length=255), nullable=True))
        if "user_agent" not in columns:
            batch_op.add_column(sa.Column("user_agent", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("push_subscriptions") as batch_op:
        batch_op.drop_column("user_agent")
        batch_op.drop_column("device_label")
