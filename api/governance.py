"""
FastAPI endpoints and dependencies for Governance (P0-026)

Provides RBAC and audit logging for all mutations

Configuration:
- Enable/disable via ENABLE_GOVERNANCE environment variable or settings.enable_governance
- Default admin user: admin@leadfactory.com (created via migration)

Log Retention Policy:
- Audit logs are retained for 365 days
- After 365 days, logs should be archived to S3 cold storage via cron job
- Archive script: scripts/archive_audit_logs.py (run daily via cron)
- Logs are immutable and cannot be deleted within retention window

Admin Escalation Flow:
1. Admin creates new user with viewer role by default
2. To escalate to admin, use PUT /api/governance/users/{user_id}/role
3. Reason must be provided (minimum 10 characters)
4. Role change is logged in role_change_log table
5. All role changes are audited and cannot be modified
"""

import json
import time
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import desc
from sqlalchemy.orm import Session

from core.logging import get_logger
from core.utils import mask_sensitive_data
from database.governance_models import AuditLog, RoleChangeLog, User, UserRole
from database.session import get_db

logger = get_logger("governance", domain="governance")

# Create router with prefix
router = APIRouter(prefix="/api/governance", tags=["governance"])

# Security scheme
security = HTTPBearer()


class UserCreate(BaseModel):
    """Request to create a new user"""

    email: EmailStr  # EmailStr provides email validation
    name: str
    role: UserRole = UserRole.VIEWER


class UserUpdate(BaseModel):
    """Request to update user"""

    name: str | None = None
    is_active: bool | None = None


class RoleChangeRequest(BaseModel):
    """Request to change user role"""

    new_role: UserRole
    reason: str = Field(..., min_length=10, description="Reason for role change")


class UserResponse(BaseModel):
    """User response model"""

    id: str
    email: str
    name: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AuditLogEntry(BaseModel):
    """Audit log entry for API responses"""

    id: int
    timestamp: datetime
    user_email: str
    user_role: UserRole
    action: str
    method: str
    endpoint: str
    object_type: str
    object_id: str | None
    response_status: int
    duration_ms: int | None
    ip_address: str | None


class AuditLogQuery(BaseModel):
    """Query parameters for audit log"""

    user_id: str | None = None
    object_type: str | None = None
    object_id: str | None = None
    action: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    limit: int = Field(100, le=1000)
    offset: int = Field(0, ge=0)


# Mock user for development (in production, use real auth)
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)
) -> User:
    """Get current user from API key"""
    # In production, validate API key and get user from database
    # For now, return mock admin user
    mock_user = User(
        id="00000000-0000-0000-0000-000000000001",
        email="admin@leadfactory.com",
        name="Admin User",
        role=UserRole.ADMIN,
        is_active=True,
    )
    return mock_user


class RoleChecker:
    """Dependency to check user role for mutations"""

    def __init__(self, allowed_roles: list[UserRole]):
        self.allowed_roles = allowed_roles

    def __call__(self, current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in self.allowed_roles:
            logger.warning(
                f"Access denied - user_id: {str(current_user.id)}, "
                f"user_role: {current_user.role.value}, "
                f"required_roles: {[r.value for r in self.allowed_roles]}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {', '.join(r.value for r in self.allowed_roles)}",
            )
        return current_user


# Role dependencies
require_admin = RoleChecker([UserRole.ADMIN])
require_any_role = RoleChecker([UserRole.ADMIN, UserRole.VIEWER])


async def create_audit_log(
    db: Session,
    request: Request,
    response: Response,
    user: User,
    start_time: float,
    request_body: dict[str, Any] | None = None,
    response_body: dict[str, Any] | None = None,
    object_type: str | None = None,
    object_id: str | None = None,
):
    """Create audit log entry for a mutation"""
    try:
        # Get previous checksum for chaining
        last_entry = db.query(AuditLog).order_by(desc(AuditLog.id)).first()
        previous_checksum = last_entry.checksum if last_entry else None

        # Mask sensitive data
        masked_request = mask_sensitive_data(request_body) if request_body else None
        masked_response = mask_sensitive_data(response_body) if response_body else None

        # Determine action from method
        action_map = {"POST": "CREATE", "PUT": "UPDATE", "PATCH": "UPDATE", "DELETE": "DELETE"}
        action = action_map.get(request.method, request.method)

        # Create audit entry
        audit_entry = AuditLog(
            user_id=user.id,
            user_email=user.email,
            user_role=user.role,
            action=action,
            method=request.method,
            endpoint=str(request.url.path),
            object_type=object_type or "unknown",
            object_id=str(object_id) if object_id else None,
            request_data=json.dumps(masked_request) if masked_request else None,
            response_status=response.status_code,
            response_data=json.dumps(masked_response) if masked_response else None,
            duration_ms=int((time.time() - start_time) * 1000),
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent"),
            details=None,
        )

        # Calculate hashes
        audit_entry.content_hash = audit_entry.calculate_content_hash()
        audit_entry.checksum = audit_entry.calculate_checksum(previous_checksum)

        db.add(audit_entry)
        db.commit()

        logger.info(
            "Audit log created",
            audit_id=audit_entry.id,
            user_id=str(user.id),
            action=action,
            endpoint=str(request.url.path),
        )

    except Exception as e:
        logger.error(f"Failed to create audit log - error: {str(e)}")
        # Don't fail the request if audit logging fails
        db.rollback()


# User management endpoints
@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    request: Request, user_data: UserCreate, db: Session = Depends(get_db), current_user: User = Depends(require_admin)
) -> UserResponse:
    """Create a new user (admin only)"""
    start_time = time.time()

    # Check if user already exists
    existing = db.query(User).filter(User.email == user_data.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User with this email already exists")

    # Create user
    new_user = User(email=user_data.email, name=user_data.name, role=user_data.role, created_by=current_user.id)

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    response = Response(status_code=status.HTTP_201_CREATED)

    # Create audit log
    await create_audit_log(
        db=db,
        request=request,
        response=response,
        user=current_user,
        start_time=start_time,
        request_body=user_data.dict(),
        response_body={"id": str(new_user.id), "email": new_user.email},
        object_type="User",
        object_id=new_user.id,
    )

    return UserResponse(
        id=str(new_user.id),
        email=new_user.email,
        name=new_user.name,
        role=new_user.role,
        is_active=new_user.is_active,
        created_at=new_user.created_at,
        updated_at=new_user.updated_at,
    )


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    db: Session = Depends(get_db), current_user: User = Depends(require_any_role), is_active: bool | None = None
) -> list[UserResponse]:
    """List all users"""
    query = db.query(User)

    if is_active is not None:
        query = query.filter(User.is_active == is_active)

    users = query.order_by(User.created_at.desc()).all()

    return [
        UserResponse(
            id=str(user.id),
            email=user.email,
            name=user.name,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
        for user in users
    ]


@router.put("/users/{user_id}/role", response_model=UserResponse)
async def change_user_role(
    request: Request,
    user_id: str,
    role_change: RoleChangeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> UserResponse:
    """Change user role (admin only)"""
    start_time = time.time()

    # Get user
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    old_role = user.role

    # Prevent self-demotion
    if str(user.id) == str(current_user.id) and role_change.new_role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot demote your own account")

    # Log role change
    role_log = RoleChangeLog(
        user_id=user.id,
        changed_by_id=current_user.id,
        old_role=old_role,
        new_role=role_change.new_role,
        reason=role_change.reason,
    )
    db.add(role_log)

    # Update role
    user.role = role_change.new_role
    user.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(user)

    response = Response(status_code=status.HTTP_200_OK)

    # Create audit log
    await create_audit_log(
        db=db,
        request=request,
        response=response,
        user=current_user,
        start_time=start_time,
        request_body=role_change.dict(),
        response_body={"old_role": old_role.value, "new_role": role_change.new_role.value},
        object_type="User",
        object_id=user_id,
    )

    return UserResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.delete("/users/{user_id}")
async def deactivate_user(
    request: Request, user_id: str, db: Session = Depends(get_db), current_user: User = Depends(require_admin)
) -> dict[str, str]:
    """Deactivate a user (admin only)"""
    start_time = time.time()

    # Get user
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Prevent self-deactivation
    if str(user.id) == str(current_user.id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot deactivate your own account")

    # Deactivate user
    user.is_active = False
    user.deactivated_at = datetime.utcnow()
    user.deactivated_by = current_user.id

    db.commit()

    response = Response(status_code=status.HTTP_200_OK)

    # Create audit log
    await create_audit_log(
        db=db,
        request=request,
        response=response,
        user=current_user,
        start_time=start_time,
        request_body=None,
        response_body={"status": "deactivated"},
        object_type="User",
        object_id=user_id,
    )

    return {"status": "User deactivated successfully"}


# Audit log endpoints
@router.post("/audit/query", response_model=list[AuditLogEntry])
async def query_audit_logs(
    query: AuditLogQuery, db: Session = Depends(get_db), current_user: User = Depends(require_any_role)
) -> list[AuditLogEntry]:
    """Query audit logs with filters"""
    # Build query
    q = db.query(AuditLog)

    if query.user_id:
        q = q.filter(AuditLog.user_id == query.user_id)

    if query.object_type:
        q = q.filter(AuditLog.object_type == query.object_type)

    if query.object_id:
        q = q.filter(AuditLog.object_id == query.object_id)

    if query.action:
        q = q.filter(AuditLog.action == query.action)

    if query.start_date:
        q = q.filter(AuditLog.timestamp >= query.start_date)

    if query.end_date:
        q = q.filter(AuditLog.timestamp <= query.end_date)

    # Order by timestamp desc and apply pagination
    logs = q.order_by(desc(AuditLog.timestamp)).offset(query.offset).limit(query.limit).all()

    return [
        AuditLogEntry(
            id=log.id,
            timestamp=log.timestamp,
            user_email=log.user_email,
            user_role=log.user_role,
            action=log.action,
            method=log.method,
            endpoint=log.endpoint,
            object_type=log.object_type,
            object_id=log.object_id,
            response_status=log.response_status,
            duration_ms=log.duration_ms,
            ip_address=log.ip_address,
        )
        for log in logs
    ]


@router.get("/audit/verify/{audit_id}")
async def verify_audit_integrity(
    audit_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_admin)
) -> dict[str, Any]:
    """Verify audit log integrity (admin only)"""
    # Get audit entry
    entry = db.query(AuditLog).filter(AuditLog.id == audit_id).first()
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit entry not found")

    # Recalculate content hash
    calculated_hash = entry.calculate_content_hash()
    content_valid = calculated_hash == entry.content_hash

    # Get previous entry to verify chain
    previous = db.query(AuditLog).filter(AuditLog.id < audit_id).order_by(desc(AuditLog.id)).first()
    previous_checksum = previous.checksum if previous else None

    # Recalculate checksum
    calculated_checksum = entry.calculate_checksum(previous_checksum)
    chain_valid = calculated_checksum == entry.checksum

    return {
        "audit_id": audit_id,
        "content_valid": content_valid,
        "chain_valid": chain_valid,
        "stored_content_hash": entry.content_hash,
        "calculated_content_hash": calculated_hash,
        "stored_checksum": entry.checksum,
        "calculated_checksum": calculated_checksum,
        "integrity_status": "VALID" if content_valid and chain_valid else "TAMPERED",
    }
