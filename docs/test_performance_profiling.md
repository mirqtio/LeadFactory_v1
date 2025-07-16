# Test Performance Profiling Results

## Overview

This document summarizes the test performance profiling conducted to identify and mark slow tests in the LeadFactory codebase. The goal was to enable faster CI runs by excluding slow tests when needed.

## Summary of Changes

- **Total tests marked as slow**: 20 tests
- **Affected files**: 7 test files
- **Threshold used**: 1 second (tests taking >1s were marked as slow)

## Slow Tests Identified

### Circuit Breaker Tests (`tests/unit/d0_gateway/test_circuit_breaker.py`)
- `test_three_states_closed_open_half_open` - Tests circuit breaker state transitions with sleep delays
- `test_configurable_recovery_timeout` - Tests configurable timeout with 2s sleep
- `test_auto_recovery_mechanism` - Tests automatic recovery with 1.1s sleep  
- `test_repeated_recovery_attempts` - Tests repeated recovery with 2.2s sleep

### Cost Enforcement Middleware (`tests/unit/d0_gateway/middleware/test_cost_enforcement.py`)
- `test_guardrail_integration` - 9.01s test for guardrail manager integration

### Gateway Facade (`tests/unit/d0_gateway/test_facade.py`)
- `test_factory_thread_safety` - Tests thread safety with concurrent operations

### Integration Tests
- `test_pipeline_concurrent_execution` - Tests concurrent pipeline execution
- `test_health_under_sustained_load` - Tests system under sustained load
- `test_data_persistence_across_restart` - Tests database persistence

### Docker Compose Tests (`tests/test_docker_compose.py`)
Multiple tests that validate Docker services are running properly - all marked as slow due to container startup times.

## Usage

### Running tests without slow tests (for quick CI runs):
```bash
pytest -m "not slow"
```

### Running only slow tests:
```bash
pytest -m slow
```

### Running all tests (including slow):
```bash
pytest
```

## Impact on Test Suite

- **Total unit tests**: 2,243
- **Tests excluded with `-m "not slow"`**: 537
- **Tests remaining for quick runs**: 1,706 (76% of tests)

This allows for ~24% faster test runs in CI when slow tests are excluded.

## Scripts Created

1. **`scripts/profile_slow_tests.py`** - Main profiling script using pytest durations
2. **`scripts/profile_slow_tests_simple.py`** - Alternative profiling using JSON report
3. **`scripts/find_slow_tests.py`** - Finds slow tests by directory
4. **`scripts/mark_slow_tests.py`** - Automatically marks tests with sleep calls
5. **`scripts/list_slow_tests.py`** - Lists all tests marked with @pytest.mark.slow

## Recommendations

1. **CI Configuration**: Update CI workflows to use `pytest -m "not slow"` for PR validation runs
2. **Nightly Runs**: Run full test suite including slow tests in nightly builds
3. **Developer Workflow**: Developers can use `pytest -m "not slow"` for quick local test runs
4. **Future Tests**: Any new tests taking >1 second should be marked with `@pytest.mark.slow`

## Next Steps

1. Update CI configuration to leverage the slow marker
2. Consider further optimization of slow tests where possible
3. Monitor and update slow test markers as tests evolve