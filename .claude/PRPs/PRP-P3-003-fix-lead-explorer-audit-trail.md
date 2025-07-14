# P3-003 - Fix Lead Explorer Audit Trail
**Priority**: P3
**Status**: Not Started
**Estimated Effort**: 4 hours
**Dependencies**: P0-021

## Goal & Success Criteria
Fix the critical SQLAlchemy audit event listener bug preventing audit logging by switching from unreliable mapper-level events to session-level events and enabling proper testing.

**Success Criteria:**
- [ ] All Lead CRUD operations create audit log entries
- [ ] Audit logs capture old values, new values, and user context
- [ ] SHA-256 checksums prevent tampering
- [ ] Failed operations are also logged
- [ ] No SQLAlchemy flush errors occur
- [ ] Audit logging works in test environment
- [ ] Coverage ≥ 80% on audit module
- [ ] All existing Lead Explorer tests pass

## Context & Background

### Business Context
- **Business value**: Audit trails are critical for compliance, debugging, and security - without working audit logs, we cannot track user actions or investigate issues
- **Integration**: The audit system must capture all Lead CRUD operations performed through the Lead Explorer API and UI
- **Problems solved**: Current mapper-level event listeners (after_insert, after_update, after_delete) are not triggering reliably, and are disabled in test environment preventing verification

### Technical Context
The current implementation uses SQLAlchemy mapper-level event listeners which have proven unreliable. The audit system must:
- Capture all CREATE, UPDATE, and DELETE operations on Lead models
- Record old and new values for all changes
- Store user context (user_id, IP address, user agent)
- Generate SHA-256 checksums for tamper detection
- Work properly in both test and production environments
- Handle exceptions gracefully without breaking main operations

### Research Findings
Based on research into SQLAlchemy best practices:
- Session-level events (before_flush) are more reliable than mapper-level events
- The before_flush event provides access to all changed objects in one place
- Modern audit trail implementations use session events for better control
- Event listeners should handle exceptions without breaking transactions

### Documentation & References
```yaml
- url: https://docs.sqlalchemy.org/en/20/orm/session_events.html
  why: Official SQLAlchemy documentation on session events including before_flush
  
- url: https://docs.sqlalchemy.org/en/20/orm/events.html
  why: Complete event system documentation explaining mapper vs session events

- url: https://medium.com/@singh.surbhicse/creating-audit-table-to-log-insert-update-and-delete-changes-in-flask-sqlalchemy-f2ca53f7b02f
  why: Best practice implementation of audit trails using before_flush

- file: /Users/charlieirwin/Documents/GitHub/LeadFactory_v1_Final/lead_explorer/audit.py
  why: Current implementation to be fixed

- file: /Users/charlieirwin/Documents/GitHub/LeadFactory_v1_Final/tests/unit/lead_explorer/test_audit.py
  why: Test suite that needs to pass with fixed implementation
```

### Current Codebase Tree
```
lead_explorer/
├── __init__.py
├── api.py
├── audit.py          # Current broken implementation
├── models.py
├── repository.py
└── schemas.py

tests/unit/lead_explorer/
├── conftest.py
├── test_api.py
├── test_audit.py     # Tests currently skipped in test env
├── test_models.py
└── test_repository.py
```

### Desired Codebase Tree
```
lead_explorer/
├── __init__.py
├── api.py
├── audit.py          # Fixed with session-level events
├── models.py
├── repository.py
└── schemas.py

tests/unit/lead_explorer/
├── conftest.py
├── test_api.py
├── test_audit.py     # All tests passing
├── test_models.py
└── test_repository.py
```

## Technical Approach

### Integration Points
- `lead_explorer/audit.py` - Main implementation file to fix
- `database/session.py` - Session configuration for event registration
- `main.py` - Application startup to ensure audit logging is initialized
- `tests/unit/lead_explorer/test_audit.py` - Test suite to verify

### Implementation Steps
1. **Replace mapper events with session events**:
   - Remove `after_insert`, `after_update`, `after_delete` listeners
   - Implement `before_flush` session event listener
   - Use SQLAlchemy's `inspect()` to track changes properly

2. **Fix environment check**:
   - Remove or make configurable the `os.getenv('ENVIRONMENT') != 'test'` check
   - Add `ENABLE_AUDIT_LOGGING` feature flag defaulting to True

3. **Improve change tracking**:
   - Use `session.new` for inserts
   - Use `session.dirty` for updates with proper history tracking
   - Use `session.deleted` for deletes
   - Handle soft deletes (is_deleted flag) as updates

4. **Error handling**:
   - Wrap audit operations in try/except blocks
   - Log errors without breaking main transaction
   - Add metrics for audit failures

5. **Testing strategy**:
   - Enable audit logging in test environment
   - Mock audit context for controlled testing
   - Verify all CRUD operations generate logs
   - Test checksum verification

## Acceptance Criteria

1. All Lead CRUD operations (CREATE, UPDATE, DELETE) generate audit log entries
2. Audit logs capture complete old values and new values for all changes
3. User context (user_id, IP, user agent) is properly recorded when available
4. SHA-256 checksums are calculated correctly and prevent tampering
5. Soft delete operations (is_deleted flag) are tracked as UPDATE operations
6. Failed database operations still generate audit logs with error details
7. Audit logging works in both test and production environments
8. No SQLAlchemy flush or session errors occur during normal operation
9. Test coverage on lead_explorer/audit.py is ≥ 80%
10. All existing Lead Explorer API tests continue to pass

## Dependencies

- **P0-021**: Lead Explorer base implementation must be complete
- SQLAlchemy >= 1.4.0 (already in requirements.txt)
- No new Python dependencies required

## Testing Strategy

### Unit Tests
- Test AuditContext for storing and retrieving user context
- Test get_model_values for extracting Lead model fields
- Test create_audit_log for generating audit entries with checksums
- Test session event listeners trigger on all CRUD operations
- Test exception handling doesn't break main transactions
- Test checksum verification detects tampering

### Integration Tests
- Test Lead Explorer API creates audit logs for all endpoints
- Test audit logs capture correct old/new values
- Test concurrent operations don't interfere with audit logging
- Test audit middleware properly sets user context

### Coverage Requirements
- Minimum 80% coverage on lead_explorer/audit.py
- All critical paths must have test coverage
- Exception handling paths must be tested

## Rollback Plan

1. **Immediate Rollback**: Set environment variable `ENABLE_AUDIT_LOGGING=false` to disable all audit logging
2. **Code Rollback**: 
   - Revert lead_explorer/audit.py to previous version
   - Session event listeners are removed automatically when module isn't imported
   - No database changes required - existing audit logs remain valid
3. **Partial Rollback**: Use feature flags to disable specific audit features:
   - `AUDIT_LOG_IN_TEST=false` - Disable in test environment only
   - `AUDIT_LOG_SOFT_DELETES=false` - Skip soft delete tracking
4. **Recovery**: If audit logs are corrupted, they can be safely truncated without affecting Lead data

## Validation Framework

### Pre-Implementation Validation
- [ ] Current test suite passes before changes
- [ ] Backup of original audit.py created
- [ ] Feature flags configured in environment

### Post-Implementation Tests
```bash
# Syntax/Style
ruff check lead_explorer/ tests/unit/lead_explorer/ --fix
mypy lead_explorer/

# Unit Tests
pytest tests/unit/lead_explorer/test_audit.py -v

# Integration Tests
pytest tests/unit/lead_explorer/test_api.py -v -k "audit"

# Coverage Check
pytest tests/unit/lead_explorer/ --cov=lead_explorer.audit --cov-report=term-missing
```

### CI/CD Validation
- [ ] All GitHub Actions workflows pass
- [ ] Docker build completes successfully
- [ ] No new security vulnerabilities introduced
- [ ] Performance benchmarks show < 100ms overhead

### Production Validation
- [ ] Audit logs generated for manual test operations
- [ ] Checksum verification works correctly
- [ ] No errors in application logs
- [ ] Database performance metrics normal

### Missing-Checks Framework

#### 1. Pre-commit Hook Configuration
```bash
# .pre-commit-config.yaml addition
- repo: local
  hooks:
    - id: audit-tests
      name: Run audit tests
      entry: pytest tests/unit/lead_explorer/test_audit.py -v
      language: system
      files: 'lead_explorer/audit\.py'
```

#### 2. Branch Protection Setup
```bash
# Configure via GitHub API after merge
gh api repos/:owner/:repo/branches/main/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":["test","lint","security"]}' \
  --field enforce_admins=true \
  --field required_pull_request_reviews='{"required_approving_review_count":1}'
```

#### 3. Security Scanning
- [ ] Dependabot alerts resolved before merge
- [ ] `bandit lead_explorer/audit.py` passes with no high severity issues
- [ ] No SQL injection vulnerabilities in audit queries

#### 4. Performance Regression Prevention
```bash
# Add to test suite
pytest tests/performance/test_audit_performance.py --benchmark-only
# Baseline: < 100ms per audit operation
```