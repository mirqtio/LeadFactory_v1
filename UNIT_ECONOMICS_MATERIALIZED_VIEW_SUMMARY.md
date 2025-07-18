# Unit Economics Materialized View Implementation Summary

## Overview

The PostgreSQL materialized view `unit_economics_day` has been implemented to calculate daily unit economics metrics for cost, revenue, leads, conversions, and key performance indicators like CPL, CAC, ROI, and LTV.

## Implementation Details

### File Locations

1. **Main Implementation**: `/Users/charlieirwin/Documents/GitHub/LeadFactory_v1_Final/d10_analytics/views.sql` (lines 465-668)
2. **Corrected Standalone Version**: `/Users/charlieirwin/Documents/GitHub/LeadFactory_v1_Final/unit_economics_day_corrected.sql`
3. **Migration**: `/Users/charlieirwin/Documents/GitHub/LeadFactory_v1_Final/alembic/versions/fix_unit_economics_table_references.py`

### Database Schema

The materialized view integrates data from multiple tables:

#### Source Tables
- **`fct_api_cost`**: API cost tracking (corrected from `gateway_cost_ledger`)
  - `cost_usd`: Cost in USD (converted to cents in view)
  - `timestamp`: Event timestamp
  - `request_id`: Unique request identifier
  - `provider`: API provider name
  - `operation`: API operation type

- **`funnel_events`**: Event tracking for conversions and leads
  - `event_type`: Type of event (PAYMENT_SUCCESS, PIPELINE_START, ASSESSMENT_SUCCESS)
  - `session_id`: Session identifier
  - `business_id`: Business identifier
  - `event_metadata`: JSON metadata including amount_cents
  - `timestamp`: Event timestamp

### Materialized View Structure

#### Date Dimensions
- `date`: Primary date key
- `year`: Year extract
- `month`: Month extract
- `day_of_week`: Day of week (0=Sunday, 6=Saturday)

#### Cost Metrics
- `total_cost_cents`: Total API costs in cents
- `total_api_calls`: Number of API calls
- `unique_requests`: Unique API requests
- `avg_cost_per_call_cents`: Average cost per API call

#### Revenue Metrics
- `total_conversions`: Number of successful payments
- `unique_converted_sessions`: Unique sessions that converted
- `total_revenue_cents`: Total revenue (defaults to $399 per conversion)

#### Lead Metrics
- `total_leads`: Number of pipeline starts
- `unique_businesses`: Unique businesses in pipeline
- `total_assessments`: Number of successful assessments
- `unique_assessed_businesses`: Unique businesses assessed

#### Unit Economics Calculations

1. **CPL (Cost Per Lead)**: `total_cost_cents / total_leads`
2. **CAC (Customer Acquisition Cost)**: `total_cost_cents / total_conversions`
3. **ROI (Return on Investment)**: `((total_revenue_cents - total_cost_cents) / total_cost_cents) * 100`
4. **LTV (Lifetime Value)**: `total_revenue_cents / total_conversions`
5. **Lead to Conversion Rate**: `(total_conversions / total_leads) * 100`
6. **Assessment to Conversion Rate**: `(total_conversions / total_assessments) * 100`
7. **Profit**: `total_revenue_cents - total_cost_cents`

### Performance Optimization

#### Indexes Created
- `idx_unit_economics_day_pk`: Primary key on date (unique)
- `idx_unit_economics_day_date_desc`: Descending date for time-series queries
- `idx_unit_economics_day_month`: Year and month for period queries
- `idx_unit_economics_day_profit`: Profit for ranking queries
- `idx_unit_economics_day_roi`: ROI for performance queries

#### Data Scope
- Includes data from the last 365 days
- Automatically filters out NULL dates
- Uses FULL OUTER JOIN to capture all date combinations

### Refresh Mechanism

#### Refresh Function
```sql
CREATE OR REPLACE FUNCTION refresh_unit_economics_day_mv()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY unit_economics_day;
    -- Logs refresh status to materialized_view_refresh_log table
END;
$$ LANGUAGE plpgsql;
```

#### Manual Refresh
```sql
SELECT refresh_unit_economics_day_mv();
```

### Monitoring Views

#### Unit Economics Stats
```sql
SELECT * FROM unit_economics_stats;
```
- View size and row count
- Date range coverage
- Average cost, revenue, and ROI

#### Recent Unit Economics
```sql
SELECT * FROM recent_unit_economics;
```
- Last 30 days of data
- Key metrics for dashboard display

## Key Corrections Made

1. **Table Reference**: Changed from `gateway_cost_ledger` to `fct_api_cost`
2. **Cost Conversion**: Added conversion from USD to cents (`cost_usd * 100`)
3. **Session Reference**: Changed from `session_id` to `request_id` for API costs
4. **Timestamp Field**: Updated to use `timestamp` instead of `created_at`

## Usage Examples

### Daily Unit Economics Query
```sql
SELECT 
    date,
    total_cost_cents / 100.0 as total_cost_usd,
    total_revenue_cents / 100.0 as total_revenue_usd,
    total_leads,
    total_conversions,
    cpl_cents / 100.0 as cpl_usd,
    cac_cents / 100.0 as cac_usd,
    roi_percentage,
    lead_to_conversion_rate_pct
FROM unit_economics_day
WHERE date >= CURRENT_DATE - INTERVAL '30 days'
ORDER BY date DESC;
```

### Monthly Aggregation
```sql
SELECT 
    year,
    month,
    SUM(total_cost_cents) as monthly_cost_cents,
    SUM(total_revenue_cents) as monthly_revenue_cents,
    SUM(total_leads) as monthly_leads,
    SUM(total_conversions) as monthly_conversions,
    AVG(roi_percentage) as avg_roi_percentage
FROM unit_economics_day
WHERE date >= CURRENT_DATE - INTERVAL '12 months'
GROUP BY year, month
ORDER BY year DESC, month DESC;
```

## Migration Status

The migration `fix_unit_economics_table_references.py` needs to be run to:
1. Drop the existing materialized view with incorrect table references
2. Create the corrected version with proper table names and schema
3. Add performance indexes
4. Create refresh functions and monitoring views

## Error Handling

The materialized view includes proper division by zero handling:
- CPL, CAC, LTV calculations return NULL when denominators are zero
- Conversion rates return 0 when no leads exist
- All metrics use COALESCE to handle NULL values gracefully

## Future Enhancements

1. **Campaign-level aggregation**: Add campaign_id dimension
2. **Provider-level costs**: Break down costs by API provider
3. **Cohort analysis**: Track customer lifetime value over time
4. **Automated refresh**: Set up scheduled refresh via cron job
5. **Alerting**: Monitor for unusual cost spikes or conversion drops