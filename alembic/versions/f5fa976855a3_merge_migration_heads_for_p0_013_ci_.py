"""Merge migration heads for P0-013 CI stabilization

Revision ID: f5fa976855a3
Revises: 163712db254c, fix_fct_api_cost_lead_id_type
Create Date: 2025-07-19 09:59:38.106994

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f5fa976855a3'
down_revision = ('163712db254c', 'fix_fct_api_cost_lead_id_type')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
