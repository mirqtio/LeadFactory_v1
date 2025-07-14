# P0-015 Implementation Plan - Post-Triangulation

## Overview
Based on triangulation feedback, we're adjusting P0-015 to focus on meaningful coverage with runtime protection. Target remains 80% coverage in <5 minutes CI runtime, but with emphasis on branch coverage and critical paths.

## Key Adjustments from Triangulation

### 1. Coverage Quality Over Quantity
- **Enable branch coverage** to catch untested decision paths
- **Focus on golden paths first** in each module (happy path, retries, circuit breakers)
- **Add module minima** (60%) to prevent coverage deserts

### 2. Runtime Protection
- **Consolidate coverage runs** with `pytest -n auto --dist loadscope`
- **Use in-memory SQLite** for unit tests (orders of magnitude faster)
- **Standardize on `responses`** library for HTTP mocking
- **Feature flag coverage gates** for debugging

### 3. Knowledge Sharing
- **Create TESTING_GUIDE.md** with real examples
- **Document fixture patterns** (fixture-returns-callable)
- **Provide mock factory templates** (YelpMockFactory, SendGridMockFactory)

## Revised Timeline: 6 Days Total

### Phase 1: Infrastructure Setup (1.5 days)
**Goal**: Set up coverage tooling with branch coverage and CI optimization

**Tasks**:
1. Enable branch coverage in .coveragerc
2. Add Codecov GitHub Action with PR comments
3. Configure pytest-xdist with loadscope distribution
4. Set up feature flags for coverage gates
5. Create initial mock factory framework

**Deliverables**:
- Branch coverage enabled and working
- Codecov integration showing diffs
- CI runtime baseline established

### Phase 2: Critical Module Coverage (2 days)
**Goal**: Cover top 3-5 golden paths in low-coverage modules

**Priority Modules** (current coverage):
1. d0_gateway providers (20-30%)
2. d1_targeting (12-17%)
3. batch_runner (30-40%)

**Focus Areas per Module**:
- Happy path execution
- Error handling and retries
- Circuit breaker behavior
- Rate limiting
- Timeout handling

**Deliverables**:
- Gateway provider mock factories
- Targeting golden path tests
- Batch runner critical path coverage

### Phase 3: New Module Coverage (1 day)
**Goal**: Add tests for recently added features

**Modules**:
- lead_explorer/
- Lineage API endpoints
- Template studio

**Deliverables**:
- Lead explorer unit tests
- API endpoint tests with mocked dependencies
- Template rendering tests

### Phase 4: Optimization & Documentation (1.5 days)
**Goal**: Tune performance and share knowledge

**Tasks**:
1. Create comprehensive TESTING_GUIDE.md
2. Optimize slow tests (profile with --durations)
3. Add module coverage minima
4. Document mock factory patterns
5. Run 10x stability test on flaky tests

**Deliverables**:
- TESTING_GUIDE.md with examples
- CI runtime <5 minutes confirmed
- All flaky tests marked and isolated

## Implementation Checklist

### Pre-Implementation
- [x] Remove failing coverage boost tests
- [ ] Enable branch coverage in .coveragerc
- [ ] Add Codecov GitHub Action

### Phase 1 Checklist
- [ ] Configure pytest-xdist with loadscope
- [ ] Create base MockFactory class
- [ ] Set up feature flags for coverage
- [ ] Establish runtime monitoring

### Phase 2 Checklist
- [ ] GooglePlacesMockFactory
- [ ] SendGridMockFactory
- [ ] TargetingService golden paths
- [ ] BatchRunner critical paths

### Phase 3 Checklist
- [ ] LeadExplorer unit tests
- [ ] Lineage API tests
- [ ] Template studio tests

### Phase 4 Checklist
- [ ] TESTING_GUIDE.md complete
- [ ] Runtime optimization verified
- [ ] Module minima configured
- [ ] 10x flaky test validation

## Success Criteria (Merge Blockers)

1. **Branch coverage enabled**, fail-under 80%, module minima 60%
2. **CI runtime ≤ 7 minutes** on GitHub runner with coverage
3. **TESTING_GUIDE.md** present and reviewed
4. **Codecov PR comment** shows ≥ +22.6pp uplift from baseline 57.37%
5. **No external calls** in test suite (validated via responses)
6. **10 consecutive CI runs green** with flaky tests marked

## Risk Mitigations

### Runtime Risk
- Use in-memory SQLite for unit tests
- Parallelize with loadscope to avoid duplication
- Mock all external HTTP calls

### Coverage Gaming Risk
- Branch coverage exposes shallow tests
- Focus on golden paths not just line count
- Code review for assertion quality

### Schedule Risk
- 6-day timeline with buffer
- Daily progress checks
- Feature flags allow partial rollout

## Mock Factory Framework Design

```python
# Base factory pattern
class MockFactory:
    """Base class for provider mock factories"""
    
    @classmethod
    def create_success_response(cls, **overrides):
        """Create standard success response"""
        pass
    
    @classmethod
    def create_error_response(cls, error_type, **overrides):
        """Create standard error response"""
        pass
    
    @classmethod
    def create_timeout_scenario(cls):
        """Create timeout scenario"""
        pass

# Example implementation
class GooglePlacesMockFactory(MockFactory):
    @classmethod
    def create_success_response(cls, **overrides):
        base = {
            "results": [{
                "place_id": "test_place_123",
                "name": "Test Business",
                "formatted_address": "123 Test St, San Francisco, CA"
            }],
            "status": "OK"
        }
        base.update(overrides)
        return base
```

## Next Steps

1. Enable branch coverage configuration
2. Set up Codecov integration
3. Begin Phase 1 infrastructure work
4. Create first mock factory for GooglePlaces provider

This plan incorporates all triangulation feedback while maintaining the ambitious 80% target with proper guardrails for quality and runtime.