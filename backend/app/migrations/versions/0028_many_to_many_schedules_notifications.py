"""many to many schedules notifications

Revision ID: 0028_many_to_many_schedules_notifications
Revises: 0027_add_xiaomi_api_key
Create Date: 2026-05-27
"""

import sqlalchemy as sa
from alembic import op

revision = "0028_many_to_many_schedules_notifications"
down_revision = "0027_add_xiaomi_api_key"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create junction table
    op.create_table(
        "schedule_notification_presets",
        sa.Column("schedule_id", sa.Integer(), nullable=False),
        sa.Column("notification_preset_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["notification_preset_id"], ["notification_presets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["schedule_id"], ["schedules.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("schedule_id", "notification_preset_id"),
    )

    # 2. Migrate existing data
    conn = op.get_bind()
    # Fetch existing schedule_id and notification_preset_id pairings
    res = conn.execute(
        sa.text("SELECT id, notification_preset_id FROM schedules WHERE notification_preset_id IS NOT NULL")
    ).fetchall()
    for row in res:
        conn.execute(
            sa.text(
                "INSERT INTO schedule_notification_presets (schedule_id, notification_preset_id) VALUES (:schedule_id, :preset_id)"
            ),
            {"schedule_id": row[0], "preset_id": row[1]},
        )

    # 3. Drop notification_preset_id column from schedules using batch operation
    with op.batch_alter_table("schedules", schema=None) as batch_op:
        batch_op.drop_column("notification_preset_id")


def downgrade() -> None:
    # 1. Add notification_preset_id column back to schedules table
    with op.batch_alter_table("schedules", schema=None) as batch_op:
        batch_op.add_column(sa.Column("notification_preset_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_schedules_notification_preset_id", "notification_presets", ["notification_preset_id"], ["id"]
        )

    # 2. Migrate data back (take the first notification preset from the association table for each schedule)
    conn = op.get_bind()
    res = conn.execute(
        sa.text("SELECT schedule_id, notification_preset_id FROM schedule_notification_presets")
    ).fetchall()
    # We group by schedule_id to set only one (since column can only store one)
    seen_schedules = set()
    for row in res:
        sched_id, preset_id = row[0], row[1]
        if sched_id not in seen_schedules:
            conn.execute(
                sa.text("UPDATE schedules SET notification_preset_id = :preset_id WHERE id = :sched_id"),
                {"preset_id": preset_id, "sched_id": sched_id},
            )
            seen_schedules.add(sched_id)

    # 3. Drop junction table
    op.drop_table("schedule_notification_presets")
