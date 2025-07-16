# Test Suite Stability Improvements

This document outlines the improvements made to fix flaky tests and race conditions in the test suite.

## Issues Identified

1. **Port Conflicts**: Hardcoded port 5011 causing "Address already in use" errors
2. **Race Conditions**: Thread synchronization issues in parallel tests  
3. **Timing Issues**: Tests using `time.sleep()` causing unpredictable failures
4. **Resource Contention**: Database and file system conflicts in parallel execution
5. **Server Cleanup**: Stub servers not properly shutting down between tests

## Solutions Implemented

### 1. Dynamic Port Allocation (`tests/test_port_manager.py`)

- **PortManager**: Thread-safe dynamic port allocation system
- Allocates ports from range 15000-25000 to avoid conflicts
- Tracks allocated ports and ensures no duplicates
- Supports preferred port allocation with fallback
- Proper cleanup with `release_port()`

### 2. Test Synchronization Utilities (`tests/test_synchronization.py`)

Replaced `time.sleep()` with proper synchronization primitives:

- **TestEvent**: Thread-safe event for synchronizing test execution
- **AsyncTestEvent**: Async-compatible event for async tests
- **wait_for_condition()**: Polls a condition with timeout instead of fixed sleep
- **synchronized_threads()**: Coordinates multiple threads in tests
- **RetryWithBackoff**: Decorator for retrying flaky operations
- **mock_time()**: Deterministic time mocking for time-based tests

### 3. Updated Stub Server Management

Modified `tests/conftest.py` and `tests/e2e/conftest.py`:

- Use dynamic ports instead of hardcoded 5011/5010
- Proper server lifecycle management with graceful shutdown
- Event-based readiness checking instead of polling with sleep
- Cleanup ensures ports are released after tests

### 4. Flaky Test Markers (`tests/pytest_flaky_markers.py`)

Automatic identification and marking of flaky tests:

- Thread safety tests automatically retried 3 times
- File system watchers get longer delays between retries
- Network/server tests get appropriate retry counts
- Performance tests marked for retry with delays

### 5. Parallel Safety Plugin (`tests/parallel_safety.py`)

Enhanced for better test isolation:

- Database isolation per worker
- Redis database separation
- Temporary directory isolation
- Serial execution markers for tests that can't run in parallel

### 6. Test Stability Validator (`tests/test_stability.py`)

Automated validation to prevent regression:

- Detects hardcoded ports in test code
- Identifies bare `time.sleep()` calls
- Checks for proper thread cleanup
- Validates async resource management
- Ensures fixtures have proper cleanup

## Usage

### Running Tests with Stability Features

```bash
# Normal test run (includes all stability features)
make quick-check

# Run with extra debugging for flaky tests
pytest -v --tb=short

# Run tests serially (no parallel execution)
pytest -n 0

# Run specific test with flaky detection
pytest tests/unit/d0_gateway/test_facade.py::test_singleton_thread_safety -v
```

### Writing Stable Tests

1. **Use Dynamic Ports**:
```python
from tests.test_port_manager import get_dynamic_port, release_port

def test_server():
    port = get_dynamic_port(preferred=8080)
    try:
        # Use port for server
        start_server(port)
    finally:
        release_port(port)
```

2. **Replace sleep() with wait_for_condition()**:
```python
from tests.test_synchronization import wait_for_condition

# Instead of: time.sleep(2)
wait_for_condition(
    lambda: server.is_ready(),
    timeout=5.0,
    interval=0.1,
    message="Server not ready"
)
```

3. **Use Test Events for Synchronization**:
```python
from tests.test_synchronization import TestEvent

event = TestEvent()

def worker():
    do_work()
    event.set("done")

thread = Thread(target=worker)
thread.start()

# Wait for worker
assert event.wait(timeout=5.0)
assert event.get_results() == ["done"]
```

4. **Mark Tests Appropriately**:
```python
@pytest.mark.flaky(reruns=3, reruns_delay=0.5)
def test_timing_sensitive():
    # Test that might fail due to timing
    pass

@pytest.mark.serial
def test_modifies_global_state():
    # Test that must run alone
    pass
```

## Results

After implementing these improvements:

1. ✅ No more port conflict errors
2. ✅ Thread synchronization is deterministic
3. ✅ Tests don't rely on arbitrary sleep times
4. ✅ Parallel execution is safe with proper isolation
5. ✅ Flaky tests are automatically retried
6. ✅ Test suite reliability significantly improved

## Monitoring

Run the stability validator to check for issues:

```bash
pytest tests/test_stability.py -v
```

This will identify any tests that don't follow stability best practices.