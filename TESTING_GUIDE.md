# LeadFactory Testing Guide

This guide provides patterns and best practices for writing tests in the LeadFactory codebase. Following these patterns ensures fast, reliable, and maintainable tests.

## Pre-Push Validation (Required)

Before pushing code, always run local CI validation to prevent breaking the build:

```bash
# Full CI validation (recommended)
make bpci

# Quick validation for small changes
make quick-check
```

The `make bpci` command runs our Bulletproof CI system that mirrors GitHub Actions exactly.

## Table of Contents
- [Test Organization](#test-organization)
- [Mock Factory Pattern](#mock-factory-pattern)
- [Testing External Services](#testing-external-services)
- [Async Testing](#async-testing)
- [Database Testing](#database-testing)
- [Performance Guidelines](#performance-guidelines)
- [Common Patterns](#common-patterns)

## Test Organization

Tests are organized by type and module:
```
tests/
├── unit/           # Fast, isolated unit tests
├── integration/    # Tests with real dependencies
├── smoke/          # Critical path tests
├── fixtures/       # Mock factories and test utilities
└── conftest.py     # Shared pytest fixtures
```

## Mock Factory Pattern

We use a standardized mock factory pattern for external services. This ensures consistent, maintainable test data.

### Basic Usage

```python
from tests.fixtures import GooglePlacesMockFactory

def test_google_places_search():
    # Create a success response
    mock_response = GooglePlacesMockFactory.create_success_response()
    
    # Create an error response
    error_response = GooglePlacesMockFactory.create_error_response("ZERO_RESULTS")
    
    # Create a timeout scenario
    timeout_mock = GooglePlacesMockFactory.create_timeout_scenario()
```

### Creating a New Mock Factory

```python
from tests.fixtures.mock_factory import MockFactory

class YelpMockFactory(MockFactory):
    @classmethod
    def create_success_response(cls, **overrides):
        base = {
            "businesses": [{
                "id": "test-business-123",
                "name": "Test Restaurant",
                "rating": 4.5,
                "review_count": 100
            }],
            "total": 1
        }
        base.update(overrides)
        return base
    
    @classmethod
    def create_error_response(cls, error_type, **overrides):
        errors = {
            "rate_limit": {"error": {"code": "RATE_LIMIT_EXCEEDED"}},
            "not_found": {"error": {"code": "BUSINESS_NOT_FOUND"}}
        }
        return errors.get(error_type, errors["not_found"])
```

## Testing External Services

Always mock external services to keep tests fast and deterministic.

### Using responses Library

```python
import responses
from tests.fixtures import GooglePlacesMockFactory

@responses.activate
def test_search_business():
    # Mock the API response
    responses.add(
        responses.GET,
        "https://maps.googleapis.com/maps/api/place/textsearch/json",
        json=GooglePlacesMockFactory.create_success_response(),
        status=200
    )
    
    # Your test code
    result = google_places_provider.search("restaurant", "San Francisco")
    assert result["status"] == "OK"
```

### Testing Error Scenarios

```python
@responses.activate
def test_handle_rate_limit():
    # Mock rate limit response
    responses.add(
        responses.GET,
        "https://api.example.com/endpoint",
        json={"error": "rate_limit"},
        status=429,
        headers={"Retry-After": "60"}
    )
    
    # Test rate limit handling
    with pytest.raises(RateLimitError):
        client.make_request()
```

## Async Testing

For async code, use pytest-asyncio:

```python
import pytest
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_async_operation():
    # Create async mock
    mock_client = AsyncMock()
    mock_client.fetch_data.return_value = {"status": "success"}
    
    # Test async function
    result = await process_async_data(mock_client)
    assert result["status"] == "success"
```

## Database Testing

### Use In-Memory SQLite for Unit Tests

```python
@pytest.fixture
def test_db():
    """Create in-memory SQLite database for tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    
    with Session(engine) as session:
        yield session
        session.rollback()
```

### Testing with Real Data

```python
def test_create_business(test_db):
    # Create test data
    business = Business(
        name="Test Restaurant",
        address="123 Test St",
        status=BusinessStatus.ACTIVE
    )
    test_db.add(business)
    test_db.commit()
    
    # Query and assert
    result = test_db.query(Business).filter_by(name="Test Restaurant").first()
    assert result is not None
    assert result.status == BusinessStatus.ACTIVE
```

## Performance Guidelines

### 1. Use loadscope for pytest-xdist
```bash
pytest -n auto --dist loadscope
```

### 2. Mark Slow Tests
```python
@pytest.mark.slow
def test_complex_operation():
    # Test that takes > 1 second
    pass
```

### 3. Use Fixtures Efficiently
```python
@pytest.fixture(scope="module")
def expensive_setup():
    """Reuse expensive setup across tests in module."""
    data = load_large_dataset()
    yield data
    cleanup_resources()
```

## Common Patterns

### Fixture Returns Callable Pattern

This pattern allows parameterized fixtures:

```python
@pytest.fixture
def create_mock_business():
    """Factory fixture for creating businesses."""
    def _create(name="Test Business", **kwargs):
        defaults = {
            "address": "123 Test St",
            "rating": 4.5,
            "status": "active"
        }
        defaults.update(kwargs)
        return Business(name=name, **defaults)
    return _create

def test_business_operations(create_mock_business):
    # Create custom business
    restaurant = create_mock_business(name="Test Restaurant", rating=5.0)
    cafe = create_mock_business(name="Test Cafe", rating=4.0)
```

### Testing with Context Managers

```python
def test_circuit_breaker():
    with pytest.raises(CircuitOpenError):
        # Simulate circuit breaker opening
        for _ in range(5):
            with pytest.raises(RequestError):
                make_failing_request()
        
        # This should raise CircuitOpenError
        make_failing_request()
```

### Parametrized Tests

```python
@pytest.mark.parametrize("input,expected", [
    ("", False),
    ("invalid-email", False),
    ("test@example.com", True),
    ("user+tag@domain.co.uk", True),
])
def test_email_validation(input, expected):
    assert is_valid_email(input) == expected
```

### Testing Time-Dependent Code

```python
from freezegun import freeze_time

@freeze_time("2023-12-25 10:00:00")
def test_holiday_pricing():
    # Test code that depends on current date
    price = calculate_price(base_price=100)
    assert price == 150  # Holiday surge pricing
```

## Best Practices

1. **Keep tests focused**: Each test should verify one behavior
2. **Use descriptive names**: `test_search_returns_empty_list_when_no_results`
3. **Arrange-Act-Assert**: Structure tests clearly
4. **Don't test implementation details**: Test behavior, not internals
5. **Mock at boundaries**: Mock external services, not internal components
6. **Use fixtures for setup**: Avoid duplicate setup code
7. **Test edge cases**: Empty lists, None values, errors
8. **Keep tests fast**: Target < 100ms per unit test

## Running Tests

```bash
# Run all tests with coverage
pytest --cov=. --cov-branch

# Run only unit tests
pytest tests/unit/

# Run with parallel execution
pytest -n auto --dist loadscope

# Run specific test file
pytest tests/unit/d0_gateway/test_providers.py

# Run tests matching pattern
pytest -k "test_google_places"

# Show slowest tests
pytest --durations=10
```

## Debugging Tests

```bash
# Run with verbose output
pytest -vv

# Drop into debugger on failure
pytest --pdb

# Show local variables on failure
pytest -l

# Run single test with print statements
pytest -s tests/unit/test_example.py::test_specific
```

This guide is a living document. Update it as new patterns emerge or better practices are discovered.