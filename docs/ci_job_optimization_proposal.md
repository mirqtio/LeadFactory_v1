# CI Job Optimization Proposal

## Executive Summary

This proposal outlines a strategy to optimize the GitHub Actions CI pipeline by splitting tests into separate, parallel jobs. This approach will provide faster feedback, better resource utilization, and easier debugging of failures.

## Current State Analysis

### Test Distribution
- **Total test files**: 220
- **Total test count**: ~3,027
- **Current CI runtime**: ~30 minutes (single job)

### Test Categories
- **Unit Tests**: ~2,900 tests (fast, isolated)
- **Integration Tests**: ~101 tests (database/API dependent)
- **E2E Tests**: ~6 test files (full system tests)
- **Smoke Tests**: Limited coverage (needs expansion)

### Domain Distribution
- 12 distinct domains (d0_gateway through d11_orchestration)
- Uneven distribution: d0_gateway (20 files) vs d2_sourcing (2 files)

## Proposed Job Structure

### 1. Fast Feedback Job (< 1 minute)
**Purpose**: Immediate feedback on critical functionality
```bash
python -m pytest -v -m 'critical or smoke' --tb=short -n 4
```
- **Current limitation**: Need to add more `@pytest.mark.critical` markers
- **Recommendation**: Mark 20-30 high-value, fast tests as critical
- **Target runtime**: < 60 seconds

### 2. Unit Tests Job (~5 minutes)
**Purpose**: Validate core business logic
```bash
python -m pytest -v tests/unit -m 'not integration and not slow' --tb=short -n auto
```
- **Parallelization**: Use all available cores
- **Coverage**: ~95% of tests
- **Target runtime**: 3-5 minutes

### 3. Integration Tests Job (~10 minutes)
**Purpose**: Validate database and external service interactions
```bash
python -m pytest -v -m 'integration' --tb=short -n 2
```
- **Dependencies**: PostgreSQL, stub server
- **Parallelization**: Limited (2 workers) to avoid database conflicts
- **Target runtime**: 8-10 minutes

### 4. Domain-Specific Jobs (Parallel)
Split tests by business domain for better parallelization:

#### 4a. Data Pipeline Tests
```bash
python -m pytest -v tests/unit/d{0,1,2,3,4}_* -m 'not slow' --tb=short -n 4
```
- Covers: gateway, targeting, sourcing, assessment, enrichment

#### 4b. Business Logic Tests
```bash
python -m pytest -v tests/unit/d{5,6,7,8}_* -m 'not slow' --tb=short -n 4
```
- Covers: scoring, reports, storefront, personalization

#### 4c. Delivery & Orchestration Tests
```bash
python -m pytest -v tests/unit/d{9,10,11}_* -m 'not slow' --tb=short -n 4
```
- Covers: delivery, analytics, orchestration

### 5. Full Validation Job
**Purpose**: Complete test suite with coverage
```bash
python -m pytest -v -m 'not slow and not phase_future' \
    --tb=short --cov=. --cov-report=xml -n auto
```
- Runs only after other jobs pass
- Generates coverage reports
- Final validation before merge

## Implementation Strategy

### Phase 1: Add Test Markers (Week 1)
1. Identify and mark 20-30 critical tests
2. Add smoke test markers to key API endpoints
3. Ensure all integration tests are properly marked
4. Review and update slow test markers

### Phase 2: Create Job Definitions (Week 2)
1. Split `.github/workflows/ci.yml` into multiple jobs
2. Configure job dependencies and conditions
3. Set appropriate timeouts for each job
4. Configure artifact sharing between jobs

### Phase 3: Optimize and Monitor (Week 3)
1. Monitor job performance and adjust parallelization
2. Balance test distribution across jobs
3. Fine-tune job dependencies
4. Document new CI structure

## Benefits

### 1. Faster Feedback
- Critical tests provide feedback in < 1 minute
- Unit tests complete in ~5 minutes
- Total CI time reduced from 30 to ~15 minutes (parallel execution)

### 2. Better Resource Utilization
- Parallel jobs utilize GitHub Actions runners efficiently
- Domain-specific jobs can run simultaneously
- Reduced queue time for developers

### 3. Improved Developer Experience
- Easier to identify which component failed
- Can re-run specific job types
- Clear separation of concerns
- Faster iteration on pull requests

### 4. Cost Optimization
- Failing fast on critical tests saves runner minutes
- Parallel execution reduces total runtime
- Selective re-runs instead of full suite

## Example GitHub Actions Configuration

```yaml
name: Optimized CI Pipeline

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  fast_feedback:
    name: Critical & Smoke Tests
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v4
      - name: Run critical tests
        run: |
          docker compose -f docker-compose.test.yml run --rm test \
            python -m pytest -v -m 'critical or smoke' --tb=short -n 4

  unit_tests:
    name: Unit Tests
    runs-on: ubuntu-latest
    timeout-minutes: 10
    needs: fast_feedback
    steps:
      - uses: actions/checkout@v4
      - name: Run unit tests
        run: |
          docker compose -f docker-compose.test.yml run --rm test \
            python -m pytest -v tests/unit -m 'not integration and not slow' -n auto

  integration_tests:
    name: Integration Tests
    runs-on: ubuntu-latest
    timeout-minutes: 15
    needs: fast_feedback
    steps:
      - uses: actions/checkout@v4
      - name: Run integration tests
        run: |
          docker compose -f docker-compose.test.yml run --rm test \
            python -m pytest -v -m 'integration' --tb=short -n 2

  full_validation:
    name: Full Test Suite & Coverage
    runs-on: ubuntu-latest
    timeout-minutes: 20
    needs: [unit_tests, integration_tests]
    steps:
      - uses: actions/checkout@v4
      - name: Run full test suite
        run: |
          docker compose -f docker-compose.test.yml run --rm test \
            python -m pytest -v -m 'not slow and not phase_future' \
            --cov=. --cov-report=xml -n auto
```

## Makefile Targets for Local Testing

```makefile
# Fast feedback tests
test-critical:
	@echo "🚀 Running critical tests..."
	python -m pytest -v -m 'critical or smoke' --tb=short -n 4

# Unit tests only
test-unit:
	@echo "🧪 Running unit tests..."
	python -m pytest -v tests/unit -m 'not integration and not slow' -n auto

# Integration tests
test-integration:
	@echo "🔗 Running integration tests..."
	python -m pytest -v -m 'integration' --tb=short -n 2

# Domain-specific tests
test-data-pipeline:
	@echo "📊 Running data pipeline tests..."
	python -m pytest -v tests/unit/d{0,1,2,3,4}_* -m 'not slow' -n 4

test-business-logic:
	@echo "💼 Running business logic tests..."
	python -m pytest -v tests/unit/d{5,6,7,8}_* -m 'not slow' -n 4

test-delivery:
	@echo "📬 Running delivery tests..."
	python -m pytest -v tests/unit/d{9,10,11}_* -m 'not slow' -n 4
```

## Success Metrics

1. **CI Runtime**: Reduce from 30 minutes to < 15 minutes
2. **Feedback Time**: Critical failures detected in < 1 minute
3. **Developer Satisfaction**: Faster PR iterations
4. **Resource Usage**: 40% reduction in total runner minutes
5. **Failure Isolation**: 90% of failures identified in specific job

## Next Steps

1. Review and approve this proposal
2. Create feature branch for CI optimization
3. Implement Phase 1 (test marking)
4. Gradually roll out job separation
5. Monitor and optimize based on metrics

## Conclusion

This CI job optimization will significantly improve the development workflow by providing faster feedback, better parallelization, and easier debugging. The phased approach ensures a smooth transition with minimal disruption to the existing process.