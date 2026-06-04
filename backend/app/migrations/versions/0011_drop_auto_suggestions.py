"""Drop auto_suggestions columns

Revision ID: 0011_drop_auto_suggestions
Revises: 0010_drop_legacy_settings_columns
Create Date: 2026-05-15
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0011_drop_auto_suggestions"
down_revision = "0010_drop_legacy_settings_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("settings")}
    with op.batch_alter_table("settings") as batch_op:
        for col in (
            "auto_suggestions_enabled",
            "auto_suggestions_schedule",
            "auto_suggestions_max_per_run",
            "auto_suggestions_lookback_days",
        ):
            if col in columns:
                batch_op.drop_column(col)


def downgrade() -> None:
    with op.batch_alter_table("settings") as batch_op:
        batch_op.add_column(sa.Column("auto_suggestions_enabled", sa.Boolean(), nullable=False, server_default="0"))
        batch_op.add_column(
            sa.Column("auto_suggestions_schedule", sa.String(50), nullable=False, server_default="weekly")
        )
        batch_op.add_column(sa.Column("auto_suggestions_max_per_run", sa.Integer(), nullable=False, server_default="3"))
        batch_op.add_column(
            sa.Column("auto_suggestions_lookback_days", sa.Integer(), nullable=False, server_default="90")
        )
