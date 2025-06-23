# Phase 0.5 Implementation Guide

## Overview

Phase 0.5 adds critical enhancements discovered after the MVP code-freeze:
- **New Data Providers**: Data Axle and Hunter for 38-45% email coverage increase
- **Cost Tracking**: API-level cost tracking for profit visibility
- **Bucket Intelligence**: Geo and vertical bucketing for performance analysis
- **Spend Guardrails**: Automatic pipeline termination if daily spend exceeds budget

## Task Execution Order

### Stage 1: Configuration & Infrastructure (1.5 hours)
1. **DX-01**: Add env keys & config blocks (0.3h)
2. **GW-04**: Cost ledger table + helper (0.5h)
3. **TG-06**: Bucket columns migration + CSV seeds (0.7h)

### Stage 2: Provider Integration (1.7 hours)
4. **GW-02**: Implement Data Axle client (1.0h)
5. **GW-03**: Implement Hunter client (0.7h)

### Stage 3: Core Logic Updates (1.4 hours)
6. **EN-05**: Modify enrichment flow (0.8h)
7. **AN-08**: Create analytics views (0.6h)

### Stage 4: Orchestration & Safety (1.3 hours)
8. **ET-07**: Nightly bucket enrichment flow (0.8h)
9. **OR-09**: Cost guardrail & profit snapshot (0.5h)

### Stage 5: Testing & Documentation (1.9 hours)
10. **TS-10**: Unit & integration tests (1.0h)
11. **DOC-11**: README & provider docs (0.4h)
12. **NB-12**: Jupyter notebook template (0.5h)

## Implementation Details

### Task DX-01: Environment Configuration
```python
# core/config.py additions
class Settings(BaseSettings):
    # Data Axle
    data_axle_api_key: Optional[str] = Field(None, env="DATA_AXLE_API_KEY")
    data_axle_base_url: str = Field("https://api.data-axle.com/v2", env="DATA_AXLE_BASE_URL")
    data_axle_rate_limit: int = Field(200, env="DATA_AXLE_RATE_LIMIT_PER_MIN")
    
    # Hunter
    hunter_api_key: Optional[str] = Field(None, env="HUNTER_API_KEY")
    hunter_rate_limit: int = Field(30, env="HUNTER_RATE_LIMIT_PER_MIN")
    
    # Feature flags
    providers_data_axle_enabled: bool = Field(True, env="PROVIDERS_DATA_AXLE_ENABLED")
    providers_hunter_enabled: bool = Field(False, env="PROVIDERS_HUNTER_ENABLED")
    
    # Cost control
    cost_budget_usd: float = Field(1000.0, env="COST_BUDGET_USD")
    lead_filter_min_score: float = Field(0.0, env="LEAD_FILTER_MIN_SCORE")
    assessment_optional: bool = Field(True, env="ASSESSMENT_OPTIONAL")
```

### Task GW-02: Data Axle Client
```python
# d0_gateway/providers/dataaxle.py
class DataAxleClient(BaseAPIClient):
    """Data Axle Business Match API client"""
    
    def __init__(self, api_key: str):
        super().__init__(
            base_url=settings.data_axle_base_url,
            api_key=api_key,
            provider="dataaxle",
            timeout=30,
            max_retries=3
        )
        
    async def match_business(self, business_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Match business and return enriched data"""
        response = await self._post(
            "/business/match",
            json={
                "name": business_data.get("name"),
                "address": business_data.get("address"),
                "city": business_data.get("city"),
                "state": business_data.get("state"),
                "zip": business_data.get("zip_code")
            }
        )
        
        if response and response.get("match_found"):
            # Emit cost for successful match
            self.emit_cost(
                lead_id=business_data.get("lead_id"),
                cost_usd=0.05  # $0.05 per match
            )
            return response.get("business_data")
        
        return None
```

### Task GW-04: Cost Tracking
```sql
-- alembic/versions/003_cost_tracking.py
CREATE TABLE fct_api_cost (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id VARCHAR(50) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    cost_usd DECIMAL(10, 4) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_lead_cost (lead_id),
    INDEX idx_provider_cost (provider, created_at)
);
```

### Task TG-06: Bucket Columns
```python
# Add to database/models.py Business model
class Business(Base):
    # ... existing fields ...
    geo_bucket = Column(String(80), nullable=True)
    vert_bucket = Column(String(80), nullable=True)
```

### Task AN-08: Analytics Views
```sql
-- d10_analytics/views_phase05.sql
CREATE OR REPLACE VIEW unit_economics_day AS
SELECT
    date_trunc('day', e.sent_at) AS day,
    COUNT(*) AS emails_sent,
    SUM(CASE WHEN p.id IS NOT NULL THEN 1 ELSE 0 END) AS purchases,
    SUM(COALESCE(p.price, 0)) AS gross_revenue,
    SUM(COALESCE(f.cost_usd, 0)) AS variable_cost,
    SUM(COALESCE(p.price, 0)) - SUM(COALESCE(f.cost_usd, 0)) AS profit
FROM emails e
LEFT JOIN purchases p ON e.business_id = p.business_id
LEFT JOIN (
    SELECT lead_id, SUM(cost_usd) as cost_usd
    FROM fct_api_cost
    GROUP BY lead_id
) f ON e.lead_id = f.lead_id
WHERE e.sent_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY 1
ORDER BY 1 DESC;

CREATE OR REPLACE VIEW bucket_performance AS
SELECT
    b.geo_bucket,
    b.vert_bucket,
    COUNT(DISTINCT e.id) AS emails_sent,
    COUNT(DISTINCT p.id) AS purchases,
    AVG(COALESCE(p.price, 0)) - 0.073 AS profit_per_email
FROM businesses b
JOIN emails e ON b.id = e.business_id
LEFT JOIN purchases p ON b.id = p.business_id
WHERE b.geo_bucket IS NOT NULL
  AND b.vert_bucket IS NOT NULL
GROUP BY 1, 2
HAVING COUNT(DISTINCT e.id) >= 10;
```

### Task OR-09: Cost Guardrail
```python
# d11_orchestration/flows/cost_guardrail.py
from prefect import flow, task
from datetime import datetime, timedelta

@task
def check_daily_spend():
    """Check if 24h spend exceeds budget"""
    with get_db() as db:
        result = db.execute("""
            SELECT SUM(cost_usd) as total_cost
            FROM fct_api_cost
            WHERE created_at >= :since
        """, {"since": datetime.utcnow() - timedelta(hours=24)})
        
        total_cost = result.scalar() or 0.0
        budget = settings.cost_budget_usd
        
        if total_cost > budget:
            raise Exception(f"Daily spend ${total_cost:.2f} exceeds budget ${budget:.2f}")
        
        return total_cost

@flow(name="cost-guardrail")
def cost_guardrail_flow():
    """Hourly check of spending vs budget"""
    daily_spend = check_daily_spend()
    logger.info(f"Current 24h spend: ${daily_spend:.2f}")
```

## Testing Strategy

### Unit Tests
- Mock Data Axle and Hunter API responses
- Test cost emission logic
- Verify bucket assignment logic
- Test guardrail triggers

### Integration Tests
- End-to-end enrichment with multiple providers
- Cost aggregation accuracy
- Bucket enrichment ETL
- View query performance

## Deployment Checklist

1. **Environment Variables**
   ```bash
   DATA_AXLE_API_KEY=your-key-here
   HUNTER_API_KEY=your-key-here
   PROVIDERS_DATA_AXLE_ENABLED=true
   PROVIDERS_HUNTER_ENABLED=false
   COST_BUDGET_USD=1000
   ```

2. **Database Migrations**
   ```bash
   alembic upgrade head
   ```

3. **Load Seed Data**
   ```bash
   python scripts/load_seed_data.py --geo-features --vertical-features
   ```

4. **Schedule Flows**
   ```bash
   prefect deployment create bucket_enrichment --cron "0 2 * * *"
   prefect deployment create cost_guardrail --interval 3600
   prefect deployment create profit_snapshot --cron "0 3 * * *"
   ```

5. **Verify Integration**
   ```bash
   python scripts/test_phase_05.py
   ```

## Success Metrics

- [ ] 40%+ email coverage improvement
- [ ] Cost tracking for 98%+ of API calls
- [ ] 100% of leads have bucket assignments
- [ ] Daily profit visibility in analytics
- [ ] Pipeline stops when budget exceeded

## Rollback Plan

If issues arise:
1. Set `PROVIDERS_DATA_AXLE_ENABLED=false`
2. Set `PROVIDERS_HUNTER_ENABLED=false`
3. Revert to previous enrichment logic
4. Monitor existing email coverage

## Notes

- Data Axle trial period has $0 cost per match
- Hunter free tier limited to 25 emails/day
- Bucket features based on ZIP-level census data
- Cost budget is rolling 24-hour window, not calendar day