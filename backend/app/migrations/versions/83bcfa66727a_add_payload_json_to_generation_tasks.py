"""add_payload_json_to_generation_tasks

Revision ID: 83bcfa66727a
Revises: 0029_add_ai_prompt_enrichment_to_schedules
Create Date: 2026-05-28 11:08:00.404543
"""
from alembic import op
import sqlalchemy as sa


revision = '83bcfa66727a'
down_revision = '0029_add_ai_prompt_enrichment_to_schedules'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('generation_tasks', sa.Column('payload_json', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('generation_tasks', 'payload_json')


