# P0-021 - Lead Explorer
**Priority**: P0
**Status**: Not Started
**Estimated Effort**: 3 days
**Dependencies**: P0-020

## Goal & Success Criteria

### Goal
Give the CPO a /leads console that supports full CRUD and an audit-log, plus a Quick-Add form that immediately kicks off async enrichment

### Success Criteria
1. POST/GET/PUT/DELETE endpoints return 2xx & validate schemas
2. Quick-Add sets enrichment_status=in_progress and persists task-id
3. CPO console table shows manual badge; filters by is_manual
4. Audit trail captures 100% of mutations with user context
5. Test coverage ≥80% on lead_explorer module
6. CI green, KEEP suite unaffected
7. Response times <500ms for all CRUD operations
8. Pagination handles 10k+ leads efficiently

## Context & Background

### Business Context
Manual seeding keeps demos moving and lets business users validate downstream flows before automated sources are live. The Lead Explorer provides a foundation for lead management that integrates with existing enrichment and pipeline flows.

### Technical Context
- No existing Lead model in codebase - system uses Business and Target models
- FastAPI already set up with SQLAlchemy models and Pydantic schemas
- Database uses UUID strings for primary keys
- No audit logging infrastructure currently exists
- Enrichment coordinator exists in d4_enrichment module

### Integration Requirements
- Must integrate with existing d4_enrichment/coordinator.py for enrichment
- Follow patterns from d1_targeting/api.py for API structure
- Use existing database session management from database/session.py
- Register router in main.py following existing patterns

### Research Context
Based on authoritative sources and current best practices (2024):

**FastAPI CRUD Patterns**:
- Use async SQLAlchemy 2.0 for non-blocking database operations [SQLAlchemy 2.0 Async Docs](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- Implement repository pattern for separation of concerns [FastAPI SQL Tutorial](https://fastapi.tiangolo.com/tutorial/sql-databases/)
- Use dependency injection for session management [FastAPI Advanced Dependencies](https://fastapi.tiangolo.com/advanced/advanced-dependencies/)

**Audit Logging Best Practices**:
- Middleware-based approach for HTTP-level audit capture
- SQLAlchemy event listeners for database-level changes
- Immutable audit records with checksums for compliance
- Async writes to prevent blocking main operations

**Pydantic V2 Validation**:
- Use Field() for extra constraints and metadata [Pydantic Validators](https://docs.pydantic.dev/latest/concepts/validators/)
- Implement custom validators for business logic
- Separate schemas for create, update, and response operations
- Leverage Rust-powered core for performance

**Security Considerations**:
- Input validation to prevent XSS and injection attacks
- Rate limiting on mutation endpoints (10 req/sec)
- Proper authentication/authorization checks
- Parameterized queries (SQLAlchemy default)

## Technical Approach

### Architecture Overview
1. **New Module Structure**: Create lead_explorer module with api, models, schemas, repository, and audit components
2. **Database Design**: Two new tables - leads and audit_log_leads with proper indexes
3. **API Design**: RESTful CRUD endpoints plus Quick-Add endpoint for enrichment
4. **Audit Pattern**: SQLAlchemy event listeners for automatic audit logging
5. **Enrichment Integration**: Async task queuing to existing enrichment pipeline

### Implementation Steps
1. Create database models for Lead and AuditLogLead
2. Generate Alembic migration for new tables
3. Implement repository pattern for database operations
4. Create Pydantic schemas for request/response validation
5. Build API endpoints with proper error handling
6. Implement audit logging with event listeners
7. Integrate Quick-Add with enrichment coordinator
8. Add comprehensive test coverage

### Key Design Decisions
- Use async SQLAlchemy for non-blocking operations
- Implement soft deletes to preserve data integrity
- Use SHA-256 checksums for audit log immutability
- Separate repository layer for testability
- Background tasks for enrichment to avoid blocking

## Acceptance Criteria

1. **API Functionality**
   - GET /api/v1/leads returns paginated list with filters
   - POST /api/v1/leads creates new lead with validation
   - GET /api/v1/leads/{id} returns lead details
   - PUT /api/v1/leads/{id} updates lead with audit trail
   - DELETE /api/v1/leads/{id} performs soft delete
   - POST /api/v1/leads/quick-add triggers enrichment

2. **Data Validation**
   - Email format validation (RFC 5322 compliant)
   - Domain format validation (valid FQDN)
   - Duplicate email/domain handled gracefully
   - Required fields enforced

3. **Audit Requirements**
   - Every mutation creates audit log entry
   - Audit logs include user context (id, IP, user agent)
   - Old and new values captured for updates
   - Checksums prevent tampering

4. **Performance Requirements**
   - All endpoints respond in <500ms (p99)
   - Pagination supports 10k+ records
   - Database queries use proper indexes
   - No N+1 query problems

5. **Testing Requirements**
   - Unit test coverage ≥80%
   - Integration tests for enrichment flow
   - Performance tests for large datasets
   - Audit trail completeness tests

## Dependencies

### Task Dependencies
- P0-020: Design System Token Extraction (for UI integration)

### Technical Dependencies
```python
# Existing dependencies (no new packages required)
- fastapi==0.104.1
- sqlalchemy==2.0.23
- pydantic==2.5.2
- alembic==1.12.1
- pytest==7.4.3
- pytest-asyncio==0.21.1
```

### System Dependencies
- PostgreSQL database
- Redis for caching (optional)
- Background task queue (existing)

## Testing Strategy

### Unit Tests
```bash
# Test individual components
pytest tests/unit/lead_explorer/test_models.py -v
pytest tests/unit/lead_explorer/test_repository.py -v
pytest tests/unit/lead_explorer/test_schemas.py -v
pytest tests/unit/lead_explorer/test_audit.py -v
```

### Integration Tests
```bash
# Test API endpoints with database
pytest tests/integration/test_lead_explorer_api.py -v
# Test enrichment integration
pytest tests/integration/test_lead_enrichment_flow.py -v
```

### Performance Tests
```bash
# Test with large datasets
pytest tests/performance/test_lead_explorer_scale.py -v -m performance
```

### Test Coverage
```bash
# Ensure ≥80% coverage
pytest tests/unit/lead_explorer/ --cov=lead_explorer --cov-report=html --cov-fail-under=80
```

## Rollback Plan

### Rollback Steps
1. **Disable Feature**: Set ENABLE_LEAD_EXPLORER=false in environment
2. **Remove Router**: Comment out lead_explorer router in main.py
3. **Rollback Migration**: Run `alembic downgrade -1`
4. **Clean Database**: Optional - remove orphaned data
5. **Remove Code**: Delete lead_explorer module if needed

### Rollback Conditions
- Critical bugs affecting production
- Performance degradation >20%
- Data integrity issues
- Security vulnerabilities discovered

### Data Preservation
- Audit logs preserved even after rollback
- Lead data exported before cleanup
- Migration designed to be reversible

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

### Pre-Deployment Validation
```bash
# Code quality checks
ruff check lead_explorer/ --fix
mypy lead_explorer/ --strict
black lead_explorer/ --check

# Security scan
bandit -r lead_explorer/
safety check

# Test suite
pytest tests/unit/lead_explorer/ -v
pytest tests/integration/test_lead_explorer_*.py -v
```

### Post-Deployment Validation
```bash
# API health check
curl -X GET http://localhost:8000/api/v1/leads/health

# Audit trail verification
python scripts/verify_audit_trail.py

# Performance check
python scripts/check_lead_api_performance.py
```

### Missing-Checks Framework
**Required Checks**:
- [x] Pre-commit hooks for code quality
- [x] Branch protection with required CI checks
- [x] Database migration testing
- [x] API contract testing
- [x] Security scanning in CI
- [x] Performance regression tests

**Monitoring Checks**:
- [x] API latency alerts (>500ms)
- [x] Error rate monitoring (>1%)
- [x] Audit log completeness checks
- [x] Database connection pool monitoring

### Validation Gates
1. **Development**: All unit tests pass, coverage ≥80%
2. **Staging**: Integration tests pass, performance benchmarks met
3. **Production**: Smoke tests pass, monitoring configured