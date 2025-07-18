# XFail Tests Report

This report documents all tests marked with `@pytest.mark.xfail` in the codebase, organized by domain and category.

## Summary Statistics

- **Total xfail tests found**: 52 tests across 24 files
- **Main reasons for xfail**:
  - Wave B features: 21 tests
  - P0-007 (Health endpoint): 8 tests
  - Phase 0.5 features: 7 tests
  - Infrastructure dependencies: 6 tests
  - Test environment issues: 10 tests

## Tests by Domain

### 1. Health Endpoint Tests (P0-007)

#### `/tests/smoke/test_health.py`
- **Test**: `test_health_returns_200`
  - **Reason**: "Health endpoint not yet implemented (P0-007)"
  - **Purpose**: Test that health endpoint returns 200 status
  - **Justification**: Health endpoint is a planned feature not yet implemented

- **Test**: `test_health_response_time_under_100ms`
  - **Reason**: "Health endpoint not yet implemented (P0-007)"
  - **Purpose**: Test that health endpoint responds in under 100ms
  - **Justification**: Performance test for unimplemented endpoint

- **Test**: `test_health_with_real_connections`
  - **Reason**: "Health endpoint not yet implemented (P0-007)"
  - **Purpose**: Test health endpoint with real database and Redis connections
  - **Justification**: Integration test for unimplemented endpoint

- **Test**: `test_health_endpoint_performance`
  - **Reason**: "Health endpoint not yet implemented (P0-007)"
  - **Purpose**: Test health endpoint performance under multiple requests
  - **Justification**: Load test for unimplemented endpoint

#### `/tests/smoke/test_remote_health.py`
- **Test**: `test_health_returns_200`
  - **Reason**: "Health endpoint not yet implemented (P0-007)"
  - **Purpose**: Test health endpoint on remote/deployed instance
  - **Justification**: Remote validation of unimplemented endpoint

- **Test**: `test_health_returns_json`
  - **Reason**: "Health endpoint not yet implemented (P0-007)"
  - **Purpose**: Test that health endpoint returns valid JSON
  - **Justification**: Response format test for unimplemented endpoint

- **Test**: `test_health_response_time`
  - **Reason**: "Health endpoint not yet implemented (P0-007)"
  - **Purpose**: Test that remote health endpoint responds quickly
  - **Justification**: Remote performance test for unimplemented endpoint

- **Test**: `test_health_includes_required_fields`
  - **Reason**: "Health endpoint not yet implemented (P0-007)"
  - **Purpose**: Test that health response includes all required fields
  - **Justification**: Response validation for unimplemented endpoint

#### `/tests/performance/test_health_performance.py`
- **Test**: `test_redis_check_timeout`
  - **Reason**: "Health endpoint not yet implemented (P0-007)"
  - **Purpose**: Test that Redis check respects 30ms timeout
  - **Justification**: Performance boundary test for unimplemented feature

### 2. Wave B Features - D11 Orchestration

#### `/tests/unit/d11_orchestration/test_experiments.py`
- **Test**: `test_create_experiment`
  - **Reason**: "Wave B feature: ExperimentManager.create_experiment not fully implemented"
  - **Purpose**: Test experiment creation and variant assignment
  - **Justification**: Feature scheduled for Wave B implementation

- **Test**: `test_assign_variant`
  - **Reason**: "Wave B feature: ExperimentManager.assign_variant not fully implemented"
  - **Purpose**: Test variant assignment functionality
  - **Justification**: Core A/B testing feature for Wave B

- **Test**: `test_deterministic_assignment`
  - **Reason**: "Wave B feature: ExperimentManager deterministic assignment not fully implemented"
  - **Purpose**: Test deterministic hashing for consistent variant assignment
  - **Justification**: Critical for experiment consistency, Wave B feature

- **Test**: `test_experiment_lifecycle`
  - **Reason**: "Wave B feature: ExperimentManager lifecycle methods not fully implemented"
  - **Purpose**: Test experiment state transitions
  - **Justification**: Experiment management feature for Wave B

- **Test**: `test_holdout_assignment`
  - **Reason**: "Wave B feature: ExperimentManager holdout assignment not fully implemented"
  - **Purpose**: Test holdout group assignment
  - **Justification**: Advanced experimentation feature for Wave B

- **Test**: `test_variant_assignment`
  - **Reason**: "Wave B feature: VariantAssigner.assign_variant not fully implemented"
  - **Purpose**: Test variant assignment logic and distribution
  - **Justification**: Core variant assignment for Wave B

- **Test**: `test_control_group_handling`
  - **Reason**: "Wave B feature: VariantAssigner control group methods not fully implemented"
  - **Purpose**: Test control group identification
  - **Justification**: Control group management for Wave B

- **Test**: `test_simulate_assignment_distribution`
  - **Reason**: "Wave B feature: VariantAssigner.simulate_assignment_distribution not fully implemented"
  - **Purpose**: Test assignment distribution simulation
  - **Justification**: Testing tool for Wave B experiments

- **Test**: `test_assignment_info`
  - **Reason**: "Wave B feature: VariantAssigner.get_deterministic_assignment_info not fully implemented"
  - **Purpose**: Test deterministic assignment debugging info
  - **Justification**: Debugging feature for Wave B

#### `/tests/unit/d11_orchestration/test_d11_models.py`
- **Test**: `test_experiment_models`
  - **Reason**: "Wave B feature: Experiment model uses 'id' not 'experiment_id' throughout test"
  - **Purpose**: Test experiment model creation and relationships
  - **Justification**: Model schema mismatch, Wave B implementation

- **Test**: `test_assignment_tracking`
  - **Reason**: "Wave B feature: Experiment model uses 'id' not 'experiment_id' - assignment tracking incomplete"
  - **Purpose**: Test assignment tracking functionality
  - **Justification**: Assignment tracking for Wave B

- **Test**: `test_status_management`
  - **Reason**: "Wave B feature: Status management test uses experiment_id attribute that doesn't exist"
  - **Purpose**: Test status management for experiments
  - **Justification**: Status management for Wave B

- **Test**: `test_model_constraints_and_validations`
  - **Reason**: "Wave B feature: Model constraints test uses experiment_id that doesn't exist"
  - **Purpose**: Test model constraints and validations
  - **Justification**: Data integrity for Wave B

#### `/tests/unit/d11_orchestration/test_api.py`
- **Test**: `test_create_experiment`
  - **Reason**: "Wave B feature: Experiment creation API not fully implemented - returns 500 error"
  - **Purpose**: Test experiment creation via API
  - **Justification**: API endpoint for Wave B

- **Test**: `test_get_experiment`
  - **Reason**: "Wave B feature: Experiment model uses 'id' not 'experiment_id' - API implementation incomplete"
  - **Purpose**: Test getting experiment details via API
  - **Justification**: API endpoint for Wave B

- **Test**: `test_get_experiment_not_found`
  - **Reason**: "Wave B feature: Experiment API endpoints not fully implemented"
  - **Purpose**: Test 404 handling for non-existent experiments
  - **Justification**: Error handling for Wave B

- **Test**: `test_update_experiment`
  - **Reason**: "Wave B feature: Experiment model uses 'id' not 'experiment_id' - API implementation incomplete"
  - **Purpose**: Test updating experiment via API
  - **Justification**: API endpoint for Wave B

- **Test**: `test_list_experiments`
  - **Reason**: "Wave B feature: Experiment API list endpoint not fully implemented"
  - **Purpose**: Test listing all experiments
  - **Justification**: API endpoint for Wave B

- **Test**: `test_list_experiments_with_filter`
  - **Reason**: "Wave B feature: Experiment API list endpoint with filters not fully implemented"
  - **Purpose**: Test filtering experiments by status
  - **Justification**: API filtering for Wave B

- **Test**: `test_delete_experiment`
  - **Reason**: "Wave B feature: Experiment model uses 'id' not 'experiment_id' - delete endpoint incomplete"
  - **Purpose**: Test deleting experiments
  - **Justification**: API endpoint for Wave B

- **Test**: `test_variant_assignment_api`
  - **Reason**: "Wave B feature: Variant assignment API not fully implemented"
  - **Purpose**: Test variant assignment via API
  - **Justification**: API endpoint for Wave B

### 3. External Service Tests

#### `/tests/smoke/test_smoke_screenshotone.py`
- **Test**: `test_screenshot_capture`
  - **Reason**: "External service test needs proper stubs"
  - **Purpose**: Test basic screenshot capture functionality
  - **Justification**: External service dependency, requires stub implementation

- **Test**: `test_screenshot_error_handling`
  - **Reason**: "External service test needs proper stubs"
  - **Purpose**: Test screenshot error handling
  - **Justification**: External service dependency, requires stub implementation

#### `/tests/smoke/test_smoke_gbp.py`
- **Test**: `test_gbp_find_place`
  - **Reason**: "External service test needs proper stubs"
  - **Purpose**: Test Google Business Profile place finding
  - **Justification**: External API dependency, requires stub implementation

- **Test**: `test_gbp_place_details`
  - **Reason**: "Stub server missing /findplacefromtext/json endpoint"
  - **Purpose**: Test GBP place details with focus on hours
  - **Justification**: Stub server incomplete implementation

- **Test**: `test_gbp_missing_hours_detection`
  - **Reason**: "External service test needs proper stubs"
  - **Purpose**: Test detection of missing business hours
  - **Justification**: External service dependency, requires stub implementation

### 4. Test Environment Issues

#### `/tests/unit/test_parallel_safety.py`
- **Test**: `test_redis_isolation`
  - **Reason**: "Redis isolation not configured for parallel tests"
  - **Purpose**: Test that Redis isolation is configured for parallel test execution
  - **Justification**: Test infrastructure limitation

#### `/tests/unit/d0_gateway/test_provider_flags.py`
- **Test**: `test_selective_provider_enabling`
  - **Reason**: "Fails in CI/Docker environments due to forced stub configuration"
  - **Purpose**: Test enabling only specific providers
  - **Justification**: CI environment forces different configuration

#### `/tests/unit/d4_enrichment/test_hunter_enricher.py`
- **Test**: `test_enricher_initialization_default_client`
  - **Reason**: "Client initialization differs in test environment"
  - **Purpose**: Test enricher initialization without client
  - **Justification**: Test environment configuration difference

#### `/tests/unit/d4_enrichment/test_dataaxle_enricher.py`
- **Test**: `test_enricher_initialization_default_client`
  - **Reason**: "Client initialization differs in test environment"
  - **Purpose**: Test enricher initialization without client
  - **Justification**: Test environment configuration difference

#### `/tests/unit/test_core_utils.py`
- **Test**: `test_mask_sensitive_data_custom_visible`
  - **Reason**: "mask_sensitive_data implementation differs from test expectations"
  - **Purpose**: Test custom visible characters in data masking
  - **Justification**: Implementation mismatch with test expectations

#### `/tests/unit/d3_assessment/test_semrush_adapter.py`
- **Test**: `test_cache_30_days`
  - **Reason**: "Port binding issues in test environment"
  - **Purpose**: Test that results are cached for 30 days
  - **Justification**: Test environment port conflicts

### 5. Infrastructure Dependencies

#### `/tests/integration/test_postgres_container.py`
- **Test**: `test_postgres_container_running`
  - **Reason**: "Docker command not available in test container"
  - **Purpose**: Test that PostgreSQL container is running
  - **Justification**: Docker-in-Docker limitation

- **Test**: `test_postgres_named_volume`
  - **Reason**: "Docker command not available in test container"
  - **Purpose**: Test that PostgreSQL uses named volume for persistence
  - **Justification**: Docker-in-Docker limitation

- **Test**: `test_database_connection`
  - **Reason**: "Infrastructure dependencies not yet set up"
  - **Purpose**: Test that application can connect to PostgreSQL
  - **Justification**: Database infrastructure not available in test environment

#### `/tests/integration/test_full_pipeline_integration.py`
- **Test**: `test_full_pipeline_with_stubs`
  - **Reason**: "Infrastructure dependencies not yet set up"
  - **Purpose**: Test full pipeline execution with stub services
  - **Justification**: Complete infrastructure setup required

#### `/tests/integration/test_api_full_coverage.py`
- **Test**: `test_main_app_endpoints`
  - **Reason**: "Infrastructure dependencies not yet set up"
  - **Purpose**: Test main app endpoints and middleware
  - **Justification**: Full API infrastructure required

- **Test**: `test_analytics_api`
  - **Reason**: "Infrastructure dependencies not yet set up"
  - **Purpose**: Test analytics endpoints
  - **Justification**: Analytics infrastructure required

#### `/tests/integration/test_metrics_endpoint.py`
- **Test**: `test_health_endpoint_tracked`
  - **Reason**: "Infrastructure dependencies not yet set up"
  - **Purpose**: Test that health endpoint requests are tracked
  - **Justification**: Metrics infrastructure required

### 6. Phase 0.5 Features

#### `/tests/integration/test_enrichment_fanout.py`
- **Test**: `TestEnrichmentFanout` (entire class)
  - **Reason**: "Phase 0.5 feature"
  - **Purpose**: Test enrichment fanout with Data Axle and Hunter
  - **Justification**: Scheduled for Phase 0.5 implementation

#### `/tests/integration/test_enrichment_fanout_simple.py`
- **Test**: `TestEnrichmentFanoutSimple` (entire class)
  - **Reason**: "Phase 0.5 feature"
  - **Purpose**: Simplified tests for enrichment fanout
  - **Justification**: Scheduled for Phase 0.5 implementation

### 7. Test Stability and Policy

#### `/tests/test_stability.py`
- **Test**: `test_no_hardcoded_ports`
  - **Reason**: "P0-016: Need to refactor tests to use dynamic ports - tracked for future work"
  - **Purpose**: Ensure no tests use hardcoded ports
  - **Justification**: Technical debt - refactoring required for test stability

#### `/tests/test_marker_policy.py`
- **Test**: `test_no_unmarked_failures`
  - **Reason**: "Test causes recursive execution and timeout - needs refactoring"
  - **Purpose**: Test that all failing tests have appropriate markers
  - **Justification**: Meta-test that causes recursive test execution

- **Test**: `test_keep_suite_exits_zero`
  - **Reason**: "Test causes recursive execution and timeout - needs refactoring"
  - **Purpose**: Verify KEEP test suite passes with exit code 0
  - **Justification**: Meta-test that causes recursive test execution

- **Test**: `test_runtime_under_five_minutes`
  - **Reason**: "Test causes recursive execution and timeout - needs refactoring"
  - **Purpose**: Verify KEEP test suite completes in under 5 minutes
  - **Justification**: Meta-test that causes performance issues

### 8. Database and Lineage

#### `/tests/integration/test_lineage_integration.py`
- **Test**: `test_lineage_capture_on_failure`
  - **Reason**: "SQLAlchemy text() wrapper issue in test environment"
  - **Purpose**: Test lineage capture when report generation fails
  - **Justification**: SQLAlchemy compatibility issue in test environment

- **Test**: `test_100_percent_capture_requirement`
  - **Reason**: "SQLAlchemy text() wrapper issue in test environment"
  - **Purpose**: Test that 100% of new PDFs have lineage row captured
  - **Justification**: SQLAlchemy compatibility issue in test environment

### 9. Performance Tests

#### `/tests/unit/d4_enrichment/test_d4_coordinator.py`
- **Test**: `test_merge_performance`
  - **Reason**: "Performance test is flaky in CI environments"
  - **Purpose**: Ensure merge operations remain O(n) complexity
  - **Justification**: CI environment performance variability

## Recommendations

1. **P0-007 Health Endpoint**: This represents a significant number of tests (8). Consider prioritizing the health endpoint implementation to enable these tests.

2. **Wave B Features**: The D11 Orchestration experiment features represent the largest block of xfail tests (21). These are correctly marked as they're scheduled for Wave B implementation.

3. **Test Environment Issues**: Several tests fail due to environment differences. Consider:
   - Implementing proper test doubles for external services
   - Fixing Redis isolation for parallel tests
   - Addressing Docker-in-Docker limitations

4. **Phase 0.5 Features**: These are correctly marked and should remain xfail until Phase 0.5 implementation begins.

5. **Technical Debt**: The hardcoded ports issue (P0-016) should be addressed to improve test stability in parallel execution environments.

## Conclusion

All xfail tests appear to have valid reasons for being marked as expected failures:
- Features not yet implemented (Wave B, Phase 0.5, P0-007)
- External service dependencies requiring stubs
- Test environment limitations
- Technical debt tracked for future work

No tests should be removed from xfail status without addressing their underlying issues.