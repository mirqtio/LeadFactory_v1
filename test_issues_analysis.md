# Test Issues Analysis Report

## Summary
- Total issues: 586
- Files with issues: 157

## HIGH Priority Issues

### Hardcoded Ports (114 issues)

**tests/test_docker_compose.py**
- Line 102: port=5432
- Line 123: port=6379
- Line 139: :5010/
- Line 156: :8000/
- Line 170: :9090/
- Line 181: :3000/
- Line 203: :8025/
- Line 139: localhost:5010
- Line 156: localhost:8000
- Line 170: localhost:9090

*... and 104 more issues*

### Missing Cleanup (85 issues)

**tests/test_infrastructure_cleanup.py**
- file created without cleanup

**tests/test_formula_evaluator.py**
- Setup without teardown

**tests/test_sheet_integration.py**
- Setup without teardown

**tests/test_visual_analyzer.py**
- Setup without teardown

**tests/test_ci_health_check.py**
- file created without cleanup

**tests/test_phase_0_integration.py**
- file created without cleanup

**tests/unit/test_migrations.py**
- connection created without cleanup

**tests/unit/test_impact_coefficients.py**
- file created without cleanup

**tests/unit/d10_analytics/test_d10_api.py**
- Setup without teardown

**tests/unit/design/test_token_extraction.py**
- file created without cleanup

*... and 75 more issues*

## MEDIUM Priority Issues

### Time Sleep (35 issues)

**tests/test_hot_reload.py**
- Line 54: time.sleep(0.2)
- Line 71: time.sleep(0.2)
- Line 87: time.sleep(0.05)
- Line 90: time.sleep(0.4)
- Line 298: time.sleep(1.0)

**tests/test_synchronization.py**
- Line 112: time.sleep(interval)
- Line 238: time.sleep(delay)

**tests/test_docker_compose.py**
- Line 45: time.sleep(10)
- Line 153: time.sleep(5)

**tests/unit/test_unit_metrics.py**
- Line 133: time.sleep(0.1)

*... and 25 more issues*

### Async Issues (203 issues)

**tests/test_humanloop_integration.py**
- Mixed sync and async tests
- asyncio.run() called in async function

**tests/test_synchronization.py**
- Mixed sync and async tests

**tests/test_visual_analyzer.py**
- Mixed sync and async tests
- Line 42: Async test 'test_assessment_type' missing @pytest.mark.asyncio
- Line 46: Async test 'test_calculate_cost' missing @pytest.mark.asyncio
- Line 50: Async test 'test_timeout' missing @pytest.mark.asyncio
- Line 55: Async test 'test_is_available_with_keys' missing @pytest.mark.asyncio
- Line 64: Async test 'test_is_available_with_stubs' missing @pytest.mark.asyncio
- Line 73: Async test 'test_stub_data' missing @pytest.mark.asyncio

*... and 193 more issues*

### External Dependencies (28 issues)

**tests/test_docker_compose.py**
- Line 170: httpx.get
- Line 181: httpx.get
- Line 203: httpx.get
- Line 100: psycopg2.connect

**tests/smoke/test_smoke_semrush.py**
- Line 14: os.getenv(

**tests/smoke/test_smoke_data_axle.py**
- Line 15: os.getenv(
- Line 110: os.getenv(

**tests/smoke/test_smoke_hunter.py**
- Line 15: os.getenv(

**tests/smoke/test_remote_health.py**
- Line 31: requests.get
- Line 38: requests.get

*... and 18 more issues*

## LOW Priority Issues

### Xfail Tests (54 issues)

**tests/test_marker_policy.py**
- Line 24: Issue found
- Line 109: Issue found
- Line 120: Issue found

**tests/smoke/test_smoke_screenshotone.py**
- Line 22: Issue found
- Line 115: Issue found

**tests/smoke/test_smoke_gbp.py**
- Line 21: Issue found
- Line 40: Issue found
- Line 81: Issue found

**tests/smoke/test_remote_health.py**
- Line 27: Issue found
- Line 34: Issue found

*... and 44 more issues*

### Skip Tests (42 issues)

**tests/test_marker_policy.py**
- Line 53: Issue found
- Line 93: Issue found

**tests/test_docker_compose.py**
- Line 53: Issue found
- Line 63: Issue found
- Line 74: Issue found
- Line 96: Issue found
- Line 119: Issue found
- Line 135: Issue found
- Line 149: Issue found
- Line 166: Issue found

*... and 32 more issues*

### No Timeout (25 issues)

**tests/test_yelp_purge.py**
- Test with blocking operations but no timeout

**tests/test_infrastructure_cleanup.py**
- Test with blocking operations but no timeout

**tests/test_marker_policy.py**
- Test with blocking operations but no timeout

**tests/test_synchronization.py**
- Test with blocking operations but no timeout

**tests/test_marker_enforcement.py**
- Test with blocking operations but no timeout

**tests/test_ci_health_check.py**
- Test with blocking operations but no timeout

**tests/unit/test_cost_ledger.py**
- Test with blocking operations but no timeout

**tests/unit/core/test_production_validation.py**
- Test with blocking operations but no timeout

**tests/unit/d4_enrichment/test_d4_coordinator.py**
- Test with blocking operations but no timeout

**tests/unit/d0_gateway/test_semrush_client.py**
- Test with blocking operations but no timeout

*... and 15 more issues*

## Recommendations for Fixing

1. **Fix hardcoded ports**: Use dynamic port allocation or fixtures
2. **Remove time.sleep()**: Use proper wait conditions or mocks
3. **Add cleanup**: Ensure all resources are properly cleaned up
4. **Fix async tests**: Use pytest-asyncio consistently
5. **Mock external dependencies**: Don't rely on external services
6. **Add timeouts**: Prevent tests from hanging indefinitely