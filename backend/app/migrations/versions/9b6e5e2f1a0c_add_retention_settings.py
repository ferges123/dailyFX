"""add configurable retention settings"""

import sqlalchemy as sa
from alembic import op

revision = "9b6e5e2f1a0c"
down_revision = "87a2437392f5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = [
        sa.Column("retention_enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("retention_rejected_files_days", sa.Integer(), nullable=True, server_default=sa.text("7")),
        sa.Column("retention_rejected_metadata_days", sa.Integer(), nullable=True, server_default=sa.text("90")),
        sa.Column("retention_failed_files_days", sa.Integer(), nullable=True, server_default=sa.text("7")),
        sa.Column("retention_failed_metadata_days", sa.Integer(), nullable=True, server_default=sa.text("90")),
        sa.Column("retention_uploaded_files_days", sa.Integer(), nullable=True, server_default=sa.text("30")),
        sa.Column("retention_uploaded_metadata_days", sa.Integer(), nullable=True, server_default=sa.text("30")),
        sa.Column("retention_task_days", sa.Integer(), nullable=True, server_default=sa.text("30")),
        sa.Column("retention_audit_days", sa.Integer(), nullable=True, server_default=sa.text("180")),
        sa.Column("retention_backup_count", sa.Integer(), nullable=False, server_default=sa.text("7")),
    ]
    for column in columns:
        op.add_column("settings", column)


def downgrade() -> None:
    for name in [
        "retention_backup_count",
        "retention_audit_days",
        "retention_task_days",
        "retention_uploaded_metadata_days",
        "retention_uploaded_files_days",
        "retention_failed_metadata_days",
        "retention_failed_files_days",
        "retention_rejected_metadata_days",
        "retention_rejected_files_days",
        "retention_enabled",
    ]:
        op.drop_column("settings", name)
