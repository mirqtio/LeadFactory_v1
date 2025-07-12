# P0-014: Path to 80% Coverage

## Current State
- **Coverage**: 21.46% (with stable test set)
- **CI Status**: All 5 workflows passing ✅
- **Runtime**: ~2-3 minutes total

## Gap Analysis
- **Current**: 21.46%
- **Target**: 80%
- **Gap**: 58.54%

## Phased Approach to 80% Coverage

### Phase 1: Model Tests (Current)
Running:
- test_core.py
- test_health_endpoint.py  
- test_unit_models.py
- test_health.py
- test_stub_server.py

Coverage: 21.46%

### Phase 2: Domain Model Tests (+~15%)
Add progressively:
```
tests/unit/d1_targeting/test_d1_models.py
tests/unit/d2_sourcing/test_d2_models.py
tests/unit/d3_assessment/test_d3_assessment_models.py
tests/unit/d4_enrichment/test_d4_enrichment_models.py
tests/unit/d5_scoring/test_d5_scoring_models.py
tests/unit/d6_reports/test_d6_reports_models.py
tests/unit/d7_storefront/test_d7_storefront_models.py
tests/unit/d8_personalization/test_d8_personalization_models.py
```

Expected: ~35-40%

### Phase 3: Gateway Tests (+~20%)
Add gateway client tests:
```
tests/unit/d0_gateway/test_base.py
tests/unit/d0_gateway/test_cache.py
tests/unit/d0_gateway/test_factory.py
tests/unit/d0_gateway/test_*_client.py (excluding problematic ones)
```

Expected: ~55-60%

### Phase 4: Core Domain Logic (+~20%)
Add business logic tests:
```
tests/unit/d3_assessment/test_*.py
tests/unit/d5_scoring/test_*.py
tests/unit/d6_reports/test_*.py
```

Expected: ~75-80%

### Phase 5: Fill Remaining Gaps
- Write new tests for uncovered modules
- Focus on high-value business logic
- Use coverage reports to identify gaps

## Implementation Strategy

1. **Test Each Phase Locally First**
   ```bash
   pytest [new_tests] -xvs
   ```

2. **Add to CI Incrementally**
   - Add 2-3 test files at a time
   - Push and verify CI passes
   - If failure, rollback immediately

3. **Monitor CI Time**
   - Keep total runtime < 5 minutes
   - Use pytest-xdist if needed

4. **Track Progress**
   - Document coverage after each addition
   - Note any problematic tests

## Risk Mitigation

1. **Always Have Rollback Ready**
   - Keep rollback script updated
   - Document last known good configuration

2. **Test Stability First**
   - Run new tests 5x locally
   - Check for flakiness
   - Fix or exclude unstable tests

3. **Gradual Enforcement**
   - Don't enforce 80% until achieved
   - Use continue-on-error for coverage
   - Only enforce when stable at 80%+

## Next Immediate Steps

1. Add d6_reports and d8_personalization model tests (already verified)
2. Push and verify CI passes
3. Check new coverage percentage
4. Continue with Phase 2 tests

This incremental approach minimizes risk while steadily working towards the 80% goal.