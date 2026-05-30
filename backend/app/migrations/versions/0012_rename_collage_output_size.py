"""Rename gemini_output_size to collage_output_size

Revision ID: 0012_rename_collage_output_size
Revises: 0011_drop_auto_suggestions
Create Date: 2026-05-15
"""

from alembic import op
from sqlalchemy import inspect

revision = "0012_rename_collage_output_size"
down_revision = "0011_drop_auto_suggestions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("settings")}
    with op.batch_alter_table("settings") as batch_op:
        if "gemini_output_size" in columns and "collage_output_size" not in columns:
            batch_op.alter_column("gemini_output_size", new_column_name="collage_output_size")


def downgrade() -> None:
    with op.batch_alter_table("settings") as batch_op:
        batch_op.alter_column("collage_output_size", new_column_name="gemini_output_size")
