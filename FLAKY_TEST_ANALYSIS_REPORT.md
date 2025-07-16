# Flaky Test Analysis Report - LeadFactory

## Executive Summary

A comprehensive analysis of the LeadFactory test suite has identified significant opportunities to improve test reliability and reduce CI failures. The analysis found **586 total issues** across **157 test files** that contribute to test flakiness.

### Key Findings

1. **Hardcoded Ports (114 issues)** - The #1 cause of flaky tests
2. **Missing Cleanup (85 issues)** - Resources not properly released
3. **Async Issues (203 issues)** - Inconsistent async/await patterns
4. **Time-based Tests (35 issues)** - Tests using `time.sleep()`

## Tools Created

### 1. Flaky Test Detector (`scripts/detect_flaky_tests.py`)
- Runs tests multiple times to identify intermittent failures
- Analyzes failure patterns (port conflicts, timeouts, async issues)
- Generates detailed reports with failure rates

### 2. Test Issue Analyzer (`scripts/analyze_test_issues.py`)
- Static analysis of test code
- Identifies common anti-patterns
- Prioritizes issues by impact

### 3. Port Fix Helper (`scripts/fix_test_ports.py`)
- Identifies hardcoded ports
- Suggests dynamic port allocation
- Provides fixture examples

## Critical Issues Requiring Immediate Attention

### 1. Port 5011 Conflicts
Multiple tests use hardcoded port 5011 for the stub server, causing conflicts when tests run in parallel:
- `tests/conftest.py` - Stub server fixture
- `tests/unit/core/test_config.py` - Configuration tests
- Various gateway tests expecting stub server on 5011

**Solution**: Implement dynamic port allocation in stub server fixture

### 2. Docker Compose Tests
The `test_docker_compose.py` file has 12 hardcoded ports:
- PostgreSQL: 5432
- Redis: 6379
- Application: 8000
- Prometheus: 9090
- Grafana: 3000
- MailHog: 8025

**Solution**: Use Docker's dynamic port mapping or skip in CI

### 3. Async Test Decorators
203 async tests are missing proper decorators or mixing sync/async patterns:
- `test_visual_analyzer.py` - 6 tests missing `@pytest.mark.asyncio`
- `test_humanloop_integration.py` - Calls `asyncio.run()` in async context
- Multiple files mixing sync and async test methods

**Solution**: Add missing decorators and standardize async test patterns

## Prioritized Action Plan

### Phase 1: High Impact Fixes (1-2 days)
1. **Fix Stub Server Port Conflicts**
   ```python
   @pytest.fixture
   def stub_server():
       port = get_free_port()
       os.environ["STUB_BASE_URL"] = f"http://localhost:{port}"
       # ... rest of fixture
   ```

2. **Add Missing Async Decorators**
   - Run: `pytest --collect-only | grep "async def test_"`
   - Add `@pytest.mark.asyncio` to all async tests

3. **Fix Docker Compose Tests**
   - Mark with `@pytest.mark.integration` 
   - Skip in regular CI runs
   - Run separately with proper teardown

### Phase 2: Resource Cleanup (2-3 days)
1. **Add Fixture Cleanup**
   - Database connections
   - Thread joins
   - File handles
   - Mock patches

2. **Implement Test Isolation**
   ```python
   @pytest.fixture(autouse=True)
   def cleanup():
       yield
       # Reset environment
       # Clear caches
       # Close connections
   ```

### Phase 3: Time-based Test Fixes (3-4 days)
1. **Replace time.sleep()**
   - Use `pytest-timeout` for test timeouts
   - Mock time for time-dependent logic
   - Use proper wait conditions

2. **Add Test Timeouts**
   ```python
   @pytest.mark.timeout(30)
   def test_with_network_calls():
       # Test will fail if takes > 30 seconds
   ```

## Recommended CI Configuration

```yaml
# .github/workflows/test.yml
test:
  runs-on: ubuntu-latest
  strategy:
    matrix:
      group: [unit, integration, smoke]
  steps:
    - name: Run Tests
      run: |
        pytest -v \
          --timeout=300 \
          --timeout-method=thread \
          -m "${{ matrix.group }}" \
          --maxfail=3 \
          --reruns=2 \
          --reruns-delay=5
```

## Monitoring and Prevention

1. **Add Flaky Test Detection to CI**
   ```yaml
   - name: Detect Flaky Tests
     if: github.event_name == 'schedule'
     run: python scripts/detect_flaky_tests.py -n 5
   ```

2. **Regular Analysis**
   - Weekly run of test issue analyzer
   - Track flaky test metrics
   - Require fixes before new features

3. **Developer Guidelines**
   - No hardcoded ports
   - Always use fixtures for resources
   - Proper async test patterns
   - Mock external dependencies

## Expected Outcomes

After implementing these fixes:
- **50-70% reduction** in intermittent test failures
- **Faster CI runs** due to parallel execution
- **Better developer experience** with reliable tests
- **Reduced debugging time** for CI failures

## Next Steps

1. Create tickets for each high-priority fix
2. Assign ownership for each test category
3. Set up monitoring dashboard for test reliability
4. Schedule weekly flaky test review
5. Update testing guidelines documentation

---

*Generated: 2025-07-16*
*Total Issues: 586 | Files Affected: 157 | Estimated Fix Time: 1-2 weeks*