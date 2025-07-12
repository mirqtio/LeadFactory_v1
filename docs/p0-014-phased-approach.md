# P0-014 Phased Implementation Approach

## Current State
- CI is stable with minimal tests (P0-013 complete)
- Coverage is at ~66.72% (below 80% target)
- Need to carefully expand test coverage without breaking CI

## Phase 1: Establish Baseline (Current)
✅ **Status: Implemented**
- Run only proven stable tests
- No coverage enforcement
- Monitor CI stability

**test.yml configuration:**
- test_core.py
- test_health_endpoint.py
- test_unit_models.py
- test_health.py (smoke)

## Phase 2: Gradual Test Addition
**Goal:** Add tests incrementally while monitoring CI

1. **Wave A - Core Unit Tests**
   ```yaml
   tests/unit/d*/test_*_models.py  # All model tests
   tests/unit/test_core.py
   tests/unit/test_health_endpoint.py
   ```

2. **Wave B - Gateway Tests**
   ```yaml
   tests/unit/d0_gateway/test_base.py
   tests/unit/d0_gateway/test_factory.py
   tests/integration/test_stub_server.py
   ```

3. **Wave C - Business Logic**
   ```yaml
   tests/unit/d5_scoring/*.py
   tests/unit/d6_reports/*.py
   tests/unit/d3_assessment/*.py
   ```

## Phase 3: Enable Optimizations
Once stable with more tests:

1. **Add pytest-xdist**
   ```yaml
   pip install pytest-xdist
   pytest -n 4  # 4x parallel execution
   ```

2. **Add test markers**
   ```yaml
   pytest -m "not slow and not flaky"
   ```

3. **Enable coverage threshold**
   ```yaml
   --cov-fail-under=80
   ```

## Phase 4: Full P0-014 Implementation
Final configuration matching PRP requirements:
- All unit tests running in parallel
- Critical integration tests
- 80% coverage enforcement
- <5 minute runtime

## Validation Steps

After each phase:
1. Commit and push changes
2. Monitor GitHub Actions logs
3. If failure: `./scripts/rollback_p0_014.sh`
4. If success: proceed to next phase

## Risk Mitigation

1. **Always have rollback ready**
   ```bash
   ./scripts/rollback_p0_014.sh
   ```

2. **Test locally first**
   ```bash
   python -m pytest [new tests] -xvs
   ```

3. **Monitor CI logs for:**
   - Import errors
   - Missing dependencies
   - Database/fixture issues
   - Timeout errors

4. **Incremental commits**
   - One change per commit
   - Clear commit messages
   - Easy to revert

## Success Criteria Tracking

| Criteria | Current | Target | Status |
|----------|---------|---------|---------|
| CI Runtime | ~1 min | <5 min | ✅ |
| Unit Test Time | 30s | <2 min | ✅ |
| Integration Time | N/A | <3 min | ⏳ |
| Coverage | 66.72% | ≥80% | ❌ |
| Flake Rate | 0% | <2% | ✅ |

## Next Immediate Steps

1. **Commit current conservative test.yml**
2. **Push and verify CI passes**
3. **If passes, add next wave of tests**
4. **If fails, rollback immediately**