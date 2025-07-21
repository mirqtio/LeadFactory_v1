# PRP-P0-026 Governance

> 💡 **Claude Implementation Note**: Consider how task subagents can be used to execute portions of this task in parallel to improve efficiency and reduce overall completion time.

## Goal
Ship single-tenant RBAC ("Admin" vs "Viewer") and a global immutable audit-trail covering every mutation in the CPO console

## Why  
- **Business value**: Enterprise deployments require proper access control and compliance-ready audit trails for regulatory requirements
- **Integration**: RBAC integrates with existing FastAPI dependency injection; audit logs track all CPO console mutations
- **Problems solved**: Prevents unauthorized data modifications, enables compliance audits, provides forensic analysis capability

## What
Implement role-based access control with two roles (Admin/Viewer) and comprehensive audit logging for all data mutations in the CPO console. Viewers can read all data but receive 403 errors on any mutation attempts. **CRITICAL: RBAC must be applied to ALL mutation endpoints across the entire application, not just governance endpoints.** All successful mutations are logged with tamper-proof checksums.

### Success Criteria
- [ ] Role-based access control implemented with Admin and Viewer roles
- [ ] Viewers receive 403 on ALL mutation endpoints (POST/PUT/DELETE) across entire application
- [ ] RBAC applied to: leads, templates, batch operations, governance, and all other API mutations
- [ ] All mutations create audit log entries with content hashes
- [ ] Audit logs include tamper-proof SHA-256 checksums
- [ ] Coverage ≥ 80% on governance module
- [ ] Coverage ≥ 80% on RBAC-protected endpoints
- [ ] No performance degradation (API response time <100ms increase)
- [ ] Audit logs cannot be modified or deleted via API
- [ ] Integration tests verify RBAC on all mutation endpoints

## All Needed Context

### Documentation & References
```yaml
- url: https://fastapi.tiangolo.com/advanced/advanced-dependencies/
  why: Official FastAPI guide for implementing security dependencies
  
- url: https://docs.sqlalchemy.org/en/20/core/event.html
  why: SQLAlchemy event system for audit log triggers

- url: https://fastapi.tiangolo.com/tutorial/security/
  why: FastAPI security patterns for authentication/authorization

- file: d0_gateway/base.py
  why: Existing gateway pattern to follow for consistent implementation

- file: core/config.py
  why: Configuration patterns for feature flags and settings

- file: api/
  why: All API endpoints that need RBAC protection
```

### Current Codebase Tree
```
LeadFactory_v1_Final/
├── core/
│   ├── config.py
│   └── database.py
├── api/
│   ├── leads.py
│   ├── templates.py
│   ├── batch_operations.py
│   └── (various endpoint files)
├── d0_gateway/
│   └── base.py
└── tests/
    └── unit/
```

### Desired Codebase Tree  
```
LeadFactory_v1_Final/
├── core/
│   ├── config.py
│   └── database.py
├── governance/
│   ├── __init__.py
│   ├── models.py         # Role enum, audit_log_global table
│   ├── dependencies.py   # RoleChecker dependency
│   ├── audit.py         # Audit logging functionality
│   └── schemas.py       # Pydantic models
├── api/
│   ├── leads.py         # Modified to use RoleChecker
│   ├── templates.py     # Modified to use RoleChecker
│   ├── batch_operations.py  # Modified to use RoleChecker
│   └── (all endpoint files - modified to use RoleChecker)
├── alembic/versions/
│   └── xxx_add_governance_tables.py
└── tests/
    └── unit/
        ├── governance/
        │   ├── __init__.py
        │   ├── test_role_checker.py
        │   ├── test_audit_logging.py
        │   └── test_governance_integration.py
        └── api/
            ├── test_rbac_leads.py
            ├── test_rbac_templates.py
            ├── test_rbac_batch.py
            └── test_rbac_all_endpoints.py
```

## Technical Implementation

### Integration Points
- `governance/models.py` - SQLAlchemy models for roles and audit_log_global
- `governance/dependencies.py` - FastAPI dependency for role checking
- `governance/audit.py` - Audit logging with SHA-256 checksums
- `api/*` - **ALL mutation endpoints across entire application** updated to use RoleChecker dependency
- `alembic/versions/` - New migration for governance tables

### Implementation Approach
1. **Database Schema**
   - Create Role enum (admin, viewer)
   - Create audit_log_global table with immutable design
   - Add user_role column to existing user table

2. **Role-Based Access Control**
   - Implement RoleChecker as FastAPI dependency
   - Check user role from JWT/session in dependency
   - Return 403 for viewers on mutation endpoints
   - **CRITICAL: Apply dependency to ALL POST/PUT/DELETE routes in:**
     - `api/leads.py` - Lead creation, update, deletion
     - `api/templates.py` - Template CRUD operations
     - `api/batch_operations.py` - Batch processing endpoints
     - `api/enrichment.py` - Enrichment operations
     - `api/tasks.py` - Task operations
     - `api/reports.py` - Report generation
     - Any other files containing mutation endpoints

3. **Audit Logging**
   - Use SQLAlchemy event listeners (after_flush)
   - Capture user_id, action, object_type, object_id, timestamp
   - Calculate SHA-256 hash of audit entry content
   - Store details as JSONB for flexibility
   - Implement async writes to prevent API slowdown

4. **Testing Strategy**
   - Unit tests for RoleChecker dependency
   - Integration tests for audit log creation
   - **CRITICAL: Tests to verify viewers get 403 on ALL mutations:**
     - Lead CRUD operations
     - Template CRUD operations
     - Batch operations
     - Enrichment operations
     - Task operations
     - Report generation
   - Performance tests to ensure <100ms impact
   - Comprehensive endpoint coverage test

## Validation Gates

### CI Validation (MANDATORY)
**CI Validation = Code merged to main + GitHub Actions logs verified + All errors resolved + Solid green CI run**

This means:
1. Code must be merged to the main branch (not just pushed)
2. GitHub Actions logs must be checked to confirm successful workflow completion
3. Any errors that appear during CI must be resolved
4. The final CI run must show all green checkmarks with no failures
5. This verification must be done by reviewing the actual GitHub Actions logs, not just assumed

**This is a mandatory requirement for PRP completion.**

### Executable Tests
```bash
# Syntax/Style
ruff check --fix governance/ api/ && mypy governance/ api/

# Unit Tests  
pytest tests/unit/governance/ -v
pytest tests/unit/api/test_rbac_*.py -v

# Integration Tests
pytest tests/integration/test_governance_integration.py -v
pytest tests/integration/test_rbac_all_endpoints.py -v

# Coverage Check
pytest tests/unit/governance/ tests/unit/api/test_rbac_*.py --cov=governance --cov=api --cov-report=term-missing --cov-fail-under=80

# Performance Tests
pytest tests/performance/test_governance_performance.py -v

# Comprehensive RBAC Verification
pytest tests/integration/test_rbac_comprehensive.py -v -k "viewer_cannot_mutate"
```

### Missing-Checks Validation
**Required for Backend/API tasks:**
- [ ] Pre-commit hooks (ruff, mypy, pytest -m "not e2e")
- [ ] Branch protection & required status checks
- [ ] Security scanning (Dependabot, Trivy, audit tools)
- [ ] API performance budgets (<100ms impact)
- [ ] Database permission verification (audit table read-only)
- [ ] RBAC endpoint coverage report (100% of mutations protected)

**Recommended:**
- [ ] Load testing for concurrent audit writes
- [ ] Audit log retention policy automation
- [ ] Monitoring alerts for authorization failures
- [ ] Automated scan for unprotected mutation endpoints

## Dependencies
- SQLAlchemy >= 2.0 (for async support)
- pydantic >= 2.0 (for schema validation)
- hashlib (standard library for SHA-256)
- No new external dependencies required

## Rollback Strategy
1. Remove RoleChecker dependency from ALL API endpoints
2. Run migration: `alembic downgrade -1`
3. Delete governance/ directory
4. Restore original API endpoint definitions
5. Feature flag: `ENABLE_GOVERNANCE=false` as emergency bypass

## Feature Flag Requirements  
- `ENABLE_GOVERNANCE` - Master switch for all governance features
- `ENABLE_AUDIT_LOGGING` - Separate control for audit logging
- `ENABLE_RBAC` - Separate control for role-based access

## Database Migration
```sql
-- Add role to users table
ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT 'viewer';

-- Create audit_log_global table
CREATE TABLE audit_log_global (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    action VARCHAR(50) NOT NULL,
    object_type VARCHAR(100) NOT NULL,
    object_id UUID,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    details JSONB,
    content_hash VARCHAR(64) NOT NULL,
    CONSTRAINT audit_log_immutable CHECK (false) NO INHERIT
);

-- Create indexes for performance
CREATE INDEX idx_audit_log_user_id ON audit_log_global(user_id);
CREATE INDEX idx_audit_log_timestamp ON audit_log_global(timestamp);
CREATE INDEX idx_audit_log_object ON audit_log_global(object_type, object_id);

-- Prevent updates and deletes at database level
CREATE TRIGGER prevent_audit_updates
    BEFORE UPDATE OR DELETE ON audit_log_global
    FOR EACH ROW EXECUTE FUNCTION raise_exception('Audit logs are immutable');
```

## Security Considerations
- Audit logs must be write-only (no UPDATE/DELETE permissions)
- Content hashes prevent tampering detection
- Separate database user for audit writes recommended
- Consider encryption at rest for sensitive audit data
- Regular backup of audit logs to separate storage
- **CRITICAL: No mutation endpoint can bypass RBAC - automated scanning required**

## Endpoint Protection Checklist
**ALL mutation endpoints must be protected. This includes but is not limited to:**

- [ ] `/api/leads/*` - All lead CRUD operations
- [ ] `/api/templates/*` - All template management
- [ ] `/api/batch/*` - All batch operations
- [ ] `/api/enrichment/*` - All enrichment operations
- [ ] `/api/tasks/*` - All task operations
- [ ] `/api/reports/*` - All report generation
- [ ] `/api/settings/*` - All settings mutations
- [ ] `/api/users/*` - All user management (except login)
- [ ] `/api/webhooks/*` - All webhook configuration
- [ ] Any other POST, PUT, PATCH, DELETE endpoints

**Verification Required:** A comprehensive test must scan all routes and verify that 100% of mutation endpoints require admin role.