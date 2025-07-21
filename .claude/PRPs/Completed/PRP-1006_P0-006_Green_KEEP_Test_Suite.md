# P3-005 - Complete Test Coverage
**Priority**: P3
**Status**: Not Started
**Estimated Effort**: 5 days
**Dependencies**: P0-006, P0-013, P0-014

## Goal
Achieve ≥80% test coverage on all modules that failed validation, establishing comprehensive testing patterns and infrastructure to prevent future coverage regression.

## Why  
- **Business value**: Production readiness requires high test coverage to prevent regressions, ensure code quality, and maintain confidence in deployments
- **Integration**: Builds upon existing pytest infrastructure while adding mock factories, property-based testing, and coverage enforcement
- **Problems solved**: Addresses 57% coverage gap, untested critical business logic, missing edge case coverage, and lack of CI coverage enforcement

## What
Implement comprehensive test coverage improvements focusing on:
- Gateway providers with mock HTTP responses
- D1 targeting modules (geo_validator, quota_tracker, batch_scheduler)
- Batch runner modules
- Formula evaluators with property-based testing
- Mock factory system for external dependencies
- Test utilities for async operations
- CI coverage gates and reporting

### Success Criteria
- [ ] Overall test coverage ≥80% (from current 57.37%)
- [ ] All gateway providers have >70% coverage with mock HTTP responses
- [ ] D1 targeting modules reach >70% coverage
- [ ] Batch runner modules achieve >70% coverage
- [ ] Mock factory system created for external dependencies
- [ ] Test utilities for async operations implemented
- [ ] CI enforces 80% coverage requirement (fails if below)
- [ ] Coverage report published to PR comments
- [ ] No critical business logic paths below 70% coverage
- [ ] Performance: test suite completes in <5 minutes
- [ ] Property-based tests for formula evaluators
- [ ] No flaky tests in 10 consecutive runs

## All Needed Context

### Documentation & References
```yaml
- url: https://docs.pytest.org/en/stable/
  why: Official pytest documentation for best practices
  
- url: https://pypi.org/project/pytest-cov/
  why: Coverage plugin configuration and usage
  
- url: https://hypothesis.readthedocs.io/
  why: Property-based testing for edge cases
  
- url: https://pytest-with-eric.com/pytest-advanced/hypothesis-testing-python/
  why: Practical guide for hypothesis with pytest
  
- file: conftest.py
  why: Existing test fixtures and configuration
  
- file: pytest.ini
  why: Current test configuration to extend
```

### Current Codebase Tree
```
├── tests/
│   ├── conftest.py
│   ├── unit/
│   │   ├── d0_gateway/
│   │   │   └── test_base_client.py (minimal)
│   │   ├── d1_targeting/
│   │   │   └── test_geo_validator.py (missing)
│   │   └── d4_enrichment/
│   │       └── test_d4_coordinator.py
│   └── integration/
│       └── test_smoke.py
├── pytest.ini
├── .coveragerc (missing)
└── requirements-dev.txt
```

### Desired Codebase Tree  
```
├── tests/
│   ├── conftest.py (enhanced)
│   ├── factories/
│   │   ├── __init__.py
│   │   ├── gateway_factory.py
│   │   ├── business_factory.py
│   │   └── api_response_factory.py
│   ├── unit/
│   │   ├── d0_gateway/
│   │   │   ├── test_base_client.py (expanded)
│   │   │   ├── test_google_places_client.py (new)
│   │   │   ├── test_builtwith_client.py (new)
│   │   │   └── test_pagespeed_client.py (new)
│   │   ├── d1_targeting/
│   │   │   ├── test_geo_validator.py (new)
│   │   │   ├── test_quota_tracker.py (new)
│   │   │   └── test_batch_scheduler.py (new)
│   │   ├── batch_runner/
│   │   │   ├── test_batch_processor.py (new)
│   │   │   └── test_progress_tracker.py (new)
│   │   └── d5_scoring/
│   │       └── test_formula_evaluator_property.py (new)
│   └── utils/
│       ├── __init__.py
│       ├── async_helpers.py
│       └── coverage_helpers.py
├── .coveragerc (new)
└── .github/workflows/coverage-report.yml (new)
```

## Technical Implementation

### Integration Points
- `conftest.py` - Add session-scoped fixtures for mock factories
- `requirements-dev.txt` - Add hypothesis, pytest-asyncio, factory-boy
- `.github/workflows/test.yml` - Add coverage enforcement
- All modules with <70% coverage

### Implementation Approach

1. **Create Mock Factory System**
   ```python
   # tests/factories/gateway_factory.py
   import factory
   from unittest.mock import Mock, AsyncMock
   
   class MockHTTPResponseFactory(factory.Factory):
       class Meta:
           model = Mock
       
       status_code = 200
       headers = factory.Dict({"Content-Type": "application/json"})
       json = factory.LazyFunction(lambda: {"status": "success"})
       
   class MockAPIClientFactory:
       @staticmethod
       def create_mock_client(provider_name: str):
           client = AsyncMock()
           client.name = provider_name
           return client
   ```

2. **Implement Property-Based Tests**
   ```python
   # tests/unit/d5_scoring/test_formula_evaluator_property.py
   from hypothesis import given, strategies as st
   from hypothesis import assume
   
   @given(
       weights=st.dictionaries(
           st.text(min_size=1),
           st.floats(min_value=0, max_value=1),
           min_size=1
       )
   )
   def test_weights_sum_to_one(weights):
       assume(abs(sum(weights.values()) - 1.0) < 0.005)
       # Test formula evaluator with generated weights
   ```

3. **Configure Coverage Requirements**
   ```ini
   # .coveragerc
   [run]
   source = .
   omit = 
       */tests/*
       */migrations/*
       */__pycache__/*
       */venv/*
       */stubs/*
   
   [report]
   precision = 2
   show_missing = True
   skip_covered = False
   
   [html]
   directory = htmlcov
   ```

4. **Add CI Coverage Gates**
   ```yaml
   # .github/workflows/test.yml addition
   - name: Run tests with coverage
     run: |
       pytest --cov=. --cov-report=term-missing --cov-report=xml --cov-fail-under=80
   
   - name: Upload coverage reports
     uses: codecov/codecov-action@v3
     with:
       file: ./coverage.xml
       fail_ci_if_error: true
   ```

5. **Create Async Test Utilities**
   ```python
   # tests/utils/async_helpers.py
   import asyncio
   from typing import Any, Coroutine
   
   def async_test(coro: Coroutine[Any, Any, Any]):
       """Decorator for async test functions"""
       def wrapper(*args, **kwargs):
           loop = asyncio.get_event_loop()
           return loop.run_until_complete(coro(*args, **kwargs))
       return wrapper
   ```

## Validation Gates

### Executable Tests
```bash
# Syntax/Style
ruff check --fix && mypy .

# Check current coverage baseline
pytest --cov=. --cov-report=term-missing | grep TOTAL

# Unit Tests with coverage
pytest tests/unit/ --cov=. --cov-report=term-missing --cov-fail-under=80 -v

# Integration Tests
pytest tests/integration/ -v

# Property-based tests
pytest tests/unit/d5_scoring/test_formula_evaluator_property.py --hypothesis-show-statistics

# Performance check
time pytest tests/ -n auto --cov=. --cov-report=term-missing

# Flaky test detection
pytest tests/ --count=10 -x
```

### Missing-Checks Validation
**Required for Backend/API tasks:**
- [X] Pre-commit hooks (ruff, mypy, pytest -m "not e2e")
- [X] Branch protection & required status checks
- [X] Security scanning (Dependabot, Trivy, audit tools)
- [X] Coverage enforcement in CI (--cov-fail-under=80)
- [X] Coverage reporting to PRs
- [X] Performance budgets (<5 minute test runtime)

**Recommended:**
- [X] Property-based testing for complex logic
- [X] Mock factory patterns for consistency
- [X] Async test utilities
- [X] Coverage trend tracking
- [X] Test parallelization with pytest-xdist

## Dependencies
- P0-006 (Green KEEP Test Suite) - Need passing test infrastructure
- P0-013 (CI/CD Pipeline Stabilization) - CI must be stable for coverage gates
- P0-014 (Test Suite Re-Enablement) - Tests must be running before enhancing coverage

### Package Dependencies
```txt
# Add to requirements-dev.txt
pytest-cov>=4.1.0
hypothesis>=6.100.0
factory-boy>=3.3.0
pytest-asyncio>=0.21.0
pytest-xdist>=3.5.0
codecov>=2.1.13
```

## Rollback Strategy
- Lower coverage requirement to 70% in CI if 80% proves too aggressive
- Remove property-based tests if they cause flakiness
- Disable parallel execution if race conditions occur
- Feature flag for coverage enforcement: `ENFORCE_COVERAGE_GATES`

## Feature Flag Requirements  
- `ENFORCE_COVERAGE_GATES` - Enable/disable CI coverage enforcement
- `ENABLE_PROPERTY_TESTS` - Toggle property-based testing
- `ENABLE_PARALLEL_TESTS` - Control pytest-xdist usage