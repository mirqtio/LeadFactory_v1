"""
Unit tests for account management schemas
Tests Pydantic validation, serialization, and custom validators
"""

from datetime import datetime

import pytest
from pydantic import ValidationError

from account_management.models import PermissionAction, ResourceType, TeamRole, UserStatus
from account_management.schemas import (
    APIKeyCreate,
    APIKeyCreateResponse,
    APIKeyResponse,
    AuditLogResponse,
    AuthTokenResponse,
    EmailVerificationRequest,
    ErrorResponse,
    OrganizationCreate,
    OrganizationResponse,
    OrganizationStatsResponse,
    PasswordChange,
    PasswordReset,
    PasswordResetRequest,
    PermissionGrant,
    PermissionResponse,
    RefreshTokenRequest,
    RoleCreate,
    RoleResponse,
    SessionResponse,
    TeamCreate,
    TeamDetailResponse,
    TeamMemberAdd,
    TeamMemberResponse,
    TeamResponse,
    TeamUpdate,
    UserLogin,
    UserProfileResponse,
    UserRegister,
    UserResponse,
    UserUpdate,
    ValidationErrorResponse,
)

# Mark entire module as unit test and critical - schemas are essential for API validation
pytestmark = [pytest.mark.unit, pytest.mark.critical]


class TestOrganizationSchemas:
    """Test organization-related schemas"""

    def test_organization_create_valid(self):
        """Test valid organization creation"""
        data = {
            "name": "Test Organization",
            "slug": "test-org",
            "billing_email": "billing@test.com",
            "max_users": 10,
            "max_teams": 5,
            "max_api_keys": 20
        }
        
        org = OrganizationCreate(**data)
        
        assert org.name == "Test Organization"
        assert org.slug == "test-org"
        assert org.billing_email == "billing@test.com"
        assert org.max_users == 10
        assert org.max_teams == 5
        assert org.max_api_keys == 20

    def test_organization_create_defaults(self):
        """Test organization creation with default values"""
        data = {
            "name": "Test Organization",
            "slug": "test-org"
        }
        
        org = OrganizationCreate(**data)
        
        assert org.max_users == 5  # Default value
        assert org.max_teams == 3   # Default value
        assert org.max_api_keys == 10  # Default value
        assert org.billing_email is None

    def test_organization_create_invalid_slug(self):
        """Test organization creation with invalid slug"""
        data = {
            "name": "Test Organization",
            "slug": "Test Org!",  # Invalid characters
        }
        
        with pytest.raises(ValidationError) as exc_info:
            OrganizationCreate(**data)
        
        assert "string does not match regex" in str(exc_info.value)

    def test_organization_create_invalid_limits(self):
        """Test organization creation with invalid limits"""
        # Test max_users too low
        data = {
            "name": "Test Organization",
            "slug": "test-org",
            "max_users": 0  # Too low
        }
        
        with pytest.raises(ValidationError) as exc_info:
            OrganizationCreate(**data)
        
        assert "ensure this value is greater than or equal to 1" in str(exc_info.value)
        
        # Test max_users too high
        data["max_users"] = 1001  # Too high
        
        with pytest.raises(ValidationError) as exc_info:
            OrganizationCreate(**data)
        
        assert "ensure this value is less than or equal to 1000" in str(exc_info.value)

    def test_organization_create_empty_name(self):
        """Test organization creation with empty name"""
        data = {
            "name": "",  # Empty name
            "slug": "test-org"
        }
        
        with pytest.raises(ValidationError) as exc_info:
            OrganizationCreate(**data)
        
        assert "ensure this value has at least 1 characters" in str(exc_info.value)

    def test_organization_response_serialization(self):
        """Test organization response serialization"""
        data = {
            "id": "org123",
            "name": "Test Organization",
            "slug": "test-org",
            "billing_email": "billing@test.com",
            "stripe_customer_id": "cus_123",
            "max_users": 10,
            "max_teams": 5,
            "max_api_keys": 20,
            "is_active": True,
            "trial_ends_at": datetime(2025, 12, 31),
            "created_at": datetime(2025, 1, 1),
            "updated_at": datetime(2025, 1, 15)
        }
        
        org = OrganizationResponse(**data)
        
        assert org.id == "org123"
        assert org.name == "Test Organization"
        assert org.is_active is True
        assert org.trial_ends_at == datetime(2025, 12, 31)

    def test_organization_stats_response(self):
        """Test organization stats response"""
        data = {
            "total_users": 25,
            "active_users": 20,
            "total_teams": 8,
            "total_api_keys": 15,
            "active_api_keys": 12,
            "storage_used_mb": 1024.5,
            "api_calls_this_month": 5000
        }
        
        stats = OrganizationStatsResponse(**data)
        
        assert stats.total_users == 25
        assert stats.active_users == 20
        assert stats.storage_used_mb == 1024.5
        assert stats.api_calls_this_month == 5000

    def test_organization_stats_response_defaults(self):
        """Test organization stats response with defaults"""
        data = {
            "total_users": 5,
            "active_users": 4,
            "total_teams": 2,
            "total_api_keys": 3,
            "active_api_keys": 2
        }
        
        stats = OrganizationStatsResponse(**data)
        
        assert stats.storage_used_mb == 0  # Default
        assert stats.api_calls_this_month == 0  # Default


class TestUserSchemas:
    """Test user-related schemas"""

    def test_user_register_valid(self):
        """Test valid user registration"""
        data = {
            "email": "test@example.com",
            "password": "SecurePass123!",
            "username": "testuser",
            "full_name": "Test User",
            "phone": "+1234567890",
            "timezone": "America/New_York",
            "locale": "en_US",
            "organization_name": "Test Org"
        }
        
        user = UserRegister(**data)
        
        assert user.email == "test@example.com"
        assert user.password.get_secret_value() == "SecurePass123!"
        assert user.username == "testuser"
        assert user.full_name == "Test User"
        assert user.organization_name == "Test Org"

    def test_user_register_defaults(self):
        """Test user registration with default values"""
        data = {
            "email": "test@example.com",
            "password": "SecurePass123!"
        }
        
        user = UserRegister(**data)
        
        assert user.timezone == "UTC"  # Default
        assert user.locale == "en_US"  # Default
        assert user.username is None
        assert user.organization_name is None

    def test_user_register_password_validation(self):
        """Test password validation rules"""
        base_data = {
            "email": "test@example.com"
        }
        
        # Test password without digit
        data = {**base_data, "password": "SecurePassword!"}
        with pytest.raises(ValidationError) as exc_info:
            UserRegister(**data)
        assert "Password must contain at least one digit" in str(exc_info.value)
        
        # Test password without uppercase
        data = {**base_data, "password": "securepass123!"}
        with pytest.raises(ValidationError) as exc_info:
            UserRegister(**data)
        assert "Password must contain at least one uppercase letter" in str(exc_info.value)
        
        # Test password without lowercase
        data = {**base_data, "password": "SECUREPASS123!"}
        with pytest.raises(ValidationError) as exc_info:
            UserRegister(**data)
        assert "Password must contain at least one lowercase letter" in str(exc_info.value)
        
        # Test password too short
        data = {**base_data, "password": "Short1!"}
        with pytest.raises(ValidationError) as exc_info:
            UserRegister(**data)
        assert "ensure this value has at least 8 characters" in str(exc_info.value)

    def test_user_register_invalid_email(self):
        """Test user registration with invalid email"""
        data = {
            "email": "not-an-email",
            "password": "SecurePass123!"
        }
        
        with pytest.raises(ValidationError) as exc_info:
            UserRegister(**data)
        
        assert "value is not a valid email address" in str(exc_info.value)

    def test_user_register_invalid_username(self):
        """Test user registration with invalid username"""
        data = {
            "email": "test@example.com",
            "password": "SecurePass123!",
            "username": "ab"  # Too short
        }
        
        with pytest.raises(ValidationError) as exc_info:
            UserRegister(**data)
        
        assert "ensure this value has at least 3 characters" in str(exc_info.value)
        
        # Test invalid characters
        data["username"] = "user@name"  # Invalid character
        
        with pytest.raises(ValidationError) as exc_info:
            UserRegister(**data)
        
        assert "string does not match regex" in str(exc_info.value)

    def test_user_login_valid(self):
        """Test valid user login"""
        data = {
            "email": "test@example.com",
            "password": "mypassword",
            "device_id": "device123"
        }
        
        login = UserLogin(**data)
        
        assert login.email == "test@example.com"
        assert login.password.get_secret_value() == "mypassword"
        assert login.device_id == "device123"

    def test_user_login_optional_device_id(self):
        """Test user login without device ID"""
        data = {
            "email": "test@example.com",
            "password": "mypassword"
        }
        
        login = UserLogin(**data)
        
        assert login.device_id is None

    def test_user_update_valid(self):
        """Test valid user update"""
        data = {
            "username": "newusername",
            "full_name": "New Name",
            "avatar_url": "https://example.com/avatar.jpg",
            "phone": "+9876543210",
            "timezone": "Europe/London",
            "locale": "en_GB"
        }
        
        update = UserUpdate(**data)
        
        assert update.username == "newusername"
        assert update.full_name == "New Name"
        assert update.avatar_url == "https://example.com/avatar.jpg"

    def test_user_update_partial(self):
        """Test partial user update"""
        data = {
            "full_name": "Updated Name"
        }
        
        update = UserUpdate(**data)
        
        assert update.full_name == "Updated Name"
        assert update.username is None
        assert update.phone is None

    def test_user_response_serialization(self):
        """Test user response serialization"""
        data = {
            "id": "user123",
            "email": "test@example.com",
            "username": "testuser",
            "full_name": "Test User",
            "phone": "+1234567890",
            "timezone": "UTC",
            "locale": "en_US",
            "organization_id": "org123",
            "status": UserStatus.ACTIVE,
            "email_verified": True,
            "email_verified_at": datetime(2025, 1, 1),
            "mfa_enabled": False,
            "last_login_at": datetime(2025, 1, 15),
            "created_at": datetime(2025, 1, 1),
            "updated_at": datetime(2025, 1, 15)
        }
        
        user = UserResponse(**data)
        
        assert user.id == "user123"
        assert user.status == UserStatus.ACTIVE
        assert user.email_verified is True

    def test_user_profile_response_with_organization(self):
        """Test user profile response with organization"""
        org_data = {
            "id": "org123",
            "name": "Test Organization",
            "slug": "test-org",
            "max_users": 10,
            "max_teams": 5,
            "max_api_keys": 20,
            "is_active": True,
            "created_at": datetime(2025, 1, 1),
            "updated_at": datetime(2025, 1, 15)
        }
        
        user_data = {
            "id": "user123",
            "email": "test@example.com",
            "username": "testuser",
            "timezone": "UTC",
            "locale": "en_US",
            "organization_id": "org123",
            "status": UserStatus.ACTIVE,
            "email_verified": True,
            "mfa_enabled": False,
            "created_at": datetime(2025, 1, 1),
            "updated_at": datetime(2025, 1, 15),
            "organization": OrganizationResponse(**org_data),
            "teams": []
        }
        
        profile = UserProfileResponse(**user_data)
        
        assert profile.organization is not None
        assert profile.organization.name == "Test Organization"
        assert profile.teams == []


class TestPasswordSchemas:
    """Test password-related schemas"""

    def test_password_change_valid(self):
        """Test valid password change"""
        data = {
            "current_password": "OldPass123!",
            "new_password": "NewPass456!"
        }
        
        change = PasswordChange(**data)
        
        assert change.current_password.get_secret_value() == "OldPass123!"
        assert change.new_password.get_secret_value() == "NewPass456!"

    def test_password_change_validation(self):
        """Test password change validation"""
        base_data = {
            "current_password": "OldPass123!"
        }
        
        # Test new password without digit
        data = {**base_data, "new_password": "NewPassword!"}
        with pytest.raises(ValidationError) as exc_info:
            PasswordChange(**data)
        assert "Password must contain at least one digit" in str(exc_info.value)

    def test_password_reset_valid(self):
        """Test valid password reset"""
        data = {
            "token": "reset_token_123",
            "new_password": "NewPass123!"
        }
        
        reset = PasswordReset(**data)
        
        assert reset.token == "reset_token_123"
        assert reset.new_password.get_secret_value() == "NewPass123!"

    def test_password_reset_request_valid(self):
        """Test valid password reset request"""
        data = {
            "email": "test@example.com"
        }
        
        request = PasswordResetRequest(**data)
        
        assert request.email == "test@example.com"

    def test_email_verification_request_valid(self):
        """Test valid email verification request"""
        data = {
            "token": "verification_token_123"
        }
        
        request = EmailVerificationRequest(**data)
        
        assert request.token == "verification_token_123"

    def test_refresh_token_request_valid(self):
        """Test valid refresh token request"""
        data = {
            "refresh_token": "refresh_token_123"
        }
        
        request = RefreshTokenRequest(**data)
        
        assert request.refresh_token == "refresh_token_123"


class TestTeamSchemas:
    """Test team-related schemas"""

    def test_team_create_valid(self):
        """Test valid team creation"""
        data = {
            "name": "Development Team",
            "slug": "dev-team",
            "description": "Main development team"
        }
        
        team = TeamCreate(**data)
        
        assert team.name == "Development Team"
        assert team.slug == "dev-team"
        assert team.description == "Main development team"

    def test_team_create_minimal(self):
        """Test team creation with minimal data"""
        data = {
            "name": "Team Alpha",
            "slug": "alpha"
        }
        
        team = TeamCreate(**data)
        
        assert team.name == "Team Alpha"
        assert team.slug == "alpha"
        assert team.description is None

    def test_team_create_invalid_slug(self):
        """Test team creation with invalid slug"""
        data = {
            "name": "Team Alpha",
            "slug": "Team Alpha!"  # Invalid characters
        }
        
        with pytest.raises(ValidationError) as exc_info:
            TeamCreate(**data)
        
        assert "string does not match regex" in str(exc_info.value)

    def test_team_update_valid(self):
        """Test valid team update"""
        data = {
            "name": "Updated Team Name",
            "description": "Updated description"
        }
        
        update = TeamUpdate(**data)
        
        assert update.name == "Updated Team Name"
        assert update.description == "Updated description"

    def test_team_update_partial(self):
        """Test partial team update"""
        data = {
            "name": "New Name Only"
        }
        
        update = TeamUpdate(**data)
        
        assert update.name == "New Name Only"
        assert update.description is None

    def test_team_member_add_valid(self):
        """Test valid team member addition"""
        data = {
            "user_id": "user123",
            "role": TeamRole.ADMIN
        }
        
        member = TeamMemberAdd(**data)
        
        assert member.user_id == "user123"
        assert member.role == TeamRole.ADMIN

    def test_team_member_add_default_role(self):
        """Test team member addition with default role"""
        data = {
            "user_id": "user123"
        }
        
        member = TeamMemberAdd(**data)
        
        assert member.user_id == "user123"
        assert member.role == TeamRole.MEMBER  # Default

    def test_team_response_serialization(self):
        """Test team response serialization"""
        data = {
            "id": "team123",
            "name": "Development Team",
            "slug": "dev-team",
            "description": "Main development team",
            "organization_id": "org123",
            "is_default": False,
            "created_at": datetime(2025, 1, 1),
            "updated_at": datetime(2025, 1, 15),
            "member_count": 5
        }
        
        team = TeamResponse(**data)
        
        assert team.id == "team123"
        assert team.is_default is False
        assert team.member_count == 5

    def test_team_member_response_serialization(self):
        """Test team member response serialization"""
        data = {
            "user_id": "user123",
            "email": "member@example.com",
            "full_name": "Team Member",
            "role": TeamRole.ADMIN,
            "joined_at": datetime(2025, 1, 10)
        }
        
        member = TeamMemberResponse(**data)
        
        assert member.user_id == "user123"
        assert member.role == TeamRole.ADMIN
        assert member.joined_at == datetime(2025, 1, 10)

    def test_team_detail_response_with_members(self):
        """Test team detail response with members"""
        member_data = {
            "user_id": "user123",
            "email": "member@example.com",
            "full_name": "Team Member",
            "role": TeamRole.MEMBER,
            "joined_at": datetime(2025, 1, 10)
        }
        
        team_data = {
            "id": "team123",
            "name": "Development Team",
            "slug": "dev-team",
            "organization_id": "org123",
            "is_default": False,
            "created_at": datetime(2025, 1, 1),
            "updated_at": datetime(2025, 1, 15),
            "member_count": 1,
            "members": [TeamMemberResponse(**member_data)]
        }
        
        detail = TeamDetailResponse(**team_data)
        
        assert len(detail.members) == 1
        assert detail.members[0].user_id == "user123"


class TestPermissionSchemas:
    """Test permission and role schemas"""

    def test_permission_grant_valid(self):
        """Test valid permission grant"""
        data = {
            "resource": ResourceType.LEAD,
            "action": PermissionAction.READ
        }
        
        grant = PermissionGrant(**data)
        
        assert grant.resource == ResourceType.LEAD
        assert grant.action == PermissionAction.READ

    def test_permission_response_serialization(self):
        """Test permission response serialization"""
        data = {
            "id": "perm123",
            "resource": ResourceType.REPORT,
            "action": PermissionAction.CREATE,
            "description": "Create reports"
        }
        
        permission = PermissionResponse(**data)
        
        assert permission.id == "perm123"
        assert permission.resource == ResourceType.REPORT
        assert permission.action == PermissionAction.CREATE

    def test_role_create_valid(self):
        """Test valid role creation"""
        data = {
            "name": "Manager",
            "description": "Team manager role",
            "permissions": ["perm1", "perm2", "perm3"]
        }
        
        role = RoleCreate(**data)
        
        assert role.name == "Manager"
        assert role.description == "Team manager role"
        assert role.permissions == ["perm1", "perm2", "perm3"]

    def test_role_create_minimal(self):
        """Test role creation with minimal data"""
        data = {
            "name": "Basic User"
        }
        
        role = RoleCreate(**data)
        
        assert role.name == "Basic User"
        assert role.description is None
        assert role.permissions == []

    def test_role_response_serialization(self):
        """Test role response serialization"""
        perm_data = {
            "id": "perm123",
            "resource": ResourceType.LEAD,
            "action": PermissionAction.READ,
            "description": "Read leads"
        }
        
        role_data = {
            "id": "role123",
            "name": "Lead Reader",
            "description": "Can read leads",
            "is_system": False,
            "permissions": [PermissionResponse(**perm_data)],
            "created_at": datetime(2025, 1, 1),
            "updated_at": datetime(2025, 1, 15)
        }
        
        role = RoleResponse(**role_data)
        
        assert role.id == "role123"
        assert role.is_system is False
        assert len(role.permissions) == 1
        assert role.permissions[0].resource == ResourceType.LEAD


class TestAPIKeySchemas:
    """Test API key schemas"""

    def test_api_key_create_valid(self):
        """Test valid API key creation"""
        data = {
            "name": "Production API Key",
            "scopes": ["read", "write"],
            "expires_in_days": 90
        }
        
        key = APIKeyCreate(**data)
        
        assert key.name == "Production API Key"
        assert key.scopes == ["read", "write"]
        assert key.expires_in_days == 90

    def test_api_key_create_minimal(self):
        """Test API key creation with minimal data"""
        data = {
            "name": "Basic Key"
        }
        
        key = APIKeyCreate(**data)
        
        assert key.name == "Basic Key"
        assert key.scopes == []
        assert key.expires_in_days is None

    def test_api_key_create_invalid_expiry(self):
        """Test API key creation with invalid expiry"""
        data = {
            "name": "Test Key",
            "expires_in_days": 0  # Too low
        }
        
        with pytest.raises(ValidationError) as exc_info:
            APIKeyCreate(**data)
        
        assert "ensure this value is greater than or equal to 1" in str(exc_info.value)
        
        # Test too high
        data["expires_in_days"] = 366  # Too high
        
        with pytest.raises(ValidationError) as exc_info:
            APIKeyCreate(**data)
        
        assert "ensure this value is less than or equal to 365" in str(exc_info.value)

    def test_api_key_response_serialization(self):
        """Test API key response serialization"""
        data = {
            "id": "key123",
            "name": "Production Key",
            "key_prefix": "sk_test_",
            "scopes": ["read", "write"],
            "last_used_at": datetime(2025, 1, 10),
            "usage_count": 50,
            "expires_at": datetime(2025, 4, 10),
            "is_active": True,
            "created_at": datetime(2025, 1, 1)
        }
        
        key = APIKeyResponse(**data)
        
        assert key.id == "key123"
        assert key.key_prefix == "sk_test_"
        assert key.usage_count == 50
        assert key.is_active is True

    def test_api_key_create_response_with_key(self):
        """Test API key creation response with actual key"""
        data = {
            "id": "key123",
            "name": "New Key",
            "key_prefix": "sk_test_",
            "scopes": ["read"],
            "last_used_at": None,
            "usage_count": 0,
            "expires_at": None,
            "is_active": True,
            "created_at": datetime(2025, 1, 1),
            "key": "sk_test_1234567890abcdef"  # Only in creation response
        }
        
        key = APIKeyCreateResponse(**data)
        
        assert key.key == "sk_test_1234567890abcdef"
        assert key.name == "New Key"


class TestAuthSchemas:
    """Test authentication-related schemas"""

    def test_auth_token_response_valid(self):
        """Test valid auth token response"""
        user_data = {
            "id": "user123",
            "email": "test@example.com",
            "username": "testuser",
            "timezone": "UTC",
            "locale": "en_US",
            "organization_id": "org123",
            "status": UserStatus.ACTIVE,
            "email_verified": True,
            "mfa_enabled": False,
            "created_at": datetime(2025, 1, 1),
            "updated_at": datetime(2025, 1, 15)
        }
        
        token_data = {
            "access_token": "access_token_123",
            "refresh_token": "refresh_token_123",
            "user": UserResponse(**user_data)
        }
        
        response = AuthTokenResponse(**token_data)
        
        assert response.access_token == "access_token_123"
        assert response.refresh_token == "refresh_token_123"
        assert response.token_type == "Bearer"  # Default
        assert response.expires_in == 1800  # Default
        assert response.user.id == "user123"

    def test_auth_token_response_custom_values(self):
        """Test auth token response with custom values"""
        user_data = {
            "id": "user123",
            "email": "test@example.com",
            "timezone": "UTC",
            "locale": "en_US",
            "status": UserStatus.ACTIVE,
            "email_verified": True,
            "mfa_enabled": False,
            "created_at": datetime(2025, 1, 1),
            "updated_at": datetime(2025, 1, 15)
        }
        
        token_data = {
            "access_token": "access_token_123",
            "refresh_token": "refresh_token_123",
            "token_type": "Custom",
            "expires_in": 3600,
            "user": UserResponse(**user_data)
        }
        
        response = AuthTokenResponse(**token_data)
        
        assert response.token_type == "Custom"
        assert response.expires_in == 3600

    def test_session_response_serialization(self):
        """Test session response serialization"""
        data = {
            "id": "session123",
            "ip_address": "192.168.1.100",
            "user_agent": "Mozilla/5.0 Test Browser",
            "device_id": "device123",
            "created_at": datetime(2025, 1, 1),
            "last_activity_at": datetime(2025, 1, 15),
            "expires_at": datetime(2025, 2, 1)
        }
        
        session = SessionResponse(**data)
        
        assert session.id == "session123"
        assert session.ip_address == "192.168.1.100"
        assert session.device_id == "device123"


class TestAuditAndErrorSchemas:
    """Test audit log and error schemas"""

    def test_audit_log_response_serialization(self):
        """Test audit log response serialization"""
        data = {
            "id": "audit123",
            "user_id": "user123",
            "user_email": "test@example.com",
            "action": "CREATE",
            "resource_type": "lead",
            "resource_id": "lead123",
            "ip_address": "192.168.1.100",
            "details": {"field": "value"},
            "created_at": datetime(2025, 1, 15)
        }
        
        audit = AuditLogResponse(**data)
        
        assert audit.id == "audit123"
        assert audit.action == "CREATE"
        assert audit.resource_type == "lead"
        assert audit.details == {"field": "value"}

    def test_audit_log_response_minimal(self):
        """Test audit log response with minimal data"""
        data = {
            "id": "audit123",
            "action": "READ",
            "resource_type": "report",
            "created_at": datetime(2025, 1, 15)
        }
        
        audit = AuditLogResponse(**data)
        
        assert audit.user_id is None
        assert audit.resource_id is None
        assert audit.details is None

    def test_error_response_valid(self):
        """Test error response"""
        data = {
            "error": "validation_error",
            "message": "Invalid input data",
            "details": {"field": "email", "issue": "invalid format"}
        }
        
        error = ErrorResponse(**data)
        
        assert error.error == "validation_error"
        assert error.message == "Invalid input data"
        assert error.details["field"] == "email"

    def test_error_response_minimal(self):
        """Test error response with minimal data"""
        data = {
            "error": "not_found",
            "message": "Resource not found"
        }
        
        error = ErrorResponse(**data)
        
        assert error.error == "not_found"
        assert error.details is None

    def test_validation_error_response_valid(self):
        """Test validation error response"""
        data = {
            "errors": [
                {"field": "email", "message": "Invalid email format"},
                {"field": "password", "message": "Password too short"}
            ]
        }
        
        error = ValidationErrorResponse(**data)
        
        assert error.error == "validation_error"  # Default
        assert error.message == "Validation failed"  # Default
        assert len(error.errors) == 2
        assert error.errors[0]["field"] == "email"

    def test_validation_error_response_custom(self):
        """Test validation error response with custom values"""
        data = {
            "error": "custom_validation_error",
            "message": "Custom validation failed",
            "errors": [{"custom": "error"}]
        }
        
        error = ValidationErrorResponse(**data)
        
        assert error.error == "custom_validation_error"
        assert error.message == "Custom validation failed"


class TestSchemaEdgeCases:
    """Test edge cases and special scenarios"""

    def test_extremely_long_strings(self):
        """Test validation with extremely long strings"""
        # Test organization name too long
        data = {
            "name": "x" * 256,  # Too long
            "slug": "test-org"
        }
        
        with pytest.raises(ValidationError) as exc_info:
            OrganizationCreate(**data)
        
        assert "ensure this value has at most 255 characters" in str(exc_info.value)

    def test_unicode_and_special_characters(self):
        """Test handling of unicode and special characters"""
        # Valid unicode in names
        data = {
            "name": "测试组织 🏢",
            "slug": "test-org"
        }
        
        org = OrganizationCreate(**data)
        assert org.name == "测试组织 🏢"
        
        # User with unicode full name
        user_data = {
            "email": "test@example.com",
            "password": "SecurePass123!",
            "full_name": "José María González"
        }
        
        user = UserRegister(**user_data)
        assert user.full_name == "José María González"

    def test_boundary_values(self):
        """Test boundary values for numeric fields"""
        # Test minimum valid values
        data = {
            "name": "Test Org",
            "slug": "test",
            "max_users": 1,
            "max_teams": 1,
            "max_api_keys": 1
        }
        
        org = OrganizationCreate(**data)
        assert org.max_users == 1
        
        # Test maximum valid values
        data.update({
            "max_users": 1000,
            "max_teams": 100,
            "max_api_keys": 1000
        })
        
        org = OrganizationCreate(**data)
        assert org.max_users == 1000

    def test_none_vs_missing_fields(self):
        """Test difference between None and missing fields"""
        # Missing optional fields
        data = {
            "name": "Test Org",
            "slug": "test-org"
        }
        
        org = OrganizationCreate(**data)
        assert org.billing_email is None
        
        # Explicitly None optional fields
        data["billing_email"] = None
        
        org = OrganizationCreate(**data)
        assert org.billing_email is None

    def test_empty_collections(self):
        """Test handling of empty collections"""
        # Empty scopes list
        data = {
            "name": "Test Key",
            "scopes": []
        }
        
        key = APIKeyCreate(**data)
        assert key.scopes == []
        
        # Empty permissions list
        role_data = {
            "name": "Basic Role",
            "permissions": []
        }
        
        role = RoleCreate(**role_data)
        assert role.permissions == []

    def test_model_serialization_round_trip(self):
        """Test that models can be serialized and deserialized"""
        original_data = {
            "email": "test@example.com",
            "password": "SecurePass123!",
            "username": "testuser",
            "full_name": "Test User"
        }
        
        # Create model instance
        user = UserRegister(**original_data)
        
        # Serialize to dict (excluding password for security)
        serialized = user.dict(exclude={"password"})
        
        # Verify serialization
        assert serialized["email"] == "test@example.com"
        assert serialized["username"] == "testuser"
        assert "password" not in serialized

    def test_password_secret_handling(self):
        """Test that password SecretStr is handled correctly"""
        data = {
            "email": "test@example.com",
            "password": "SecurePass123!"
        }
        
        user = UserRegister(**data)
        
        # Verify password is SecretStr
        assert hasattr(user.password, 'get_secret_value')
        assert user.password.get_secret_value() == "SecurePass123!"
        
        # Verify password is not in string representation
        user_str = str(user)
        assert "SecurePass123!" not in user_str
        assert "**********" in user_str  # SecretStr representation