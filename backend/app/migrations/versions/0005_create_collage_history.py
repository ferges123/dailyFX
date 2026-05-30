"""create collage history

Revision ID: 0005_create_collage_history
Revises: 0004_add_collage_image_mode
Create Date: 2026-05-13 12:10:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_create_collage_history"
down_revision = "0004_add_collage_image_mode"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "collage_history",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("task_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("layout", sa.String(length=100), nullable=False),
        sa.Column("proposal_json", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False, server_default="gemini"),
        sa.Column("model", sa.String(length=100), nullable=False, server_default="gemini-2.5-flash"),
        sa.Column("asset_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_token_count", sa.Integer(), nullable=True),
        sa.Column("image_path", sa.Text(), nullable=True),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="SUCCESS"),
        sa.Column("uploaded_asset_id", sa.String(length=64), nullable=True),
        sa.Column("upload_status", sa.String(length=50), nullable=True),
        sa.Column("album_id", sa.String(length=64), nullable=True),
        sa.Column("album_name", sa.String(length=255), nullable=True),
        sa.Column("album_created", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("album_updated", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_collage_history_task_id", "collage_history", ["task_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_collage_history_task_id", table_name="collage_history")
    op.drop_table("collage_history")
