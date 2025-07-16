# Test Suite Developer Onboarding Guide

Welcome to the LeadFactory test suite! This guide will help you write reliable, fast tests that integrate seamlessly with our testing infrastructure.

## Quick Start

### 1. Run Your First Test

```bash
# Clone and setup
git clone <repo>
cd LeadFactory_v1_Final
pip install -r requirements.txt

# Run a single test
pytest tests/smoke/test_health.py -v

# Run all tests (parallel)
pytest -n auto

# Run tests for a specific domain
pytest -m d5_scoring
```

### 2. Validate Your Environment

```bash
# Check prerequisites
python -m core.prerequisites

# Validate test markers
pytest --validate-markers

# Quick local validation
make quick-check
```

## Writing Your First Test

### Basic Test Structure

```python
import pytest
from datetime import datetime

@pytest.mark.unit  # REQUIRED: Primary marker
class TestMyFeature:
    """Test suite for my new feature"""
    
    @pytest.fixture
    def sample_data(self):
        """Fixture providing test data"""
        return {
            "name": "Test Business",
            "created_at": datetime.now()
        }
    
    def test_feature_happy_path(self, sample_data):
        """Test normal operation"""
        # Arrange
        feature = MyFeature()
        
        # Act
        result = feature.process(sample_data)
        
        # Assert
        assert result.status == "success"
        assert result.name == sample_data["name"]
    
    def test_feature_handles_errors(self):
        """Test error handling"""
        feature = MyFeature()
        
        with pytest.raises(ValueError):
            feature.process(None)
```

### Key Requirements

1. **Every test needs a primary marker**: `@pytest.mark.unit`, `integration`, `e2e`, or `smoke`
2. **Place tests in the correct directory**: Domain-specific tests go in `tests/unit/d{N}_{domain}/`
3. **Use descriptive names**: `test_` prefix, clear description of what's being tested
4. **Write docstrings**: Explain what the test validates

## Using Test Fixtures

### Essential Fixtures

#### 1. Settings and Configuration
```python
def test_with_settings(test_settings):
    """test_settings provides validated test configuration"""
    assert test_settings.environment == "test"
    assert test_settings.use_stubs is True
```

#### 2. Database Isolation
```python
def test_database_operation(db_session, isolated_db):
    """Each test gets isolated database access"""
    # Create test data
    business = Business(name="Test")
    db_session.add(business)
    db_session.commit()
    
    # Verify
    count = db_session.query(Business).count()
    assert count == 1
```

#### 3. Temporary Files
```python
def test_file_operations(isolated_temp_dir):
    """Worker-safe temporary directory"""
    test_file = isolated_temp_dir / "data.json"
    test_file.write_text('{"key": "value"}')
    
    assert test_file.exists()
    # Automatically cleaned up after test
```

### Creating Custom Fixtures

```python
@pytest.fixture
def mock_external_api(monkeypatch):
    """Mock external API calls"""
    class MockAPI:
        def fetch_data(self, id):
            return {"id": id, "status": "mocked"}
    
    api = MockAPI()
    monkeypatch.setattr("mymodule.external_api", api)
    return api

def test_with_mocked_api(mock_external_api):
    result = process_external_data("123")
    assert result["status"] == "mocked"
```

## Avoiding Common Pitfalls

### 1. Port Conflicts ❌

```python
# BAD - Causes "Address already in use" errors
def test_server():
    server = TestServer(port=8080)  # Hardcoded port
    server.start()
```

```python
# GOOD - Dynamic port allocation
from tests.test_port_manager import get_dynamic_port

def test_server():
    port = get_dynamic_port()
    server = TestServer(port=port)
    server.start()
```

### 2. Race Conditions ❌

```python
# BAD - Unreliable timing
def test_async_operation():
    start_background_task()
    time.sleep(2)  # Hope it's done?
    assert task_completed()
```

```python
# GOOD - Deterministic synchronization
from tests.test_synchronization import wait_for_condition

def test_async_operation():
    start_background_task()
    wait_for_condition(
        lambda: task_completed(),
        timeout=5.0,
        message="Task failed to complete"
    )
```

### 3. Missing Cleanup ❌

```python
# BAD - Leaves resources hanging
def test_resource():
    client = ExpensiveClient()
    client.connect()
    assert client.is_connected()
    # Oops, never disconnected!
```

```python
# GOOD - Guaranteed cleanup
@pytest.fixture
def client():
    client = ExpensiveClient()
    client.connect()
    yield client
    client.disconnect()  # Always runs

def test_resource(client):
    assert client.is_connected()
```

### 4. Shared State ❌

```python
# BAD - Tests interfere with each other
class TestCounter:
    counter = 0  # Shared between tests!
    
    def test_increment(self):
        self.counter += 1
        assert self.counter == 1  # Fails if tests run in different order
```

```python
# GOOD - Isolated state per test
class TestCounter:
    def test_increment(self):
        counter = Counter()  # Fresh instance
        counter.increment()
        assert counter.value == 1
```

## Working with Test Data

### Using Test Generators

```python
from tests.generators import BusinessGenerator, BusinessScenario

def test_restaurant_processing():
    # Generate deterministic test data
    generator = BusinessGenerator(seed=42)
    restaurants = generator.generate_scenario_dataset(
        BusinessScenario.RESTAURANTS,
        count=10
    )
    
    # Process test data
    results = process_businesses(restaurants)
    
    # Verify
    assert len(results) == 10
    assert all(r.vertical == "restaurants" for r in results)
```

### Creating Realistic Test Scenarios

```python
from tests.generators import AssessmentGenerator, AssessmentScenario

def test_performance_tiers():
    generator = AssessmentGenerator()
    businesses = [...]  # Your test businesses
    
    # Generate different performance profiles
    high_perf = generator.generate_assessments(
        businesses[:5], 
        [AssessmentScenario.HIGH_PERFORMANCE]
    )
    low_perf = generator.generate_assessments(
        businesses[5:], 
        [AssessmentScenario.POOR_MOBILE]
    )
    
    # Test scoring differentiation
    scores_high = [score(a) for a in high_perf]
    scores_low = [score(a) for a in low_perf]
    
    assert min(scores_high) > max(scores_low)
```

## Testing Best Practices

### 1. Test Organization

```python
# Group related tests in classes
@pytest.mark.unit
class TestScoringEngine:
    """All scoring engine tests in one place"""
    
    @pytest.fixture
    def engine(self):
        """Shared engine instance"""
        return ScoringEngine()
    
    def test_basic_scoring(self, engine):
        """Test basic functionality"""
        pass
    
    def test_edge_cases(self, engine):
        """Test boundary conditions"""
        pass
    
    @pytest.mark.slow
    def test_performance(self, engine):
        """Test with large datasets"""
        pass
```

### 2. Descriptive Test Names

```python
# Bad names
def test1():
    pass

def test_scoring():
    pass

# Good names
def test_scoring_engine_returns_zero_for_missing_data():
    pass

def test_scoring_engine_handles_perfect_scores():
    pass
```

### 3. Test Independence

Each test should:
- Set up its own data
- Not depend on other tests
- Clean up after itself
- Run successfully in any order

### 4. Performance Awareness

```python
@pytest.mark.slow  # Mark tests >1 second
@pytest.mark.timeout(30)  # Fail if exceeds timeout
def test_large_dataset():
    """Process 10,000 records"""
    data = generate_large_dataset()
    
    start = time.time()
    results = process_all(data)
    duration = time.time() - start
    
    assert len(results) == 10000
    assert duration < 25  # Performance requirement
```

## Debugging Failed Tests

### 1. Run with Verbose Output

```bash
# See detailed test output
pytest -vvv tests/unit/test_failing.py

# Show print statements
pytest -s tests/unit/test_failing.py

# Stop on first failure
pytest -x tests/unit/test_failing.py
```

### 2. Use the Debugger

```bash
# Drop into debugger on failure
pytest --pdb tests/unit/test_failing.py

# Or add breakpoint in code
def test_complex_logic():
    result = complex_function()
    import pdb; pdb.set_trace()  # Debugger stops here
    assert result == expected
```

### 3. Check Test Markers

```bash
# See what markers are applied
pytest --collect-only tests/unit/test_file.py

# Validate markers are correct
pytest --validate-markers
```

### 4. Debug Parallel Execution

```bash
# Force serial execution to isolate issues
pytest -n 1 tests/unit/test_file.py

# Check for worker crashes
pytest -n auto --max-worker-restart=0

# See which worker runs which test
pytest -n auto -v
```

## CI/CD Integration

### Pre-Push Checklist

1. **Run quick validation**
   ```bash
   make quick-check
   ```

2. **Run full test suite locally**
   ```bash
   make bpci  # Runs tests in Docker like CI
   ```

3. **Check test coverage**
   ```bash
   pytest --cov=. --cov-report=term-missing
   ```

4. **Verify no new slow tests**
   ```bash
   pytest --durations=10
   ```

### Understanding CI Failures

If tests pass locally but fail in CI:

1. **Check for environment differences**
   - Missing environment variables
   - Different Python versions
   - Database state

2. **Look for timing issues**
   - Tests relying on sleep()
   - Race conditions
   - Network timeouts

3. **Review parallel execution**
   - Shared state between tests
   - Resource conflicts
   - Port collisions

## Advanced Topics

### Testing Async Code

```python
import asyncio
import pytest

@pytest.mark.asyncio
async def test_async_function():
    """Test asynchronous operations"""
    result = await async_operation()
    assert result == "expected"

@pytest.mark.asyncio
async def test_concurrent_operations():
    """Test multiple async operations"""
    tasks = [
        async_operation(i) for i in range(10)
    ]
    results = await asyncio.gather(*tasks)
    assert len(results) == 10
```

### Testing with Multiple Fixtures

```python
@pytest.mark.integration
def test_full_flow(
    db_session,
    mock_external_api,
    isolated_temp_dir,
    test_settings
):
    """Complex test using multiple fixtures"""
    # All fixtures are properly isolated
    # and cleaned up automatically
    pass
```

### Custom Markers

```python
# Define custom marker in pytest.ini
# markers =
#     requires_redis: Tests that need Redis

@pytest.mark.requires_redis
def test_caching():
    """This test needs Redis running"""
    pass

# Run only Redis tests
# pytest -m requires_redis
```

## Getting Help

### Resources

1. **Documentation**
   - `docs/TEST_SUITE_GUIDE.md` - Comprehensive guide
   - `tests/README.md` - Test structure overview
   - `docs/testing_guide.md` - Testing best practices

2. **Example Tests**
   - `tests/unit/d5_scoring/test_engine.py` - Well-structured unit tests
   - `tests/integration/test_health_integration.py` - Integration test patterns
   - `tests/e2e/test_framework.py` - End-to-end test examples

3. **Debugging Tools**
   - `scripts/detect_flaky_tests.py` - Find unstable tests
   - `scripts/profile_slow_tests.py` - Identify performance issues
   - `pytest --markers` - List all available markers

### Common Questions

**Q: How do I run just my tests?**
```bash
pytest tests/unit/my_domain/test_my_feature.py
```

**Q: Why do tests fail in parallel but pass serially?**
Check for shared state, hardcoded ports, or missing isolation.

**Q: How do I mock an external service?**
Use the stub server (automatic) or create a fixture with `monkeypatch`.

**Q: What's the difference between unit and integration tests?**
- Unit: Test single components in isolation
- Integration: Test multiple components working together

**Q: How do I test database operations?**
Use the `db_session` fixture which provides transaction rollback.

## Next Steps

1. **Write your first test** following the examples above
2. **Run the test suite** to ensure everything works
3. **Check test coverage** for your code
4. **Submit a PR** with your well-tested feature!

Remember: Good tests enable confident changes. When in doubt, add a test!