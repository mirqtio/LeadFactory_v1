"""Add campaign_id to funnel_events table

Revision ID: f4101a0ee2c8
Revises: add_lead_explorer_001
Create Date: 2025-07-15 10:55:20.499808

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f4101a0ee2c8'
down_revision = 'e3ab105c6555'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add campaign_id column to funnel_events table
    op.add_column('funnel_events', sa.Column('campaign_id', sa.String(), nullable=True))
    op.create_index('idx_funnel_events_campaign_id', 'funnel_events', ['campaign_id'])


def downgrade() -> None:
    # Remove campaign_id column from funnel_events table
    op.drop_index('idx_funnel_events_campaign_id', table_name='funnel_events')
    op.drop_column('funnel_events', 'campaign_id')
