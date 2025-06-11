# Phase 0.5 Provider Documentation

## Overview

Phase 0.5 introduces two new data enrichment providers to enhance lead quality and reduce manual research:

1. **Data Axle Business Match API** - Business data enrichment with firmographic details
2. **Hunter.io Email Finder** - Professional email discovery (fallback option)

## Provider Details

### Data Axle

Data Axle provides comprehensive business data enrichment through their Business Match API.

**Key Features:**
- Business matching with 80%+ confidence threshold
- Firmographic data: employee count, revenue, years in business
- Industry codes (SIC/NAICS)
- Contact information verification
- Cost: $0.05 per successful match

**Configuration:**
```yaml
DATA_AXLE_API_KEY: your-api-key-here
DATA_AXLE_RATE_LIMIT: 200  # requests per minute
```

**Usage Example:**
```python
from d0_gateway.providers.dataaxle import DataAxleClient

client = DataAxleClient()
result = await client.match_business({
    'name': 'ABC Restaurant',
    'address': '123 Main St',
    'city': 'San Francisco',
    'state': 'CA',
    'zip_code': '94105'
})

if result:
    print(f"Matched! Employees: {result['employee_count']}")
    print(f"Revenue: ${result['annual_revenue']:,}")
```

### Hunter.io

Hunter provides email finding capabilities as a fallback when other methods fail.

**Key Features:**
- Email discovery from domain/company name
- Contact details (name, position)
- Confidence scoring
- Source verification
- Cost: $0.01 per email found

**Configuration:**
```yaml
HUNTER_API_KEY: your-api-key-here
HUNTER_RATE_LIMIT: 30  # requests per minute
```

**Usage Example:**
```python
from d0_gateway.providers.hunter import HunterClient

client = HunterClient()
result = await client.find_email({
    'domain': 'example.com',
    'first_name': 'John',  # optional
    'last_name': 'Doe'     # optional
})

if result:
    print(f"Email: {result['email']}")
    print(f"Confidence: {result['confidence']}%")
```

## Cost Tracking

All API calls are automatically tracked in the `fct_api_cost` table:

```sql
-- View daily costs by provider
SELECT 
    provider,
    DATE(timestamp) as date,
    COUNT(*) as api_calls,
    SUM(cost_usd) as total_cost
FROM fct_api_cost
WHERE provider IN ('dataaxle', 'hunter')
GROUP BY provider, DATE(timestamp)
ORDER BY date DESC;
```

## Cost Controls

### Daily Budget Limits

The system enforces a daily budget limit (default: $1,000) across all providers:

```yaml
COST_BUDGET_USD: 1000  # Daily limit in USD
```

### Cost Guardrail Flow

An hourly Prefect flow monitors spending and automatically pauses expensive operations when approaching budget limits:

- **Warning threshold**: 80% of daily budget
- **Critical threshold**: 100% of daily budget
- **Auto-pause providers**: openai, dataaxle, hunter

### Manual Cost Check

```bash
# Check current daily spend
python scripts/check_daily_costs.py

# Generate profit report
python scripts/generate_profit_report.py --days 7
```

## Integration with Enrichment Flow

Phase 0.5 providers are integrated into the standard enrichment workflow:

```python
from d4_enrichment.coordinator import EnrichmentCoordinator

coordinator = EnrichmentCoordinator()

# Enrich with all available sources
result = await coordinator.enrich_lead(
    business_data,
    enable_dataaxle=True,  # Phase 0.5
    enable_hunter=True     # Phase 0.5 fallback
)
```

## Bucket Intelligence

Phase 0.5 introduces bucket-based segmentation for targeted campaigns:

### Geographic Buckets
Based on ZIP code characteristics:
- **Affluence**: high/medium/low
- **Agency Density**: high/medium/low  
- **Broadband Quality**: high/medium/low

Example: `high-high-high` = Affluent area with many agencies and excellent broadband

### Vertical Buckets
Based on business category:
- **Urgency**: How urgently businesses need marketing
- **Ticket Size**: Average customer transaction value
- **Maturity**: Digital marketing sophistication

Example: `high-high-medium` = Urgent need, high ticket, moderate sophistication

### Enrichment Process

Buckets are assigned nightly via Prefect flow:

```bash
# Run bucket enrichment manually
python -c "from d11_orchestration.bucket_enrichment import bucket_enrichment_flow; bucket_enrichment_flow()"
```

## Analytics Views

Two views provide insights into performance:

### unit_economics_day
Daily P&L tracking with provider cost breakdown:

```sql
SELECT * FROM unit_economics_day
ORDER BY date DESC
LIMIT 30;
```

### bucket_performance
Performance metrics by geo/vertical bucket:

```sql
SELECT 
    geo_bucket,
    vert_bucket,
    total_businesses,
    total_revenue_usd,
    roi
FROM bucket_performance
WHERE total_revenue_usd > 0
ORDER BY roi DESC;
```

## Best Practices

1. **Rate Limiting**: Both providers have strict rate limits. The gateway automatically handles this, but avoid parallel requests to the same provider.

2. **Cost Optimization**: 
   - Use Data Axle only for high-value prospects
   - Enable Hunter only as a fallback
   - Monitor daily costs via the cost guardrail flow

3. **Data Quality**:
   - Provide complete address data for better Data Axle matches
   - Include website/domain for Hunter searches
   - Verify email deliverability before sending

4. **Error Handling**:
   - Both providers use circuit breakers
   - Failed requests are cached to prevent retries
   - Check logs for detailed error messages

## Monitoring

### Metrics
Available in Prometheus/Grafana:
- `gateway_api_calls_total{provider="dataaxle|hunter"}`
- `gateway_api_cost_usd{provider="dataaxle|hunter"}`
- `gateway_api_errors_total{provider="dataaxle|hunter"}`

### Logs
```bash
# View provider logs
tail -f logs/gateway.log | grep -E "(dataaxle|hunter)"

# Check cost tracking
tail -f logs/gateway.log | grep "emit_cost"
```

## Troubleshooting

### Common Issues

1. **Authentication Errors**
   - Verify API keys in `.env`
   - Check key permissions/quotas with provider

2. **Rate Limit Errors**
   - Gateway auto-retries with backoff
   - Check current limits in provider dashboard

3. **Poor Match Quality**
   - Ensure complete business data
   - Verify address formatting
   - Check business name variations

4. **Missing Costs**
   - Verify cost tracking is enabled
   - Check database connectivity
   - Review emit_cost logs

### Support

For issues or questions:
1. Check provider status pages
2. Review error logs
3. Contact provider support
4. Open GitHub issue with details