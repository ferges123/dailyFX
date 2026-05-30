"""add_debug_mode

Revision ID: 104dd93b730f
Revises: 0017_add_automation_filters_json
Create Date: 2026-05-23 09:09:01.216251
"""
from alembic import op
import sqlalchemy as sa


revision = '104dd93b730f'
down_revision = '0017_add_automation_filters_json'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('settings', sa.Column('debug_mode', sa.Boolean(), nullable=False, server_default='0'))


def downgrade() -> None:
    op.drop_column('settings', 'debug_mode')
