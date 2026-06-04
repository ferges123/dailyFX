"""move_ai_settings_to_schedules

Revision ID: 3a2c9b4e5f7d
Revises: 2f3fe6dbc8ae
Create Date: 2026-05-27 10:52:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "3a2c9b4e5f7d"
down_revision = "2f3fe6dbc8ae"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add columns to schedules table
    with op.batch_alter_table("schedules", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("ai_vision_provider", sa.String(length=50), nullable=False, server_default="none")
        )
        batch_op.add_column(
            sa.Column("ai_vision_model", sa.String(length=100), nullable=False, server_default="gpt-4o-mini")
        )
        batch_op.add_column(sa.Column("ai_image_provider", sa.String(length=50), nullable=False, server_default="none"))
        batch_op.add_column(
            sa.Column("ai_image_model", sa.String(length=100), nullable=False, server_default="gpt-image-1")
        )

    # 2. Data Migration: copy settings fields into schedules
    # Find settings row and copy fields to existing schedules
    connection = op.get_bind()
    try:
        settings_row = connection.execute(
            sa.text(
                "SELECT default_ai_provider, default_ai_model, ai_image_provider, ai_image_model FROM settings LIMIT 1"
            )
        ).fetchone()

        if settings_row:
            default_ai_provider = settings_row[0] or "none"
            default_ai_model = settings_row[1] or "gpt-4o-mini"
            ai_image_provider = settings_row[2] or "none"
            ai_image_model = settings_row[3] or "gpt-image-1"

            connection.execute(
                sa.text(
                    "UPDATE schedules SET "
                    "ai_vision_provider = :vip, "
                    "ai_vision_model = :vim, "
                    "ai_image_provider = :imp, "
                    "ai_image_model = :imm"
                ),
                {"vip": default_ai_provider, "vim": default_ai_model, "imp": ai_image_provider, "imm": ai_image_model},
            )
    except Exception:
        # If settings table is empty or column queries fail, ignore
        pass

    # 3. Drop columns from settings table
    with op.batch_alter_table("settings", schema=None) as batch_op:
        batch_op.drop_column("default_ai_provider")
        batch_op.drop_column("default_ai_model")
        batch_op.drop_column("ai_image_provider")
        batch_op.drop_column("ai_image_model")


def downgrade() -> None:
    # 1. Add columns back to settings table
    with op.batch_alter_table("settings", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("default_ai_provider", sa.String(length=50), nullable=False, server_default="none")
        )
        batch_op.add_column(
            sa.Column("default_ai_model", sa.String(length=100), nullable=False, server_default="gpt-image-1")
        )
        batch_op.add_column(sa.Column("ai_image_provider", sa.String(length=50), nullable=True, server_default="none"))
        batch_op.add_column(
            sa.Column("ai_image_model", sa.String(length=100), nullable=True, server_default="gpt-image-1")
        )

    # 2. Data Migration: copy settings fields from first schedule if possible
    connection = op.get_bind()
    try:
        schedule_row = connection.execute(
            sa.text(
                "SELECT ai_vision_provider, ai_vision_model, ai_image_provider, ai_image_model FROM schedules LIMIT 1"
            )
        ).fetchone()

        if schedule_row:
            connection.execute(
                sa.text(
                    "UPDATE settings SET "
                    "default_ai_provider = :vip, "
                    "default_ai_model = :vim, "
                    "ai_image_provider = :imp, "
                    "ai_image_model = :imm"
                ),
                {"vip": schedule_row[0], "vim": schedule_row[1], "imp": schedule_row[2], "imm": schedule_row[3]},
            )
    except Exception:
        pass

    # 3. Drop columns from schedules table
    with op.batch_alter_table("schedules", schema=None) as batch_op:
        batch_op.drop_column("ai_vision_provider")
        batch_op.drop_column("ai_vision_model")
        batch_op.drop_column("ai_image_provider")
        batch_op.drop_column("ai_image_model")
