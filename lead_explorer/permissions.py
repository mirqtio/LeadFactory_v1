"""
Permission system for Lead Explorer Badge Management (P0-021)

Provides role-based access control for badge management operations,
with specific support for CPO (Chief Product Officer) permissions.
"""
from typing import Dict, List, Set

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from account_management.models import AccountUser, Permission, PermissionAction, ResourceType, Role
from core.logging import get_logger

logger = get_logger("lead_explorer_permissions")


class BadgePermissions:
    """Badge management permissions for CPO role system"""
    
    # System-level badge permissions
    SYSTEM_BADGE_PERMISSIONS = {
        "cpo": {
            "badge": ["create", "read", "update", "delete"],
            "lead_badge": ["create", "read", "update", "delete"],
            "system_badge": ["create", "read", "update", "delete"]  # System badges
        },
        "sales_manager": {
            "badge": ["create", "read", "update"],
            "lead_badge": ["create", "read", "update", "delete"],
            "system_badge": ["read"]  # Can't modify system badges
        },
        "sales_rep": {
            "badge": ["read"],
            "lead_badge": ["create", "read", "update"],
            "system_badge": ["read"]
        },
        "analyst": {
            "badge": ["read"],
            "lead_badge": ["read"],
            "system_badge": ["read"]
        },
        "admin": {
            "badge": ["create", "read", "update", "delete"],
            "lead_badge": ["create", "read", "update", "delete"],
            "system_badge": ["create", "read", "update", "delete"]
        }
    }
    
    # Badge type restrictions by role
    BADGE_TYPE_RESTRICTIONS = {
        "sales_rep": ["priority", "contacted", "follow_up", "custom"],
        "sales_manager": ["priority", "qualified", "contacted", "opportunity", "follow_up", "demo_scheduled", "proposal_sent", "custom"],
        "cpo": ["priority", "qualified", "contacted", "opportunity", "customer", "blocked", "follow_up", "demo_scheduled", "proposal_sent", "custom"],
        "analyst": [],  # Read-only
        "admin": ["priority", "qualified", "contacted", "opportunity", "customer", "blocked", "follow_up", "demo_scheduled", "proposal_sent", "custom"]
    }


def get_user_role(user: AccountUser, db: Session) -> str:
    """
    Get the user's primary role for badge management.
    
    Args:
        user: Authenticated user
        db: Database session
    
    Returns:
        str: User's primary role
    """
    # Check if user has explicit CPO role
    if user.full_name and "cpo" in user.full_name.lower():
        return "cpo"
    
    # Check if user has admin role
    if user.email and "admin" in user.email.lower():
        return "admin"
    
    # Check user's organization settings for role
    if user.organization and user.organization.settings:
        user_settings = user.organization.settings.get("users", {}).get(user.id, {})
        if "role" in user_settings:
            return user_settings["role"]
    
    # Default role based on email domain or patterns
    if user.email:
        if "sales" in user.email.lower():
            return "sales_rep"
        elif "manager" in user.email.lower():
            return "sales_manager"
        elif "analyst" in user.email.lower():
            return "analyst"
    
    # Default to basic sales rep
    return "sales_rep"


def check_badge_permission(user: AccountUser, action: str, resource: str, db: Session) -> bool:
    """
    Check if user has permission for badge management action.
    
    Args:
        user: Authenticated user
        action: Action to check (create, read, update, delete)
        resource: Resource type (badge, lead_badge, system_badge)
        db: Database session
    
    Returns:
        bool: True if user has permission
    """
    user_role = get_user_role(user, db)
    
    # Check if role has permission for this action/resource
    role_permissions = BadgePermissions.SYSTEM_BADGE_PERMISSIONS.get(user_role, {})
    resource_permissions = role_permissions.get(resource, [])
    
    has_permission = action in resource_permissions
    
    logger.info(f"Permission check: user={user.email}, role={user_role}, action={action}, resource={resource}, granted={has_permission}")
    
    return has_permission


def check_badge_type_permission(user: AccountUser, badge_type: str, db: Session) -> bool:
    """
    Check if user can work with specific badge types.
    
    Args:
        user: Authenticated user
        badge_type: Badge type to check
        db: Database session
    
    Returns:
        bool: True if user can work with this badge type
    """
    user_role = get_user_role(user, db)
    
    # Get allowed badge types for this role
    allowed_types = BadgePermissions.BADGE_TYPE_RESTRICTIONS.get(user_role, [])
    
    # CPO and admin can work with all badge types
    if user_role in ["cpo", "admin"]:
        return True
    
    # Check if badge type is allowed for this role
    has_permission = badge_type in allowed_types
    
    logger.info(f"Badge type permission check: user={user.email}, role={user_role}, badge_type={badge_type}, granted={has_permission}")
    
    return has_permission


def require_badge_permission(action: str, resource: str = "badge"):
    """
    Decorator to require badge management permission.
    
    Args:
        action: Required action (create, read, update, delete)
        resource: Resource type (badge, lead_badge, system_badge)
    
    Returns:
        Decorator function
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Extract user and db from function arguments
            user = kwargs.get("current_user")
            db = kwargs.get("db")
            
            if not user or not db:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Missing user or database context"
                )
            
            # Check permission
            if not check_badge_permission(user, action, resource, db):
                user_role = get_user_role(user, db)
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions. Role '{user_role}' cannot '{action}' '{resource}'"
                )
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


def require_badge_type_permission(badge_type: str):
    """
    Decorator to require permission for specific badge types.
    
    Args:
        badge_type: Badge type to check
    
    Returns:
        Decorator function
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Extract user and db from function arguments
            user = kwargs.get("current_user")
            db = kwargs.get("db")
            
            if not user or not db:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Missing user or database context"
                )
            
            # Check badge type permission
            if not check_badge_type_permission(user, badge_type, db):
                user_role = get_user_role(user, db)
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Role '{user_role}' cannot work with badge type '{badge_type}'"
                )
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


def get_user_badge_permissions(user: AccountUser, db: Session) -> Dict[str, List[str]]:
    """
    Get all badge permissions for a user.
    
    Args:
        user: Authenticated user
        db: Database session
    
    Returns:
        Dict[str, List[str]]: Permissions by resource type
    """
    user_role = get_user_role(user, db)
    permissions = BadgePermissions.SYSTEM_BADGE_PERMISSIONS.get(user_role, {})
    allowed_types = BadgePermissions.BADGE_TYPE_RESTRICTIONS.get(user_role, [])
    
    result = {
        "role": user_role,
        "permissions": permissions,
        "allowed_badge_types": allowed_types,
        "can_manage_system_badges": user_role in ["cpo", "admin"]
    }
    
    return result


def filter_badges_by_permission(user: AccountUser, badges: List, db: Session) -> List:
    """
    Filter badges based on user permissions.
    
    Args:
        user: Authenticated user
        badges: List of badge objects
        db: Database session
    
    Returns:
        List: Filtered badges
    """
    user_role = get_user_role(user, db)
    
    # CPO and admin can see all badges
    if user_role in ["cpo", "admin"]:
        return badges
    
    # Filter based on badge type permissions
    allowed_types = BadgePermissions.BADGE_TYPE_RESTRICTIONS.get(user_role, [])
    
    filtered_badges = []
    for badge in badges:
        # Check if user can work with this badge type
        if hasattr(badge, 'badge_type') and badge.badge_type.value in allowed_types:
            filtered_badges.append(badge)
        # Always show badges they can read
        elif check_badge_permission(user, "read", "badge", db):
            filtered_badges.append(badge)
    
    return filtered_badges


class BadgePermissionMiddleware:
    """Middleware for badge permission checking"""
    
    @staticmethod
    def check_create_badge_permission(user: AccountUser, badge_data: dict, db: Session) -> None:
        """
        Check if user can create a badge with given data.
        
        Args:
            user: Authenticated user
            badge_data: Badge creation data
            db: Database session
        
        Raises:
            HTTPException: If user lacks permission
        """
        # Check basic create permission
        if not check_badge_permission(user, "create", "badge", db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to create badges"
            )
        
        # Check badge type permission
        badge_type = badge_data.get("badge_type")
        if badge_type and not check_badge_type_permission(user, badge_type, db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Cannot create badges of type '{badge_type}'"
            )
        
        # Check system badge permission
        is_system = badge_data.get("is_system", False)
        if is_system and not check_badge_permission(user, "create", "system_badge", db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to create system badges"
            )
    
    @staticmethod
    def check_assign_badge_permission(user: AccountUser, badge_id: str, lead_id: str, db: Session) -> None:
        """
        Check if user can assign a badge to a lead.
        
        Args:
            user: Authenticated user
            badge_id: Badge ID to assign
            lead_id: Lead ID to assign to
            db: Database session
        
        Raises:
            HTTPException: If user lacks permission
        """
        # Check basic assign permission
        if not check_badge_permission(user, "create", "lead_badge", db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to assign badges"
            )
        
        # Get badge to check type permission
        from .repository import BadgeRepository
        badge_repo = BadgeRepository(db)
        badge = badge_repo.get_badge_by_id(badge_id)
        
        if not badge:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Badge not found"
            )
        
        # Check badge type permission
        if not check_badge_type_permission(user, badge.badge_type.value, db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Cannot assign badges of type '{badge.badge_type.value}'"
            )