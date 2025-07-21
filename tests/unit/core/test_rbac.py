"""
Unit tests for RBAC (Role-Based Access Control) system

Tests cover:
- Role assignment and hierarchy
- Permission checking and enforcement
- Resource-based access control
- FastAPI dependency integration
- Security audit logging
"""

from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from account_management.models import AccountUser
from core.rbac import (
    Permission,
    RBACService,
    Resource,
    Role,
    rbac_required,
    require_admin,
    require_delete_access,
    require_domain_access,
    require_manager,
    require_read_access,
    require_write_access,
)


@pytest.fixture
def mock_db():
    """Mock database session"""
    return Mock(spec=Session)


@pytest.fixture
def admin_user():
    """Create admin user for testing"""
    user = Mock(spec=AccountUser)
    user.id = "admin-123"
    user.email = "admin@leadfactory.com"
    user.organization_id = "org-123"
    user.organization = Mock()
    user.organization.settings = {}
    return user


@pytest.fixture
def manager_user():
    """Create manager user for testing"""
    user = Mock(spec=AccountUser)
    user.id = "manager-456"
    user.email = "manager@company.com"
    user.organization_id = "org-123"
    user.organization = Mock()
    user.organization.settings = {}
    return user


@pytest.fixture
def sales_user():
    """Create sales rep user for testing"""
    user = Mock(spec=AccountUser)
    user.id = "sales-789"
    user.email = "sales@company.com"
    user.organization_id = "org-123"
    user.organization = Mock()
    user.organization.settings = {}
    return user


@pytest.fixture
def viewer_user():
    """Create viewer user for testing"""
    user = Mock(spec=AccountUser)
    user.id = "viewer-999"
    user.email = "viewer@company.com"
    user.organization_id = "org-123"
    user.organization = Mock()
    user.organization.settings = {}
    return user


@pytest.fixture
def guest_user():
    """Create guest user with no organization"""
    user = Mock(spec=AccountUser)
    user.id = "guest-000"
    user.email = "guest@example.com"
    user.organization_id = None
    user.organization = None
    return user


class TestRoleAssignment:
    """Test role assignment logic"""

    def test_super_admin_role_assignment(self, mock_db):
        """Test super admin role assignment"""
        user = Mock(spec=AccountUser)
        user.email = "admin@leadfactory.com"
        user.organization = None

        role = RBACService.get_user_role(user, mock_db)
        assert role == Role.SUPER_ADMIN

    def test_admin_role_assignment(self, mock_db):
        """Test admin role assignment from email pattern"""
        user = Mock(spec=AccountUser)
        user.email = "admin@company.com"
        user.organization = Mock()
        user.organization.settings = {}

        role = RBACService.get_user_role(user, mock_db)
        assert role == Role.ADMIN

    def test_manager_role_assignment(self, mock_db):
        """Test manager role assignment from email pattern"""
        user = Mock(spec=AccountUser)
        user.email = "manager@company.com"
        user.organization = Mock()
        user.organization.settings = {}

        role = RBACService.get_user_role(user, mock_db)
        assert role == Role.MANAGER

    def test_sales_role_assignment(self, mock_db):
        """Test sales rep role assignment from email pattern"""
        user = Mock(spec=AccountUser)
        user.email = "sales@company.com"
        user.organization = Mock()
        user.organization.settings = {}

        role = RBACService.get_user_role(user, mock_db)
        assert role == Role.SALES_REP

    def test_explicit_role_from_organization_settings(self, mock_db):
        """Test explicit role assignment from organization settings"""
        user = Mock(spec=AccountUser)
        user.id = "123"
        user.email = "user@company.com"
        user.organization = Mock()
        user.organization.settings = {"users": {"123": {"role": "analyst"}}}

        role = RBACService.get_user_role(user, mock_db)
        assert role == Role.ANALYST

    def test_default_viewer_role(self, mock_db):
        """Test default viewer role assignment"""
        user = Mock(spec=AccountUser)
        user.email = "unknown@company.com"
        user.organization = Mock()
        user.organization.settings = {}

        role = RBACService.get_user_role(user, mock_db)
        assert role == Role.VIEWER


class TestPermissionChecking:
    """Test permission checking logic"""

    def test_admin_has_all_permissions(self, admin_user, mock_db):
        """Test that admin users have all permissions"""
        # Admin should have all permissions
        assert RBACService.has_permission(admin_user, Permission.READ, Resource.CAMPAIGNS, mock_db)
        assert RBACService.has_permission(admin_user, Permission.CREATE, Resource.CAMPAIGNS, mock_db)
        assert RBACService.has_permission(admin_user, Permission.UPDATE, Resource.CAMPAIGNS, mock_db)
        assert RBACService.has_permission(admin_user, Permission.DELETE, Resource.CAMPAIGNS, mock_db)
        assert RBACService.has_permission(admin_user, Permission.MANAGE_USERS, None, mock_db)

    def test_manager_permissions(self, manager_user, mock_db):
        """Test manager permissions"""
        # Manager should have business function permissions
        assert RBACService.has_permission(manager_user, Permission.MANAGE_CAMPAIGNS, Resource.CAMPAIGNS, mock_db)
        assert RBACService.has_permission(manager_user, Permission.CREATE, Resource.CAMPAIGNS, mock_db)
        assert RBACService.has_permission(manager_user, Permission.READ, Resource.REPORTS, mock_db)

        # But not system administration
        assert not RBACService.has_permission(manager_user, Permission.MANAGE_SYSTEM, None, mock_db)

    def test_sales_rep_permissions(self, sales_user, mock_db):
        """Test sales rep permissions"""
        # Sales rep should have lead management permissions
        assert RBACService.has_permission(sales_user, Permission.MANAGE_LEADS, Resource.LEADS, mock_db)
        assert RBACService.has_permission(sales_user, Permission.READ, Resource.LEADS, mock_db)
        assert RBACService.has_permission(sales_user, Permission.CREATE, Resource.LEADS, mock_db)

        # But not campaign management
        assert not RBACService.has_permission(sales_user, Permission.MANAGE_CAMPAIGNS, Resource.CAMPAIGNS, mock_db)
        assert not RBACService.has_permission(sales_user, Permission.DELETE, Resource.CAMPAIGNS, mock_db)

    def test_viewer_permissions(self, viewer_user, mock_db):
        """Test viewer permissions"""
        # Viewer should only have read permissions
        assert RBACService.has_permission(viewer_user, Permission.READ, Resource.CAMPAIGNS, mock_db)
        assert RBACService.has_permission(viewer_user, Permission.READ, Resource.LEADS, mock_db)

        # But no write permissions
        assert not RBACService.has_permission(viewer_user, Permission.CREATE, Resource.CAMPAIGNS, mock_db)
        assert not RBACService.has_permission(viewer_user, Permission.UPDATE, Resource.LEADS, mock_db)
        assert not RBACService.has_permission(viewer_user, Permission.DELETE, Resource.REPORTS, mock_db)

    def test_organization_access_requirement(self, guest_user, mock_db):
        """Test that organization membership is required for org-scoped resources"""
        # Guest user without organization should not have access to org resources
        assert not RBACService.has_permission(guest_user, Permission.READ, Resource.CAMPAIGNS, mock_db)
        assert not RBACService.has_permission(guest_user, Permission.READ, Resource.TARGETING, mock_db)
        assert not RBACService.has_permission(guest_user, Permission.READ, Resource.LEADS, mock_db)

    def test_permission_without_database_session(self, admin_user):
        """Test permission check fails without database session"""
        result = RBACService.has_permission(admin_user, Permission.READ, Resource.CAMPAIGNS, None)
        assert result is False


class TestFastAPIDependencies:
    """Test FastAPI dependency integration"""

    @patch("core.rbac.get_current_user_dependency")
    @patch("core.rbac.get_db")
    def test_require_permission_dependency_success(self, mock_get_db, mock_get_user, admin_user, mock_db):
        """Test successful permission dependency"""
        mock_get_user.return_value = admin_user
        mock_get_db.return_value = mock_db

        dependency = RBACService.require_permission(Permission.READ, Resource.CAMPAIGNS)
        result = dependency(admin_user, mock_db)

        assert result == admin_user

    @patch("core.rbac.get_current_user_dependency")
    @patch("core.rbac.get_db")
    def test_require_permission_dependency_failure(self, mock_get_db, mock_get_user, viewer_user, mock_db):
        """Test failed permission dependency"""
        mock_get_user.return_value = viewer_user
        mock_get_db.return_value = mock_db

        dependency = RBACService.require_permission(Permission.DELETE, Resource.CAMPAIGNS)

        with pytest.raises(HTTPException) as exc_info:
            dependency(viewer_user, mock_db)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Insufficient permissions" in exc_info.value.detail

    @patch("core.rbac.get_current_user_dependency")
    @patch("core.rbac.get_db")
    def test_require_role_dependency_success(self, mock_get_db, mock_get_user, admin_user, mock_db):
        """Test successful role dependency"""
        mock_get_user.return_value = admin_user
        mock_get_db.return_value = mock_db

        dependency = RBACService.require_role(Role.ADMIN)
        result = dependency(admin_user, mock_db)

        assert result == admin_user

    @patch("core.rbac.get_current_user_dependency")
    @patch("core.rbac.get_db")
    def test_require_role_dependency_failure(self, mock_get_db, mock_get_user, sales_user, mock_db):
        """Test failed role dependency"""
        mock_get_user.return_value = sales_user
        mock_get_db.return_value = mock_db

        dependency = RBACService.require_role(Role.ADMIN)

        with pytest.raises(HTTPException) as exc_info:
            dependency(sales_user, mock_db)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Insufficient role" in exc_info.value.detail


class TestRBACDecorator:
    """Test RBAC decorator functionality"""

    def test_rbac_decorator_success(self, admin_user, mock_db):
        """Test successful RBAC decorator"""

        @rbac_required(Permission.READ, Resource.CAMPAIGNS)
        def test_function(current_user, db):
            return "success"

        result = test_function(current_user=admin_user, db=mock_db)
        assert result == "success"

    def test_rbac_decorator_failure(self, viewer_user, mock_db):
        """Test failed RBAC decorator"""

        @rbac_required(Permission.DELETE, Resource.CAMPAIGNS)
        def test_function(current_user, db):
            return "success"

        with pytest.raises(HTTPException) as exc_info:
            test_function(current_user=viewer_user, db=mock_db)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Access denied" in exc_info.value.detail

    def test_rbac_decorator_missing_context(self):
        """Test RBAC decorator with missing context"""

        @rbac_required(Permission.READ, Resource.CAMPAIGNS)
        def test_function():
            return "success"

        with pytest.raises(HTTPException) as exc_info:
            test_function()

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Missing authentication context" in exc_info.value.detail


class TestRoleHierarchy:
    """Test role hierarchy and inheritance"""

    def test_role_hierarchy_levels(self, mock_db):
        """Test that role hierarchy is properly enforced"""
        # Create users with different roles
        super_admin = Mock(spec=AccountUser)
        super_admin.email = "superadmin@leadfactory.com"
        super_admin.organization = None

        admin = Mock(spec=AccountUser)
        admin.email = "admin@company.com"
        admin.organization = Mock()
        admin.organization.settings = {}

        manager = Mock(spec=AccountUser)
        manager.email = "manager@company.com"
        manager.organization = Mock()
        manager.organization.settings = {}

        viewer = Mock(spec=AccountUser)
        viewer.email = "viewer@company.com"
        viewer.organization = Mock()
        viewer.organization.settings = {}

        # Test dependency that requires manager role
        dependency = RBACService.require_role(Role.MANAGER)

        # Super admin and admin should pass
        assert dependency(super_admin, mock_db) == super_admin
        assert dependency(admin, mock_db) == admin
        assert dependency(manager, mock_db) == manager

        # Viewer should fail
        with pytest.raises(HTTPException):
            dependency(viewer, mock_db)


class TestResourceAccess:
    """Test resource-specific access control"""

    def test_domain_specific_permissions(self, mock_db):
        """Test domain-specific permission requirements"""
        # Create marketing user
        marketing_user = Mock(spec=AccountUser)
        marketing_user.email = "marketing@company.com"
        marketing_user.organization_id = "org-123"
        marketing_user.organization = Mock()
        marketing_user.organization.settings = {}

        # Marketing user should have campaign access
        assert RBACService.has_permission(marketing_user, Permission.MANAGE_CAMPAIGNS, Resource.CAMPAIGNS, mock_db)

        # But not lead management (sales-specific)
        assert not RBACService.has_permission(marketing_user, Permission.MANAGE_LEADS, Resource.LEADS, mock_db)

    def test_cost_access_restrictions(self, sales_user, manager_user, mock_db):
        """Test cost data access restrictions"""
        # Sales rep should not see costs
        assert not RBACService.has_permission(sales_user, Permission.VIEW_COSTS, Resource.COSTS, mock_db)

        # Manager should see costs
        assert RBACService.has_permission(manager_user, Permission.VIEW_COSTS, Resource.COSTS, mock_db)

        # But not manage costs (admin-only)
        assert not RBACService.has_permission(manager_user, Permission.MANAGE_COSTS, Resource.COSTS, mock_db)


class TestSecurityLogging:
    """Test security audit logging"""

    @patch("core.rbac.logger")
    def test_permission_check_logging(self, mock_logger, admin_user, mock_db):
        """Test that permission checks are logged"""
        RBACService.has_permission(admin_user, Permission.READ, Resource.CAMPAIGNS, mock_db)

        # Verify info log was called
        mock_logger.info.assert_called()
        log_call = mock_logger.info.call_args[0][0]
        assert "Permission check" in log_call
        assert admin_user.email in log_call

    @patch("core.rbac.logger")
    def test_access_denied_logging(self, mock_logger, viewer_user, mock_db):
        """Test that access denials are logged"""
        dependency = RBACService.require_permission(Permission.DELETE, Resource.CAMPAIGNS)

        with pytest.raises(HTTPException):
            dependency(viewer_user, mock_db)

        # Verify warning log was called
        mock_logger.warning.assert_called()
        log_call = mock_logger.warning.call_args[0][0]
        assert "Access denied" in log_call
        assert viewer_user.email in log_call


class TestConvenienceFunctions:
    """Test convenience dependency functions"""

    def test_require_read_access(self, viewer_user, mock_db):
        """Test require_read_access convenience function"""
        dependency = require_read_access(Resource.CAMPAIGNS)
        # This returns a Depends object, we need to get the actual dependency function
        actual_dependency = dependency.dependency
        result = actual_dependency(viewer_user, mock_db)
        assert result == viewer_user

    def test_require_write_access_failure(self, viewer_user, mock_db):
        """Test require_write_access convenience function failure"""
        dependency = require_write_access(Resource.CAMPAIGNS)

        with pytest.raises(HTTPException):
            dependency(viewer_user, mock_db)

    def test_require_delete_access_failure(self, sales_user, mock_db):
        """Test require_delete_access convenience function failure"""
        dependency = require_delete_access(Resource.CAMPAIGNS)
        # This returns a Depends object, we need to get the actual dependency function
        actual_dependency = dependency.dependency

        with pytest.raises(HTTPException):
            actual_dependency(sales_user, mock_db)

    def test_require_domain_access(self, manager_user, mock_db):
        """Test require_domain_access convenience function"""
        dependency = require_domain_access(Resource.CAMPAIGNS)
        # This returns a Depends object, we need to get the actual dependency function
        actual_dependency = dependency.dependency
        result = actual_dependency(manager_user, mock_db)
        assert result == manager_user


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
