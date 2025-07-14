# P3-001 - Fix RBAC for All API Endpoints
**Priority**: P3  
**Status**: Not Started  
**Estimated Effort**: 2 days  
**Dependencies**: P0-026

## Goal & Success Criteria

Apply RoleChecker dependency to ALL mutation endpoints (POST/PUT/PATCH/DELETE) across the entire API surface to ensure consistent role-based access control, preventing unauthorized users from performing data modifications.

**Success Criteria:**
- 100% of mutation endpoints have RoleChecker dependency enforced
- Zero unprotected mutation endpoints (verified by automated test)
- All viewers receive 403 Forbidden on mutation attempts
- All admins can perform operations without restrictions
- Auth checks add <100ms latency overhead
- Test coverage ≥80% on RBAC implementation
- All existing tests continue to pass
- CI validates RBAC coverage on every PR

## Context & Background

The governance module (P0-026) introduced RoleChecker for governance-specific endpoints, but other API domains remain unprotected. This creates security vulnerabilities where any authenticated user can modify critical data through endpoints like:
- Lead creation/update/deletion
- Batch job execution
- Template modifications
- Scoring weight changes
- Assessment data mutations

Based on research from FastAPI security best practices (2024), the recommended approach is to use dependency injection with the Security() wrapper for clarity and apply dependencies at the router level for consistent protection.

## Technical Approach

### 1. Refactor RoleChecker for Shared Use
Move RoleChecker from `api/governance.py` to `api/dependencies.py`:

```python
# api/dependencies.py
from typing import List
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from core.config import settings
from core.logging import get_logger
from database.session import get_db
from database.governance_models import User, UserRole

logger = get_logger("auth", domain="governance")
security = HTTPBearer()

# Import get_current_user from governance
from api.governance import get_current_user

class RoleChecker:
    """
    Dependency to check user role for mutations.
    
    Usage:
        @router.post("/resource")
        async def create_resource(
            current_user: User = Depends(require_admin)
        ):
            ...
    """
    
    def __init__(self, allowed_roles: List[UserRole]):
        self.allowed_roles = allowed_roles
    
    def __call__(self, current_user: User = Depends(get_current_user)) -> User:
        # Feature flag check
        if not settings.enable_rbac_enforcement:
            logger.warning("RBAC enforcement disabled - allowing access")
            return current_user
            
        if current_user.role not in self.allowed_roles:
            logger.warning(
                f"Access denied - user_id: {str(current_user.id)}, "
                f"user_role: {current_user.role.value}, "
                f"required_roles: {[r.value for r in self.allowed_roles]}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {', '.join(r.value for r in self.allowed_roles)}"
            )
        return current_user

# Export role dependencies
require_admin = RoleChecker([UserRole.ADMIN])
require_any_role = RoleChecker([UserRole.ADMIN, UserRole.VIEWER])
```

### 2. Apply Protection Systematically

For each API module, add RoleChecker to mutations:

```python
# Example: lead_explorer/api.py
from fastapi import Security  # Use Security for auth dependencies
from api.dependencies import require_admin

@router.post("/leads", response_model=LeadResponseSchema, status_code=201)
@limiter.limit("10/second")
@handle_api_errors
async def create_lead(
    lead_data: CreateLeadSchema, 
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Security(require_admin)  # ADD THIS
):
    """Create a new lead with audit logging (admin only)"""
    # ... existing implementation
```

### 3. Router-Level Protection (where applicable)

For routers where all endpoints need the same protection:

```python
# Example: batch_runner/api.py
from api.dependencies import require_admin

# Apply to entire router
batch_router = APIRouter(
    prefix="/batch",
    tags=["batch"],
    dependencies=[Security(require_admin)]  # All endpoints require admin
)
```

### 4. Update Existing Tests

Use dependency overrides for testing:

```python
# tests/conftest.py
@pytest.fixture
def admin_user():
    return User(
        id="test-admin",
        email="admin@test.com",
        role=UserRole.ADMIN
    )

@pytest.fixture
def viewer_user():
    return User(
        id="test-viewer",
        email="viewer@test.com",
        role=UserRole.VIEWER
    )

@pytest.fixture
def admin_client(app, admin_user):
    from api.dependencies import get_current_user
    app.dependency_overrides[get_current_user] = lambda: admin_user
    return TestClient(app)

@pytest.fixture
def viewer_client(app, viewer_user):
    from api.dependencies import get_current_user
    app.dependency_overrides[get_current_user] = lambda: viewer_user
    return TestClient(app)
```

## Acceptance Criteria

1. **Dependency Module Created**
   - `api/dependencies.py` contains shared RoleChecker class
   - RoleChecker properly imported in all API modules
   - Feature flag `ENABLE_RBAC_ENFORCEMENT` respected

2. **All Mutations Protected**
   - d1_targeting: create/update/delete universe, campaigns, batches
   - d3_assessment: any mutation endpoints
   - d7_storefront: any mutation endpoints  
   - d11_orchestration: job control endpoints
   - lead_explorer: create/update/delete leads, quick-add
   - batch_runner: create/cancel batch jobs
   - template_studio: save templates, create PRs
   - scoring_playground: update weights, create PRs
   - lineage: no mutations (verify read-only)

3. **Test Coverage**
   - Unit tests for RoleChecker with feature flag scenarios
   - Integration tests verify 403 for viewers on all mutations
   - Automated sweep test counts protected endpoints
   - Performance test confirms <100ms overhead

4. **Documentation Updated**
   - API documentation shows required roles
   - README updated with RBAC configuration
   - Migration guide for existing API consumers

## Dependencies

- P0-026: Governance module with existing RoleChecker implementation
- Database models: User, UserRole from governance_models
- FastAPI 0.104.1+ for Security dependency support
- pytest-benchmark for performance testing

## Testing Strategy

### Unit Tests
```python
# tests/unit/api/test_dependencies.py
def test_role_checker_allows_admin(admin_user):
    checker = RoleChecker([UserRole.ADMIN])
    result = checker(admin_user)
    assert result == admin_user

def test_role_checker_blocks_viewer(viewer_user):
    checker = RoleChecker([UserRole.ADMIN])
    with pytest.raises(HTTPException) as exc:
        checker(viewer_user)
    assert exc.value.status_code == 403

def test_role_checker_respects_feature_flag(viewer_user, monkeypatch):
    monkeypatch.setattr(settings, "enable_rbac_enforcement", False)
    checker = RoleChecker([UserRole.ADMIN])
    result = checker(viewer_user)  # Should not raise
    assert result == viewer_user
```

### Integration Tests
```python
# tests/integration/test_rbac_enforcement.py
@pytest.mark.parametrize("endpoint,method", [
    ("/api/v1/leads", "POST"),
    ("/api/v1/leads/123", "PUT"),
    ("/api/v1/leads/123", "DELETE"),
    # ... all mutation endpoints
])
def test_viewer_blocked_on_mutations(viewer_client, endpoint, method):
    response = viewer_client.request(method, endpoint, json={})
    assert response.status_code == 403
    assert "Access denied" in response.json()["detail"]

def test_admin_allowed_on_mutations(admin_client):
    response = admin_client.post("/api/v1/leads", json={
        "email": "test@example.com",
        "domain": "example.com"
    })
    assert response.status_code in [201, 422]  # 422 for validation errors
```

### Coverage Test
```python
# tests/unit/api/test_rbac_coverage.py
import inspect
from fastapi import FastAPI
from fastapi.routing import APIRoute

from main import app
from api.dependencies import RoleChecker

def get_all_routes(app: FastAPI) -> List[APIRoute]:
    """Recursively get all routes from app"""
    routes = []
    for route in app.routes:
        if isinstance(route, APIRoute):
            routes.append(route)
    return routes

def test_all_mutations_have_rbac():
    """Verify all mutation endpoints have RoleChecker dependency"""
    unprotected_mutations = []
    mutation_methods = {"POST", "PUT", "PATCH", "DELETE"}
    
    for route in get_all_routes(app):
        if any(method in route.methods for method in mutation_methods):
            # Check dependencies
            has_role_checker = False
            
            # Check route-level dependencies
            for dependency in route.dependencies:
                if isinstance(dependency.dependency, RoleChecker):
                    has_role_checker = True
                    break
            
            # Check endpoint function parameters
            if not has_role_checker:
                sig = inspect.signature(route.endpoint)
                for param in sig.parameters.values():
                    if param.default and hasattr(param.default, "dependency"):
                        if isinstance(param.default.dependency, RoleChecker):
                            has_role_checker = True
                            break
            
            if not has_role_checker:
                unprotected_mutations.append({
                    "path": route.path,
                    "methods": list(route.methods),
                    "name": route.name
                })
    
    assert len(unprotected_mutations) == 0, \
        f"Found {len(unprotected_mutations)} unprotected mutation endpoints: {unprotected_mutations}"
```

### Performance Tests
```python
# tests/performance/test_auth_overhead.py
@pytest.mark.benchmark
def test_auth_overhead(client, benchmark):
    """Verify auth adds <100ms overhead"""
    
    # Baseline: health check without auth
    def health_check():
        response = client.get("/health")
        assert response.status_code == 200
    
    baseline_time = benchmark(health_check)
    
    # With auth: protected endpoint
    def protected_call():
        response = client.post(
            "/api/v1/leads",
            json={"email": "test@example.com"},
            headers={"Authorization": "Bearer test-token"}
        )
        assert response.status_code in [201, 403]
    
    auth_time = benchmark(protected_call)
    
    overhead_ms = (auth_time - baseline_time) * 1000
    assert overhead_ms < 100, f"Auth overhead {overhead_ms}ms exceeds 100ms limit"
```

## Rollback Plan

1. **Feature Flag Disable**
   - Set `ENABLE_RBAC_ENFORCEMENT=false` in environment
   - RoleChecker will log warnings but allow all access
   - No code changes required

2. **Emergency Revert**
   - If critical issues arise, revert the commit
   - Remove Security dependencies from endpoints
   - Restore previous authentication logic

3. **Gradual Rollback**
   - Selectively disable RBAC on specific routers
   - Use router-specific feature flags if needed
   - Monitor and fix issues before re-enabling

## Validation Framework

### Pre-commit Hooks
```yaml
# .pre-commit-config.yaml additions
- repo: local
  hooks:
  - id: rbac-coverage
    name: Check RBAC Coverage
    entry: python scripts/check_rbac_coverage.py
    language: python
    files: 'api/.*\.py$'
```

### CI Gates
```yaml
# .github/workflows/security.yml
- name: Verify RBAC Coverage
  run: |
    pytest tests/unit/api/test_rbac_coverage.py -v
    pytest tests/integration/test_rbac_enforcement.py -v

- name: Security Scan
  run: |
    bandit -r api/ d*/api.py lead_explorer/api.py batch_runner/api.py
    safety check
```

### Performance Monitoring
- Add auth overhead metrics to Prometheus
- Alert if p95 latency exceeds 100ms
- Dashboard showing auth performance by endpoint

### Rollback Procedures
- Document in runbooks/rbac_rollback.md
- Test rollback in staging environment
- Ensure ops team knows feature flag location