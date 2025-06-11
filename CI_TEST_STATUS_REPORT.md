# CI Test Status Report
Generated: 2025-06-10T21:42:50.222941

## Summary
- Total Tests: 926
- Passed: 904 (97.6%)
- Failed: 1 (0.1%)
- Skipped: 21 (2.3%)

## Failures by Module

### tests/unit/d7_storefront/test_d7_api.py (1 failures)
- [ ] test_get_session_status_success

## Failures by Type

### Other (1 failures)
- tests/unit/d7_storefront/test_d7_api.py::TestSessionStatusAPI::test_get_session_status_success

## Skipped Tests (21)
- tests/unit/d11_orchestration/test_api.py::TestPipelineAPI::test_trigger_pipeline
- tests/unit/d11_orchestration/test_api.py::TestPipelineAPI::test_get_pipeline_status
- tests/unit/d11_orchestration/test_api.py::TestPipelineAPI::test_get_pipeline_status_not_found
- tests/unit/d11_orchestration/test_api.py::TestPipelineAPI::test_get_pipeline_run
- tests/unit/d11_orchestration/test_api.py::TestPipelineAPI::test_get_pipeline_history
- tests/unit/d11_orchestration/test_api.py::TestPipelineAPI::test_get_pipeline_history_with_filters
- tests/unit/d11_orchestration/test_api.py::TestExperimentAPI::test_create_experiment
- tests/unit/d11_orchestration/test_api.py::TestExperimentAPI::test_create_experiment_duplicate_name
- tests/unit/d11_orchestration/test_api.py::TestExperimentAPI::test_get_experiment
- tests/unit/d11_orchestration/test_api.py::TestExperimentAPI::test_get_experiment_not_found
- ... and 11 more

## Fix Priority Order
1. **Async Mock Issues** - Create standard async mocking pattern
2. **FastAPI Dependencies** - Use dependency override helper
3. **Environment Variables** - Use env mock helper
4. **Test Isolation** - Add proper cleanup fixtures
5. **Timeouts** - Adjust timeouts and add retries
