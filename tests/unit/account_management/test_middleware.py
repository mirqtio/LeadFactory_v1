"""
Unit tests for account management middleware
Tests authentication, authorization, and audit logging middleware
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from account_management.middleware import (
    AuditLogger,
    AuthMiddleware,
    OrganizationMemberChecker,
    PermissionChecker,
    get_optional_user,
    require_organization_member,
    require_permission,
    require_user,
)
from account_management.models import (
    AccountAuditLog,
    AccountUser,
    PermissionAction,
    ResourceType,
    UserStatus,
)

# Mark entire module as unit test and critical - middleware is essential
pytestmark = [pytest.mark.unit, pytest.mark.critical]


class TestAuthMiddleware:
    """Test authentication middleware"""

    @pytest.fixture
    def mock_request(self):
        """Mock FastAPI request"""
        request = MagicMock(spec=Request)
        request.headers = {}
        request.client.host = "127.0.0.1"
        return request

    @pytest.fixture
    def valid_user(self, db: Session):
        """Create valid active user"""
        user = AccountUser(
            id="user123",
            email="test@example.com",
            username="testuser",
            password_hash="hashed_password",
            status=UserStatus.ACTIVE,
            organization_id="org123"
        )
        db.add(user)
        db.commit()
        return user

    async def test_get_current_user_from_token_success(self, db: Session, valid_user: AccountUser):
        """Test successful token authentication"""
        with patch.object(AuthMiddleware, 'get_current_user_from_token') as mock_method:
            # Test the actual implementation
            mock_method.side_effect = AuthMiddleware.get_current_user_from_token.__func__
            
            with patch('account_management.middleware.AuthService.decode_token') as mock_decode:
                mock_decode.return_value = {
                    "type": "access",
                    "sub": valid_user.id
                }
                
                result = await AuthMiddleware.get_current_user_from_token("valid_token", db)
                
                assert result is not None
                assert result.id == valid_user.id
                assert result.email == valid_user.email

    async def test_get_current_user_from_token_wrong_type(self, db: Session):
        """Test token authentication with wrong token type"""
        with patch('account_management.middleware.AuthService.decode_token') as mock_decode:
            mock_decode.return_value = {
                "type": "refresh",  # Wrong type
                "sub": "user123"
            }
            
            result = await AuthMiddleware.get_current_user_from_token("refresh_token", db)
            assert result is None

    async def test_get_current_user_from_token_no_user_id(self, db: Session):
        """Test token authentication with missing user ID"""
        with patch('account_management.middleware.AuthService.decode_token') as mock_decode:
            mock_decode.return_value = {
                "type": "access"
                # Missing "sub" field
            }
            
            result = await AuthMiddleware.get_current_user_from_token("token", db)
            assert result is None

    async def test_get_current_user_from_token_user_not_found(self, db: Session):
        """Test token authentication when user doesn't exist"""
        with patch('account_management.middleware.AuthService.decode_token') as mock_decode:
            mock_decode.return_value = {
                "type": "access",
                "sub": "nonexistent_user"
            }
            
            result = await AuthMiddleware.get_current_user_from_token("token", db)
            assert result is None

    async def test_get_current_user_from_token_inactive_user(self, db: Session):
        """Test token authentication with inactive user"""
        inactive_user = AccountUser(
            id="inactive123",
            email="inactive@example.com",
            status=UserStatus.INACTIVE
        )
        db.add(inactive_user)
        db.commit()
        
        with patch('account_management.middleware.AuthService.decode_token') as mock_decode:
            mock_decode.return_value = {
                "type": "access",
                "sub": inactive_user.id
            }
            
            result = await AuthMiddleware.get_current_user_from_token("token", db)
            assert result is None

    async def test_get_current_user_from_token_decode_error(self, db: Session):
        """Test token authentication when decode fails"""
        with patch('account_management.middleware.AuthService.decode_token') as mock_decode:
            mock_decode.side_effect = Exception("Token decode error")
            
            result = await AuthMiddleware.get_current_user_from_token("invalid_token", db)
            assert result is None

    async def test_get_current_user_from_api_key_success(self, db: Session, valid_user: AccountUser):
        """Test successful API key authentication"""
        mock_api_key = MagicMock()
        mock_api_key.user_id = valid_user.id
        
        with patch('account_management.middleware.AuthService.validate_api_key') as mock_validate:
            mock_validate.return_value = mock_api_key
            
            result = await AuthMiddleware.get_current_user_from_api_key("valid_api_key", db)
            
            assert result is not None
            assert result.id == valid_user.id

    async def test_get_current_user_from_api_key_invalid_key(self, db: Session):
        """Test API key authentication with invalid key"""
        with patch('account_management.middleware.AuthService.validate_api_key') as mock_validate:
            mock_validate.return_value = None
            
            result = await AuthMiddleware.get_current_user_from_api_key("invalid_key", db)
            assert result is None

    async def test_get_current_user_from_api_key_user_not_found(self, db: Session):
        """Test API key authentication when user doesn't exist"""
        mock_api_key = MagicMock()
        mock_api_key.user_id = "nonexistent_user"
        
        with patch('account_management.middleware.AuthService.validate_api_key') as mock_validate:
            mock_validate.return_value = mock_api_key
            
            result = await AuthMiddleware.get_current_user_from_api_key("valid_key", db)
            assert result is None

    async def test_get_current_user_from_api_key_inactive_user(self, db: Session):
        """Test API key authentication with inactive user"""
        inactive_user = AccountUser(
            id="inactive123",
            email="inactive@example.com",
            status=UserStatus.INACTIVE
        )
        db.add(inactive_user)
        db.commit()
        
        mock_api_key = MagicMock()
        mock_api_key.user_id = inactive_user.id
        
        with patch('account_management.middleware.AuthService.validate_api_key') as mock_validate:
            mock_validate.return_value = mock_api_key
            
            result = await AuthMiddleware.get_current_user_from_api_key("valid_key", db)
            assert result is None

    async def test_authenticate_request_bearer_token(self, db: Session, valid_user: AccountUser, mock_request):
        """Test request authentication with Bearer token"""
        mock_request.headers = {"Authorization": "Bearer valid_token"}
        
        with patch.object(AuthMiddleware, 'get_current_user_from_token') as mock_token_auth:
            mock_token_auth.return_value = valid_user
            
            result = await AuthMiddleware.authenticate_request(mock_request, db)
            
            assert result == valid_user
            mock_token_auth.assert_called_once_with("valid_token", db)

    async def test_authenticate_request_api_key_authorization(self, db: Session, valid_user: AccountUser, mock_request):
        """Test request authentication with API key in Authorization header"""
        mock_request.headers = {"Authorization": "ApiKey valid_api_key"}
        
        with patch.object(AuthMiddleware, 'get_current_user_from_token') as mock_token_auth, \
             patch.object(AuthMiddleware, 'get_current_user_from_api_key') as mock_api_auth:
            
            mock_token_auth.return_value = None  # Token auth fails
            mock_api_auth.return_value = valid_user
            
            result = await AuthMiddleware.authenticate_request(mock_request, db)
            
            assert result == valid_user
            mock_api_auth.assert_called_once_with("valid_api_key", db)

    async def test_authenticate_request_x_api_key_header(self, db: Session, valid_user: AccountUser, mock_request):
        """Test request authentication with X-API-Key header"""
        mock_request.headers = {"X-API-Key": "valid_api_key"}
        
        with patch.object(AuthMiddleware, 'get_current_user_from_token') as mock_token_auth, \
             patch.object(AuthMiddleware, 'get_current_user_from_api_key') as mock_api_auth:
            
            mock_token_auth.return_value = None  # No bearer token
            mock_api_auth.return_value = valid_user
            
            result = await AuthMiddleware.authenticate_request(mock_request, db)
            
            assert result == valid_user
            mock_api_auth.assert_called_once_with("valid_api_key", db)

    async def test_authenticate_request_no_auth(self, db: Session, mock_request):
        """Test request authentication with no authentication headers"""
        mock_request.headers = {}
        
        result = await AuthMiddleware.authenticate_request(mock_request, db)
        assert result is None

    async def test_authenticate_request_all_methods_fail(self, db: Session, mock_request):
        """Test request authentication when all methods fail"""
        mock_request.headers = {
            "Authorization": "Bearer invalid_token",
            "X-API-Key": "invalid_key"
        }
        
        with patch.object(AuthMiddleware, 'get_current_user_from_token') as mock_token_auth, \
             patch.object(AuthMiddleware, 'get_current_user_from_api_key') as mock_api_auth:
            
            mock_token_auth.return_value = None
            mock_api_auth.return_value = None
            
            result = await AuthMiddleware.authenticate_request(mock_request, db)
            assert result is None

    async def test_authenticate_request_bearer_token_priority(self, db: Session, valid_user: AccountUser, mock_request):
        """Test that Bearer token takes priority over API key"""
        mock_request.headers = {
            "Authorization": "Bearer valid_token",
            "X-API-Key": "valid_api_key"
        }
        
        with patch.object(AuthMiddleware, 'get_current_user_from_token') as mock_token_auth, \
             patch.object(AuthMiddleware, 'get_current_user_from_api_key') as mock_api_auth:
            
            mock_token_auth.return_value = valid_user
            mock_api_auth.return_value = valid_user
            
            result = await AuthMiddleware.authenticate_request(mock_request, db)
            
            assert result == valid_user
            mock_token_auth.assert_called_once()
            mock_api_auth.assert_not_called()


class TestPermissionChecker:
    """Test permission checking middleware"""

    @pytest.fixture
    def mock_request(self):
        """Mock FastAPI request"""
        request = MagicMock(spec=Request)
        request.client.host = "127.0.0.1"
        request.headers = {"User-Agent": "test-agent"}
        return request

    @pytest.fixture
    def valid_user(self, db: Session):
        """Create valid user with organization"""
        user = AccountUser(
            id="user123",
            email="test@example.com",
            status=UserStatus.ACTIVE,
            organization_id="org123"
        )
        db.add(user)
        db.commit()
        return user

    @pytest.fixture
    def permission_checker(self):
        """Create permission checker"""
        return PermissionChecker(ResourceType.LEAD, PermissionAction.READ)

    async def test_permission_checker_success(self, db: Session, valid_user: AccountUser, 
                                            mock_request, permission_checker):
        """Test successful permission check"""
        with patch.object(AuthMiddleware, 'authenticate_request') as mock_auth, \
             patch.object(permission_checker, 'check_user_permission') as mock_check:
            
            mock_auth.return_value = valid_user
            mock_check.return_value = True
            
            # Mock the database session generator
            with patch('account_management.middleware.get_db') as mock_get_db:
                mock_get_db.return_value = iter([db])
                
                result = await permission_checker(mock_request, db)
                
                assert result == valid_user
                mock_check.assert_called_once_with(valid_user, db)

    async def test_permission_checker_no_auth(self, db: Session, mock_request, permission_checker):
        """Test permission check with no authentication"""
        with patch.object(AuthMiddleware, 'authenticate_request') as mock_auth:
            mock_auth.return_value = None
            
            with patch('account_management.middleware.get_db') as mock_get_db:
                mock_get_db.return_value = iter([db])
                
                with pytest.raises(HTTPException) as exc_info:
                    await permission_checker(mock_request, db)
                
                assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
                assert "Authentication required" in str(exc_info.value.detail)

    async def test_permission_checker_permission_denied(self, db: Session, valid_user: AccountUser,
                                                       mock_request, permission_checker):
        """Test permission check when permission is denied"""
        with patch.object(AuthMiddleware, 'authenticate_request') as mock_auth, \
             patch.object(permission_checker, 'check_user_permission') as mock_check:
            
            mock_auth.return_value = valid_user
            mock_check.return_value = False
            
            with patch('account_management.middleware.get_db') as mock_get_db:
                mock_get_db.return_value = iter([db])
                
                with pytest.raises(HTTPException) as exc_info:
                    await permission_checker(mock_request, db)
                
                assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
                assert "Permission denied: lead:read" in str(exc_info.value.detail)
                
                # Verify audit log was created
                audit_log = db.query(AccountAuditLog).filter(
                    AccountAuditLog.user_id == valid_user.id,
                    AccountAuditLog.action == "UNAUTHORIZED_READ"
                ).first()
                
                assert audit_log is not None
                assert audit_log.resource_type == "lead"
                assert audit_log.ip_address == "127.0.0.1"
                assert audit_log.user_agent == "test-agent"

    def test_permission_checker_init(self):
        """Test permission checker initialization"""
        checker = PermissionChecker(ResourceType.REPORT, PermissionAction.CREATE)
        
        assert checker.resource == ResourceType.REPORT
        assert checker.action == PermissionAction.CREATE

    async def test_check_user_permission_default_implementation(self, db: Session, valid_user: AccountUser):
        """Test default permission check implementation (always returns True)"""
        checker = PermissionChecker(ResourceType.LEAD, PermissionAction.READ)
        
        result = await checker.check_user_permission(valid_user, db)
        assert result is True


class TestOrganizationMemberChecker:
    """Test organization membership checking middleware"""

    @pytest.fixture
    def mock_request(self):
        """Mock FastAPI request"""
        request = MagicMock(spec=Request)
        request.client.host = "127.0.0.1"
        request.headers = {"User-Agent": "test-agent"}
        return request

    @pytest.fixture
    def org_user(self, db: Session):
        """Create user with organization"""
        user = AccountUser(
            id="user123",
            email="test@example.com",
            status=UserStatus.ACTIVE,
            organization_id="org123"
        )
        db.add(user)
        db.commit()
        return user

    @pytest.fixture
    def no_org_user(self, db: Session):
        """Create user without organization"""
        user = AccountUser(
            id="user456",
            email="noorg@example.com",
            status=UserStatus.ACTIVE,
            organization_id=None
        )
        db.add(user)
        db.commit()
        return user

    async def test_organization_member_checker_success(self, db: Session, org_user: AccountUser, mock_request):
        """Test successful organization membership check"""
        checker = OrganizationMemberChecker()
        
        with patch.object(AuthMiddleware, 'authenticate_request') as mock_auth:
            mock_auth.return_value = org_user
            
            with patch('account_management.middleware.get_db') as mock_get_db:
                mock_get_db.return_value = iter([db])
                
                result = await checker(mock_request, db)
                assert result == org_user

    async def test_organization_member_checker_no_auth(self, db: Session, mock_request):
        """Test organization membership check with no authentication"""
        checker = OrganizationMemberChecker()
        
        with patch.object(AuthMiddleware, 'authenticate_request') as mock_auth:
            mock_auth.return_value = None
            
            with patch('account_management.middleware.get_db') as mock_get_db:
                mock_get_db.return_value = iter([db])
                
                with pytest.raises(HTTPException) as exc_info:
                    await checker(mock_request, db)
                
                assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
                assert "Authentication required" in str(exc_info.value.detail)

    async def test_organization_member_checker_no_org_strict(self, db: Session, no_org_user: AccountUser, mock_request):
        """Test organization membership check when user has no org (strict mode)"""
        checker = OrganizationMemberChecker(allow_no_org=False)
        
        with patch.object(AuthMiddleware, 'authenticate_request') as mock_auth:
            mock_auth.return_value = no_org_user
            
            with patch('account_management.middleware.get_db') as mock_get_db:
                mock_get_db.return_value = iter([db])
                
                with pytest.raises(HTTPException) as exc_info:
                    await checker(mock_request, db)
                
                assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
                assert "User must be member of an organization" in str(exc_info.value.detail)

    async def test_organization_member_checker_no_org_allowed(self, db: Session, no_org_user: AccountUser, mock_request):
        """Test organization membership check when user has no org (allow mode)"""
        checker = OrganizationMemberChecker(allow_no_org=True)
        
        with patch.object(AuthMiddleware, 'authenticate_request') as mock_auth:
            mock_auth.return_value = no_org_user
            
            with patch('account_management.middleware.get_db') as mock_get_db:
                mock_get_db.return_value = iter([db])
                
                result = await checker(mock_request, db)
                assert result == no_org_user

    def test_organization_member_checker_init(self):
        """Test organization member checker initialization"""
        checker1 = OrganizationMemberChecker()
        assert checker1.allow_no_org is False
        
        checker2 = OrganizationMemberChecker(allow_no_org=True)
        assert checker2.allow_no_org is True


class TestAuditLogger:
    """Test audit logging functionality"""

    @pytest.fixture
    def mock_request(self):
        """Mock FastAPI request"""
        request = MagicMock(spec=Request)
        request.client.host = "192.168.1.100"
        request.headers = {"User-Agent": "Mozilla/5.0 Test Browser"}
        return request

    @pytest.fixture
    def valid_user(self, db: Session):
        """Create valid user"""
        user = AccountUser(
            id="user123",
            email="test@example.com",
            status=UserStatus.ACTIVE,
            organization_id="org123"
        )
        db.add(user)
        db.commit()
        return user

    async def test_log_action_basic(self, db: Session, valid_user: AccountUser, mock_request):
        """Test basic action logging"""
        with patch('account_management.middleware.get_db') as mock_get_db:
            mock_get_db.return_value = iter([db])
            
            await AuditLogger.log_action(
                request=mock_request,
                user=valid_user,
                action="CREATE",
                resource_type="lead",
                resource_id="lead123",
                details={"field": "value"},
                db=db
            )
            
            # Verify audit log was created
            audit_log = db.query(AccountAuditLog).filter(
                AccountAuditLog.user_id == valid_user.id,
                AccountAuditLog.action == "CREATE"
            ).first()
            
            assert audit_log is not None
            assert audit_log.organization_id == "org123"
            assert audit_log.resource_type == "lead"
            assert audit_log.resource_id == "lead123"
            assert audit_log.ip_address == "192.168.1.100"
            assert audit_log.user_agent == "Mozilla/5.0 Test Browser"
            assert audit_log.details == {"field": "value"}

    async def test_log_action_minimal(self, db: Session, valid_user: AccountUser, mock_request):
        """Test action logging with minimal parameters"""
        with patch('account_management.middleware.get_db') as mock_get_db:
            mock_get_db.return_value = iter([db])
            
            await AuditLogger.log_action(
                request=mock_request,
                user=valid_user,
                action="READ",
                resource_type="report",
                db=db
            )
            
            # Verify audit log was created
            audit_log = db.query(AccountAuditLog).filter(
                AccountAuditLog.user_id == valid_user.id,
                AccountAuditLog.action == "READ"
            ).first()
            
            assert audit_log is not None
            assert audit_log.resource_type == "report"
            assert audit_log.resource_id is None
            assert audit_log.details is None


class TestDependencyHelpers:
    """Test dependency injection helper functions"""

    @pytest.fixture
    def mock_request(self):
        """Mock FastAPI request"""
        request = MagicMock(spec=Request)
        request.client.host = "127.0.0.1"
        return request

    @pytest.fixture
    def valid_user(self, db: Session):
        """Create valid user"""
        user = AccountUser(
            id="user123",
            email="test@example.com",
            status=UserStatus.ACTIVE,
            organization_id="org123"
        )
        db.add(user)
        db.commit()
        return user

    async def test_get_optional_user_authenticated(self, db: Session, valid_user: AccountUser, mock_request):
        """Test getting optional user when authenticated"""
        with patch.object(AuthMiddleware, 'authenticate_request') as mock_auth:
            mock_auth.return_value = valid_user
            
            with patch('account_management.middleware.get_db') as mock_get_db:
                mock_get_db.return_value = iter([db])
                
                result = await get_optional_user(mock_request, db)
                assert result == valid_user

    async def test_get_optional_user_not_authenticated(self, db: Session, mock_request):
        """Test getting optional user when not authenticated"""
        with patch.object(AuthMiddleware, 'authenticate_request') as mock_auth:
            mock_auth.return_value = None
            
            with patch('account_management.middleware.get_db') as mock_get_db:
                mock_get_db.return_value = iter([db])
                
                result = await get_optional_user(mock_request, db)
                assert result is None

    async def test_require_user_authenticated(self, db: Session, valid_user: AccountUser, mock_request):
        """Test requiring user when authenticated"""
        with patch.object(AuthMiddleware, 'authenticate_request') as mock_auth:
            mock_auth.return_value = valid_user
            
            with patch('account_management.middleware.get_db') as mock_get_db:
                mock_get_db.return_value = iter([db])
                
                result = await require_user(mock_request, db)
                assert result == valid_user

    async def test_require_user_not_authenticated(self, db: Session, mock_request):
        """Test requiring user when not authenticated"""
        with patch.object(AuthMiddleware, 'authenticate_request') as mock_auth:
            mock_auth.return_value = None
            
            with patch('account_management.middleware.get_db') as mock_get_db:
                mock_get_db.return_value = iter([db])
                
                with pytest.raises(HTTPException) as exc_info:
                    await require_user(mock_request, db)
                
                assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
                assert "Authentication required" in str(exc_info.value.detail)

    async def test_require_organization_member_success(self, db: Session, valid_user: AccountUser, mock_request):
        """Test requiring organization member when user has organization"""
        with patch('account_management.middleware.require_user') as mock_require:
            mock_require.return_value = valid_user
            
            with patch('account_management.middleware.get_db') as mock_get_db:
                mock_get_db.return_value = iter([db])
                
                result = await require_organization_member(mock_request, db)
                assert result == valid_user

    async def test_require_organization_member_no_org(self, db: Session, mock_request):
        """Test requiring organization member when user has no organization"""
        no_org_user = AccountUser(
            id="user456",
            email="noorg@example.com",
            status=UserStatus.ACTIVE,
            organization_id=None
        )
        
        with patch('account_management.middleware.require_user') as mock_require:
            mock_require.return_value = no_org_user
            
            with patch('account_management.middleware.get_db') as mock_get_db:
                mock_get_db.return_value = iter([db])
                
                with pytest.raises(HTTPException) as exc_info:
                    await require_organization_member(mock_request, db)
                
                assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
                assert "User must be member of an organization" in str(exc_info.value.detail)


class TestPermissionDependencyCreators:
    """Test permission dependency creator functions"""

    def test_require_permission_creator(self):
        """Test permission dependency creator"""
        dependency = require_permission(ResourceType.LEAD, PermissionAction.CREATE)
        
        assert isinstance(dependency, PermissionChecker)
        assert dependency.resource == ResourceType.LEAD
        assert dependency.action == PermissionAction.CREATE

    def test_predefined_permission_dependencies(self):
        """Test predefined permission dependencies"""
        from account_management.middleware import (
            require_lead_read,
            require_lead_create,
            require_lead_update,
            require_lead_delete,
            require_report_read,
            require_report_create,
            require_user_read,
            require_user_update,
            require_user_delete,
            require_organization_read,
            require_organization_update,
            require_billing_read,
            require_billing_update,
        )
        
        # Test lead permissions
        assert isinstance(require_lead_read, PermissionChecker)
        assert require_lead_read.resource == ResourceType.LEAD
        assert require_lead_read.action == PermissionAction.READ
        
        assert isinstance(require_lead_create, PermissionChecker)
        assert require_lead_create.resource == ResourceType.LEAD
        assert require_lead_create.action == PermissionAction.CREATE
        
        assert isinstance(require_lead_update, PermissionChecker)
        assert require_lead_update.resource == ResourceType.LEAD
        assert require_lead_update.action == PermissionAction.UPDATE
        
        assert isinstance(require_lead_delete, PermissionChecker)
        assert require_lead_delete.resource == ResourceType.LEAD
        assert require_lead_delete.action == PermissionAction.DELETE
        
        # Test report permissions
        assert isinstance(require_report_read, PermissionChecker)
        assert require_report_read.resource == ResourceType.REPORT
        assert require_report_read.action == PermissionAction.READ
        
        assert isinstance(require_report_create, PermissionChecker)
        assert require_report_create.resource == ResourceType.REPORT
        assert require_report_create.action == PermissionAction.CREATE
        
        # Test user permissions
        assert isinstance(require_user_read, PermissionChecker)
        assert require_user_read.resource == ResourceType.USER
        assert require_user_read.action == PermissionAction.READ
        
        assert isinstance(require_user_update, PermissionChecker)
        assert require_user_update.resource == ResourceType.USER
        assert require_user_update.action == PermissionAction.UPDATE
        
        assert isinstance(require_user_delete, PermissionChecker)
        assert require_user_delete.resource == ResourceType.USER
        assert require_user_delete.action == PermissionAction.DELETE
        
        # Test organization permissions
        assert isinstance(require_organization_read, PermissionChecker)
        assert require_organization_read.resource == ResourceType.ORGANIZATION
        assert require_organization_read.action == PermissionAction.READ
        
        assert isinstance(require_organization_update, PermissionChecker)
        assert require_organization_update.resource == ResourceType.ORGANIZATION
        assert require_organization_update.action == PermissionAction.UPDATE
        
        # Test billing permissions
        assert isinstance(require_billing_read, PermissionChecker)
        assert require_billing_read.resource == ResourceType.BILLING
        assert require_billing_read.action == PermissionAction.READ
        
        assert isinstance(require_billing_update, PermissionChecker)
        assert require_billing_update.resource == ResourceType.BILLING
        assert require_billing_update.action == PermissionAction.UPDATE


class TestMiddlewareIntegration:
    """Test middleware integration scenarios"""

    @pytest.fixture
    def mock_request_with_auth(self):
        """Mock request with authorization header"""
        request = MagicMock(spec=Request)
        request.headers = {
            "Authorization": "Bearer valid_token",
            "User-Agent": "test-client"
        }
        request.client.host = "10.0.0.1"
        return request

    @pytest.fixture
    def org_user(self, db: Session):
        """Create user with organization"""
        user = AccountUser(
            id="user123",
            email="test@example.com",
            status=UserStatus.ACTIVE,
            organization_id="org123"
        )
        user.roles = []  # Mock roles attribute for audit logging
        db.add(user)
        db.commit()
        return user

    async def test_full_authentication_flow(self, db: Session, org_user: AccountUser, mock_request_with_auth):
        """Test complete authentication flow"""
        # Test token authentication
        with patch('account_management.middleware.AuthService.decode_token') as mock_decode:
            mock_decode.return_value = {
                "type": "access",
                "sub": org_user.id
            }
            
            user = await AuthMiddleware.authenticate_request(mock_request_with_auth, db)
            assert user == org_user

    async def test_permission_check_with_audit_logging(self, db: Session, org_user: AccountUser, mock_request_with_auth):
        """Test permission check that creates audit log"""
        permission_checker = PermissionChecker(ResourceType.REPORT, PermissionAction.DELETE)
        
        with patch.object(AuthMiddleware, 'authenticate_request') as mock_auth, \
             patch.object(permission_checker, 'check_user_permission') as mock_check:
            
            mock_auth.return_value = org_user
            mock_check.return_value = False  # Permission denied
            
            with patch('account_management.middleware.get_db') as mock_get_db:
                mock_get_db.return_value = iter([db])
                
                with pytest.raises(HTTPException):
                    await permission_checker(mock_request_with_auth, db)
                
                # Verify audit log was created with correct details
                audit_log = db.query(AccountAuditLog).filter(
                    AccountAuditLog.user_id == org_user.id,
                    AccountAuditLog.action == "UNAUTHORIZED_DELETE"
                ).first()
                
                assert audit_log is not None
                assert audit_log.resource_type == "report"
                assert audit_log.details["required_permission"] == "report:delete"
                assert audit_log.details["user_roles"] == []

    async def test_organization_member_check_integration(self, db: Session, org_user: AccountUser, mock_request_with_auth):
        """Test organization member check integration"""
        checker = OrganizationMemberChecker()
        
        with patch.object(AuthMiddleware, 'authenticate_request') as mock_auth:
            mock_auth.return_value = org_user
            
            with patch('account_management.middleware.get_db') as mock_get_db:
                mock_get_db.return_value = iter([db])
                
                result = await checker(mock_request_with_auth, db)
                assert result == org_user
                assert result.organization_id == "org123"