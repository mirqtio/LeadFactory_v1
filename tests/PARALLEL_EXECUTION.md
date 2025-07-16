# Test Parallelization Guide

This document describes the test parallelization setup for LeadFactory, implemented using pytest-xdist.

## Overview

Test parallelization is configured to speed up test execution by running tests across multiple workers. The system automatically adjusts the number of workers based on:
- Available CPU cores
- Memory constraints
- Test type (unit, integration, e2e)
- Execution environment (local, CI, Docker)

## Performance Improvements

Expected performance improvements:
- **Unit tests**: 50-75% reduction in execution time
- **Integration tests**: 30-40% reduction (limited parallelization due to shared resources)
- **E2E tests**: No improvement (run serially for reliability)

## Usage

### Automatic Parallelization

The default pytest configuration includes automatic parallelization:

```bash
# Run all tests with auto-parallelization
make test

# Run specific test types with optimized parallelization
make test-unit        # Maximum parallel workers
make test-integration # Limited to 2 workers
make test-e2e        # Serial execution
```

### Manual Configuration

You can also manually control parallelization:

```bash
# Run with specific number of workers
pytest -n 4

# Run with automatic worker detection
pytest -n auto

# Run with work stealing (better load balancing)
pytest -n auto --dist worksteal
```

### Parallelization Report

To see the parallelization configuration:

```bash
# View full parallelization report
python scripts/test_parallelization_config.py

# View configuration for specific test type
python scripts/test_parallelization_config.py --type unit
```

## Test Isolation

The `tests/parallel_safety.py` plugin ensures proper test isolation:

### Database Isolation

- **SQLite**: Each worker uses a separate database file (e.g., `test_gw0.db`, `test_gw1.db`)
- **PostgreSQL**: Each worker uses a separate database or schema

### Redis Isolation

- Each worker uses a different Redis database (0-15)
- Additional key prefixing for extra safety

### Temporary Files

- Each worker has its own temp directory
- Test-specific subdirectories prevent conflicts

## Serial Test Execution

Some tests must run serially due to shared state or resource constraints. Mark these tests with:

```python
@pytest.mark.serial
def test_shared_resource():
    # This test will skip in parallel execution
    pass

@pytest.mark.no_parallel
def test_database_migration():
    # Critical tests that modify global state
    pass
```

## Known Serial Tests

The following test categories should run serially:

1. **Database Migration Tests**: Tests that modify the database schema
2. **Full Pipeline E2E Tests**: Complex integration tests with multiple dependencies
3. **Docker Compose Tests**: Tests that manage Docker containers
4. **Performance Tests**: Tests that measure execution time

## CI/CD Configuration

### GitHub Actions

The CI environment is automatically detected and uses conservative parallelization:
- Maximum 2 workers (GitHub Actions limit)
- Memory-aware worker allocation

### Docker

When running in Docker containers:
- Maximum 4 workers to prevent resource exhaustion
- Automatic detection of container environment

## Troubleshooting

### Tests Failing in Parallel

If tests pass individually but fail in parallel:

1. Check for shared state between tests
2. Ensure proper test isolation (use fixtures)
3. Mark problematic tests as `@pytest.mark.serial`

### Database Connection Errors

If you see "too many connections" errors:

1. Reduce worker count: `pytest -n 2`
2. Check database connection pool settings
3. Ensure proper connection cleanup in tests

### Memory Issues

If tests run out of memory:

1. Reduce worker count based on available RAM
2. Use `--dist worksteal` for better memory distribution
3. Run memory-intensive tests serially

## Best Practices

1. **Write Isolated Tests**: Each test should be independent
2. **Use Fixtures**: Leverage pytest fixtures for proper setup/teardown
3. **Avoid Shared State**: Don't rely on test execution order
4. **Clean Up Resources**: Ensure all resources are properly released
5. **Monitor Performance**: Track test execution times to identify bottlenecks

## Configuration Files

- `pytest.ini`: Default configuration with `-n auto`
- `pytest-full.ini`: Full test suite configuration
- `pytest-minimal.ini`: Minimal configuration without parallelization
- `scripts/test_parallelization_config.py`: Dynamic worker calculation
- `tests/parallel_safety.py`: Test isolation plugin