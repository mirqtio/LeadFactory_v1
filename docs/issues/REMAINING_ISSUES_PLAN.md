# LeadFactory Remaining Issues Resolution Plan

## Current State
- Smoke test success rate: 41.7% (5/12 domains passing)
- Passing domains: D4, D5, D6, D8, D9
- Failing domains: D0, D1, D2, D3, D7, D10, D11

## Issues to Address

### 1. D0 Gateway - SendGrid Stub 404 Error
**Issue**: SendGrid stub service returning 404
**Root Cause**: Stub server routing issue for SendGrid endpoints
**Solution**: Fix stub server routes for SendGrid API

### 2. D1, D3, D7, D10, D11 - API Health Check Failures
**Issue**: Health endpoints returning 500 errors
**Root Cause**: Missing or misconfigured health endpoints
**Solution**: Implement proper health check endpoints for each domain

### 3. D2 Sourcing - SQLite Database Issue
**Issue**: Using SQLite instead of PostgreSQL
**Root Cause**: Hardcoded SQLite connection in sourcing module
**Solution**: Update D2 to use PostgreSQL from environment

### 4. Missing Prometheus Metrics
**Issue**: Some domains not exposing metrics
**Root Cause**: Metrics not properly integrated
**Solution**: Add metrics collection to all domains

## Resolution Plan

### Phase 1: Fix Stub Services (30 mins)
1. Update stub server SendGrid routes
2. Add missing stub endpoints
3. Verify all stub services working

### Phase 2: Fix Health Endpoints (1 hour)
1. Add health check to D1 Targeting
2. Add health check to D3 Assessment
3. Add health check to D7 Storefront
4. Add health check to D10 Analytics
5. Add health check to D11 Orchestration
6. Standardize health check responses

### Phase 3: Fix Database Issues (30 mins)
1. Update D2 Sourcing to use PostgreSQL
2. Remove hardcoded SQLite references
3. Ensure all domains use shared database

### Phase 4: Complete Metrics Integration (30 mins)
1. Add Prometheus metrics to missing domains
2. Ensure /metrics endpoint exposed
3. Verify metrics collection

### Phase 5: Final Validation (30 mins)
1. Run complete smoke test
2. Verify all domains passing
3. Check production readiness
4. Update documentation

## Success Criteria
- All 12 domains passing smoke test (100%)
- All health endpoints returning 200
- All domains using PostgreSQL
- Prometheus metrics available for all domains
- No stub service errors

## Execution Timeline
- Total estimated time: 3 hours
- Priority: Fix blocking issues first (stub services, health checks)
- Approach: Systematic domain-by-domain fixes