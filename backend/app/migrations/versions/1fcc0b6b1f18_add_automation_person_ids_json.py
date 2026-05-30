"""add_automation_person_ids_json

Revision ID: 1fcc0b6b1f18
Revises: 0015_add_default_ai_model
Create Date: 2026-05-21 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1fcc0b6b1f18'
down_revision = '0015_add_default_ai_model'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('settings', sa.Column('automation_person_ids_json', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('settings', 'automation_person_ids_json')
