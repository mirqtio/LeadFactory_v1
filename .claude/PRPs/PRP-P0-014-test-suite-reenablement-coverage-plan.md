# P0-014 - Test Suite Re-Enablement and Coverage Plan
**Priority**: P0
**Status**: Not Started
**Estimated Effort**: 3 days
**Dependencies**: P0-013

## Goal & Success Criteria

Reintroduce full KEEP test coverage, optimize test structure for CI reliability, and establish a path to restore coverage ≥70% through strategic marker usage, parallel execution optimization, and gradual coverage improvement.

### Success Criteria
- [ ] All KEEP tests either run, are `xfail`, or are conditionally skipped with markers
- [ ] CI test collection time remains under 30 seconds
- [ ] GitHub Actions workflows pass with full test suite enabled or split
- [ ] Test execution time reduced via selective markers or job matrix
- [ ] Formula evaluator test structure supports partial implementation
- [ ] Coverage baseline established with path to 70%+ coverage
- [ ] Test marker policy documented and enforced

## Context & Background

### Business Context
Phase 0.5 tooling (especially CPO tools) requires confidence in rule, config, and evaluator correctness. Rebuilding full test coverage enables safe validation of pipeline behavior.

### Technical Context
- Currently many KEEP tests are disabled or marked xfail without clear documentation
- CI test execution is slow, preventing rapid iteration
- No coverage visibility or quality gates in place
- Test organization lacks consistent marker strategy
- Parallel execution not optimized for CI environment

### Integration Points
- Builds on P0-013's green CI to systematically re-enable disabled tests
- Maintains compatibility with existing test infrastructure
- Integrates with GitHub Actions matrix strategy
- Coordinates with coverage reporting tools

## Technical Approach

### Phase 1: Test Audit and Categorization
1. Scan all KEEP test files for current xfail markers
2. Document reasons for each xfail in tracking document
3. Apply consistent markers:
   - `@pytest.mark.unit` - Fast, isolated unit tests (<1s)
   - `@pytest.mark.integration` - Tests requiring database/services (1-10s)
   - `@pytest.mark.slow` - Tests taking >10s
   - `@pytest.mark.e2e` - End-to-end pipeline tests
   - `@pytest.mark.phase_future` - Phase 0.5 functionality

### Phase 2: Parallel Execution Configuration
1. Install pytest-xdist and configure for CI environment
2. Ensure test isolation (database schemas, file system state)
3. Configure optimal worker count (2 for GitHub Actions)
4. Implement `--dist loadscope` for class-based grouping

### Phase 3: Coverage Enhancement
1. Set baseline coverage measurement
2. Configure branch coverage in .coveragerc
3. Implement gradual coverage gates:
   - Week 1: Baseline
   - Week 2: Baseline + 5%
   - Week 4: 70% target

### Phase 4: CI Optimization
1. Implement test collection caching
2. Create matrix strategy for test categories
3. Separate workflows by test speed:
   - PR builds: unit + fast integration
   - Main branch: all except slow
   - Nightly: full suite

### Phase 5: Test Maintenance
1. Create test_marker_policy.py for enforcement
2. Add pre-commit hooks for validation
3. Document standards in CONTRIBUTING.md

## Acceptance Criteria

1. All KEEP tests have appropriate markers with documented reasons
2. Test collection completes in under 30 seconds
3. CI workflows pass consistently with full test suite
4. Test execution time reduced by at least 30%
5. Coverage reporting integrated with CI
6. Test marker policy enforced via automated checks
7. Documentation updated with test organization guidelines
8. Formula evaluator tests structured for incremental implementation
9. Rollback procedure tested and documented
10. Feature flags control test execution modes

## Dependencies

- P0-013: CI/CD Pipeline Stabilization (must have green CI first)
- pytest>=7.0.0
- pytest-xdist>=3.0.0 (parallel execution)
- pytest-cov>=4.0.0 (coverage reporting)
- pytest-timeout>=2.1.0 (prevent hanging tests)
- pytest-randomly>=3.12.0 (ensure test independence)
- coverage[toml]>=7.0.0 (coverage configuration)

## Testing Strategy

### Unit Testing
- Test marker validation logic
- Coverage calculation accuracy
- Collection speed benchmarks

### Integration Testing
- Full KEEP suite execution
- Parallel execution reliability
- CI workflow integration

### Performance Testing
- Collection time benchmarks
- Execution time with various worker counts
- Coverage report generation speed

### Test Coverage Target
- 95% coverage on new test infrastructure code
- 70% overall project coverage (gradual increase)
- 100% coverage on marker validation logic

## Rollback Plan

### Conditions for Rollback
- CI execution time exceeds 15 minutes
- Test failures block development for >4 hours
- Coverage gates prevent legitimate merges

### Rollback Steps
1. Revert pytest.ini and conftest.py changes
2. Re-apply minimal test ignore patterns
3. Document failing tests in tracking issue
4. Switch to test-minimal.yml workflow
5. Create incremental fix PRs

### Data Preservation
- Keep test execution metrics
- Preserve coverage baselines
- Document failure patterns

## Validation Framework


### CI Validation (MANDATORY)
**CI Validation = Code merged to main + GitHub Actions logs verified + All errors resolved + Solid green CI run**

This means:
1. Code must be merged to the main branch (not just pushed)
2. GitHub Actions logs must be checked to confirm successful workflow completion
3. Any errors that appear during CI must be resolved
4. The final CI run must show all green checkmarks with no failures
5. This verification must be done by reviewing the actual GitHub Actions logs, not just assumed

**This is a mandatory requirement for PRP completion.**

### Pre-Implementation Validation
- [ ] Current test suite audit complete
- [ ] Marker strategy documented
- [ ] CI environment capabilities verified
- [ ] Coverage baseline measured

### Implementation Validation
- [ ] Each phase passes CI before next phase
- [ ] Performance metrics meet targets
- [ ] No regression in existing tests
- [ ] Documentation reviewed and approved

### Post-Implementation Validation
- [ ] All success criteria met
- [ ] Performance targets achieved
- [ ] Team trained on new workflow
- [ ] Monitoring dashboards operational

### Missing-Checks Validation
**Required for CI/DevOps tasks:**
- [x] Pre-commit hooks (ruff, mypy, pytest -m "not e2e")
- [x] Branch protection & required status checks
- [x] Security scanning (Dependabot, Trivy, audit tools)
- [x] Recursive CI-log triage automation
- [ ] Test execution time budgets (<10 min for PR builds)
- [ ] Coverage trend tracking and alerts
- [ ] Flaky test detection and quarantine

**Recommended:**
- [ ] Test impact analysis (run only affected tests)
- [ ] Parallel test execution optimization
- [ ] Test result caching for unchanged code
- [ ] Automated test categorization based on execution time