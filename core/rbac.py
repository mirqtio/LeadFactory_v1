"""
Role-Based Access Control (RBAC) system for LeadFactory API endpoints

Comprehensive RBAC implementation providing:
- Role definitions and permission mappings
- Resource-based access control
- FastAPI dependency decorators
- Audit logging for access decisions
- Security enforcement for all API endpoints
"""

import functools
from enum import Enum

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from account_management.models import AccountUser
from core.auth import get_current_user_dependency
from core.logging import get_logger
from database.session import get_db

logger = get_logger("rbac", domain="security")


class Permission(Enum):
    """System permissions"""

    # Resource permissions
    READ = "read"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"

    # Administrative permissions
    ADMIN = "admin"
    MANAGE_USERS = "manage_users"
    MANAGE_ROLES = "manage_roles"

    # Domain-specific permissions
    MANAGE_CAMPAIGNS = "manage_campaigns"
    MANAGE_TARGETING = "manage_targeting"
    MANAGE_REPORTS = "manage_reports"
    MANAGE_ASSESSMENTS = "manage_assessments"
    MANAGE_ORCHESTRATION = "manage_orchestration"
    MANAGE_PERSONALIZATION = "manage_personalization"
    MANAGE_ANALYTICS = "manage_analytics"
    MANAGE_STOREFRONT = "manage_storefront"
    MANAGE_GATEWAY = "manage_gateway"
    MANAGE_LEADS = "manage_leads"
    MANAGE_COLLABORATION = "manage_collaboration"

    # Cost and billing permissions
    VIEW_COSTS = "view_costs"
    MANAGE_COSTS = "manage_costs"

    # System permissions
    VIEW_HEALTH = "view_health"
    MANAGE_SYSTEM = "manage_system"


class Role(Enum):
    """System roles with hierarchical permissions"""

    # Administrative roles
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"

    # Management roles
    MANAGER = "manager"
    TEAM_LEAD = "team_lead"

    # Operational roles
    ANALYST = "analyst"
    SALES_REP = "sales_rep"
    MARKETING_USER = "marketing_user"

    # Read-only roles
    VIEWER = "viewer"
    GUEST = "guest"


class Resource(Enum):
    """Protected resources"""

    # Domain resources
    CAMPAIGNS = "campaigns"
    TARGETING = "targeting"
    LEADS = "leads"
    REPORTS = "reports"
    ASSESSMENTS = "assessments"
    ORCHESTRATION = "orchestration"
    PERSONALIZATION = "personalization"
    ANALYTICS = "analytics"
    STOREFRONT = "storefront"
    GATEWAY = "gateway"
    COLLABORATION = "collaboration"

    # Administrative resources
    USERS = "users"
    ROLES = "roles"
    ORGANIZATIONS = "organizations"

    # System resources
    COSTS = "costs"
    HEALTH = "health"
    SYSTEM = "system"


# Role permission mappings with hierarchical inheritance
ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.SUPER_ADMIN: {
        # Full system access
        Permission.ADMIN,
        Permission.MANAGE_SYSTEM,
        Permission.MANAGE_USERS,
        Permission.MANAGE_ROLES,
        Permission.MANAGE_COSTS,
        Permission.VIEW_COSTS,
        Permission.VIEW_HEALTH,
        # All domain permissions
        Permission.MANAGE_CAMPAIGNS,
        Permission.MANAGE_TARGETING,
        Permission.MANAGE_REPORTS,
        Permission.MANAGE_ASSESSMENTS,
        Permission.MANAGE_ORCHESTRATION,
        Permission.MANAGE_PERSONALIZATION,
        Permission.MANAGE_ANALYTICS,
        Permission.MANAGE_STOREFRONT,
        Permission.MANAGE_GATEWAY,
        Permission.MANAGE_LEADS,
        Permission.MANAGE_COLLABORATION,
        # All CRUD operations
        Permission.CREATE,
        Permission.READ,
        Permission.UPDATE,
        Permission.DELETE,
    },
    Role.ADMIN: {
        # Administrative access without system management
        Permission.MANAGE_USERS,
        Permission.MANAGE_ROLES,
        Permission.VIEW_COSTS,
        Permission.VIEW_HEALTH,
        # Most domain permissions
        Permission.MANAGE_CAMPAIGNS,
        Permission.MANAGE_TARGETING,
        Permission.MANAGE_REPORTS,
        Permission.MANAGE_ASSESSMENTS,
        Permission.MANAGE_PERSONALIZATION,
        Permission.MANAGE_ANALYTICS,
        Permission.MANAGE_LEADS,
        Permission.MANAGE_COLLABORATION,
        # Full CRUD
        Permission.CREATE,
        Permission.READ,
        Permission.UPDATE,
        Permission.DELETE,
    },
    Role.MANAGER: {
        # Management access to business functions
        Permission.VIEW_COSTS,
        Permission.VIEW_HEALTH,
        Permission.MANAGE_CAMPAIGNS,
        Permission.MANAGE_TARGETING,
        Permission.MANAGE_REPORTS,
        Permission.MANAGE_PERSONALIZATION,
        Permission.MANAGE_ANALYTICS,
        Permission.MANAGE_LEADS,
        Permission.MANAGE_COLLABORATION,
        # Full CRUD for managed resources
        Permission.CREATE,
        Permission.READ,
        Permission.UPDATE,
        Permission.DELETE,
    },
    Role.TEAM_LEAD: {
        # Team leadership access
        Permission.VIEW_HEALTH,
        Permission.MANAGE_CAMPAIGNS,
        Permission.MANAGE_TARGETING,
        Permission.MANAGE_LEADS,
        Permission.MANAGE_COLLABORATION,
        # Limited CRUD
        Permission.CREATE,
        Permission.READ,
        Permission.UPDATE,
    },
    Role.ANALYST: {
        # Analytical and reporting access
        Permission.VIEW_HEALTH,
        Permission.MANAGE_REPORTS,
        Permission.MANAGE_ASSESSMENTS,
        Permission.MANAGE_ANALYTICS,
        # Read and create analysis
        Permission.READ,
        Permission.CREATE,
    },
    Role.SALES_REP: {
        # Sales-focused access
        Permission.MANAGE_LEADS,
        Permission.MANAGE_COLLABORATION,
        Permission.MANAGE_PERSONALIZATION,
        # Basic CRUD for assigned resources
        Permission.READ,
        Permission.CREATE,
        Permission.UPDATE,
    },
    Role.MARKETING_USER: {
        # Marketing-focused access
        Permission.MANAGE_CAMPAIGNS,
        Permission.MANAGE_TARGETING,
        Permission.MANAGE_PERSONALIZATION,
        # Basic CRUD for marketing resources
        Permission.READ,
        Permission.CREATE,
        Permission.UPDATE,
    },
    Role.VIEWER: {
        # Read-only access to most resources
        Permission.READ,
        Permission.VIEW_HEALTH,
    },
    Role.GUEST: {
        # Minimal access
        Permission.READ,  # Limited read access to be enforced by resource-specific checks
    },
}

# Resource-permission mappings
RESOURCE_PERMISSIONS: dict[Resource, set[Permission]] = {
    Resource.CAMPAIGNS: {Permission.MANAGE_CAMPAIGNS, Permission.ADMIN},
    Resource.TARGETING: {Permission.MANAGE_TARGETING, Permission.ADMIN},
    Resource.LEADS: {Permission.MANAGE_LEADS, Permission.ADMIN},
    Resource.REPORTS: {Permission.MANAGE_REPORTS, Permission.ADMIN},
    Resource.ASSESSMENTS: {Permission.MANAGE_ASSESSMENTS, Permission.ADMIN},
    Resource.ORCHESTRATION: {Permission.MANAGE_ORCHESTRATION, Permission.ADMIN},
    Resource.PERSONALIZATION: {Permission.MANAGE_PERSONALIZATION, Permission.ADMIN},
    Resource.ANALYTICS: {Permission.MANAGE_ANALYTICS, Permission.ADMIN},
    Resource.STOREFRONT: {Permission.MANAGE_STOREFRONT, Permission.ADMIN},
    Resource.GATEWAY: {Permission.MANAGE_GATEWAY, Permission.ADMIN},
    Resource.COLLABORATION: {Permission.MANAGE_COLLABORATION, Permission.ADMIN},
    Resource.USERS: {Permission.MANAGE_USERS, Permission.ADMIN},
    Resource.ROLES: {Permission.MANAGE_ROLES, Permission.ADMIN},
    Resource.ORGANIZATIONS: {Permission.MANAGE_USERS, Permission.ADMIN},
    Resource.COSTS: {Permission.VIEW_COSTS, Permission.MANAGE_COSTS, Permission.ADMIN},
    Resource.HEALTH: {Permission.VIEW_HEALTH, Permission.ADMIN},
    Resource.SYSTEM: {Permission.MANAGE_SYSTEM, Permission.ADMIN},
}


class RBACService:
    """Service for RBAC operations"""

    @staticmethod
    def get_user_role(user: AccountUser, db: Session) -> Role:
        """
        Determine user's role based on user attributes and organization settings

        Args:
            user: Authenticated user
            db: Database session

        Returns:
            Role: User's primary role
        """
        # Check for super admin (system-level admin)
        if user.email and user.email.lower() in ["admin@leadfactory.com", "superadmin@leadfactory.com"]:
            return Role.SUPER_ADMIN

        # Check explicit role from user metadata or organization settings
        if hasattr(user, "role") and user.role:
            try:
                return Role(user.role.lower())
            except ValueError:
                pass

        # Check organization settings for role
        if user.organization and hasattr(user.organization, "settings") and user.organization.settings:
            user_settings = user.organization.settings.get("users", {}).get(str(user.id), {})
            if "role" in user_settings:
                try:
                    return Role(user_settings["role"].lower())
                except ValueError:
                    pass

        # Role inference from email patterns
        if user.email:
            email_lower = user.email.lower()
            if "admin" in email_lower:
                return Role.ADMIN
            if "manager" in email_lower:
                return Role.MANAGER
            if "lead" in email_lower:
                return Role.TEAM_LEAD
            if "analyst" in email_lower:
                return Role.ANALYST
            if "sales" in email_lower:
                return Role.SALES_REP
            if "marketing" in email_lower:
                return Role.MARKETING_USER

        # Default role for authenticated users
        return Role.VIEWER

    @staticmethod
    def has_permission(
        user: AccountUser, permission: Permission, resource: Resource | None = None, db: Session = None
    ) -> bool:
        """
        Check if user has specific permission for a resource

        Args:
            user: Authenticated user
            permission: Required permission
            resource: Target resource (optional)
            db: Database session

        Returns:
            bool: True if user has permission
        """
        if not db:
            logger.warning("Database session not provided for permission check")
            return False

        user_role = RBACService.get_user_role(user, db)
        user_permissions = ROLE_PERMISSIONS.get(user_role, set())

        # Check direct permission
        has_direct = permission in user_permissions

        # Check resource-specific permissions if resource specified
        has_resource = True
        if resource:
            required_perms = RESOURCE_PERMISSIONS.get(resource, set())
            if required_perms:
                # For READ permission, allow if user has READ permission and org access
                if permission == Permission.READ:
                    has_resource = Permission.READ in user_permissions
                else:
                    has_resource = bool(required_perms.intersection(user_permissions))

        # Check organization membership for organization-scoped resources
        has_org_access = True
        if resource in [Resource.CAMPAIGNS, Resource.TARGETING, Resource.LEADS, Resource.REPORTS]:
            has_org_access = user.organization_id is not None

        result = has_direct and has_resource and has_org_access

        logger.info(
            f"Permission check: user={user.email}, role={user_role.value}, "
            f"permission={permission.value}, resource={resource.value if resource else None}, "
            f"granted={result}"
        )

        return result

    @staticmethod
    def require_permission(permission: Permission, resource: Resource | None = None):
        """
        FastAPI dependency to require specific permission

        Args:
            permission: Required permission
            resource: Target resource (optional)

        Returns:
            Dependency function
        """

        def dependency(
            user: AccountUser = Depends(get_current_user_dependency), db: Session = Depends(get_db)
        ) -> AccountUser:
            if not RBACService.has_permission(user, permission, resource, db):
                user_role = RBACService.get_user_role(user, db)
                logger.warning(
                    f"Access denied: user={user.email}, role={user_role.value}, "
                    f"permission={permission.value}, resource={resource.value if resource else None}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions. Required: {permission.value}"
                    + (f" on {resource.value}" if resource else ""),
                )
            return user

        return dependency

    @staticmethod
    def require_role(required_role: Role):
        """
        FastAPI dependency to require specific role or higher

        Args:
            required_role: Minimum required role

        Returns:
            Dependency function
        """

        def dependency(
            user: AccountUser = Depends(get_current_user_dependency), db: Session = Depends(get_db)
        ) -> AccountUser:
            user_role = RBACService.get_user_role(user, db)

            # Role hierarchy check (simplified - could be more sophisticated)
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
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient role. Required: {required_role.value}, current: {user_role.value}",
                )
            return user

        return dependency


# Convenience dependencies for common permission checks
def require_admin() -> AccountUser:
    """Require admin role"""
    return Depends(RBACService.require_role(Role.ADMIN))


def require_manager() -> AccountUser:
    """Require manager role or higher"""
    return Depends(RBACService.require_role(Role.MANAGER))


def require_read_access(resource: Resource = None) -> AccountUser:
    """Require read permission"""
    return Depends(RBACService.require_permission(Permission.READ, resource))


def require_write_access(resource: Resource = None) -> AccountUser:
    """Require create/update permission"""

    def dependency(
        user: AccountUser = Depends(get_current_user_dependency), db: Session = Depends(get_db)
    ) -> AccountUser:
        if not (
            RBACService.has_permission(user, Permission.CREATE, resource, db)
            or RBACService.has_permission(user, Permission.UPDATE, resource, db)
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Write access required" + (f" for {resource.value}" if resource else ""),
            )
        return user

    return dependency


def require_delete_access(resource: Resource = None) -> AccountUser:
    """Require delete permission"""
    return Depends(RBACService.require_permission(Permission.DELETE, resource))


def require_domain_access(resource: Resource) -> AccountUser:
    """Require domain-specific management permission"""
    permission_map = {
        Resource.CAMPAIGNS: Permission.MANAGE_CAMPAIGNS,
        Resource.TARGETING: Permission.MANAGE_TARGETING,
        Resource.LEADS: Permission.MANAGE_LEADS,
        Resource.REPORTS: Permission.MANAGE_REPORTS,
        Resource.ASSESSMENTS: Permission.MANAGE_ASSESSMENTS,
        Resource.ORCHESTRATION: Permission.MANAGE_ORCHESTRATION,
        Resource.PERSONALIZATION: Permission.MANAGE_PERSONALIZATION,
        Resource.ANALYTICS: Permission.MANAGE_ANALYTICS,
        Resource.STOREFRONT: Permission.MANAGE_STOREFRONT,
        Resource.GATEWAY: Permission.MANAGE_GATEWAY,
        Resource.COLLABORATION: Permission.MANAGE_COLLABORATION,
    }

    permission = permission_map.get(resource, Permission.READ)
    return Depends(RBACService.require_permission(permission, resource))


# Decorator for function-level RBAC
def rbac_required(permission: Permission, resource: Resource | None = None):
    """
    Decorator to enforce RBAC on any function

    Args:
        permission: Required permission
        resource: Target resource (optional)
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Extract user and db from function arguments or kwargs
            user = kwargs.get("current_user") or kwargs.get("user")
            db = kwargs.get("db")

            # Try to find in args if not in kwargs
            if not user or not db:
                for arg in args:
                    if isinstance(arg, AccountUser):
                        user = arg
                    elif hasattr(arg, "query"):  # SQLAlchemy Session
                        db = arg

            if not user or not db:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Missing authentication context"
                )

            if not RBACService.has_permission(user, permission, resource, db):
                user_role = RBACService.get_user_role(user, db)
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied. Role '{user_role.value}' lacks permission '{permission.value}'"
                    + (f" on resource '{resource.value}'" if resource else ""),
                )

            return func(*args, **kwargs)

        return wrapper

    return decorator
