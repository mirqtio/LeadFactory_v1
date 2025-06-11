"""Create analytics views for Phase 0.5

Task AN-08: Views unit_economics_day, bucket_performance

Revision ID: 004_analytics_views
Revises: 003_cost_tracking
Create Date: 2025-06-11

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '004_analytics_views'
down_revision = '003_cost_tracking'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create analytics views for unit economics and bucket performance"""
    
    # Create unit_economics_day view
    op.execute("""
        CREATE OR REPLACE VIEW unit_economics_day AS
        WITH daily_metrics AS (
            SELECT 
                DATE(e.sent_at) as date,
                COUNT(DISTINCT b.id) as businesses_contacted,
                COUNT(DISTINCT CASE WHEN e.status = 'delivered' THEN b.id END) as businesses_delivered,
                COUNT(DISTINCT CASE WHEN e.status = 'opened' THEN b.id END) as businesses_opened,
                COUNT(DISTINCT CASE WHEN e.status = 'clicked' THEN b.id END) as businesses_clicked,
                COUNT(DISTINCT p.id) as purchases,
                SUM(p.amount_cents) / 100.0 as revenue_usd
            FROM emails e
            JOIN businesses b ON e.business_id = b.id
            LEFT JOIN purchases p ON b.id = p.business_id 
                AND DATE(p.created_at) = DATE(e.sent_at)
            WHERE e.sent_at IS NOT NULL
            GROUP BY DATE(e.sent_at)
        ),
        daily_costs AS (
            SELECT 
                date,
                SUM(total_cost_usd) as total_cost_usd,
                SUM(CASE WHEN provider = 'yelp' THEN total_cost_usd ELSE 0 END) as yelp_cost,
                SUM(CASE WHEN provider = 'googlemaps' THEN total_cost_usd ELSE 0 END) as maps_cost,
                SUM(CASE WHEN provider = 'pagespeed' THEN total_cost_usd ELSE 0 END) as pagespeed_cost,
                SUM(CASE WHEN provider = 'openai' THEN total_cost_usd ELSE 0 END) as openai_cost,
                SUM(CASE WHEN provider = 'sendgrid' THEN total_cost_usd ELSE 0 END) as sendgrid_cost,
                SUM(CASE WHEN provider = 'dataaxle' THEN total_cost_usd ELSE 0 END) as dataaxle_cost,
                SUM(CASE WHEN provider = 'hunter' THEN total_cost_usd ELSE 0 END) as hunter_cost
            FROM agg_daily_cost
            GROUP BY date
        )
        SELECT 
            COALESCE(m.date, c.date) as date,
            COALESCE(m.businesses_contacted, 0) as businesses_contacted,
            COALESCE(m.businesses_delivered, 0) as businesses_delivered,
            COALESCE(m.businesses_opened, 0) as businesses_opened,
            COALESCE(m.businesses_clicked, 0) as businesses_clicked,
            COALESCE(m.purchases, 0) as purchases,
            COALESCE(m.revenue_usd, 0) as revenue_usd,
            COALESCE(c.total_cost_usd, 0) as total_cost_usd,
            COALESCE(m.revenue_usd, 0) - COALESCE(c.total_cost_usd, 0) as profit_usd,
            CASE 
                WHEN COALESCE(c.total_cost_usd, 0) > 0 
                THEN (COALESCE(m.revenue_usd, 0) - COALESCE(c.total_cost_usd, 0)) / c.total_cost_usd
                ELSE NULL 
            END as roi,
            CASE 
                WHEN COALESCE(m.businesses_contacted, 0) > 0 
                THEN COALESCE(c.total_cost_usd, 0) / m.businesses_contacted
                ELSE NULL 
            END as cost_per_contact,
            CASE 
                WHEN COALESCE(m.purchases, 0) > 0 
                THEN COALESCE(c.total_cost_usd, 0) / m.purchases
                ELSE NULL 
            END as cost_per_acquisition,
            CASE 
                WHEN COALESCE(m.businesses_contacted, 0) > 0 
                THEN m.purchases::FLOAT / m.businesses_contacted * 100
                ELSE 0 
            END as conversion_rate,
            -- Provider breakdown
            COALESCE(c.yelp_cost, 0) as yelp_cost,
            COALESCE(c.maps_cost, 0) as maps_cost,
            COALESCE(c.pagespeed_cost, 0) as pagespeed_cost,
            COALESCE(c.openai_cost, 0) as openai_cost,
            COALESCE(c.sendgrid_cost, 0) as sendgrid_cost,
            COALESCE(c.dataaxle_cost, 0) as dataaxle_cost,
            COALESCE(c.hunter_cost, 0) as hunter_cost
        FROM daily_metrics m
        FULL OUTER JOIN daily_costs c ON m.date = c.date
        ORDER BY date DESC;
    """)
    
    # Create bucket_performance view
    op.execute("""
        CREATE OR REPLACE VIEW bucket_performance AS
        WITH bucket_metrics AS (
            SELECT 
                b.geo_bucket,
                b.vert_bucket,
                COUNT(DISTINCT b.id) as total_businesses,
                COUNT(DISTINCT e.id) as emails_sent,
                COUNT(DISTINCT CASE WHEN e.status = 'delivered' THEN e.id END) as emails_delivered,
                COUNT(DISTINCT CASE WHEN e.status = 'opened' THEN e.id END) as emails_opened,
                COUNT(DISTINCT CASE WHEN e.status = 'clicked' THEN e.id END) as emails_clicked,
                COUNT(DISTINCT p.id) as purchases,
                SUM(p.amount_cents) / 100.0 as total_revenue_usd,
                AVG(s.score_pct) as avg_score,
                COUNT(DISTINCT CASE WHEN s.tier = 'A' THEN b.id END) as tier_a_count,
                COUNT(DISTINCT CASE WHEN s.tier = 'B' THEN b.id END) as tier_b_count,
                COUNT(DISTINCT CASE WHEN s.tier = 'C' THEN b.id END) as tier_c_count,
                COUNT(DISTINCT CASE WHEN s.tier = 'D' THEN b.id END) as tier_d_count
            FROM businesses b
            LEFT JOIN emails e ON b.id = e.business_id
            LEFT JOIN purchases p ON b.id = p.business_id
            LEFT JOIN scoring_results s ON b.id = s.business_id
            WHERE b.geo_bucket IS NOT NULL 
               OR b.vert_bucket IS NOT NULL
            GROUP BY b.geo_bucket, b.vert_bucket
        ),
        bucket_costs AS (
            SELECT 
                b.geo_bucket,
                b.vert_bucket,
                SUM(ac.cost_usd) as total_cost_usd,
                COUNT(DISTINCT ac.id) as api_calls,
                AVG(ac.cost_usd) as avg_cost_per_call
            FROM businesses b
            JOIN fct_api_cost ac ON b.id = ac.lead_id
            WHERE b.geo_bucket IS NOT NULL 
               OR b.vert_bucket IS NOT NULL
            GROUP BY b.geo_bucket, b.vert_bucket
        )
        SELECT 
            COALESCE(m.geo_bucket, 'unknown') as geo_bucket,
            COALESCE(m.vert_bucket, 'unknown') as vert_bucket,
            m.total_businesses,
            m.emails_sent,
            m.emails_delivered,
            m.emails_opened,
            m.emails_clicked,
            m.purchases,
            COALESCE(m.total_revenue_usd, 0) as total_revenue_usd,
            COALESCE(c.total_cost_usd, 0) as total_cost_usd,
            COALESCE(m.total_revenue_usd, 0) - COALESCE(c.total_cost_usd, 0) as profit_usd,
            CASE 
                WHEN m.emails_sent > 0 
                THEN m.emails_delivered::FLOAT / m.emails_sent * 100
                ELSE 0 
            END as delivery_rate,
            CASE 
                WHEN m.emails_delivered > 0 
                THEN m.emails_opened::FLOAT / m.emails_delivered * 100
                ELSE 0 
            END as open_rate,
            CASE 
                WHEN m.emails_opened > 0 
                THEN m.emails_clicked::FLOAT / m.emails_opened * 100
                ELSE 0 
            END as click_rate,
            CASE 
                WHEN m.emails_sent > 0 
                THEN m.purchases::FLOAT / m.emails_sent * 100
                ELSE 0 
            END as conversion_rate,
            CASE 
                WHEN m.purchases > 0 
                THEN m.total_revenue_usd / m.purchases
                ELSE 0 
            END as avg_order_value,
            CASE 
                WHEN m.purchases > 0 
                THEN c.total_cost_usd / m.purchases
                ELSE NULL 
            END as cost_per_acquisition,
            CASE 
                WHEN c.total_cost_usd > 0 
                THEN (m.total_revenue_usd - c.total_cost_usd) / c.total_cost_usd
                ELSE NULL 
            END as roi,
            m.avg_score,
            m.tier_a_count,
            m.tier_b_count,
            m.tier_c_count,
            m.tier_d_count,
            c.api_calls,
            c.avg_cost_per_call
        FROM bucket_metrics m
        LEFT JOIN bucket_costs c ON m.geo_bucket = c.geo_bucket 
            AND m.vert_bucket = c.vert_bucket
        ORDER BY m.total_businesses DESC;
    """)
    
    # Create indexes on bucket columns if they don't exist
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_businesses_geo_bucket ON businesses(geo_bucket);
        CREATE INDEX IF NOT EXISTS idx_businesses_vert_bucket ON businesses(vert_bucket);
        CREATE INDEX IF NOT EXISTS idx_businesses_buckets ON businesses(geo_bucket, vert_bucket);
        CREATE INDEX IF NOT EXISTS idx_targets_geo_bucket ON targets(geo_bucket);
        CREATE INDEX IF NOT EXISTS idx_targets_vert_bucket ON targets(vert_bucket);
    """)


def downgrade() -> None:
    """Drop analytics views"""
    op.execute("DROP VIEW IF EXISTS bucket_performance")
    op.execute("DROP VIEW IF EXISTS unit_economics_day")
    
    # Drop indexes
    op.execute("DROP INDEX IF EXISTS idx_businesses_geo_bucket")
    op.execute("DROP INDEX IF EXISTS idx_businesses_vert_bucket")
    op.execute("DROP INDEX IF EXISTS idx_businesses_buckets")
    op.execute("DROP INDEX IF EXISTS idx_targets_geo_bucket")
    op.execute("DROP INDEX IF EXISTS idx_targets_vert_bucket")