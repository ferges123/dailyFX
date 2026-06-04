"""add automation_last_run_at to settings

Revision ID: 0009_add_automation_last_run_at
Revises: cf1791cf9d4b
Create Date: 2026-05-14 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0009_add_automation_last_run_at"
down_revision = "cf1791cf9d4b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("settings")}
    if "automation_last_run_at" not in columns:
        op.add_column("settings", sa.Column("automation_last_run_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("settings")}
    if "automation_last_run_at" in columns:
        op.drop_column("settings", "automation_last_run_at")
