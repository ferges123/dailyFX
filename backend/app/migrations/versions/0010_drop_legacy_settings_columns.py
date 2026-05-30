"""Drop legacy settings columns

Revision ID: 0010_drop_legacy_settings_columns
Revises: cf1791cf9d4b
Create Date: 2026-05-15 11:30:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0010_drop_legacy_settings_columns"
down_revision = "0009_add_automation_last_run_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("settings")}
    with op.batch_alter_table("settings") as batch_op:
        if "automation_filter_json" in columns:
            batch_op.drop_column("automation_filter_json")
        if "collage_image_mode" in columns:
            batch_op.drop_column("collage_image_mode")
        if "collage_filter_style" in columns:
            batch_op.drop_column("collage_filter_style")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("settings")}
    with op.batch_alter_table("settings") as batch_op:
        if "automation_filter_json" not in columns:
            batch_op.add_column(sa.Column("automation_filter_json", sa.Text(), nullable=True))
        if "collage_image_mode" not in columns:
            batch_op.add_column(sa.Column("collage_image_mode", sa.String(length=20), nullable=True))
        if "collage_filter_style" not in columns:
            batch_op.add_column(sa.Column("collage_filter_style", sa.String(length=32), nullable=True))
