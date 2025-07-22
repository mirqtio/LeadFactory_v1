# PRP-1059 - Lua Promotion Script

**Priority**: P0
**Status**: Not Started
**Estimated Effort**: 2 days
**Dependencies**: PRP-1058

## Goal & Success Criteria

Implement atomic Redis Lua referee script for queue promotion with evidence validation to enable reliable PRP state transitions with mandatory evidence enforcement and performance targets of ≤50µs per call @ 1K RPS.

**Specific Goal**: Create `redis/promote.lua` script with SHA caching for atomic PRP queue promotion operations with comprehensive evidence schema validation.

## Context & Background

- **Business value**: Ensures reliable PRP state transitions with atomic operations, preventing data corruption and lost work that can occur with multi-command operations
- **Integration**: Builds on PRP-1058 (Redis Queue Broker) to provide atomic promotion operations between queue states with evidence validation
- **Problems solved**: 
  - Eliminates race conditions in PRP state transitions that can occur with separate Redis commands
  - Enforces evidence schema validation atomically with state changes
  - Provides sub-100µs performance for high-throughput queue operations
  - Prevents partial state updates that can leave PRPs in inconsistent states

**Current State**: Redis queue infrastructure from PRP-1058 provides basic queue operations but lacks atomic promotion with evidence validation.

**Research Context**: Based on Redis Lua scripting best practices, EVALSHA performance optimization patterns, and reliable queue promotion techniques from Redis community and official documentation.

## Technical Approach

### Implementation Strategy

**Phase 1: Script Design**
- Analyze existing `d0_gateway/lua_scripts/rate_limit.lua` for patterns
- Design evidence schema structure using Redis hashes at `cfg:evidence_schema`
- Implement atomic promotion logic with BRPOPLPUSH and evidence validation
- Include comprehensive error handling with assert() for validation failures

**Phase 2: Script Loader Implementation**
- Create `redis/script_loader.py` with SHA caching at boot
- Implement EVALSHA with automatic EVAL fallback for NOSCRIPT errors
- Handle Redis connection management using existing patterns
- Include script reloading capabilities for development

**Phase 3: Integration and Testing**
- Unit tests for Lua script logic using Redis test instance
- Integration tests with queue broker operations
- Performance benchmarking to verify ≤50µs target @ 1K RPS
- Error handling tests for invalid evidence and transitions

### Integration Points

- `redis/promote.lua` - Main atomic promotion script with evidence validation
- `redis/script_loader.py` - Script management with SHA caching and EVALSHA fallback  
- `infra/redis_queue.py` - Integration with queue broker from PRP-1058
- `core/config.py` - Redis configuration and evidence schema definitions
- Existing `d0_gateway/cache.py` patterns for Redis connections

### Code Structure

```
redis/
├── promote.lua                 # Atomic promotion script
├── __init__.py                # Redis Lua script manager
└── script_loader.py           # SHA caching and EVALSHA fallback

tests/unit/redis/
├── test_promotion_script.py    # Unit tests for Lua script
└── test_script_loader.py      # Script loading and caching tests

tests/integration/
└── test_redis_promotion.py    # Integration tests with actual Redis
```

### Error Handling Strategy

- **Invalid Evidence**: Assert validation with detailed error messages
- **Invalid Transitions**: Lua error() with specific transition requirements
- **NOSCRIPT Errors**: Automatic fallback from EVALSHA to EVAL
- **Redis Connection**: Graceful degradation with connection retry logic
- **Performance Degradation**: Monitoring and alerting for response time SLA violations

## Acceptance Criteria

1. Lua script performs atomic queue promotion with evidence validation in single Redis transaction
2. Script cached at application boot using SCRIPT LOAD with SHA1 hash stored
3. Evidence schema validation enforced per transition type (pending→development, development→validation, etc.)
4. Performance target: ≤50µs per call @ 1K RPS sustained load achieved
5. EVALSHA with automatic EVAL fallback on NOSCRIPT errors implemented
6. Comprehensive error handling for invalid transitions and missing evidence
7. Coverage ≥ 80% on tests including atomic transaction verification
8. Integration with existing Redis infrastructure (d0_gateway patterns) completed

## Dependencies

- **PRP-1058 (Redis Queue Broker)**: Required queue infrastructure and Redis connection patterns
- **Redis Server**: Version 6.0+ with Lua scripting support
- **Python redis library**: Version 4.5.0+ with async support for EVALSHA operations  
- **pytest-benchmark**: For performance testing and regression detection

## Testing Strategy

**Unit Tests**: Lua script logic verification with mock Redis instances
- Test evidence validation logic for all transition types
- Verify EVALSHA fallback mechanisms with NOSCRIPT simulation
- Validate error handling for malformed evidence data

**Integration Tests**: End-to-end promotion workflows with real Redis
- Test complete promotion workflows between queue states
- Verify atomic transaction behavior under concurrent load
- Test integration with PRP-1058 queue broker infrastructure

**Performance Tests**: Load testing to verify 1K RPS @ ≤50µs targets
- Benchmark script execution time under sustained load
- Memory usage profiling for script caching mechanisms
- Throughput testing with multiple concurrent promotions

**Test Frameworks**: pytest, pytest-benchmark, redis-py test utilities

## Rollback Plan

**Step 1: Immediate Rollback**
- Revert to previous script SHA using cached version
- Disable feature flags: `REDIS_LUA_PROMOTION_ENABLED=false`
- Switch to multi-command fallback operations

**Step 2: Evidence Schema Rollback**
- Revert evidence schema configuration in Redis
- Restore previous validation rules from backup
- Update queue workers to use legacy validation

**Step 3: Performance Fallback**
- Monitor system performance after rollback
- Verify queue operations resume normal latency
- Re-enable gradual rollout if needed

**Trigger Conditions**: Script errors >1%, performance degradation >100µs, evidence validation failures >5%

## Validation Framework

**Pre-commit Validation**:
```bash
ruff check redis/ --fix && mypy redis/
pytest tests/unit/redis/ -v --cov=redis/
```

**Integration Validation**:
```bash
pytest tests/integration/test_redis_promotion.py -v
pytest tests/performance/test_promotion_performance.py -v --benchmark-only
```

**Production Validation**:
- Redis script security review (no unsafe operations)
- Performance regression budgets (≤50µs @ 1K RPS)
- Evidence schema validation testing
- Script SHA integrity verification