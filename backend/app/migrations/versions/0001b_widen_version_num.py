"""Widen alembic_version.version_num for long revision IDs

Revision ID: 0001b_widen_version_num
Revises: 0001_create_settings
Create Date: 2026-10-03

Alembic creates alembic_version.version_num as VARCHAR(32), but several
revision IDs in this project are longer (up to 49 chars). SQLite ignores
the length limit, so this went unnoticed; PostgreSQL enforces it and the
bookkeeping UPDATE fails. Widen the column right at the start of the chain
so every fresh build (SQLite and PostgreSQL) can stamp all revisions.
Existing databases are unaffected (VARCHAR widening is a no-op for data).
"""

import sqlalchemy as sa
from alembic import op

revision = "0001b_widen_version_num"
down_revision = "0001_create_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("alembic_version") as batch_op:
        batch_op.alter_column(
            "version_num",
            type_=sa.String(255),
            existing_type=sa.String(32),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("alembic_version") as batch_op:
        batch_op.alter_column(
            "version_num",
            type_=sa.String(32),
            existing_type=sa.String(255),
            existing_nullable=False,
        )
