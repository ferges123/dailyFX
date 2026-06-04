"""add ai effects table

Revision ID: 0030_add_ai_effects_table
Revises: 0029_add_ai_prompt_enrichment_to_schedules, merge_83bcfa66727a_and_f5a6b7c8d9e0
Create Date: 2026-06-01
"""

from alembic import op
import sqlalchemy as sa

revision = "0030_add_ai_effects_table"
down_revision = ("0029_add_ai_prompt_enrichment_to_schedules", "merge_83bcfa66727a_and_f5a6b7c8d9e0")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_effects",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("positive_prompt", sa.Text(), nullable=False),
        sa.Column("negative_prompt", sa.Text(), nullable=True),
        sa.Column("custom_prompt_placeholder", sa.String(length=255), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="builtin"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("weight", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("builtin_hash", sa.String(length=128), nullable=True),
        sa.Column("latest_builtin_hash", sa.String(length=128), nullable=True),
        sa.Column("user_modified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("ai_effects")
