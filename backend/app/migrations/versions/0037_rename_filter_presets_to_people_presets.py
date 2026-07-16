"""rename filter presets to people presets

Revision ID: 0037_rename_filter_presets_to_people_presets
Revises: 2b9a7c90cff1
Create Date: 2026-07-16 10:00:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0037_rename_filter_presets_to_people_presets"
down_revision = "2b9a7c90cff1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Rename table filter_presets to people_presets
    op.rename_table("filter_presets", "people_presets")

    # 2. Rename column filter_preset_id to people_preset_id in schedules table
    with op.batch_alter_table("schedules", schema=None) as batch_op:
        batch_op.alter_column("filter_preset_id", new_column_name="people_preset_id")


def downgrade() -> None:
    with op.batch_alter_table("schedules", schema=None) as batch_op:
        batch_op.alter_column("people_preset_id", new_column_name="filter_preset_id")

    op.rename_table("people_presets", "filter_presets")
