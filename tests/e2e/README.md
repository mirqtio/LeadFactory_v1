# End-to-End Production Tests

This directory contains comprehensive production readiness tests for LeadFactory.

## Test Structure

### 1. Smoke Tests (`test_production_smoke.py`)
Full pipeline validation with 5 parallel test variants:
- **HVAC Normal**: Baseline happy path
- **HVAC Negative**: PageSpeed latency injection (500ms)
- **Restaurant Email Fail**: Invalid email handling
- **Lawyer Stripe Error**: Payment failure resilience
- **Rotating Vertical**: Different vertical each day of week

**Schedule**: Daily at 20:30 UTC (30 min before nightly batch)  
**Duration**: ≤ 8 minutes  
**Alerts**: PagerDuty on any failure

### 2. Heartbeat Checks (`test_heartbeat.py`)
Lightweight service health monitoring:
- Database connectivity
- Redis cache (non-critical)
- Yelp API credentials & quota
- Stripe authentication
- SendGrid authentication
- OpenAI API (non-critical)
- PageSpeed API (non-critical)

**Schedule**: Every 2 hours  
**Duration**: ≤ 90 seconds  
**Alerts**: Slack warnings only (no pager)

## Running Tests

### Quick Commands
```bash
# Run full production test suite
make prod-test

# Run only smoke tests
make smoke

# Run only heartbeat checks
make heartbeat

# Run with Python directly
python scripts/run_production_tests.py [--smoke-only] [--heartbeat-only]
```

### Schedule in Prefect
```bash
# Set up scheduled test flows
make schedule-tests

# Start Prefect agent
make start-agent

# Or schedule manually
python scripts/prefect_schedule_tests.py
```

## Test Assertions

### Timing Requirements
- Assessment: < 25 seconds
- PDF Generation: < 30 seconds
- Stripe Webhook: < 10 seconds
- Email Delivery: < 15 seconds

### Data Quality Checks
- Assessment must have ≥ 2 issues and ≥ 1 screenshot
- Email subject must contain `SMOKE-{run_id}`
- Email body must be > 800 characters
- All smoke test data cleaned up after 24 hours

### Performance Monitoring
All timings are recorded to Prometheus:
- `smoke_test_duration_seconds{variant, task}`
- `heartbeat_health_status{service}`
- `heartbeat_check_duration_seconds{service}`

## Alerting Matrix

| Condition | Alert Type | Channel |
|-----------|-----------|---------|
| Smoke test failure | PagerDuty sev-1 | On-call engineer |
| Heartbeat critical failure | Slack #ops | Team notification |
| Timing breach (p95 > 150%) | Slack #pipeline | Performance warning |
| Data quality issue | Slack #data | Data team |

## Cleanup

Test data is automatically cleaned up:
- Smoke test data: After 24 hours
- Heartbeat data: After 1 day
- Uses prefixed transactions for safety
- Pattern: `smoke_%` and `heartbeat_%`

## Local Development

### Running Individual Variants
```python
# Test a specific variant
from tests.e2e.test_production_smoke import HVACNormalVariant, run_smoke_variant

variant = HVACNormalVariant()
result = await run_smoke_variant(variant)
```

### Adding New Test Variants
1. Create a new class inheriting from `SmokeTestVariant`
2. Override `inject_failures()` for fault injection
3. Override `validate_results()` for custom assertions
4. Add to the variant matrix in `daily_smoke_flow()`

## CI Integration

Tests are designed to run in CI:
```yaml
# GitHub Actions example
- name: Run Production Tests
  run: |
    make prod-test
  env:
    DATABASE_URL: ${{ secrets.DATABASE_URL }}
    USE_STUBS: false
```

## Troubleshooting

### Common Issues

1. **Heartbeat timeout**: Check external API rate limits
2. **Smoke test flakes**: Review timing assertions
3. **Cleanup failures**: Check database permissions
4. **Prefect scheduling**: Ensure agent is running

### Debug Mode
```bash
# Run with debug logging
PREFECT_LOGGING_LEVEL=DEBUG python scripts/run_production_tests.py

# Check test results
cat production_test_results_*.json | jq .
```