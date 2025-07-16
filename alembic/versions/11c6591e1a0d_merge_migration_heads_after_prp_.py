"""Merge migration heads after PRP completion

Revision ID: 11c6591e1a0d
Revises: create_agg_daily_cost, fix_p2_000_timezone_support, p2_010_collaborative_buckets
Create Date: 2025-07-16 11:37:40.419642

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '11c6591e1a0d'
down_revision = ('create_agg_daily_cost', 'fix_p2_000_timezone_support', 'p2_010_collaborative_buckets')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
