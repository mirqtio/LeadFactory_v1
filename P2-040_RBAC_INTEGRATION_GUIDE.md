# P2-040 RBAC Integration Implementation Guide

## Overview

This guide provides step-by-step instructions for integrating the P2-040 Dynamic Report Designer with the enterprise RBAC system deployed in P3-001.

## Implementation Checklist

### Phase 1: RBAC Resource Definition ✅ Ready for Implementation

**File**: `core/rbac.py`

**Changes Required**:
```python
# Add REPORTS resource to Resource enum (around line 100)
class Resource(Enum):
    # ... existing resources ...
    REPORTS = "reports"  # Add this line
```

**Validation**: Ensure REPORTS resource is accessible throughout RBAC system.

### Phase 2: Permission Updates ✅ Ready for Implementation

**File**: `core/rbac.py`

**Update Role Permissions** (around line 111):
```python
ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
    Role.SUPER_ADMIN: {
        # ... existing permissions ...
        Permission.MANAGE_REPORTS,  # Already exists
    },
    Role.ADMIN: {
        # ... existing permissions ...
        Permission.MANAGE_REPORTS,  # Already exists
    },
    Role.MANAGER: {
        # ... existing permissions ...
        Permission.MANAGE_REPORTS,  # Already exists
    },
    Role.ANALYST: {
        # ... existing permissions ...
        Permission.MANAGE_REPORTS,  # Already exists - ADD IF MISSING
    },
    # ... other roles as appropriate
}
```

**Validation**: Verify analysts and appropriate roles have MANAGE_REPORTS permission.

### Phase 3: Designer API Security Integration 🔄 Requires Implementation

**File**: `d6_reports/designer/designer_api.py`

**Update Imports** (around line 28):
```python
# Replace existing auth imports with RBAC-enabled versions
from core.auth import get_current_user_dependency, require_organization_access
from core.rbac import Resource, require_read_permission, require_write_permission, require_delete_permission
```

**Update Authentication Dependencies** - Replace all instances:

**Before**:
```python
current_user: AccountUser = Depends(get_current_user_dependency),
```

**After** (by operation type):
```python
# For read operations (GET endpoints)
current_user: AccountUser = require_read_permission(Resource.REPORTS),

# For write operations (POST, PUT endpoints)
current_user: AccountUser = require_write_permission(Resource.REPORTS),

# For delete operations (DELETE endpoints)
current_user: AccountUser = require_delete_permission(Resource.REPORTS),
```

**Specific Endpoint Updates**:

1. **Session Management**:
```python
@router.post("/sessions", response_model=SessionResponse)
async def create_session(
    template_id: Optional[str] = Query(None, description="Template ID to load"),
    current_user: AccountUser = require_write_permission(Resource.REPORTS),
    organization_id: str = Depends(require_organization_access),
):

@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str = Path(..., description="Session ID"),
    current_user: AccountUser = require_read_permission(Resource.REPORTS),
):

@router.delete("/sessions/{session_id}")
async def close_session(
    session_id: str = Path(..., description="Session ID"),
    current_user: AccountUser = require_write_permission(Resource.REPORTS),
):
```

2. **Template Operations**:
```python
@router.post("/sessions/{session_id}/templates")
async def create_template(
    request: CreateTemplateRequest,
    session_id: str = Path(..., description="Session ID"),
    current_user: AccountUser = require_write_permission(Resource.REPORTS),
):

@router.get("/templates", response_model=List[TemplateResponse])
async def list_templates(
    current_user: AccountUser = require_read_permission(Resource.REPORTS)
):

@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: str = Path(..., description="Template ID"),
    current_user: AccountUser = require_delete_permission(Resource.REPORTS),
):
```

3. **Component Operations**:
```python
@router.post("/sessions/{session_id}/components")
async def add_component(
    request: AddComponentRequest,
    session_id: str = Path(..., description="Session ID"),
    current_user: AccountUser = require_write_permission(Resource.REPORTS),
):

@router.put("/sessions/{session_id}/components/{component_id}")
async def update_component(
    request: UpdateComponentRequest,
    session_id: str = Path(..., description="Session ID"),
    component_id: str = Path(..., description="Component ID"),
    current_user: AccountUser = require_write_permission(Resource.REPORTS),
):

@router.delete("/sessions/{session_id}/components/{component_id}")
async def remove_component(
    session_id: str = Path(..., description="Session ID"),
    component_id: str = Path(..., description="Component ID"),
    current_user: AccountUser = require_delete_permission(Resource.REPORTS),
):

@router.get("/sessions/{session_id}/components", response_model=List[ComponentResponse])
async def list_components(
    session_id: str = Path(..., description="Session ID"),
    current_user: AccountUser = require_read_permission(Resource.REPORTS),
):
```

4. **Preview and Validation Operations**:
```python
@router.post("/sessions/{session_id}/preview")
async def generate_preview(
    request: PreviewRequest,
    session_id: str = Path(..., description="Session ID"),
    current_user: AccountUser = require_read_permission(Resource.REPORTS),
):

@router.post("/sessions/{session_id}/validate")
async def validate_template(
    session_id: str = Path(..., description="Session ID"),
    current_user: AccountUser = require_read_permission(Resource.REPORTS),
):

@router.post("/sessions/{session_id}/save")
async def save_template(
    session_id: str = Path(..., description="Session ID"),
    current_user: AccountUser = require_write_permission(Resource.REPORTS),
):
```

### Phase 4: API Router Registration 🔄 Requires Implementation

**File**: `main.py`

**Add Import** (around line 37):
```python
from d6_reports.designer.designer_api import router as designer_router
```

**Register Router** (find the section with other router registrations):
```python
# Register designer router
app.include_router(designer_router, prefix="/api/v1/reports/designer", tags=["report-designer"])
```

**Location**: Add this after the existing d6_reports router registration:
```python
# Register d6_reports router
app.include_router(reports_router, prefix="/api/v1/reports", tags=["reports"])
# Add designer router registration here
app.include_router(designer_router, prefix="/api/v1/reports/designer", tags=["report-designer"])
```

### Phase 5: Session Security Enhancement 🔄 Requires Implementation

**File**: `d6_reports/designer/designer_core.py`

**Add Organization Scoping**:
```python
@dataclass
class DesignerSession:
    """Designer session state"""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: Optional[str] = None
    organization_id: Optional[str] = None  # Add this field
    template_id: Optional[str] = None
    # ... rest of existing fields
```

**Update Session Validation**:
```python
# In designer_api.py helper functions
def get_designer_session(session_id: str, user_id: str = None, organization_id: str = None) -> DesignerSession:
    """Get designer session with validation"""
    session = report_designer.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if user_id and session.user_id != user_id:
        raise HTTPException(status_code=403, detail="Session access denied")
    
    # Add organization validation
    if organization_id and session.organization_id != organization_id:
        raise HTTPException(status_code=403, detail="Organization access denied")

    return session
```

### Phase 6: Audit Logging Integration 🔄 Requires Implementation

**File**: `d6_reports/designer/designer_api.py`

**Add Audit Logging** (after successful operations):
```python
# Example for template creation
@router.post("/sessions/{session_id}/templates")
async def create_template(
    request: CreateTemplateRequest,
    session_id: str = Path(..., description="Session ID"),
    current_user: AccountUser = require_write_permission(Resource.REPORTS),
):
    """Create a new template"""
    session = get_designer_session(session_id, current_user.id)

    result = report_designer.create_template(
        session_id=session_id, template_name=request.name, template_id=request.template_id
    )
    
    if result.success:
        # Add audit logging
        logger.info(
            f"Template created - user: {current_user.email}, "
            f"template_id: {result.template_id}, session: {session_id}"
        )

    return handle_designer_result(result)
```

## Testing and Validation

### Security Testing Checklist

1. **Authentication Testing**:
   ```bash
   # Test unauthenticated access (should fail)
   curl -X GET http://localhost:8000/api/v1/reports/designer/templates
   
   # Test with valid token (should succeed)
   curl -X GET http://localhost:8000/api/v1/reports/designer/templates \
        -H "Authorization: Bearer <valid_token>"
   ```

2. **Role-Based Access Testing**:
   ```python
   # Test with different user roles
   # Ensure analysts can create reports
   # Ensure viewers can only read
   # Ensure proper organization isolation
   ```

3. **Session Security Testing**:
   ```python
   # Test session isolation between users
   # Test organization-scoped access
   # Test session timeout and cleanup
   ```

### Functional Testing

1. **Designer Workflow**:
   - Create session
   - Create template
   - Add components
   - Generate preview
   - Save template
   - Export report

2. **Multi-User Testing**:
   - Concurrent session handling
   - Template sharing (future)
   - Organization isolation

## Security Considerations

### Data Protection
- **Template Isolation**: Templates scoped to organizations
- **Session Security**: User-specific session management
- **Audit Trail**: Complete operation logging
- **Input Validation**: All user inputs validated and sanitized

### Access Control
- **Role-Based**: Permission-based operation access
- **Organization-Scoped**: Multi-tenant data isolation
- **Session-Based**: Temporary design session security
- **Resource-Specific**: Fine-grained permission control

## Performance Considerations

### Optimization Strategies
- **Session Caching**: Redis-based session storage
- **Template Caching**: Preview result caching
- **Lazy Loading**: Component library optimization
- **Async Operations**: Non-blocking preview generation

## Error Handling

### Security Errors
- **401 Unauthorized**: Missing or invalid authentication
- **403 Forbidden**: Insufficient permissions
- **404 Not Found**: Session or template not found
- **409 Conflict**: Session ownership conflicts

### Graceful Degradation
- **Fallback Modes**: Read-only access for insufficient permissions
- **Error Recovery**: Session state recovery
- **User Feedback**: Clear error messages without security leaks

## Deployment Steps

1. **Update RBAC System**: Add REPORTS resource and permissions
2. **Deploy API Changes**: Update designer API with security decorators
3. **Register Router**: Add designer router to main application
4. **Test Security**: Validate authentication and authorization
5. **Monitor Operations**: Enable audit logging and monitoring

## Success Metrics

- [ ] All designer endpoints require authentication
- [ ] Role-based access control working properly
- [ ] Organization-scoped template isolation
- [ ] Complete audit trail for operations
- [ ] Zero security vulnerabilities in testing
- [ ] Performance within acceptable limits (<2s preview generation)

This integration maintains the security excellence established by the P3-001 RBAC implementation while enabling the powerful P2-040 Dynamic Report Designer capabilities.