"""Fix migration dependency order for fct_api_cost table

The unit_economics_day materialized view depends on fct_api_cost table
but the table creation was ordered after the view creation, causing CI failures.

Revision ID: fix_migration_dependency_order_fct_api_cost
Revises: 5186822f03ee
Create Date: 2025-07-19 14:15:00.000000

"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "fix_migration_dependency_order_fct_api_cost"
down_revision = "5186822f03ee"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Ensure fct_api_cost table exists before analytics views are created"""

    # Check if fct_api_cost table exists, create if not
    # This handles the case where the migration order was wrong
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM information_schema.tables 
                         WHERE table_schema = 'public' 
                         AND table_name = 'fct_api_cost') THEN
                
                CREATE TABLE fct_api_cost (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMPTZ NOT NULL,
                    cost_usd NUMERIC(10,6) NOT NULL,
                    request_id VARCHAR(100),
                    lead_id VARCHAR(100),
                    gateway_provider VARCHAR(50),
                    api_endpoint VARCHAR(200),
                    response_status INTEGER,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                
                CREATE INDEX IF NOT EXISTS idx_api_cost_timestamp ON fct_api_cost (timestamp);
                CREATE INDEX IF NOT EXISTS idx_api_cost_lead ON fct_api_cost (lead_id);
                CREATE INDEX IF NOT EXISTS idx_api_cost_provider ON fct_api_cost (gateway_provider);
                
            END IF;
        END $$;
        """
    )

    # Now safely recreate the unit_economics_day view with proper dependencies
    op.execute("DROP MATERIALIZED VIEW IF EXISTS unit_economics_day CASCADE;")

    # Create the unit economics materialized view with proper table references
    op.execute(
        """
        CREATE MATERIALIZED VIEW unit_economics_day AS
        WITH daily_costs AS (
            -- Aggregate daily gateway costs from API cost ledger
            SELECT 
                DATE(timestamp) as date,
                SUM(cost_usd * 100) as total_cost_cents, -- Convert USD to cents
                COUNT(*) as total_api_calls,
                COUNT(DISTINCT request_id) as unique_requests,
                AVG(cost_usd * 100) as avg_cost_per_call_cents
            FROM fct_api_cost
            WHERE timestamp >= CURRENT_DATE - INTERVAL '365 days'
            GROUP BY DATE(timestamp)
        ),
        daily_conversions AS (
            -- Aggregate daily conversions from payment events
            SELECT 
                DATE(timestamp) as date,
                COUNT(*) as total_conversions,
                COUNT(DISTINCT session_id) as unique_converted_sessions,
                SUM(CASE WHEN event_metadata->>'amount_cents' IS NOT NULL 
                    THEN (event_metadata->>'amount_cents')::integer 
                    ELSE 39900 END) as total_revenue_cents -- Default $399 price
            FROM funnel_events
            WHERE event_type = 'PAYMENT_SUCCESS'
                AND timestamp >= CURRENT_DATE - INTERVAL '365 days'
            GROUP BY DATE(timestamp)
        ),
        daily_metrics AS (
            -- Combine cost and conversion data
            SELECT 
                COALESCE(c.date, conv.date) as date,
                COALESCE(c.total_cost_cents, 0) as total_cost_cents,
                COALESCE(c.total_api_calls, 0) as total_api_calls,
                COALESCE(c.unique_requests, 0) as unique_requests,
                COALESCE(c.avg_cost_per_call_cents, 0) as avg_cost_per_call_cents,
                COALESCE(conv.total_conversions, 0) as total_conversions,
                COALESCE(conv.unique_converted_sessions, 0) as unique_converted_sessions,
                COALESCE(conv.total_revenue_cents, 0) as total_revenue_cents
            FROM daily_costs c
            FULL OUTER JOIN daily_conversions conv ON c.date = conv.date
        )
        SELECT 
            date,
            total_cost_cents,
            total_api_calls,
            unique_requests,
            avg_cost_per_call_cents,
            total_conversions,
            unique_converted_sessions,
            total_revenue_cents,
            -- Calculate derived metrics
            CASE 
                WHEN total_conversions > 0 THEN total_cost_cents::FLOAT / total_conversions
                ELSE 0
            END as cost_per_acquisition_cents,
            CASE 
                WHEN total_cost_cents > 0 THEN (total_revenue_cents - total_cost_cents)::FLOAT / total_cost_cents * 100
                ELSE 0
            END as roi_percentage,
            (total_revenue_cents - total_cost_cents) as profit_cents,
            CASE 
                WHEN total_api_calls > 0 THEN unique_requests::FLOAT / total_api_calls * 100
                ELSE 0
            END as request_efficiency_percentage
        FROM daily_metrics
        WHERE date >= CURRENT_DATE - INTERVAL '365 days'
        ORDER BY date DESC;
        """
    )

    # Create index for better query performance
    op.execute("CREATE INDEX IF NOT EXISTS idx_unit_economics_day_date ON unit_economics_day (date);")


def downgrade() -> None:
    """Drop the corrected materialized view"""
    op.execute("DROP MATERIALIZED VIEW IF EXISTS unit_economics_day CASCADE;")
