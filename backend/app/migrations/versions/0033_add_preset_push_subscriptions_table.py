"""add preset push subscriptions table

Revision ID: 0033
Revises: 0032_add_ai_photo_selection_to_schedules
Create Date: 2026-06-10 17:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "0033"
down_revision = "0032_add_ai_photo_selection_to_schedules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "preset_push_subscriptions",
        sa.Column("notification_preset_id", sa.Integer(), nullable=False),
        sa.Column("push_subscription_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["notification_preset_id"], ["notification_presets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["push_subscription_id"], ["push_subscriptions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("notification_preset_id", "push_subscription_id"),
    )

    # Development app policy: existing subscriptions are not migrated into preset targets.
    # They may be stale or from old browser permission state, so clear them and force re-subscription.
    op.execute("DELETE FROM push_subscriptions")


def downgrade() -> None:
    op.drop_table("preset_push_subscriptions")
