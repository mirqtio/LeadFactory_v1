"""create unit_economics_day materialized view

Revision ID: 324616807570
Revises: a41430908e80
Create Date: 2025-07-18 08:39:38.841454

"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "324616807570"
down_revision = "a41430908e80"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the unit economics materialized view with proper table references"""

    # Create the unit economics materialized view
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
        daily_leads AS (
            -- Count daily lead generation (pipeline starts)
            SELECT 
                DATE(timestamp) as date,
                COUNT(*) as total_leads,
                COUNT(DISTINCT business_id) as unique_businesses
            FROM funnel_events
            WHERE event_type = 'PIPELINE_START'
                AND timestamp >= CURRENT_DATE - INTERVAL '365 days'
            GROUP BY DATE(timestamp)
        ),
        daily_assessments AS (
            -- Count daily successful assessments
            SELECT 
                DATE(timestamp) as date,
                COUNT(*) as total_assessments,
                COUNT(DISTINCT business_id) as unique_assessed_businesses
            FROM funnel_events
            WHERE event_type = 'ASSESSMENT_SUCCESS'
                AND timestamp >= CURRENT_DATE - INTERVAL '365 days'
            GROUP BY DATE(timestamp)
        )
        -- Final unit economics view with all key metrics
        SELECT 
            -- Date dimension
            COALESCE(dc.date, dcv.date, dl.date, da.date) as date,
            EXTRACT(YEAR FROM COALESCE(dc.date, dcv.date, dl.date, da.date)) as year,
            EXTRACT(MONTH FROM COALESCE(dc.date, dcv.date, dl.date, da.date)) as month,
            EXTRACT(DOW FROM COALESCE(dc.date, dcv.date, dl.date, da.date)) as day_of_week,
            
            -- Cost metrics
            COALESCE(dc.total_cost_cents, 0) as total_cost_cents,
            COALESCE(dc.total_api_calls, 0) as total_api_calls,
            COALESCE(dc.unique_requests, 0) as unique_requests,
            COALESCE(dc.avg_cost_per_call_cents, 0) as avg_cost_per_call_cents,
            
            -- Revenue metrics
            COALESCE(dcv.total_conversions, 0) as total_conversions,
            COALESCE(dcv.unique_converted_sessions, 0) as unique_converted_sessions,
            COALESCE(dcv.total_revenue_cents, 0) as total_revenue_cents,
            
            -- Lead metrics
            COALESCE(dl.total_leads, 0) as total_leads,
            COALESCE(dl.unique_businesses, 0) as unique_businesses,
            
            -- Assessment metrics
            COALESCE(da.total_assessments, 0) as total_assessments,
            COALESCE(da.unique_assessed_businesses, 0) as unique_assessed_businesses,
            
            -- Unit Economics Calculations (P2-010 Requirements)
            
            -- CPL (Cost Per Lead) in cents
            CASE 
                WHEN COALESCE(dl.total_leads, 0) > 0 THEN 
                    ROUND(COALESCE(dc.total_cost_cents, 0)::decimal / dl.total_leads::decimal, 2)
                ELSE NULL 
            END as cpl_cents,
            
            -- CAC (Customer Acquisition Cost) in cents
            CASE 
                WHEN COALESCE(dcv.total_conversions, 0) > 0 THEN 
                    ROUND(COALESCE(dc.total_cost_cents, 0)::decimal / dcv.total_conversions::decimal, 2)
                ELSE NULL 
            END as cac_cents,
            
            -- ROI (Return on Investment) as percentage
            CASE 
                WHEN COALESCE(dc.total_cost_cents, 0) > 0 THEN 
                    ROUND(
                        ((COALESCE(dcv.total_revenue_cents, 0) - COALESCE(dc.total_cost_cents, 0))::decimal 
                         / COALESCE(dc.total_cost_cents, 0)::decimal) * 100, 2
                    )
                ELSE NULL 
            END as roi_percentage,
            
            -- LTV (Lifetime Value) in cents - simplified as average revenue per customer
            CASE 
                WHEN COALESCE(dcv.total_conversions, 0) > 0 THEN 
                    ROUND(COALESCE(dcv.total_revenue_cents, 0)::decimal / dcv.total_conversions::decimal, 2)
                ELSE NULL 
            END as ltv_cents,
            
            -- Lead to conversion rate percentage
            CASE 
                WHEN COALESCE(dl.total_leads, 0) > 0 THEN 
                    ROUND((COALESCE(dcv.total_conversions, 0)::decimal / dl.total_leads::decimal) * 100, 2)
                ELSE 0 
            END as lead_to_conversion_rate_pct,
            
            -- Assessment to conversion rate percentage
            CASE 
                WHEN COALESCE(da.total_assessments, 0) > 0 THEN 
                    ROUND((COALESCE(dcv.total_conversions, 0)::decimal / da.total_assessments::decimal) * 100, 2)
                ELSE 0 
            END as assessment_to_conversion_rate_pct,
            
            -- Profit calculation in cents
            COALESCE(dcv.total_revenue_cents, 0) - COALESCE(dc.total_cost_cents, 0) as profit_cents,
            
            -- Metadata
            NOW() as last_updated
            
        FROM daily_costs dc
        FULL OUTER JOIN daily_conversions dcv ON dc.date = dcv.date
        FULL OUTER JOIN daily_leads dl ON COALESCE(dc.date, dcv.date) = dl.date
        FULL OUTER JOIN daily_assessments da ON COALESCE(dc.date, dcv.date, dl.date) = da.date
        WHERE COALESCE(dc.date, dcv.date, dl.date, da.date) IS NOT NULL
        ORDER BY COALESCE(dc.date, dcv.date, dl.date, da.date) DESC;
    """
    )

    # Create indexes for performance optimization
    op.execute(
        """
        CREATE UNIQUE INDEX idx_unit_economics_day_pk 
        ON unit_economics_day (date);
    """
    )

    op.execute(
        """
        CREATE INDEX idx_unit_economics_day_date_desc 
        ON unit_economics_day (date DESC);
    """
    )

    op.execute(
        """
        CREATE INDEX idx_unit_economics_day_month 
        ON unit_economics_day (year, month);
    """
    )


def downgrade() -> None:
    """Drop the unit economics materialized view"""
    op.execute("DROP MATERIALIZED VIEW IF EXISTS unit_economics_day CASCADE;")
