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
        sa.Column('metadata', sa.JSON(), nullable=True),
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
    
    # Create a view for total costs by provider
    op.execute("""
        CREATE OR REPLACE VIEW v_provider_costs AS
        SELECT 
            provider,
            DATE(timestamp) as date,
            COUNT(*) as request_count,
            SUM(cost_usd) as total_cost_usd,
            AVG(cost_usd) as avg_cost_usd,
            MIN(timestamp) as first_request,
            MAX(timestamp) as last_request
        FROM fct_api_cost
        GROUP BY provider, DATE(timestamp)
        ORDER BY date DESC, provider;
    """)
    
    # Create a view for campaign costs
    op.execute("""
        CREATE OR REPLACE VIEW v_campaign_costs AS
        SELECT 
            c.id as campaign_id,
            c.name as campaign_name,
            c.status as campaign_status,
            COUNT(DISTINCT ac.id) as api_calls,
            COALESCE(SUM(ac.cost_usd), 0) as total_cost_usd,
            COALESCE(AVG(ac.cost_usd), 0) as avg_cost_per_call,
            MIN(ac.timestamp) as first_api_call,
            MAX(ac.timestamp) as last_api_call
        FROM dim_campaign c
        LEFT JOIN fct_api_cost ac ON c.id = ac.campaign_id
        GROUP BY c.id, c.name, c.status
        ORDER BY total_cost_usd DESC;
    """)
    
    # Create a trigger to automatically update daily aggregates
    op.execute("""
        CREATE OR REPLACE FUNCTION update_daily_cost_aggregate()
        RETURNS TRIGGER AS $$
        BEGIN
            INSERT INTO agg_daily_cost (
                date, provider, operation, campaign_id, 
                total_cost_usd, request_count
            )
            VALUES (
                DATE(NEW.timestamp), 
                NEW.provider, 
                NEW.operation,
                NEW.campaign_id,
                NEW.cost_usd, 
                1
            )
            ON CONFLICT (date, provider, operation, campaign_id)
            DO UPDATE SET
                total_cost_usd = agg_daily_cost.total_cost_usd + EXCLUDED.total_cost_usd,
                request_count = agg_daily_cost.request_count + 1,
                updated_at = CURRENT_TIMESTAMP;
            
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        
        CREATE TRIGGER trigger_update_daily_cost
        AFTER INSERT ON fct_api_cost
        FOR EACH ROW
        EXECUTE FUNCTION update_daily_cost_aggregate();
    """)


def downgrade():
    """Drop cost tracking tables"""
    
    # Drop trigger and function
    op.execute("DROP TRIGGER IF EXISTS trigger_update_daily_cost ON fct_api_cost")
    op.execute("DROP FUNCTION IF EXISTS update_daily_cost_aggregate()")
    
    # Drop views
    op.execute("DROP VIEW IF EXISTS v_campaign_costs")
    op.execute("DROP VIEW IF EXISTS v_provider_costs")
    
    # Drop tables
    op.drop_table('agg_daily_cost')
    op.drop_table('fct_api_cost')