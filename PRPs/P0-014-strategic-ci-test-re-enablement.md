# PRP-P0-014: Strategic CI Test Re-enablement

## Overview
Re-activate the most valuable unit and integration tests in GitHub Actions CI while keeping the P90 runtime ≤ 5 minutes and eliminating known flaky cases.

## Business Logic
Fast, reliable CI is essential for developer productivity. By strategically selecting high-value tests and optimizing their execution, we can maintain quality gates without blocking deployment velocity. The 5-minute target ensures developers get rapid feedback while the ≥80% coverage requirement maintains code quality standards.

## Acceptance Criteria
- [ ] Selected tests run on every push to `main` and all PRs
- [ ] CI duration ≤ 5 min (P90)
- [ ] Flake rate < 2% over 20 consecutive runs
- [ ] Overall coverage remains ≥ 80%
- [ ] README "Development → Tests" section documents the updated strategy

## Dependencies
- P0-003 (Docker test environment must be working)
- P0-004 (Database migrations must be current)
- P0-013 (CI workflows must be passing)

## Integration Points
- `.github/workflows/test.yml` - Main test workflow configuration
- `tests/` directory structure
- `pytest.ini` - Test markers and configuration
- `conftest.py` - Test fixtures and setup
- `.coveragerc` - Coverage configuration

## Tests to Pass
```bash
# Unit tests must complete in <2 minutes
pytest tests/unit -xvs --timeout=120

# Critical integration tests must complete in <3 minutes  
pytest tests/integration -m "critical" -xvs --timeout=180

# Coverage must meet threshold
coverage report --fail-under=80
```

## Test Selection Strategy

### High-Value Unit Tests (Run Always)
- Core business logic (d5_scoring, d6_reports)
- Data models and schemas
- Gateway/API client tests
- Utility functions

### Critical Integration Tests (Run Always)
- Database connection and migrations
- API endpoints (health, metrics)
- End-to-end happy path
- Authentication/authorization

### Deferred Tests (Run Nightly)
- Slow integration tests (>30s each)
- External API tests (SEMrush, etc.)
- Full regression suite
- Performance benchmarks

## Implementation Plan

### Phase 1: Test Audit and Marking (Day 1)
1. Profile all tests to identify slow ones
2. Mark tests with appropriate pytest markers:
   - `@pytest.mark.critical` - Must run in CI
   - `@pytest.mark.slow` - Defer to nightly
   - `@pytest.mark.flaky` - Fix or remove
3. Create test execution report

### Phase 2: CI Optimization (Day 2)
1. Configure pytest to run in parallel with pytest-xdist
2. Set up test sharding across multiple jobs
3. Implement fail-fast with -x flag
4. Add caching for dependencies and test data

### Phase 3: Monitoring and Tuning (Day 3)
1. Set up test duration tracking
2. Monitor flake rates
3. Adjust timeouts and retries
4. Document final strategy

## Performance Budget
- Test collection: <10 seconds
- Unit tests: <2 minutes
- Integration tests: <3 minutes
- Total CI time: <5 minutes (including setup)

## Rollback Strategy
If new test configuration causes CI failures:
1. Revert to previous pytest marker configuration
2. Restore original test selection in workflow
3. Document issues for investigation
4. Fall back to minimal test suite if needed

## Success Metrics
- P90 CI runtime ≤ 5 minutes (measured over 1 week)
- Zero CI failures due to flaky tests (measured over 20 runs)
- Developer satisfaction with CI speed (informal feedback)
- Coverage maintained at ≥80% (measured daily)