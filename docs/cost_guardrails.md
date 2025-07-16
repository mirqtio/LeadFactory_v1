# Cost Guardrails Documentation (P1-060)

## Overview

The Cost Guardrails system provides proactive cost controls and alerting to prevent runaway API spending. Building on the Gateway Cost Ledger (P1-050), it adds configurable spending limits, real-time enforcement, and multi-channel alerting.

## Features

### 1. Configurable Spending Limits
- **Scopes**: Global, Provider, Campaign, Operation, or Provider+Operation
- **Periods**: Hourly, Daily, Weekly, Monthly, or Total (lifetime)
- **Thresholds**: Warning (default 80%) and Critical (default 95%)
- **Actions**: Log, Alert, Throttle, Block, or Circuit Break

### 2. Real-time Cost Enforcement
- Pre-flight cost estimation before API calls
- Automatic blocking when limits are exceeded
- Request throttling as limits approach
- Circuit breaker pattern for repeated failures

### 3. Rate Limiting
- Token bucket algorithm for smooth rate limiting
- Configurable requests per minute and burst size
- Cost-based rate limiting (dollars per minute)
- Per-provider and per-operation limits

### 4. Alert System
- Multi-channel alerts: Email, Slack, Webhooks, Logs
- Severity-based routing (Info, Warning, Critical, Emergency)
- Rate-limited alerts to prevent spam
- Rich formatting for different channels

## Configuration

### Default Limits

The system comes with sensible defaults:

```python
# Global daily limit
global_daily: $1,000.00

# Provider-specific daily limits
openai_daily: $500.00
dataaxle_daily: $300.00
hunter_daily: $100.00
semrush_daily: $200.00
```

### Creating Custom Limits

#### Via API:
```bash
curl -X POST http://localhost:8000/api/v1/gateway/guardrails/limits \
  -H "Content-Type: application/json" \
  -d '{
    "name": "campaign_123_monthly",
    "scope": "campaign",
    "period": "monthly",
    "limit_usd": 5000.0,
    "campaign_id": 123,
    "warning_threshold": 0.75,
    "critical_threshold": 0.9,
    "circuit_breaker_enabled": true
  }'
```

#### Via Code:
```python
from d0_gateway.guardrails import CostLimit, LimitScope, LimitPeriod, guardrail_manager

limit = CostLimit(
    name="high_value_provider",
    scope=LimitScope.PROVIDER,
    period=LimitPeriod.DAILY,
    limit_usd=Decimal("1000.00"),
    provider="premium_api",
    warning_threshold=0.7,
    critical_threshold=0.9,
    actions=[GuardrailAction.LOG, GuardrailAction.ALERT, GuardrailAction.THROTTLE]
)

guardrail_manager.add_limit(limit)
```

### Configuring Rate Limits

```python
from d0_gateway.guardrails import RateLimitConfig

rate_limit = RateLimitConfig(
    provider="openai",
    operation="chat",
    requests_per_minute=60,
    burst_size=10,
    cost_per_minute=Decimal("10.00"),
    cost_burst_size=Decimal("2.00")
)

guardrail_manager.add_rate_limit(rate_limit)
```

### Setting Up Alerts

#### Slack Integration:
```python
from d0_gateway.guardrail_alerts import configure_alerts, AlertChannel

configure_alerts(
    channel=AlertChannel.SLACK,
    slack_webhook_url="https://hooks.slack.com/services/YOUR/WEBHOOK/URL",
    min_severity=AlertSeverity.WARNING,
    providers=["openai", "dataaxle"]  # Only alert for these providers
)
```

#### Email Alerts:
```python
configure_alerts(
    channel=AlertChannel.EMAIL,
    email_addresses=["ops@company.com", "finance@company.com"],
    min_severity=AlertSeverity.CRITICAL
)
```

#### Custom Webhooks:
```python
configure_alerts(
    channel=AlertChannel.WEBHOOK,
    webhook_url="https://api.company.com/cost-alerts",
    webhook_headers={"Authorization": "Bearer YOUR_TOKEN"},
    min_severity=AlertSeverity.WARNING
)
```

## Usage

### Automatic Enforcement

The guardrail system automatically integrates with all gateway API calls:

```python
# This is handled automatically by the base API client
async def make_api_call():
    # Guardrails check limits before the call
    # If blocked, raises GuardrailBlocked exception
    # If throttled, adds appropriate delay
    response = await client.make_request("POST", "endpoint", data={...})
    return response
```

### Manual Checks

You can also manually check budgets:

```python
from d0_gateway.guardrail_middleware import check_budget_available, get_remaining_budget

# Check if budget is available
if check_budget_available("openai", "chat", estimated_cost=5.00):
    # Proceed with operation
    pass

# Get remaining budgets
remaining = get_remaining_budget(period="daily")
# Returns: {"openai": Decimal("450.00"), "dataaxle": Decimal("275.00"), ...}
```

### Temporary Overrides

Use context managers for temporary limit adjustments:

```python
from d0_gateway.guardrail_middleware import GuardrailContext

# Bypass guardrails for critical operations
with GuardrailContext(provider="openai", bypass_guardrails=True):
    # Guardrails disabled for OpenAI within this context
    await critical_operation()

# Temporarily increase limits
with GuardrailContext(temporary_limits={"openai_daily": Decimal("2000.00")}):
    # OpenAI daily limit increased to $2000 within this context
    await high_cost_operation()
```

## API Endpoints

### Status and Monitoring

```bash
# Get current guardrail status
GET /api/v1/gateway/guardrails/status

# Get budget summary
GET /api/v1/gateway/guardrails/budget?period=daily

# Get recent violations
GET /api/v1/gateway/guardrails/violations?hours=24
```

### Configuration Management

```bash
# List all limits
GET /api/v1/gateway/guardrails/limits

# Create new limit
POST /api/v1/gateway/guardrails/limits

# Update existing limit
PUT /api/v1/gateway/guardrails/limits/{name}

# Delete limit
DELETE /api/v1/gateway/guardrails/limits/{name}

# Create rate limit
POST /api/v1/gateway/guardrails/rate-limits

# Configure alerts
POST /api/v1/gateway/guardrails/alerts/configure

# Reset circuit breaker
POST /api/v1/gateway/guardrails/circuit-breakers/{limit_name}/reset
```

## Alert Examples

### Slack Alert
![Slack Alert Example](https://via.placeholder.com/600x300?text=Slack+Alert+Example)

The Slack alert includes:
- Color-coded severity (green/yellow/red)
- Current spend vs limit
- Usage percentage
- Provider and operation details

### Email Alert
```html
Subject: URGENT - Cost Limit Exceeded

OpenAI spending has exceeded the daily limit!

Current Spend: $1,050.00
Limit Amount: $1,000.00
Usage: 105%

Immediate attention required.
Further requests may be blocked!
```

### Webhook Payload
```json
{
  "title": "Cost Alert - Critical Threshold",
  "message": "Provider openai (chat) has reached 95.0% of the openai_daily limit.",
  "severity": "critical",
  "violation": {
    "limit_name": "openai_daily",
    "scope": "provider",
    "current_spend": 950.00,
    "limit_amount": 1000.00,
    "percentage_used": 0.95,
    "provider": "openai",
    "operation": "chat"
  },
  "timestamp": "2025-01-16T12:34:56.789Z"
}
```

## Circuit Breaker Pattern

The circuit breaker helps prevent cascading failures:

1. **Closed State**: Normal operation, requests allowed
2. **Open State**: After N failures, all requests blocked
3. **Half-Open State**: After recovery timeout, limited requests allowed

Configure circuit breakers on limits:
```python
limit = CostLimit(
    name="api_protection",
    # ... other settings ...
    circuit_breaker_enabled=True,
    circuit_breaker_failure_threshold=5,  # Open after 5 failures
    circuit_breaker_recovery_timeout=300  # Try recovery after 5 minutes
)
```

## Best Practices

1. **Start Conservative**: Begin with higher limits and gradually reduce based on actual usage
2. **Use Warning Thresholds**: Set warning at 80% to get early notifications
3. **Layer Your Limits**: Use both global and provider-specific limits
4. **Monitor Violations**: Review violation patterns to adjust limits
5. **Test Alert Channels**: Ensure alerts are received before relying on them
6. **Document Overrides**: Keep track of when and why limits are bypassed

## Troubleshooting

### Common Issues

1. **"Operation blocked by guardrail"**
   - Check current spend: `GET /api/v1/gateway/guardrails/status`
   - Review limit configuration
   - Consider temporary override if justified

2. **"Rate limit exceeded"**
   - Wait for retry_after period
   - Review rate limit configuration
   - Consider implementing request queuing

3. **"Circuit breaker open"**
   - Check for repeated failures in logs
   - Reset circuit breaker if issue resolved
   - Review failure threshold settings

4. **"Alerts not received"**
   - Verify alert configuration
   - Check alert channel credentials
   - Review min_severity settings
   - Check rate limiting on alerts

### Debug Mode

Enable detailed logging:
```python
import logging
logging.getLogger("gateway.guardrails").setLevel(logging.DEBUG)
logging.getLogger("gateway.guardrail_middleware").setLevel(logging.DEBUG)
logging.getLogger("gateway.guardrail_alerts").setLevel(logging.DEBUG)
```

## Performance Considerations

1. **Caching**: Current spend is cached for 60 seconds to reduce database queries
2. **Aggregates**: Daily aggregates are used when available for better performance
3. **Rate Limiting**: Token bucket calculations are O(1) operations
4. **Alerts**: Sent asynchronously to avoid blocking API calls

## Integration with Existing Systems

The guardrail system integrates seamlessly with:
- **Cost Ledger**: Uses existing cost tracking data
- **Prefect Flows**: Can trigger flows based on violations
- **Observability**: Exports metrics to Prometheus
- **Audit Logs**: All limit changes and violations are logged

## Future Enhancements

Planned improvements include:
- Machine learning-based limit recommendations
- Predictive alerts before limits are reached
- Cost allocation and chargeback support
- Integration with cloud provider billing APIs
- Mobile app push notifications