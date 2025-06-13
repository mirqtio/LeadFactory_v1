-- Phase 0.5 Analytics Views
-- Task AN-08: unit_economics_day and bucket_performance views
--
-- Provides cost tracking and bucket-based performance analysis

-- =============================================================================
-- UNIT ECONOMICS BY DAY VIEW
-- =============================================================================

-- Drop existing view if it exists
DROP VIEW IF EXISTS unit_economics_day CASCADE;

-- Create unit economics daily view
CREATE VIEW unit_economics_day AS
WITH daily_costs AS (
    -- Aggregate API costs by day
    SELECT 
        DATE(timestamp) as date,
        provider,
        SUM(cost_usd) as total_cost_usd,
        COUNT(*) as api_calls,
        COUNT(DISTINCT lead_id) as unique_leads,
        COUNT(DISTINCT campaign_id) as unique_campaigns
    FROM fct_api_cost
    WHERE timestamp >= CURRENT_DATE - INTERVAL '90 days'
    GROUP BY DATE(timestamp), provider
),
daily_revenue AS (
    -- Get revenue by day (from purchases)
    SELECT 
        DATE(completed_at) as date,
        SUM(amount_cents) / 100.0 as revenue_usd,
        COUNT(*) as purchases,
        COUNT(DISTINCT business_id) as unique_businesses
    FROM purchases
    WHERE status = 'completed'
        AND completed_at >= CURRENT_DATE - INTERVAL '90 days'
    GROUP BY DATE(completed_at)
),
daily_metrics AS (
    -- Combine costs and revenue
    SELECT 
        COALESCE(dc.date, dr.date) as date,
        COALESCE(SUM(dc.total_cost_usd), 0) as total_cost_usd,
        COALESCE(dr.revenue_usd, 0) as revenue_usd,
        COALESCE(dr.revenue_usd, 0) - COALESCE(SUM(dc.total_cost_usd), 0) as profit_usd,
        CASE 
            WHEN COALESCE(SUM(dc.total_cost_usd), 0) > 0 
            THEN (COALESCE(dr.revenue_usd, 0) - COALESCE(SUM(dc.total_cost_usd), 0)) / SUM(dc.total_cost_usd) * 100
            ELSE 0 
        END as profit_margin_pct,
        SUM(COALESCE(dc.api_calls, 0)) as total_api_calls,
        MAX(COALESCE(dc.unique_leads, 0)) as unique_leads,
        COALESCE(dr.purchases, 0) as purchases,
        COALESCE(dr.unique_businesses, 0) as unique_businesses,
        -- Provider breakdown
        STRING_AGG(
            dc.provider || ':$' || ROUND(dc.total_cost_usd::numeric, 2)::text,
            ', ' ORDER BY dc.total_cost_usd DESC
        ) as provider_costs
    FROM daily_costs dc
    FULL OUTER JOIN daily_revenue dr ON dc.date = dr.date
    GROUP BY COALESCE(dc.date, dr.date), dr.revenue_usd, dr.purchases, dr.unique_businesses
)
SELECT 
    date,
    total_cost_usd,
    revenue_usd,
    profit_usd,
    profit_margin_pct,
    total_api_calls,
    unique_leads,
    purchases,
    unique_businesses,
    CASE 
        WHEN unique_leads > 0 
        THEN total_cost_usd / unique_leads 
        ELSE 0 
    END as cost_per_lead,
    CASE 
        WHEN purchases > 0 
        THEN total_cost_usd / purchases 
        ELSE 0 
    END as cost_per_acquisition,
    provider_costs
FROM daily_metrics
ORDER BY date DESC;

-- =============================================================================
-- BUCKET PERFORMANCE VIEW
-- =============================================================================

-- Drop existing view if it exists
DROP VIEW IF EXISTS bucket_performance CASCADE;

-- Create bucket performance view
CREATE VIEW bucket_performance AS
WITH bucket_metrics AS (
    -- Get performance metrics by bucket combination
    SELECT 
        b.geo_bucket,
        b.vert_bucket,
        COUNT(DISTINCT b.id) as total_businesses,
        COUNT(DISTINCT p.id) as total_purchases,
        COUNT(DISTINCT e.id) as total_emails_sent,
        COUNT(DISTINCT CASE WHEN e.status = 'opened' THEN e.id END) as emails_opened,
        COUNT(DISTINCT CASE WHEN e.status = 'clicked' THEN e.id END) as emails_clicked,
        COUNT(DISTINCT sr.id) as total_scored,
        AVG(sr.score_pct) as avg_score_pct,
        COUNT(DISTINCT CASE WHEN sr.tier = 'A' THEN sr.id END) as tier_a_count,
        COUNT(DISTINCT CASE WHEN sr.tier = 'B' THEN sr.id END) as tier_b_count,
        SUM(p.amount_cents) / 100.0 as total_revenue_usd
    FROM businesses b
    LEFT JOIN purchases p ON b.id = p.business_id AND p.status = 'completed'
    LEFT JOIN emails e ON b.id = e.business_id
    LEFT JOIN scoring_results sr ON b.id = sr.business_id
    WHERE b.geo_bucket IS NOT NULL 
        AND b.vert_bucket IS NOT NULL
    GROUP BY b.geo_bucket, b.vert_bucket
),
bucket_costs AS (
    -- Get costs by bucket (via lead association when available)
    SELECT 
        b.geo_bucket,
        b.vert_bucket,
        SUM(ac.cost_usd) as total_cost_usd,
        COUNT(DISTINCT ac.provider) as providers_used,
        AVG(ac.cost_usd) as avg_cost_per_call
    FROM fct_api_cost ac
    -- Join through lead_id when we have a proper lead table
    -- For now, approximate by joining through timing
    JOIN businesses b ON DATE(ac.timestamp) = DATE(b.created_at)
    WHERE b.geo_bucket IS NOT NULL 
        AND b.vert_bucket IS NOT NULL
    GROUP BY b.geo_bucket, b.vert_bucket
),
bucket_conversion AS (
    -- Calculate conversion metrics
    SELECT 
        bm.geo_bucket,
        bm.vert_bucket,
        bm.total_businesses,
        bm.total_purchases,
        bm.total_emails_sent,
        bm.emails_opened,
        bm.emails_clicked,
        bm.total_scored,
        bm.avg_score_pct,
        bm.tier_a_count,
        bm.tier_b_count,
        COALESCE(bm.total_revenue_usd, 0) as total_revenue_usd,
        COALESCE(bc.total_cost_usd, 0) as total_cost_usd,
        COALESCE(bm.total_revenue_usd, 0) - COALESCE(bc.total_cost_usd, 0) as profit_usd,
        -- Conversion rates
        CASE 
            WHEN bm.total_businesses > 0 
            THEN bm.total_purchases * 100.0 / bm.total_businesses 
            ELSE 0 
        END as purchase_rate_pct,
        CASE 
            WHEN bm.total_emails_sent > 0 
            THEN bm.emails_opened * 100.0 / bm.total_emails_sent 
            ELSE 0 
        END as open_rate_pct,
        CASE 
            WHEN bm.emails_opened > 0 
            THEN bm.emails_clicked * 100.0 / bm.emails_opened 
            ELSE 0 
        END as click_rate_pct,
        -- Unit economics
        CASE 
            WHEN bm.total_businesses > 0 
            THEN COALESCE(bc.total_cost_usd, 0) / bm.total_businesses 
            ELSE 0 
        END as cost_per_business,
        CASE 
            WHEN bm.total_purchases > 0 
            THEN COALESCE(bc.total_cost_usd, 0) / bm.total_purchases 
            ELSE 0 
        END as cost_per_acquisition,
        CASE 
            WHEN bm.total_purchases > 0 
            THEN bm.total_revenue_usd / bm.total_purchases 
            ELSE 0 
        END as avg_order_value
    FROM bucket_metrics bm
    LEFT JOIN bucket_costs bc USING (geo_bucket, vert_bucket)
)
SELECT 
    geo_bucket,
    vert_bucket,
    -- Parse bucket components for analysis
    SPLIT_PART(geo_bucket, '-', 1) as affluence,
    SPLIT_PART(geo_bucket, '-', 2) as density,
    SPLIT_PART(geo_bucket, '-', 3) as broadband,
    SPLIT_PART(vert_bucket, '-', 1) as urgency,
    SPLIT_PART(vert_bucket, '-', 2) as ticket,
    SPLIT_PART(vert_bucket, '-', 3) as maturity,
    -- Metrics
    total_businesses,
    total_purchases,
    total_emails_sent,
    emails_opened,
    emails_clicked,
    total_scored,
    avg_score_pct,
    tier_a_count,
    tier_b_count,
    total_revenue_usd,
    total_cost_usd,
    profit_usd,
    purchase_rate_pct,
    open_rate_pct,
    click_rate_pct,
    cost_per_business,
    cost_per_acquisition,
    avg_order_value,
    -- Performance rank
    RANK() OVER (ORDER BY profit_usd DESC) as profit_rank,
    RANK() OVER (ORDER BY purchase_rate_pct DESC) as conversion_rank
FROM bucket_conversion
ORDER BY profit_usd DESC;

-- =============================================================================
-- COST GUARDRAIL MONITORING VIEW
-- =============================================================================

-- Drop existing view if it exists
DROP VIEW IF EXISTS cost_guardrail_status CASCADE;

-- Create cost guardrail monitoring view
CREATE VIEW cost_guardrail_status AS
WITH hourly_costs AS (
    -- Get costs for the last 24 hours by hour
    SELECT 
        DATE_TRUNC('hour', timestamp) as hour,
        SUM(cost_usd) as hourly_cost,
        COUNT(*) as api_calls,
        COUNT(DISTINCT provider) as providers_used
    FROM fct_api_cost
    WHERE timestamp >= NOW() - INTERVAL '24 hours'
    GROUP BY DATE_TRUNC('hour', timestamp)
),
daily_total AS (
    -- Calculate 24-hour rolling total
    SELECT 
        SUM(cost_usd) as total_24h_cost,
        AVG(cost_usd) as avg_cost_per_call,
        MAX(cost_usd) as max_single_cost
    FROM fct_api_cost
    WHERE timestamp >= NOW() - INTERVAL '24 hours'
),
provider_breakdown AS (
    -- Break down by provider for the last 24 hours
    SELECT 
        provider,
        SUM(cost_usd) as provider_cost,
        COUNT(*) as provider_calls,
        AVG(cost_usd) as avg_cost
    FROM fct_api_cost
    WHERE timestamp >= NOW() - INTERVAL '24 hours'
    GROUP BY provider
)
SELECT 
    dt.total_24h_cost,
    1000.0 as daily_budget_usd,  -- From COST_BUDGET_USD env var
    (dt.total_24h_cost / 1000.0) * 100 as budget_used_pct,
    CASE 
        WHEN dt.total_24h_cost >= 1000.0 THEN 'OVER_BUDGET'
        WHEN dt.total_24h_cost >= 900.0 THEN 'WARNING'
        ELSE 'OK'
    END as budget_status,
    dt.avg_cost_per_call,
    dt.max_single_cost,
    -- Hourly trend
    (
        SELECT JSON_AGG(
            JSON_BUILD_OBJECT(
                'hour', hour,
                'cost', hourly_cost,
                'calls', api_calls
            ) ORDER BY hour
        )
        FROM hourly_costs
    ) as hourly_breakdown,
    -- Provider breakdown
    (
        SELECT JSON_AGG(
            JSON_BUILD_OBJECT(
                'provider', provider,
                'cost', provider_cost,
                'calls', provider_calls,
                'avg_cost', avg_cost
            ) ORDER BY provider_cost DESC
        )
        FROM provider_breakdown
    ) as provider_breakdown,
    NOW() as checked_at;

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_fct_api_cost_timestamp_provider 
    ON fct_api_cost(timestamp, provider);
CREATE INDEX IF NOT EXISTS idx_businesses_geo_vert_bucket 
    ON businesses(geo_bucket, vert_bucket);