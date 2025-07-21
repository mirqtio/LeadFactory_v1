"""
Authentication Middleware for Account Management
Provides authentication and authorization middleware
"""

from fastapi import HTTPException, Request, status
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session

from account_management.auth_service import AuthService
from account_management.models import AccountAuditLog, AccountUser, PermissionAction, ResourceType, UserStatus
from core.logging import get_logger
from database.base import get_db

logger = get_logger(__name__)

# Security scheme
security = HTTPBearer(auto_error=False)


class AuthMiddleware:
    """Authentication middleware for request processing"""

    @staticmethod
    async def get_current_user_from_token(token: str, db: Session) -> AccountUser | None:
        """Extract current user from JWT token"""
        try:
            payload = AuthService.decode_token(token)

            if payload.get("type") != "access":
                return None

            user_id = payload.get("sub")
            if not user_id:
                return None

            user = (
                db.query(AccountUser).filter(AccountUser.id == user_id, AccountUser.status == UserStatus.ACTIVE).first()
            )

            return user

        except Exception as e:
            logger.debug(f"Token validation failed: {str(e)}")
            return None

    @staticmethod
    async def get_current_user_from_api_key(api_key: str, db: Session) -> AccountUser | None:
        """Extract current user from API key"""
        key = AuthService.validate_api_key(db, api_key)

        if not key:
            return None

        user = (
            db.query(AccountUser).filter(AccountUser.id == key.user_id, AccountUser.status == UserStatus.ACTIVE).first()
        )

        return user

    @staticmethod
    async def authenticate_request(request: Request, db: Session) -> AccountUser | None:
        """
        Authenticate request using either JWT token or API key

        Checks in order:
        1. Authorization header with Bearer token
        2. Authorization header with API key
        3. X-API-Key header

        Returns:
            AccountUser if authenticated, None otherwise
        """
        auth_header = request.headers.get("Authorization")

        # Check Bearer token
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            user = await AuthMiddleware.get_current_user_from_token(token, db)
            if user:
                return user

        # Check API key in Authorization header
        if auth_header and auth_header.startswith("ApiKey "):
            api_key = auth_header.split(" ")[1]
            user = await AuthMiddleware.get_current_user_from_api_key(api_key, db)
            if user:
                return user

        # Check X-API-Key header
        api_key_header = request.headers.get("X-API-Key")
        if api_key_header:
            user = await AuthMiddleware.get_current_user_from_api_key(api_key_header, db)
            if user:
                return user

        return None


class PermissionChecker:
    """Check user permissions for resources"""

    def __init__(self, resource: ResourceType, action: PermissionAction):
        self.resource = resource
        self.action = action

    async def __call__(self, request: Request, db: Session = next(get_db())) -> AccountUser:
        """
        Check if user has required permission

        Returns:
            AccountUser if authorized

        Raises:
            HTTPException if not authorized
        """
        # Authenticate user
        user = await AuthMiddleware.authenticate_request(request, db)

        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

        # Check permission
        has_permission = await self.check_user_permission(user, db)

        if not has_permission:
            # Log unauthorized access attempt
            audit_log = AccountAuditLog(
                user_id=user.id,
                organization_id=user.organization_id,
                action=f"UNAUTHORIZED_{self.action.value.upper()}",
                resource_type=self.resource.value,
                ip_address=request.client.host,
                user_agent=request.headers.get("User-Agent"),
                details={
                    "required_permission": f"{self.resource.value}:{self.action.value}",
                    "user_roles": [r.name for r in user.roles] if hasattr(user, "roles") else [],
                },
            )
            db.add(audit_log)
            db.commit()

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {self.resource.value}:{self.action.value}",
            )

        return user

    async def check_user_permission(self, user: AccountUser, db: Session) -> bool:
        """
        Check if user has specific permission

        Args:
            user: User to check
            db: Database session

        Returns:
            bool: True if user has permission
        """
        # TODO: Implement actual permission checking logic
        # For now, return True for all authenticated users
        # In production, this should check user roles and permissions

        # Example implementation:
        # 1. Get user's roles (global, organization, team)
        # 2. Get permissions for those roles
        # 3. Check if required permission exists

        return True


class OrganizationMemberChecker:
    """Check if user is member of organization"""

    def __init__(self, allow_no_org: bool = False):
        self.allow_no_org = allow_no_org

    async def __call__(self, request: Request, db: Session = next(get_db())) -> AccountUser:
        """
        Check if user is member of an organization

        Returns:
            AccountUser if authorized

        Raises:
            HTTPException if not authorized
        """
        # Authenticate user
        user = await AuthMiddleware.authenticate_request(request, db)

        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

        if not user.organization_id and not self.allow_no_org:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User must be member of an organization")

        return user


class AuditLogger:
    """Middleware for logging API actions"""

    @staticmethod
    async def log_action(
        request: Request,
        user: AccountUser,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        details: dict | None = None,
        db: Session = next(get_db()),
    ):
        """
        Log an API action to audit log

        Args:
            request: FastAPI request
            user: User performing action
            action: Action performed (e.g., "CREATE", "UPDATE")
            resource_type: Type of resource affected
            resource_id: ID of specific resource
            details: Additional details to log
            db: Database session
        """
        audit_log = AccountAuditLog(
            user_id=user.id,
            organization_id=user.organization_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=request.client.host,
            user_agent=request.headers.get("User-Agent"),
            details=details,
        )

        db.add(audit_log)
        db.commit()


# Dependency injection helpers
async def get_optional_user(request: Request, db: Session = next(get_db())) -> AccountUser | None:
    """Get current user if authenticated, None otherwise"""
    return await AuthMiddleware.authenticate_request(request, db)


async def require_user(request: Request, db: Session = next(get_db())) -> AccountUser:
    """Require authenticated user"""
    user = await AuthMiddleware.authenticate_request(request, db)

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    return user


async def require_organization_member(request: Request, db: Session = next(get_db())) -> AccountUser:
    """Require user to be member of organization"""
    user = await require_user(request, db)

    if not user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User must be member of an organization")

    return user


# Permission dependency creators
def require_permission(resource: ResourceType, action: PermissionAction):
    """Create dependency that requires specific permission"""
    return PermissionChecker(resource, action)


# Common permission dependencies
require_lead_read = require_permission(ResourceType.LEAD, PermissionAction.READ)
require_lead_create = require_permission(ResourceType.LEAD, PermissionAction.CREATE)
require_lead_update = require_permission(ResourceType.LEAD, PermissionAction.UPDATE)
require_lead_delete = require_permission(ResourceType.LEAD, PermissionAction.DELETE)

require_report_read = require_permission(ResourceType.REPORT, PermissionAction.READ)
require_report_create = require_permission(ResourceType.REPORT, PermissionAction.CREATE)

require_user_read = require_permission(ResourceType.USER, PermissionAction.READ)
require_user_update = require_permission(ResourceType.USER, PermissionAction.UPDATE)
require_user_delete = require_permission(ResourceType.USER, PermissionAction.DELETE)

require_organization_read = require_permission(ResourceType.ORGANIZATION, PermissionAction.READ)
require_organization_update = require_permission(ResourceType.ORGANIZATION, PermissionAction.UPDATE)

require_billing_read = require_permission(ResourceType.BILLING, PermissionAction.READ)
require_billing_update = require_permission(ResourceType.BILLING, PermissionAction.UPDATE)
