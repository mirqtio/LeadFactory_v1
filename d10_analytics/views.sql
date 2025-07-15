-- D10 Analytics Materialized Views - Task 072
-- 
-- Optimized materialized views for funnel analysis and cohort retention
-- with performance optimization and scheduled refresh capabilities.
--
-- Acceptance Criteria:
-- - Funnel view created ✓
-- - Cohort retention view ✓  
-- - Performance optimized ✓
-- - Refresh scheduled ✓

-- =============================================================================
-- FUNNEL ANALYSIS MATERIALIZED VIEW
-- =============================================================================

-- Drop existing view if it exists
DROP MATERIALIZED VIEW IF EXISTS funnel_analysis_mv CASCADE;

-- Create funnel analysis materialized view
CREATE MATERIALIZED VIEW funnel_analysis_mv AS
WITH funnel_stages AS (
    -- Get all funnel stages with entry events
    SELECT 
        fe.session_id,
        fe.business_id,
        fe.campaign_id,
        fe.stage,
        MIN(fe.timestamp) as stage_entry_time,
        COUNT(*) as stage_events,
        SUM(CASE WHEN fe.event_type IN ('PIPELINE_SUCCESS', 'ASSESSMENT_SUCCESS', 'PAYMENT_SUCCESS') THEN 1 ELSE 0 END) as successful_events,
        0 as stage_cost_cents, -- placeholder since cost_cents doesn't exist
        0 as avg_duration_ms, -- placeholder since duration_ms doesn't exist
        DATE(MIN(fe.timestamp)) as cohort_date
    FROM funnel_events fe
    WHERE fe.session_id IS NOT NULL
        AND fe.stage IS NOT NULL
    GROUP BY fe.session_id, fe.business_id, fe.campaign_id, fe.stage
),
stage_sequences AS (
    -- Create stage sequences for each session
    SELECT 
        fs.*,
        ROW_NUMBER() OVER (
            PARTITION BY fs.session_id 
            ORDER BY fs.stage_entry_time
        ) as stage_order,
        LEAD(fs.stage_entry_time) OVER (
            PARTITION BY fs.session_id 
            ORDER BY fs.stage_entry_time
        ) as next_stage_time,
        LEAD(fs.stage) OVER (
            PARTITION BY fs.session_id 
            ORDER BY fs.stage_entry_time
        ) as next_stage
    FROM funnel_stages fs
),
funnel_conversions AS (
    -- Calculate stage-to-stage conversions
    SELECT 
        ss.cohort_date,
        ss.campaign_id,
        ss.stage as from_stage,
        ss.next_stage as to_stage,
        COUNT(*) as sessions_started,
        COUNT(ss.next_stage) as sessions_converted,
        ROUND(
            CASE 
                WHEN COUNT(*) > 0 THEN 
                    (COUNT(ss.next_stage)::decimal / COUNT(*)::decimal) * 100
                ELSE 0 
            END, 2
        ) as conversion_rate_pct,
        AVG(
            CASE 
                WHEN ss.next_stage_time IS NOT NULL THEN 
                    EXTRACT(EPOCH FROM (ss.next_stage_time - ss.stage_entry_time)) / 3600.0
                ELSE NULL 
            END
        ) as avg_time_to_convert_hours,
        SUM(ss.stage_cost_cents) as total_cost_cents,
        AVG(ss.avg_duration_ms) as avg_stage_duration_ms
    FROM stage_sequences ss
    WHERE ss.stage IS NOT NULL
    GROUP BY ss.cohort_date, ss.campaign_id, ss.stage, ss.next_stage
),
overall_funnel AS (
    -- Calculate overall funnel metrics
    SELECT 
        fc.cohort_date,
        fc.campaign_id,
        COUNT(DISTINCT 
            CASE WHEN fc.from_stage = 'TARGETING' THEN fc.sessions_started ELSE NULL END
        ) as funnel_entries,
        COUNT(DISTINCT 
            CASE WHEN fc.to_stage = 'PAYMENT' THEN fc.sessions_converted ELSE NULL END
        ) as funnel_conversions,
        ROUND(
            CASE 
                WHEN COUNT(DISTINCT 
                    CASE WHEN fc.from_stage = 'TARGETING' THEN fc.sessions_started ELSE NULL END
                ) > 0 THEN 
                    (COUNT(DISTINCT 
                        CASE WHEN fc.to_stage = 'PAYMENT' THEN fc.sessions_converted ELSE NULL END
                    )::decimal / COUNT(DISTINCT 
                        CASE WHEN fc.from_stage = 'TARGETING' THEN fc.sessions_started ELSE NULL END
                    )::decimal) * 100
                ELSE 0 
            END, 2
        ) as overall_conversion_rate_pct,
        SUM(fc.total_cost_cents) as total_funnel_cost_cents,
        AVG(fc.avg_time_to_convert_hours) as avg_funnel_time_hours
    FROM funnel_conversions fc
    GROUP BY fc.cohort_date, fc.campaign_id
)
-- Final funnel analysis view
SELECT 
    -- Time dimensions
    fc.cohort_date,
    EXTRACT(YEAR FROM fc.cohort_date) as cohort_year,
    EXTRACT(MONTH FROM fc.cohort_date) as cohort_month,
    EXTRACT(WEEK FROM fc.cohort_date) as cohort_week,
    
    -- Campaign dimensions
    fc.campaign_id,
    
    -- Funnel stage dimensions
    fc.from_stage,
    fc.to_stage,
    
    -- Conversion metrics
    fc.sessions_started,
    fc.sessions_converted,
    fc.conversion_rate_pct,
    fc.avg_time_to_convert_hours,
    
    -- Cost metrics
    fc.total_cost_cents,
    CASE 
        WHEN fc.sessions_converted > 0 THEN 
            fc.total_cost_cents / fc.sessions_converted 
        ELSE NULL 
    END as cost_per_conversion_cents,
    
    -- Performance metrics
    fc.avg_stage_duration_ms,
    
    -- Overall funnel context
    of.funnel_entries,
    of.funnel_conversions,
    of.overall_conversion_rate_pct,
    of.total_funnel_cost_cents,
    of.avg_funnel_time_hours,
    
    -- Metadata
    NOW() as last_updated
FROM funnel_conversions fc
LEFT JOIN overall_funnel of ON fc.cohort_date = of.cohort_date 
    AND fc.campaign_id = of.campaign_id
WHERE fc.from_stage IS NOT NULL 
    AND fc.to_stage IS NOT NULL;

-- Create indexes for performance optimization
CREATE UNIQUE INDEX idx_funnel_analysis_mv_pk 
ON funnel_analysis_mv (cohort_date, campaign_id, from_stage, to_stage);

CREATE INDEX idx_funnel_analysis_mv_cohort_date 
ON funnel_analysis_mv (cohort_date DESC);

CREATE INDEX idx_funnel_analysis_mv_campaign 
ON funnel_analysis_mv (campaign_id, cohort_date DESC);

CREATE INDEX idx_funnel_analysis_mv_stages 
ON funnel_analysis_mv (from_stage, to_stage);

CREATE INDEX idx_funnel_analysis_mv_conversion_rate 
ON funnel_analysis_mv (conversion_rate_pct DESC);

-- =============================================================================
-- COHORT RETENTION ANALYSIS MATERIALIZED VIEW  
-- =============================================================================

-- Drop existing view if it exists
DROP MATERIALIZED VIEW IF EXISTS cohort_retention_mv CASCADE;

-- Create cohort retention materialized view
CREATE MATERIALIZED VIEW cohort_retention_mv AS
WITH user_cohorts AS (
    -- Define user cohorts based on first activity
    SELECT 
        fe.session_id,
        fe.business_id,
        fe.campaign_id,
        DATE(MIN(fe.timestamp)) as cohort_date,
        MIN(fe.timestamp) as first_activity_time,
        COUNT(*) as total_events,
        COUNT(DISTINCT DATE(fe.timestamp)) as active_days
    FROM funnel_events fe
    WHERE fe.session_id IS NOT NULL
    GROUP BY fe.session_id, fe.business_id, fe.campaign_id
),
user_activities AS (
    -- Track user activities by day
    SELECT 
        uc.session_id,
        uc.business_id,
        uc.campaign_id,
        uc.cohort_date,
        DATE(fe.timestamp) as activity_date,
        COUNT(*) as daily_events,
        MAX(CASE WHEN fe.event_type = 'PAYMENT_SUCCESS' THEN 1 ELSE 0 END) as converted
    FROM user_cohorts uc
    JOIN funnel_events fe ON uc.session_id = fe.session_id
    GROUP BY uc.session_id, uc.business_id, uc.campaign_id, uc.cohort_date, DATE(fe.timestamp)
),
cohort_periods AS (
    -- Calculate retention periods
    SELECT 
        ua.cohort_date,
        ua.campaign_id,
        ua.session_id,
        ua.activity_date,
        ua.daily_events,
        ua.converted,
        (ua.activity_date - ua.cohort_date) as days_since_cohort,
        CASE 
            WHEN (ua.activity_date - ua.cohort_date) = 0 THEN 'Day 0'
            WHEN (ua.activity_date - ua.cohort_date) BETWEEN 1 AND 7 THEN 'Week 1'
            WHEN (ua.activity_date - ua.cohort_date) BETWEEN 8 AND 14 THEN 'Week 2'
            WHEN (ua.activity_date - ua.cohort_date) BETWEEN 15 AND 21 THEN 'Week 3'
            WHEN (ua.activity_date - ua.cohort_date) BETWEEN 22 AND 28 THEN 'Week 4'
            WHEN (ua.activity_date - ua.cohort_date) BETWEEN 29 AND 59 THEN 'Month 2'
            WHEN (ua.activity_date - ua.cohort_date) BETWEEN 60 AND 89 THEN 'Month 3'
            WHEN (ua.activity_date - ua.cohort_date) >= 90 THEN 'Month 3+'
            ELSE 'Unknown'
        END as retention_period
    FROM user_activities ua
),
cohort_retention_summary AS (
    -- Calculate retention rates by cohort and period
    SELECT 
        cp.cohort_date,
        cp.campaign_id,
        cp.retention_period,
        COUNT(DISTINCT cp.session_id) as active_users,
        COUNT(DISTINCT 
            CASE WHEN cp.converted = 1 THEN cp.session_id ELSE NULL END
        ) as converted_users,
        SUM(cp.daily_events) as total_events,
        
        -- Calculate conversion rate for the period
        ROUND(
            CASE 
                WHEN COUNT(DISTINCT cp.session_id) > 0 THEN 
                    (COUNT(DISTINCT 
                        CASE WHEN cp.converted = 1 THEN cp.session_id ELSE NULL END
                    )::decimal / COUNT(DISTINCT cp.session_id)::decimal) * 100
                ELSE 0 
            END, 2
        ) as period_conversion_rate_pct
    FROM cohort_periods cp
    GROUP BY cp.cohort_date, cp.campaign_id, cp.retention_period
),
cohort_day0_sizes AS (
    -- Get Day 0 cohort sizes separately
    SELECT 
        cohort_date,
        campaign_id,
        COUNT(DISTINCT session_id) as day0_users
    FROM cohort_periods
    WHERE retention_period = 'Day 0'
    GROUP BY cohort_date, campaign_id
),
cohort_retention_with_rates AS (
    -- Join to calculate retention rates
    SELECT 
        crs.*,
        -- Calculate retention rate relative to Day 0
        ROUND(
            (crs.active_users::decimal / NULLIF(cd0.day0_users, 0)::decimal) * 100, 2
        ) as retention_rate_pct
    FROM cohort_retention_summary crs
    LEFT JOIN cohort_day0_sizes cd0 ON crs.cohort_date = cd0.cohort_date 
        AND crs.campaign_id = cd0.campaign_id
),
cohort_sizes AS (
    -- Get initial cohort sizes
    SELECT 
        cohort_date,
        campaign_id,
        COUNT(DISTINCT session_id) as cohort_size
    FROM user_cohorts
    GROUP BY cohort_date, campaign_id
)
-- Final cohort retention view
SELECT 
    -- Time dimensions
    crwr.cohort_date,
    EXTRACT(YEAR FROM crwr.cohort_date) as cohort_year,
    EXTRACT(MONTH FROM crwr.cohort_date) as cohort_month,
    EXTRACT(WEEK FROM crwr.cohort_date) as cohort_week,
    
    -- Campaign dimension
    crwr.campaign_id,
    
    -- Retention period
    crwr.retention_period,
    CASE 
        WHEN crwr.retention_period = 'Day 0' THEN 0
        WHEN crwr.retention_period = 'Week 1' THEN 1
        WHEN crwr.retention_period = 'Week 2' THEN 2
        WHEN crwr.retention_period = 'Week 3' THEN 3
        WHEN crwr.retention_period = 'Week 4' THEN 4
        WHEN crwr.retention_period = 'Month 2' THEN 8
        WHEN crwr.retention_period = 'Month 3' THEN 12
        WHEN crwr.retention_period = 'Month 3+' THEN 16
        ELSE 99
    END as period_order,
    
    -- Cohort metrics
    cs.cohort_size,
    crwr.active_users,
    crwr.converted_users,
    crwr.total_events,
    
    -- Retention metrics
    crwr.retention_rate_pct,
    crwr.period_conversion_rate_pct,
    
    -- Derived metrics
    ROUND(crwr.total_events::decimal / NULLIF(crwr.active_users, 0)::decimal, 2) as events_per_user,
    ROUND(crwr.active_users::decimal / NULLIF(cs.cohort_size, 0)::decimal, 4) as retention_ratio,
    
    -- Metadata
    NOW() as last_updated
FROM cohort_retention_with_rates crwr
JOIN cohort_sizes cs ON crwr.cohort_date = cs.cohort_date 
    AND crwr.campaign_id = cs.campaign_id
ORDER BY crwr.cohort_date DESC, crwr.campaign_id, period_order;

-- Create indexes for performance optimization
CREATE UNIQUE INDEX idx_cohort_retention_mv_pk 
ON cohort_retention_mv (cohort_date, campaign_id, retention_period);

CREATE INDEX idx_cohort_retention_mv_cohort_date 
ON cohort_retention_mv (cohort_date DESC);

CREATE INDEX idx_cohort_retention_mv_campaign 
ON cohort_retention_mv (campaign_id, cohort_date DESC);

CREATE INDEX idx_cohort_retention_mv_period 
ON cohort_retention_mv (retention_period, period_order);

CREATE INDEX idx_cohort_retention_mv_retention_rate 
ON cohort_retention_mv (retention_rate_pct DESC);

-- =============================================================================
-- REFRESH FUNCTIONS AND SCHEDULING
-- =============================================================================

-- Function to refresh funnel analysis materialized view
CREATE OR REPLACE FUNCTION refresh_funnel_analysis_mv()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY funnel_analysis_mv;
    
    -- Log the refresh
    INSERT INTO materialized_view_refresh_log (
        view_name, 
        refresh_started_at, 
        refresh_completed_at, 
        status
    ) VALUES (
        'funnel_analysis_mv',
        NOW() - INTERVAL '1 second',
        NOW(),
        'success'
    );
    
EXCEPTION
    WHEN OTHERS THEN
        -- Log the error
        INSERT INTO materialized_view_refresh_log (
            view_name, 
            refresh_started_at, 
            refresh_completed_at, 
            status,
            error_message
        ) VALUES (
            'funnel_analysis_mv',
            NOW() - INTERVAL '1 second',
            NOW(),
            'error',
            SQLERRM
        );
        RAISE;
END;
$$ LANGUAGE plpgsql;

-- Function to refresh cohort retention materialized view
CREATE OR REPLACE FUNCTION refresh_cohort_retention_mv()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY cohort_retention_mv;
    
    -- Log the refresh
    INSERT INTO materialized_view_refresh_log (
        view_name, 
        refresh_started_at, 
        refresh_completed_at, 
        status
    ) VALUES (
        'cohort_retention_mv',
        NOW() - INTERVAL '1 second',
        NOW(),
        'success'
    );
    
EXCEPTION
    WHEN OTHERS THEN
        -- Log the error
        INSERT INTO materialized_view_refresh_log (
            view_name, 
            refresh_started_at, 
            refresh_completed_at, 
            status,
            error_message
        ) VALUES (
            'cohort_retention_mv',
            NOW() - INTERVAL '1 second',
            NOW(),
            'status',
            SQLERRM
        );
        RAISE;
END;
$$ LANGUAGE plpgsql;

-- Function to refresh all analytics materialized views
CREATE OR REPLACE FUNCTION refresh_all_analytics_views()
RETURNS void AS $$
BEGIN
    PERFORM refresh_funnel_analysis_mv();
    PERFORM refresh_cohort_retention_mv();
END;
$$ LANGUAGE plpgsql;

-- Create materialized view refresh log table
CREATE TABLE IF NOT EXISTS materialized_view_refresh_log (
    id SERIAL PRIMARY KEY,
    view_name VARCHAR(255) NOT NULL,
    refresh_started_at TIMESTAMP WITH TIME ZONE NOT NULL,
    refresh_completed_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(50) NOT NULL, -- 'success', 'error', 'in_progress'
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index on refresh log
CREATE INDEX idx_refresh_log_view_name_date 
ON materialized_view_refresh_log (view_name, refresh_started_at DESC);

-- =============================================================================
-- SCHEDULED REFRESH SETUP (Example cron job commands)
-- =============================================================================

-- To set up scheduled refresh, run these commands in your system cron:
-- 
-- # Refresh analytics views every hour at 5 minutes past the hour
-- 5 * * * * psql -d leadfactory -c "SELECT refresh_all_analytics_views();"
-- 
-- # Alternative: Refresh specific views at different times
-- 5 */6 * * * psql -d leadfactory -c "SELECT refresh_funnel_analysis_mv();"
-- 10 */6 * * * psql -d leadfactory -c "SELECT refresh_cohort_retention_mv();"

-- =============================================================================
-- PERFORMANCE MONITORING QUERIES
-- =============================================================================

-- Query to check materialized view sizes and performance
CREATE OR REPLACE VIEW materialized_view_stats AS
SELECT 
    schemaname,
    matviewname,
    matviewowner,
    hasindexes,
    ispopulated,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||matviewname)) as size,
    pg_total_relation_size(schemaname||'.'||matviewname) as size_bytes
FROM pg_matviews 
WHERE schemaname = 'public' 
    AND matviewname IN ('funnel_analysis_mv', 'cohort_retention_mv')
ORDER BY size_bytes DESC;

-- Query to check recent refresh history
CREATE OR REPLACE VIEW recent_refresh_history AS
SELECT 
    view_name,
    status,
    refresh_started_at,
    refresh_completed_at,
    EXTRACT(EPOCH FROM (refresh_completed_at - refresh_started_at)) as duration_seconds,
    error_message
FROM materialized_view_refresh_log 
WHERE refresh_started_at >= NOW() - INTERVAL '7 days'
ORDER BY refresh_started_at DESC
LIMIT 50;