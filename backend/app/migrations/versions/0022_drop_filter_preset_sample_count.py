"""drop sample_count from filter_presets

Revision ID: 0022_drop_filter_preset_sample_count
Revises: 0021_drop_legacy_automation_fields
Create Date: 2026-05-26
"""

from alembic import op

revision = "0022_drop_filter_preset_sample_count"
down_revision = "0021_drop_legacy_automation_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("filter_presets") as batch_op:
        batch_op.drop_column("sample_count")


def downgrade() -> None:
    import sqlalchemy as sa

    with op.batch_alter_table("filter_presets") as batch_op:
        batch_op.add_column(sa.Column("sample_count", sa.Integer(), nullable=False, server_default="24"))
