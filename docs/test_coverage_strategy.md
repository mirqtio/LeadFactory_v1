# Test Coverage Strategy for 80% in <5 Minutes

## Current State
- Coverage: 59.14%
- Runtime: 79 seconds
- Tests: 842 passed

## Path to 80% Coverage

### 1. Include Critical API Integration Tests
API endpoints provide high coverage because they exercise entire code paths:
- `/api/v1/assessments` - Covers d3_assessment modules
- `/api/v1/reports` - Covers d6_reports modules
- `/api/v1/batch` - Covers batch_runner modules
- `/api/v1/lead-explorer` - Already included

### 2. Add Fast Provider Tests
Many d0_gateway providers have low coverage but fast tests:
- Mock-based provider tests run quickly
- Each provider test covers ~100 lines

### 3. Strategic Test Selection
Focus on modules with:
- High statement count (>100)
- Low current coverage (<30%)
- Fast test execution (<0.5s per test)

### 4. Exclude Truly Slow Tests
Keep excluding:
- Tests marked with @pytest.mark.slow
- Docker-based tests
- External API tests
- Performance benchmarks

## Implementation
```bash
pytest \
  tests/unit \
  tests/integration \
  tests/smoke \
  -m "not slow and not flaky and not external" \
  --ignore=tests/unit/d10_analytics/test_d10_models.py \
  --ignore=tests/unit/d10_analytics/test_warehouse.py \
  --ignore=tests/unit/d11_orchestration/test_bucket_flow.py \
  --ignore=tests/unit/d11_orchestration/test_pipeline.py \
  --ignore=tests/unit/d9_delivery/test_delivery_manager.py \
  --ignore=tests/unit/d9_delivery/test_sendgrid.py \
  --ignore=tests/integration/test_postgres_container.py \
  --ignore=tests/integration/test_prd_v1_2_pipeline.py \
  -n auto
```

## Expected Results
- Coverage: ~82%
- Runtime: ~90 seconds
- Reliable CI with meaningful coverage