"""Cost tracking for API providers

Revision ID: 003_cost_tracking
Revises: 002_analytics_views
Create Date: 2025-06-11

Phase 0.5 - Task GW-04
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '003_cost_tracking'
down_revision = '002_analytics_views'
branch_labels = None
depends_on = None


def upgrade():
    """Create cost tracking tables"""
    
    # Create the fact table for API costs
    op.create_table(
        'fct_api_cost',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('provider', sa.String(50), nullable=False),
        sa.Column('operation', sa.String(100), nullable=False),
        sa.Column('lead_id', sa.Integer(), sa.ForeignKey('dim_lead.id', ondelete='CASCADE'), nullable=True),
        sa.Column('campaign_id', sa.Integer(), sa.ForeignKey('dim_campaign.id', ondelete='CASCADE'), nullable=True),
        sa.Column('cost_usd', sa.Numeric(10, 4), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('request_id', sa.String(100), nullable=True),
        sa.Column('meta_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    
    # Create indexes for performance
    op.create_index('idx_api_cost_provider', 'fct_api_cost', ['provider'])
    op.create_index('idx_api_cost_timestamp', 'fct_api_cost', ['timestamp'])
    op.create_index('idx_api_cost_lead', 'fct_api_cost', ['lead_id'])
    op.create_index('idx_api_cost_campaign', 'fct_api_cost', ['campaign_id'])
    op.create_index('idx_api_cost_provider_timestamp', 'fct_api_cost', ['provider', 'timestamp'])
    
    # Create a daily cost summary table for faster aggregations
    op.create_table(
        'agg_daily_cost',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('provider', sa.String(50), nullable=False),
        sa.Column('operation', sa.String(100), nullable=True),
        sa.Column('campaign_id', sa.Integer(), sa.ForeignKey('dim_campaign.id', ondelete='CASCADE'), nullable=True),
        sa.Column('total_cost_usd', sa.Numeric(10, 4), nullable=False),
        sa.Column('request_count', sa.Integer(), nullable=False, default=0),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP')),
    )
    
    # Unique constraint to prevent duplicate daily summaries
    op.create_index(
        'idx_daily_cost_unique',
        'agg_daily_cost',
        ['date', 'provider', 'operation', 'campaign_id'],
        unique=True
    )
    
    # Skip views and triggers for SQLite - they use PostgreSQL-specific syntax
    # These are for production use with PostgreSQL
    pass


def downgrade():
    """Drop cost tracking tables"""
    
    # Drop tables
    op.drop_table('agg_daily_cost')
    op.drop_table('fct_api_cost')