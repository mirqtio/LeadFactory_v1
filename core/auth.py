"""Authentication utilities for FastAPI routes with RBAC support"""
import os
from typing import TYPE_CHECKING, Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from account_management.auth_service import AuthService
from account_management.models import AccountUser, APIKey, UserStatus
from core.config import settings
from core.logging import get_logger
from database.session import get_db

if TYPE_CHECKING:
    from core.rbac import Permission, RBACService, Resource, Role

logger = get_logger(__name__)
security = HTTPBearer()

# Import RBAC system for integration
try:
    from core.rbac import Permission, RBACService, Resource, Role

    RBAC_ENABLED = True
except ImportError:
    logger.warning("RBAC system not available")
    RBAC_ENABLED = False
    # Define stub types for when RBAC is not available
    Permission = None
    Resource = None
    Role = None
    RBACService = None


def get_current_user_dependency(
    credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)
) -> AccountUser:
    """FastAPI dependency to get current authenticated user

    Args:
        credentials: HTTP authorization credentials
        db: Database session

    Returns:
        AccountUser: Authenticated user object

    Raises:
        HTTPException: If authentication fails
    """
    token = credentials.credentials

    # Try JWT token first
    if token.startswith("lf_"):
        # This is an API key
        user = get_current_user_from_api_key(token, db)
    else:
        # This is a JWT token
        user = get_current_user_from_token(token, db)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security), db: Session = Depends(get_db)
) -> Optional[AccountUser]:
    """FastAPI dependency to get current authenticated user (optional)

    Args:
        credentials: HTTP authorization credentials (optional)
        db: Database session

    Returns:
        Optional[AccountUser]: Authenticated user object or None
    """
    if not credentials:
        return None

    try:
        return get_current_user_dependency(credentials, db)
    except HTTPException:
        return None


def require_organization_access(user: AccountUser = Depends(get_current_user_dependency)) -> str:
    """FastAPI dependency to require organization access

    Args:
        user: Authenticated user

    Returns:
        str: Organization ID

    Raises:
        HTTPException: If user has no organization access
    """
    if not user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization access required")

    return user.organization_id


def verify_internal_token(token: str) -> bool:
    """Verify internal authentication token

    Args:
        token: The token to verify

    Returns:
        bool: True if token is valid, False otherwise
    """
    # Get expected token from environment
    expected_token = os.environ.get("INTERNAL_API_TOKEN", "internal-token-default")

    # In test environment, accept default token
    if os.environ.get("ENVIRONMENT") == "test":
        return token in [expected_token, "test-token"]

    return token == expected_token


def get_current_user_from_token(token: str, db: Session) -> Optional[AccountUser]:
    """Get current authenticated user from JWT token

    Args:
        token: JWT token
        db: Database session

    Returns:
        Optional[AccountUser]: User object if authenticated, None otherwise
    """
    try:
        # Decode JWT token
        payload = AuthService.decode_token(token)
        user_id = payload.get("sub")

        if not user_id:
            logger.warning("Token missing user ID")
            return None

        # Get user from database
        user = db.query(AccountUser).filter(AccountUser.id == user_id, AccountUser.status == UserStatus.ACTIVE).first()

        if not user:
            logger.warning(f"User not found or inactive: {user_id}")
            return None

        return user

    except jwt.ExpiredSignatureError:
        logger.warning("Token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {e}")
        return None
    except Exception as e:
        logger.error(f"Token verification failed: {e}")
        return None


def get_current_user_from_api_key(api_key: str, db: Session) -> Optional[AccountUser]:
    """Get current authenticated user from API key

    Args:
        api_key: API key
        db: Database session

    Returns:
        Optional[AccountUser]: User object if authenticated, None otherwise
    """
    try:
        # Validate API key
        key_obj = AuthService.validate_api_key(db, api_key)

        if not key_obj:
            logger.warning("Invalid API key")
            return None

        # Get user from API key
        user = (
            db.query(AccountUser)
            .filter(AccountUser.id == key_obj.user_id, AccountUser.status == UserStatus.ACTIVE)
            .first()
        )

        if not user:
            logger.warning(f"User not found or inactive: {key_obj.user_id}")
            return None

        return user

    except Exception as e:
        logger.error(f"API key verification failed: {e}")
        return None


def get_current_user() -> Optional[str]:
    """Get current authenticated user (legacy method)

    Returns:
        Optional[str]: Username if authenticated, None otherwise
    """
    # TODO: Implement actual user authentication
    return "system"


def get_current_user_with_rbac(
    permission: Optional["Permission"] = None,
    resource: Optional["Resource"] = None,
    required_role: Optional["Role"] = None,
):
    """
    Enhanced authentication dependency with RBAC support

    Args:
        permission: Required permission for access
        resource: Target resource for permission check
        required_role: Minimum required role

    Returns:
        Dependency function that returns authenticated user with RBAC validation
    """

    def dependency(
        credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)
    ) -> AccountUser:
        # First, authenticate the user
        user = get_current_user_dependency(credentials, db)

        if not RBAC_ENABLED:
            logger.warning("RBAC not enabled, skipping authorization checks")
            return user

        # Perform RBAC checks if specified
        if required_role:
            user_role = RBACService.get_user_role(user, db)
            role_hierarchy = {
                Role.GUEST: 0,
                Role.VIEWER: 1,
                Role.SALES_REP: 2,
                Role.MARKETING_USER: 2,
                Role.ANALYST: 3,
                Role.TEAM_LEAD: 4,
                Role.MANAGER: 5,
                Role.ADMIN: 6,
                Role.SUPER_ADMIN: 7,
            }

            user_level = role_hierarchy.get(user_role, 0)
            required_level = role_hierarchy.get(required_role, 0)

            if user_level < required_level:
                logger.warning(
                    f"Role access denied: user={user.email}, role={user_role.value}, required={required_role.value}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail=f"Insufficient role. Required: {required_role.value}"
                )

        if permission:
            if not RBACService.has_permission(user, permission, resource, db):
                user_role = RBACService.get_user_role(user, db)
                logger.warning(
                    f"Permission denied: user={user.email}, role={user_role.value}, permission={permission.value}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions. Required: {permission.value}"
                    + (f" on {resource.value}" if resource else ""),
                )

        return user

    return dependency


# Convenience functions for common RBAC patterns
def require_authenticated_user():
    """Require any authenticated user"""
    return Depends(get_current_user_dependency)


def require_read_permission(resource: Optional["Resource"] = None):
    """Require read permission on resource"""
    if RBAC_ENABLED:
        return get_current_user_with_rbac(permission=Permission.READ, resource=resource)
    return require_authenticated_user()


def require_write_permission(resource: Optional["Resource"] = None):
    """Require create/update permission on resource"""
    if RBAC_ENABLED:
        return get_current_user_with_rbac(permission=Permission.CREATE, resource=resource)
    return require_authenticated_user()


def require_delete_permission(resource: Optional["Resource"] = None):
    """Require delete permission on resource"""
    if RBAC_ENABLED:
        return get_current_user_with_rbac(permission=Permission.DELETE, resource=resource)
    return require_authenticated_user()


def require_admin_role():
    """Require admin role or higher"""
    if RBAC_ENABLED:
        return get_current_user_with_rbac(required_role=Role.ADMIN)
    return require_authenticated_user()


def require_manager_role():
    """Require manager role or higher"""
    if RBAC_ENABLED:
        return get_current_user_with_rbac(required_role=Role.MANAGER)
    return require_authenticated_user()
