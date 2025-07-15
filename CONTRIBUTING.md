# Contributing to LeadFactory

## Pre-Push Validation (Required)

Before pushing any code changes, you MUST run local CI validation:

```bash
# For quick changes (30 seconds)
make quick-check

# For any significant changes (5-10 minutes)
make bpci
```

The `make bpci` command runs our Bulletproof CI system that exactly mirrors GitHub Actions:
- Uses the same Docker Compose test environment
- Runs the full test suite with real PostgreSQL
- Generates coverage and test reports
- If this passes, GitHub CI will pass

## Testing Guidelines

### Test Organization

Tests are organized by type and domain:
- `tests/unit/` - Unit tests for individual components
- `tests/integration/` - Integration tests for component interactions
- `tests/e2e/` - End-to-end tests (excluded from regular CI)
- `tests/smoke/` - Quick API smoke tests
- `tests/performance/` - Performance and load tests
- `tests/security/` - Security compliance tests

### Test Markers

We use pytest markers to categorize tests:

- `@pytest.mark.slow` - Long-running tests (excluded from PR builds)
- `@pytest.mark.phase05` - Phase 0.5 features (auto-xfailed)
- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.e2e` - End-to-end tests

### Phase 0.5 Features

**IMPORTANT**: If you're implementing a Phase 0.5 feature that isn't ready yet:

1. **New test files**: The root `conftest.py` will automatically mark tests as xfail if they match Phase 0.5 patterns (e.g., `test_*phase05*.py`, `test_dataaxle*.py`, `test_bucket_*.py`)

2. **Individual tests**: For specific tests in mixed files, add:
   ```python
   @pytest.mark.xfail(reason="Phase 0.5 feature - not implemented", strict=False)
   def test_my_phase05_feature():
       ...
   ```

3. **Entire test modules**: Add at module level:
   ```python
   import pytest
   pytestmark = pytest.mark.xfail(reason="Phase 0.5 feature", strict=False)
   ```

### Running Tests

```bash
# Run all tests (except slow and e2e)
pytest

# Run only fast tests (for PRs)
pytest -m "not slow"

# Run all tests including slow ones
pytest -m ""

# Run specific domain tests
pytest tests/unit/d0_gateway/

# Run with coverage
pytest --cov=. --cov-report=html
```

### CI Configuration

- **Pull Requests**: Run `pytest -m "not slow"` (fast tests only)
- **Main Branch**: Run all tests except e2e
- **Nightly**: Run full test suite including performance tests

### Writing New Tests

1. **Test Naming**: Use descriptive names that explain what is being tested
2. **Assertions**: Use clear assertions with helpful messages
3. **Fixtures**: Prefer fixtures over setup/teardown methods
4. **Mocking**: Mock external dependencies appropriately
5. **Performance**: Keep unit tests fast (< 1 second each)

### Common Issues

1. **Import Errors**: Ensure all dependencies are installed and modules are importable
2. **Yelp References**: The Yelp provider has been removed; update tests accordingly
3. **Database Tests**: Use in-memory SQLite for unit tests, not production database
4. **External APIs**: Always mock external API calls in unit/integration tests