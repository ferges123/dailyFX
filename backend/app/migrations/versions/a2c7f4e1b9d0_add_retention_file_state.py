"""add local file retention state"""

import sqlalchemy as sa
from alembic import op

revision = "a2c7f4e1b9d0"
down_revision = "9b6e5e2f1a0c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "generation_history",
        sa.Column("local_file_status", sa.String(length=30), nullable=False, server_default="available"),
    )
    op.add_column("generation_history", sa.Column("local_file_deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("generation_history", sa.Column("local_file_delete_reason", sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column("generation_history", "local_file_delete_reason")
    op.drop_column("generation_history", "local_file_deleted_at")
    op.drop_column("generation_history", "local_file_status")
