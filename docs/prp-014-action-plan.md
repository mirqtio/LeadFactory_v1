# PRP-014 Action Plan: Achieving 80% Coverage in <5 Minutes

## Current Status
- **Coverage**: 59.14%
- **Runtime**: 79 seconds  
- **Gap to 80%**: 20.86%

## Modules to Target for Maximum Impact

### 1. High-Impact API Tests (Est. +15% coverage)
Add integration tests for these API endpoints:
- `POST /api/v1/assessments/assess` - Covers d3_assessment (363 lines)
- `POST /api/v1/reports/generate` - Covers d6_reports (204 lines)
- `POST /api/v1/batch/jobs` - Covers batch_runner (257 lines)
- `POST /api/v1/targeting/validate` - Covers d1_targeting (304 lines)

### 2. Fast Unit Tests to Add (Est. +8% coverage)
- `d5_scoring/formula_evaluator.py` (107 lines, 0% covered)
- `d5_scoring/rules_schema.py` (149 lines, 0% covered)
- `d0_gateway/providers/*` mock tests (average 75 lines each)

### 3. Tests to Remove/Skip
Mark these as @pytest.mark.slow:
- `test_d3_coordinator.py` tests (3+ seconds each)
- Any test taking >1 second

## Implementation Steps

1. **Create fast integration test suite**
   ```python
   # tests/integration/test_api_coverage.py
   def test_assessment_api_flow(client):
       # Single test covers entire assessment flow
       response = client.post("/api/v1/assessments/assess", ...)
       assert response.status_code == 200
   ```

2. **Add mock-based provider tests**
   ```python
   # tests/unit/d0_gateway/test_providers_fast.py
   @patch('requests.post')
   def test_all_providers_basic_flow(mock_post):
       # Test each provider's happy path
   ```

3. **Mark slow tests**
   ```bash
   python scripts/mark_slow_tests.py --threshold=1.0
   ```

## Expected Results
- **Coverage**: ~82%
- **Runtime**: ~120 seconds
- **Test count**: ~950

## Validation
Run locally before pushing:
```bash
time pytest tests/unit tests/integration tests/smoke \
  -m "not slow and not flaky and not external" \
  --cov=. --cov-report=term --cov-config=.coveragerc
```

Success criteria:
- [ ] Coverage ≥ 80%
- [ ] Runtime < 300 seconds
- [ ] All tests pass