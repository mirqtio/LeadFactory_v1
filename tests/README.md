# LeadFactory Test Suite

## Overview

The LeadFactory test suite contains 2,829 tests organized by domain and test type. This guide helps developers write reliable tests and use our testing infrastructure effectively.

## Test Structure

```
tests/
├── conftest.py              # Root configuration and stub server setup
├── markers.py               # Marker validation system
├── parallel_safety.py       # Parallel execution isolation
├── test_port_manager.py     # Dynamic port allocation
├── test_synchronization.py  # Synchronization utilities
│
├── unit/                    # Fast, isolated component tests
│   ├── d0_gateway/         # Gateway and API tests
│   ├── d1_targeting/       # Targeting logic tests
│   ├── d2_sourcing/        # Data sourcing tests
│   ├── d3_assessment/      # Assessment tests
│   ├── d4_enrichment/      # Enrichment tests
│   ├── d5_scoring/         # Scoring engine tests
│   ├── d6_reports/         # Report generation tests
│   ├── d7_storefront/      # Payment and checkout tests
│   ├── d8_personalization/ # Personalization tests
│   ├── d9_delivery/        # Email delivery tests
│   ├── d10_analytics/      # Analytics tests
│   └── d11_orchestration/  # Pipeline tests
│
├── integration/            # Cross-domain integration tests
├── e2e/                   # End-to-end workflow tests
├── performance/           # Performance benchmarks
├── smoke/                 # Quick health checks
│
├── fixtures/              # Shared test fixtures
│   ├── mock_factory.py    # Mock object factories
│   ├── sendgrid_mock.py   # SendGrid API mocks
│   └── google_places_mock.py # Google Places mocks
│
└── generators/            # Test data generators
    ├── business_generator.py    # Business data factory
    └── assessment_generator.py  # Assessment data factory
```

## Marker Usage Guide

### Required Primary Markers

Every test MUST have one of these markers:

```python
@pytest.mark.unit         # Fast, isolated tests
@pytest.mark.integration  # Multi-component tests
@pytest.mark.e2e         # Full workflow tests
@pytest.mark.smoke       # Health check tests
```

### Domain Markers (Auto-Applied)

Tests in domain directories automatically get domain markers:

```python
# In tests/unit/d5_scoring/test_engine.py
@pytest.mark.unit
def test_scoring_calculation():
    # Automatically gets @pytest.mark.d5_scoring
    pass
```

### Special Markers

```python
@pytest.mark.critical    # Always runs in CI (use sparingly)
@pytest.mark.slow       # Tests >1 second (runs nightly)
@pytest.mark.flaky      # Intermittent failures (auto-retry)
@pytest.mark.no_stubs   # Doesn't need stub server
@pytest.mark.minimal    # Runs without infrastructure
```

## Fixture Documentation

### Core Fixtures

#### `test_settings` (conftest.py)
Provides validated test configuration:
```python
def test_api_client(test_settings):
    assert test_settings.use_stubs is True
    assert test_settings.environment == "test"
```

#### `isolated_db` (parallel_safety.py)
Database isolation for parallel execution:
```python
def test_database_operation(isolated_db):
    # Each worker gets its own database
    db_url = isolated_db["db_url"]
```

#### `isolated_temp_dir` (parallel_safety.py)
Isolated temporary directory per test:
```python
def test_file_operation(isolated_temp_dir):
    # Worker-specific temp directory
    test_file = isolated_temp_dir / "test.txt"
    test_file.write_text("data")
```

### Mock Fixtures

#### Business Data Mocks
```python
from tests.fixtures.mock_factory import (
    mock_business,
    mock_assessment,
    mock_lead
)

def test_business_logic(mock_business):
    assert mock_business.name == "Test Business"
    assert mock_business.website == "https://example.com"
```

#### API Mocks
```python
@pytest.fixture
def mock_sendgrid(monkeypatch):
    from tests.fixtures.sendgrid_mock import MockSendGridClient
    client = MockSendGridClient()
    monkeypatch.setattr("d9_delivery.client.SendGridClient", lambda: client)
    return client

def test_email_delivery(mock_sendgrid):
    # Test with mocked SendGrid
    pass
```

## Best Practices

### 1. Writing Reliable Tests

#### Use Proper Synchronization
```python
# Bad - Race condition prone
server.start()
time.sleep(2)  # Unreliable

# Good - Deterministic waiting
from tests.test_synchronization import wait_for_condition
server.start()
wait_for_condition(
    lambda: server.is_ready(),
    timeout=5.0,
    message="Server failed to start"
)
```

#### Use Dynamic Ports
```python
# Bad - Port conflicts
server = TestServer(port=5000)

# Good - Conflict-free
from tests.test_port_manager import get_dynamic_port
port = get_dynamic_port()
server = TestServer(port=port)
```

#### Clean Up Resources
```python
# Use fixtures for automatic cleanup
@pytest.fixture
def test_client():
    client = TestClient()
    yield client
    client.close()  # Automatic cleanup

# Or use try/finally
def test_with_resources():
    server = None
    try:
        server = TestServer()
        # Test code
    finally:
        if server:
            server.stop()
```

### 2. Test Data Generation

#### Use Factories for Consistency
```python
from tests.generators import BusinessGenerator, BusinessScenario

@pytest.fixture
def restaurant_dataset():
    generator = BusinessGenerator(seed=42)  # Deterministic
    return generator.generate_scenario_dataset(
        BusinessScenario.RESTAURANTS, 
        count=10
    )

def test_restaurant_processing(restaurant_dataset):
    # Consistent test data every run
    assert len(restaurant_dataset) == 10
    assert all(b.vertical == "restaurants" for b in restaurant_dataset)
```

#### Generate Realistic Data
```python
from tests.generators import AssessmentGenerator, AssessmentScenario

def test_high_performance_sites():
    generator = AssessmentGenerator()
    assessments = generator.generate_assessments(
        businesses,
        [AssessmentScenario.HIGH_PERFORMANCE]
    )
    assert all(a.performance_score > 85 for a in assessments)
```

### 3. Testing Async Code

```python
import pytest

@pytest.mark.asyncio
async def test_async_operation():
    from tests.test_synchronization import AsyncTestEvent
    
    event = AsyncTestEvent()
    
    async def background_task():
        await asyncio.sleep(1)
        await event.set("completed")
    
    task = asyncio.create_task(background_task())
    
    # Wait for completion
    assert await event.wait(timeout=2.0)
    results = await event.get_results()
    assert results == ["completed"]
```

### 4. Performance Testing

```python
@pytest.mark.slow  # Mark as slow test
@pytest.mark.timeout(30)  # Fail if exceeds 30s
def test_large_dataset_processing():
    generator = BusinessGenerator()
    large_dataset = generator.generate_performance_dataset("large")
    
    start_time = time.time()
    process_businesses(large_dataset)
    duration = time.time() - start_time
    
    assert duration < 25  # Performance requirement
```

## Common Patterns

### Testing API Endpoints

```python
from fastapi.testclient import TestClient

def test_api_endpoint(test_client: TestClient):
    response = test_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
```

### Testing Database Operations

```python
def test_database_query(db_session):
    # Create test data
    business = Business(name="Test", website="https://test.com")
    db_session.add(business)
    db_session.commit()
    
    # Test query
    result = db_session.query(Business).filter_by(name="Test").first()
    assert result is not None
    assert result.website == "https://test.com"
```

### Testing with Mocked External APIs

```python
def test_external_api_integration(monkeypatch):
    # Mock the API client
    mock_response = {"status": "success", "data": [...]}
    
    def mock_api_call(*args, **kwargs):
        return mock_response
    
    monkeypatch.setattr("d0_gateway.client.make_request", mock_api_call)
    
    # Test the integration
    result = process_external_data()
    assert result["status"] == "success"
```

## Anti-Patterns to Avoid

### 1. Hardcoded Values
```python
# Bad
def test_api():
    response = requests.get("http://localhost:5000/api")  # Port conflict

# Good
def test_api(test_client):
    response = test_client.get("/api")  # Uses test client
```

### 2. Shared State
```python
# Bad - Modifies global state
GLOBAL_COUNTER = 0

def test_increment():
    global GLOBAL_COUNTER
    GLOBAL_COUNTER += 1  # Breaks parallel execution

# Good - Isolated state
def test_increment():
    counter = Counter()
    counter.increment()
    assert counter.value == 1
```

### 3. Unreliable Timing
```python
# Bad
async def test_async():
    start_task()
    await asyncio.sleep(5)  # Arbitrary wait
    assert task_completed()

# Good
async def test_async():
    task = start_task()
    await task  # Wait for actual completion
    assert task.result() is not None
```

## Debugging Test Failures

### Common Commands

```bash
# Run single test with verbose output
pytest -vvv tests/unit/test_file.py::test_name

# Show test output even on success
pytest -s tests/unit/test_file.py

# Debug parallel execution issues
pytest -n 1 tests/unit/test_file.py  # Force serial

# Show slowest tests
pytest --durations=10

# Run with debugger
pytest --pdb tests/unit/test_file.py
```

### Debugging Markers

```bash
# Check which markers are applied
pytest --collect-only -q tests/unit/test_file.py

# Validate all markers
pytest --validate-markers

# Show marker statistics
pytest --show-marker-report
```

### Debugging Flaky Tests

```bash
# Run test multiple times
pytest --count=10 tests/unit/test_file.py::test_name

# Run with flaky plugin
pytest --reruns 5 --reruns-delay 2 tests/unit/test_file.py
```

## Contributing

When adding new tests:

1. **Choose appropriate location** based on test type and domain
2. **Apply correct markers** (primary marker required)
3. **Use existing fixtures** when possible
4. **Follow naming conventions**: `test_*.py`, `test_*()` 
5. **Write descriptive docstrings** explaining what's being tested
6. **Keep tests focused** - one concept per test
7. **Make tests deterministic** - same result every run
8. **Clean up resources** - use fixtures or try/finally

Example of a well-structured test:

```python
import pytest
from tests.generators import BusinessGenerator

@pytest.mark.unit
class TestScoringEngine:
    """Test lead scoring engine functionality"""
    
    @pytest.fixture
    def sample_businesses(self):
        """Generate consistent test businesses"""
        generator = BusinessGenerator(seed=42)
        return generator.generate_businesses(10)
    
    def test_scoring_calculation(self, sample_businesses):
        """Test that scoring engine calculates scores correctly"""
        # Arrange
        engine = ScoringEngine()
        business = sample_businesses[0]
        
        # Act
        score = engine.calculate_score(business)
        
        # Assert
        assert isinstance(score, float)
        assert 0 <= score <= 100
        assert score == 75.5  # Expected score for test data
    
    def test_scoring_with_missing_data(self):
        """Test scoring handles missing data gracefully"""
        engine = ScoringEngine()
        incomplete_business = Business(name="Test", website=None)
        
        score = engine.calculate_score(incomplete_business)
        
        assert score == 0  # Default for missing data
    
    @pytest.mark.slow
    def test_bulk_scoring_performance(self, sample_businesses):
        """Test scoring performance with large dataset"""
        engine = ScoringEngine()
        
        start_time = time.time()
        scores = engine.score_batch(sample_businesses * 100)  # 1000 businesses
        duration = time.time() - start_time
        
        assert len(scores) == 1000
        assert duration < 5.0  # Performance requirement
```

For questions or improvements to the test suite, please consult the comprehensive documentation in `docs/TEST_SUITE_GUIDE.md`.