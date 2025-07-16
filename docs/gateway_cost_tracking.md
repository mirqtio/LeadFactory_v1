# Gateway Cost Tracking Documentation

## Overview

The Gateway Cost Ledger (P1-050) provides centralized cost tracking for all external API calls made through the d0_gateway module. This system tracks costs in real-time, aggregates them for reporting, and provides APIs for cost analysis.

## Architecture

### Components

1. **Cost Models** (`database/models.py`)
   - `APICost`: Individual API call costs with full context
   - `DailyCostAggregate`: Pre-aggregated daily costs for fast reporting

2. **Cost Ledger** (`d0_gateway/cost_ledger.py`)
   - Core cost tracking and aggregation logic
   - Database operations for cost records
   - Daily aggregation and cleanup utilities

3. **Cost API** (`d0_gateway/cost_api.py`)
   - RESTful endpoints for cost queries
   - Provider and campaign cost summaries
   - Cost trend analysis

4. **Base Client Integration** (`d0_gateway/base.py`)
   - Automatic cost tracking via `emit_cost()` method
   - Cost calculation via provider-specific `calculate_cost()` methods

## Usage

### Automatic Cost Tracking

Cost tracking is automatically handled by the base API client. Each provider implements:

```python
def calculate_cost(self, operation: str, **kwargs) -> Decimal:
    """Calculate cost for specific operations"""
    if operation == "match_business":
        return Decimal("0.05")  # $0.05 per match
    return Decimal("0.00")
```

And emits costs after successful operations:

```python
self.emit_cost(
    lead_id=business_data.get("lead_id"),
    cost_usd=0.05,
    operation="match_business",
    metadata={"match_confidence": 0.95}
)
```

### API Endpoints

#### Get Provider Costs
```bash
GET /api/v1/gateway/costs/providers/{provider}?days=30
```

Returns cost summary for a specific provider with breakdown by operation.

#### Get Campaign Costs
```bash
GET /api/v1/gateway/costs/campaigns/{campaign_id}
```

Returns total costs for a campaign broken down by provider and operation.

#### Get Daily Costs
```bash
GET /api/v1/gateway/costs/daily?start_date=2025-01-01&provider=dataaxle
```

Returns daily cost aggregates with optional filtering.

#### Get Cost Trends
```bash
GET /api/v1/gateway/costs/trends?days=30
```

Returns cost trend analysis including peak days and averages.

### Cost Aggregation

Daily cost aggregation runs automatically via Prefect flows, but can be triggered manually:

```bash
POST /api/v1/gateway/costs/aggregate/2025-01-15
```

### Cleanup

Old cost records are automatically cleaned up after 90 days (configurable). Aggregates are preserved indefinitely.

```bash
DELETE /api/v1/gateway/costs/cleanup?days_to_keep=90
```

## Provider Cost Reference

| Provider | Operation | Cost per Call | Notes |
|----------|-----------|---------------|-------|
| DataAxle | match_business | $0.05 | Per successful match |
| Hunter | find_email | $0.01 | Per email lookup |
| OpenAI | analyze (GPT-4o-mini) | ~$0.0008 | Per 1000 tokens |
| SEMrush | domain_overview | $0.10 | Per domain analysis |
| ScreenshotOne | capture | $0.003 | Per screenshot |
| Humanloop | prompt_completion | Variable | Based on model used |

## Integration Example

```python
from d0_gateway.cost_ledger import get_provider_costs, get_campaign_costs

# Get last 30 days of DataAxle costs
dataaxle_costs = get_provider_costs("dataaxle", days=30)
print(f"Total cost: ${dataaxle_costs['total_cost']:.2f}")
print(f"Total requests: {dataaxle_costs['total_requests']}")

# Get campaign costs
campaign_costs = get_campaign_costs(campaign_id=123)
print(f"Campaign total: ${campaign_costs['total_cost']:.2f}")
```

## Database Schema

### APICost Table (fct_api_cost)
- `id`: Primary key
- `provider`: API provider name
- `operation`: Specific operation performed
- `cost_usd`: Cost in USD (decimal)
- `lead_id`: Associated lead (nullable)
- `campaign_id`: Associated campaign (nullable)
- `request_id`: Provider's request ID
- `meta_data`: JSON metadata
- `timestamp`: When the cost was incurred

### DailyCostAggregate Table (agg_daily_cost)
- `id`: Primary key
- `date`: Aggregation date
- `provider`: API provider name
- `operation`: Operation type (nullable)
- `campaign_id`: Campaign ID (nullable)
- `total_cost_usd`: Total cost for the day
- `request_count`: Number of requests
- `created_at`: When aggregate was created
- `updated_at`: Last update time

## Monitoring and Alerts

Cost tracking integrates with the observability stack:

1. **Metrics**: Cost metrics are exported to Prometheus
2. **Logging**: All cost records are logged at INFO level
3. **Alerts**: Cost guardrails can trigger alerts on budget overruns (see P1-060)

## Performance Considerations

1. **Real-time Tracking**: Costs are recorded synchronously but don't block API calls
2. **Aggregation**: Daily aggregates reduce query load for reporting
3. **Indexes**: Optimized indexes on provider, timestamp, and campaign_id
4. **Cleanup**: Automatic cleanup prevents unbounded table growth

## Error Handling

Cost tracking failures are non-blocking:
- If cost recording fails, the API call still succeeds
- Errors are logged but don't propagate to the caller
- Missing costs can be reconciled from provider logs

## Testing

Run cost tracking tests:
```bash
# Unit tests
pytest tests/unit/test_cost_ledger.py -v

# Integration tests
pytest tests/integration/test_cost_tracking.py -v
```