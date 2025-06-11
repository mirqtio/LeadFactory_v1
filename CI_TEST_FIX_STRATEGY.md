# CI Test Fix Strategy - Comprehensive Resolution Plan

## Current Situation
After implementing 100 tasks and closing PRD gaps, the test suite has become fragmented with various failures across multiple modules. We need a systematic approach to restore full CI reliability.

## Success Criteria
- ✅ All tests pass locally without skipping
- ✅ All tests pass in Docker environment
- ✅ CI shows "conclusion": "success" on GitHub
- ✅ No tests are skipped or disabled
- ✅ No test effectiveness is reduced

## Root Causes Identified
1. **Async Mocking Issues**: Gateway facade methods require proper async mocking
2. **FastAPI Dependency Injection**: Tests need proper dependency override for FastAPI endpoints
3. **Environment Variables**: Live mode configs require mocked environment variables
4. **Test Isolation**: Tests sharing state causing cascading failures
5. **Docker Compose Timeouts**: Integration tests timing out in CI environment

## Strategic Fix Plan

### Phase 1: Inventory All Failures (1-2 hours)
1. Run full test suite and document ALL failures
2. Categorize failures by type:
   - Async/await issues
   - Mock configuration
   - Environment dependencies
   - Test isolation
   - Timeout issues
3. Create priority order based on dependencies

### Phase 2: Fix Core Infrastructure (2-3 hours)
1. **Gateway Mock Helper**
   ```python
   # Create reusable async mock helper
   def create_async_mock(return_value):
       async def mock_coro(*args, **kwargs):
           return return_value
       return mock_coro
   ```

2. **FastAPI Test Helper**
   ```python
   # Create dependency override helper
   def override_dependency(app, dependency, mock_value):
       app.dependency_overrides[dependency] = lambda: mock_value
       return mock_value
   ```

3. **Environment Mock Helper**
   ```python
   # Create environment variable context manager
   @contextmanager
   def mock_env_vars(**kwargs):
       with patch.dict("os.environ", kwargs):
           yield
   ```

### Phase 3: Systematic Module Fixes (4-6 hours)
Fix modules in dependency order:

1. **D0 Gateway** (Foundation)
   - Fix all async gateway method mocks
   - Ensure proper error handling
   - Test retry logic

2. **D7 Storefront** (Current focus)
   - Fix remaining API test dependency overrides
   - Fix Stripe client async mocks
   - Ensure webhook handling works

3. **D4 Enrichment** (Data pipeline)
   - Fix test isolation issues
   - Add proper cleanup between tests
   - Fix decimal serialization

4. **D3 Assessment** (Core logic)
   - Fix cache test timing
   - Fix metrics tracking
   - Fix LLM mock responses

5. **D11 Orchestration** (Integration)
   - Fix database table creation
   - Fix async task handling
   - Fix pipeline coordination

### Phase 4: Integration Test Fixes (2-3 hours)
1. **Docker Compose Tests**
   - Increase timeouts appropriately
   - Add proper health checks
   - Ensure service dependencies

2. **E2E Tests**
   - Fix test data setup
   - Ensure proper teardown
   - Add retry logic for flaky tests

### Phase 5: CI Verification (1-2 hours)
1. Run full test suite locally
2. Run full test suite in Docker
3. Push to GitHub and verify CI
4. Monitor for any flaky tests

## Execution Tracking

### Current Progress
- [x] Identified async mocking issues in D7
- [x] Fixed some D7 checkout tests
- [ ] Fix remaining D7 API tests
- [ ] Create reusable test helpers
- [ ] Fix D0 gateway tests
- [ ] Fix D4 enrichment tests
- [ ] Fix D3 assessment tests
- [ ] Fix D11 orchestration tests
- [ ] Fix Docker compose tests
- [ ] Verify full CI pass

### Test Categories to Fix
1. **Async Mock Issues** (~40 tests)
   - D7 Storefront API tests
   - D0 Gateway client tests
   - D3 Assessment async operations

2. **FastAPI Dependency Issues** (~20 tests)
   - All API endpoint tests
   - Webhook handlers
   - Background task tests

3. **Environment Variable Issues** (~15 tests)
   - Stripe live mode tests
   - Production config tests
   - API key validation tests

4. **Test Isolation Issues** (~10 tests)
   - D4 Enrichment database tests
   - D11 Orchestration state tests
   - Cache-dependent tests

5. **Timeout Issues** (~5 tests)
   - Docker Compose startup
   - Integration test timeouts
   - E2E flow tests

## Implementation Guidelines

### DO:
- Fix root causes, not symptoms
- Create reusable solutions
- Maintain test effectiveness
- Document complex fixes
- Test fixes in isolation first

### DON'T:
- Skip tests
- Reduce test coverage
- Add sleep() for timing issues
- Ignore flaky tests
- Make tests "pass" without fixing issues

## Next Immediate Actions
1. Create test helper module with reusable mocking utilities
2. Fix remaining D7 API tests using dependency override pattern
3. Run full D7 test suite to verify complete fix
4. Move to D0 gateway async mocking issues
5. Continue systematically through all modules

## Monitoring & Validation
After each module fix:
1. Run module tests locally
2. Run module tests in Docker
3. Run dependent module tests
4. Commit with descriptive message
5. Verify CI status on GitHub

## Long-term Improvements
1. Add pre-commit hooks for test validation
2. Create test best practices documentation
3. Add CI test result monitoring
4. Implement test performance tracking
5. Create automated test health dashboard