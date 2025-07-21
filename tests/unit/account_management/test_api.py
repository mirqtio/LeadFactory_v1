"""
Unit tests for account management API endpoints
Tests authentication, user management, and organization endpoints
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from account_management.api import (
    get_current_user,
    get_current_user_optional,
    make_aware,
    router,
    utc_now,
)
from account_management.auth_service import AuthService
from account_management.models import (
    AccountUser,
    APIKey,
    Organization,
    Team,
    UserSession,
    UserStatus,
)
from account_management.schemas import (
    APIKeyCreate,
    EmailVerificationRequest,
    OrganizationCreate,
    PasswordChange,
    PasswordReset,
    PasswordResetRequest,
    RefreshTokenRequest,
    TeamCreate,
    UserLogin,
    UserRegister,
    UserUpdate,
)

# Mark entire module as unit test and critical - API endpoints are essential
pytestmark = [pytest.mark.unit, pytest.mark.critical]


class TestUtilityFunctions:
    """Test utility functions"""

    def test_make_aware_naive_datetime(self):
        """Test making naive datetime timezone-aware"""
        naive_dt = datetime(2025, 1, 1, 12, 0, 0)
        aware_dt = make_aware(naive_dt)
        
        assert aware_dt.tzinfo == UTC
        assert aware_dt.year == 2025
        assert aware_dt.month == 1
        assert aware_dt.day == 1

    def test_make_aware_already_aware(self):
        """Test making already aware datetime"""
        aware_dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        result = make_aware(aware_dt)
        
        assert result == aware_dt
        assert result.tzinfo == UTC

    def test_utc_now(self):
        """Test getting current UTC datetime"""
        now = utc_now()
        
        assert now.tzinfo == UTC
        assert isinstance(now, datetime)


class TestDependencies:
    """Test FastAPI dependencies"""

    @pytest.fixture
    def mock_request(self):
        """Mock FastAPI request"""
        request = MagicMock()
        request.client.host = "127.0.0.1"
        request.headers = {"User-Agent": "test-agent"}
        return request

    @pytest.fixture
    def valid_user(self, db: Session):
        """Create a valid active user"""
        user = AccountUser(
            id="user123",
            email="test@example.com",
            username="testuser",
            password_hash="hashed_password",
            full_name="Test User",
            status=UserStatus.ACTIVE,
            email_verified=True,
        )
        db.add(user)
        db.commit()
        return user

    @pytest.fixture
    def valid_credentials(self):
        """Mock valid authorization credentials"""
        return HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="valid_token"
        )

    async def test_get_current_user_valid_token(self, db: Session, valid_user: AccountUser, valid_credentials):
        """Test getting current user with valid token"""
        with patch.object(AuthService, 'decode_token') as mock_decode:
            mock_decode.return_value = {
                "type": "access",
                "sub": valid_user.id,
                "exp": datetime.now().timestamp() + 3600
            }
            
            user = await get_current_user(valid_credentials, db)
            
            assert user.id == valid_user.id
            assert user.email == valid_user.email

    async def test_get_current_user_invalid_token_type(self, db: Session, valid_credentials):
        """Test getting current user with invalid token type"""
        with patch.object(AuthService, 'decode_token') as mock_decode:
            mock_decode.return_value = {
                "type": "refresh",  # Wrong type
                "sub": "user123"
            }
            
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(valid_credentials, db)
            
            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "Invalid token type" in str(exc_info.value.detail)

    async def test_get_current_user_no_user_id(self, db: Session, valid_credentials):
        """Test getting current user with token missing user ID"""
        with patch.object(AuthService, 'decode_token') as mock_decode:
            mock_decode.return_value = {
                "type": "access",
                # Missing "sub" field
            }
            
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(valid_credentials, db)
            
            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "Invalid token" in str(exc_info.value.detail)

    async def test_get_current_user_user_not_found(self, db: Session, valid_credentials):
        """Test getting current user when user doesn't exist"""
        with patch.object(AuthService, 'decode_token') as mock_decode:
            mock_decode.return_value = {
                "type": "access",
                "sub": "nonexistent_user"
            }
            
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(valid_credentials, db)
            
            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "User not found" in str(exc_info.value.detail)

    async def test_get_current_user_inactive_user(self, db: Session, valid_credentials):
        """Test getting current user when user is inactive"""
        inactive_user = AccountUser(
            id="inactive123",
            email="inactive@example.com",
            password_hash="hashed_password",
            status=UserStatus.INACTIVE,  # Inactive status
        )
        db.add(inactive_user)
        db.commit()
        
        with patch.object(AuthService, 'decode_token') as mock_decode:
            mock_decode.return_value = {
                "type": "access",
                "sub": inactive_user.id
            }
            
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(valid_credentials, db)
            
            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "User not found" in str(exc_info.value.detail)

    async def test_get_current_user_decode_token_exception(self, db: Session, valid_credentials):
        """Test getting current user when token decode fails"""
        with patch.object(AuthService, 'decode_token') as mock_decode:
            mock_decode.side_effect = Exception("Token decode error")
            
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(valid_credentials, db)
            
            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "Invalid authentication credentials" in str(exc_info.value.detail)

    async def test_get_current_user_optional_no_credentials(self, db: Session):
        """Test optional user dependency with no credentials"""
        user = await get_current_user_optional(None, db)
        assert user is None

    async def test_get_current_user_optional_valid_credentials(self, db: Session, valid_user: AccountUser):
        """Test optional user dependency with valid credentials"""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="valid_token"
        )
        
        with patch.object(AuthService, 'decode_token') as mock_decode:
            mock_decode.return_value = {
                "type": "access",
                "sub": valid_user.id
            }
            
            user = await get_current_user_optional(credentials, db)
            
            assert user is not None
            assert user.id == valid_user.id

    async def test_get_current_user_optional_invalid_credentials(self, db: Session):
        """Test optional user dependency with invalid credentials"""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="invalid_token"
        )
        
        with patch.object(AuthService, 'decode_token') as mock_decode:
            mock_decode.side_effect = Exception("Invalid token")
            
            user = await get_current_user_optional(credentials, db)
            assert user is None


class TestAuthEndpoints:
    """Test authentication endpoints"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    @pytest.fixture
    def mock_request(self):
        """Mock request object"""
        request = MagicMock()
        request.client.host = "127.0.0.1"
        request.headers = {"User-Agent": "test-agent"}
        return request

    def test_register_success(self, db: Session, mock_request):
        """Test successful user registration"""
        user_data = UserRegister(
            email="new@example.com",
            password="SecurePass123!",
            username="newuser",
            full_name="New User",
            organization_name="Test Org"
        )
        
        with patch('account_management.api.AuthService.hash_password') as mock_hash, \
             patch('account_management.api.AuthService.create_session') as mock_session, \
             patch('account_management.api.AuthService.create_email_verification_token') as mock_verify:
            
            mock_hash.return_value = "hashed_password"
            mock_session.return_value = ("access_token", "refresh_token", MagicMock())
            mock_verify.return_value = "verification_token"
            
            # Import and call the endpoint function directly
            from account_management.api import register
            result = register(mock_request, user_data, db)
            
            # Verify user was created
            user = db.query(AccountUser).filter(AccountUser.email == "new@example.com").first()
            assert user is not None
            assert user.username == "newuser"
            assert user.full_name == "New User"
            
            # Verify organization was created
            org = db.query(Organization).first()
            assert org is not None
            assert org.name == "Test Org"
            assert user.organization_id == org.id

    def test_register_duplicate_email(self, db: Session, mock_request):
        """Test registration with existing email"""
        # Create existing user
        existing_user = AccountUser(
            email="existing@example.com",
            password_hash="hashed_password",
            status=UserStatus.ACTIVE
        )
        db.add(existing_user)
        db.commit()
        
        user_data = UserRegister(
            email="existing@example.com",  # Same email
            password="SecurePass123!",
            username="newuser"
        )
        
        from account_management.api import register
        
        with pytest.raises(HTTPException) as exc_info:
            register(mock_request, user_data, db)
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Email already registered" in str(exc_info.value.detail)

    def test_register_duplicate_username(self, db: Session, mock_request):
        """Test registration with existing username"""
        # Create existing user
        existing_user = AccountUser(
            email="existing@example.com",
            username="existinguser",
            password_hash="hashed_password",
            status=UserStatus.ACTIVE
        )
        db.add(existing_user)
        db.commit()
        
        user_data = UserRegister(
            email="new@example.com",
            password="SecurePass123!",
            username="existinguser"  # Same username
        )
        
        from account_management.api import register
        
        with pytest.raises(HTTPException) as exc_info:
            register(mock_request, user_data, db)
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Username already taken" in str(exc_info.value.detail)

    def test_login_success(self, db: Session, mock_request):
        """Test successful login"""
        login_data = UserLogin(
            email="test@example.com",
            password="password123"
        )
        
        mock_user = AccountUser(
            id="user123",
            email="test@example.com",
            status=UserStatus.ACTIVE
        )
        
        with patch('account_management.api.AuthService.authenticate_user') as mock_auth, \
             patch('account_management.api.AuthService.create_session') as mock_session:
            
            mock_auth.return_value = mock_user
            mock_session.return_value = ("access_token", "refresh_token", MagicMock())
            
            from account_management.api import login
            result = login(mock_request, login_data, db)
            
            assert result.access_token == "access_token"
            assert result.refresh_token == "refresh_token"
            assert result.user.email == "test@example.com"

    def test_login_invalid_credentials(self, db: Session, mock_request):
        """Test login with invalid credentials"""
        login_data = UserLogin(
            email="test@example.com",
            password="wrongpassword"
        )
        
        with patch('account_management.api.AuthService.authenticate_user') as mock_auth:
            mock_auth.return_value = None  # Authentication failed
            
            from account_management.api import login
            
            with pytest.raises(HTTPException) as exc_info:
                login(mock_request, login_data, db)
            
            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "Invalid email or password" in str(exc_info.value.detail)

    def test_refresh_token_success(self, db: Session, mock_request):
        """Test successful token refresh"""
        # Create user in database
        user = AccountUser(
            id="user123",
            email="test@example.com",
            status=UserStatus.ACTIVE
        )
        db.add(user)
        db.commit()
        
        refresh_data = RefreshTokenRequest(
            refresh_token="valid_refresh_token"
        )
        
        with patch('account_management.api.AuthService.decode_token') as mock_decode, \
             patch('account_management.api.AuthService.create_session') as mock_session:
            
            mock_decode.return_value = {
                "type": "refresh",
                "sub": "user123"
            }
            mock_session.return_value = ("new_access_token", "new_refresh_token", MagicMock())
            
            from account_management.api import refresh_token
            result = refresh_token(mock_request, refresh_data, db)
            
            assert result.access_token == "new_access_token"
            assert result.refresh_token == "new_refresh_token"

    def test_refresh_token_invalid_type(self, db: Session, mock_request):
        """Test refresh token with wrong token type"""
        refresh_data = RefreshTokenRequest(
            refresh_token="access_token_not_refresh"
        )
        
        with patch('account_management.api.AuthService.decode_token') as mock_decode:
            mock_decode.return_value = {
                "type": "access",  # Wrong type
                "sub": "user123"
            }
            
            from account_management.api import refresh_token
            
            with pytest.raises(HTTPException) as exc_info:
                refresh_token(mock_request, refresh_data, db)
            
            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "Invalid token type" in str(exc_info.value.detail)

    def test_refresh_token_user_not_found(self, db: Session, mock_request):
        """Test refresh token with nonexistent user"""
        refresh_data = RefreshTokenRequest(
            refresh_token="valid_refresh_token"
        )
        
        with patch('account_management.api.AuthService.decode_token') as mock_decode:
            mock_decode.return_value = {
                "type": "refresh",
                "sub": "nonexistent_user"
            }
            
            from account_management.api import refresh_token
            
            with pytest.raises(HTTPException) as exc_info:
                refresh_token(mock_request, refresh_data, db)
            
            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "User not found" in str(exc_info.value.detail)

    def test_refresh_token_decode_error(self, db: Session, mock_request):
        """Test refresh token with decode error"""
        refresh_data = RefreshTokenRequest(
            refresh_token="invalid_token"
        )
        
        with patch('account_management.api.AuthService.decode_token') as mock_decode:
            mock_decode.side_effect = Exception("Token decode error")
            
            from account_management.api import refresh_token
            
            with pytest.raises(HTTPException) as exc_info:
                refresh_token(mock_request, refresh_data, db)
            
            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "Invalid refresh token" in str(exc_info.value.detail)

    def test_logout(self, db: Session):
        """Test logout endpoint"""
        mock_user = AccountUser(id="user123", email="test@example.com")
        
        from account_management.api import logout
        result = logout(mock_user, db)
        
        assert result["message"] == "Logged out successfully"

    def test_verify_email_success(self, db: Session):
        """Test successful email verification"""
        verification_data = EmailVerificationRequest(
            token="valid_verification_token"
        )
        
        mock_user = AccountUser(id="user123", email="test@example.com")
        
        with patch('account_management.api.AuthService.verify_email_token') as mock_verify:
            mock_verify.return_value = mock_user
            
            from account_management.api import verify_email
            result = verify_email(verification_data, db)
            
            assert result["message"] == "Email verified successfully"

    def test_verify_email_invalid_token(self, db: Session):
        """Test email verification with invalid token"""
        verification_data = EmailVerificationRequest(
            token="invalid_token"
        )
        
        with patch('account_management.api.AuthService.verify_email_token') as mock_verify:
            mock_verify.return_value = None
            
            from account_management.api import verify_email
            
            with pytest.raises(HTTPException) as exc_info:
                verify_email(verification_data, db)
            
            assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
            assert "Invalid or expired verification token" in str(exc_info.value.detail)

    def test_request_password_reset_with_token(self, db: Session):
        """Test password reset request that returns token"""
        reset_request = PasswordResetRequest(
            email="test@example.com"
        )
        
        with patch('account_management.api.AuthService.create_password_reset_token') as mock_create:
            mock_create.return_value = "reset_token_123"
            
            from account_management.api import request_password_reset
            result = request_password_reset(reset_request, db)
            
            assert result["message"] == "If the email exists, a reset link has been sent"

    def test_request_password_reset_no_token(self, db: Session):
        """Test password reset request that returns no token"""
        reset_request = PasswordResetRequest(
            email="nonexistent@example.com"
        )
        
        with patch('account_management.api.AuthService.create_password_reset_token') as mock_create:
            mock_create.return_value = None
            
            from account_management.api import request_password_reset
            result = request_password_reset(reset_request, db)
            
            # Should still return success to prevent email enumeration
            assert result["message"] == "If the email exists, a reset link has been sent"

    def test_reset_password_success(self, db: Session):
        """Test successful password reset"""
        reset_data = PasswordReset(
            token="valid_reset_token",
            new_password="NewSecurePass123!"
        )
        
        mock_user = AccountUser(id="user123", email="test@example.com")
        
        with patch('account_management.api.AuthService.reset_password') as mock_reset:
            mock_reset.return_value = mock_user
            
            from account_management.api import reset_password
            result = reset_password(reset_data, db)
            
            assert result["message"] == "Password reset successfully"

    def test_reset_password_invalid_token(self, db: Session):
        """Test password reset with invalid token"""
        reset_data = PasswordReset(
            token="invalid_token",
            new_password="NewSecurePass123!"
        )
        
        with patch('account_management.api.AuthService.reset_password') as mock_reset:
            mock_reset.return_value = None
            
            from account_management.api import reset_password
            
            with pytest.raises(HTTPException) as exc_info:
                reset_password(reset_data, db)
            
            assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
            assert "Invalid or expired reset token" in str(exc_info.value.detail)


class TestUserProfileEndpoints:
    """Test user profile management endpoints"""

    @pytest.fixture
    def current_user(self, db: Session):
        """Create current user for testing"""
        user = AccountUser(
            id="user123",
            email="test@example.com",
            username="testuser",
            full_name="Test User",
            status=UserStatus.ACTIVE
        )
        db.add(user)
        db.commit()
        return user

    def test_get_current_user_profile(self, db: Session, current_user: AccountUser):
        """Test getting current user profile"""
        from account_management.api import get_current_user_profile
        result = get_current_user_profile(current_user, db)
        
        assert result.email == "test@example.com"
        assert result.username == "testuser"
        assert result.full_name == "Test User"

    def test_update_profile_success(self, db: Session, current_user: AccountUser):
        """Test successful profile update"""
        update_data = UserUpdate(
            full_name="Updated Name",
            phone="+1234567890"
        )
        
        from account_management.api import update_profile
        result = update_profile(update_data, current_user, db)
        
        assert result.full_name == "Updated Name"
        assert result.phone == "+1234567890"
        
        # Verify database was updated
        db.refresh(current_user)
        assert current_user.full_name == "Updated Name"
        assert current_user.phone == "+1234567890"

    def test_update_profile_username_taken(self, db: Session, current_user: AccountUser):
        """Test updating profile with taken username"""
        # Create another user with the desired username
        other_user = AccountUser(
            id="other123",
            email="other@example.com",
            username="takenusername",
            status=UserStatus.ACTIVE
        )
        db.add(other_user)
        db.commit()
        
        update_data = UserUpdate(
            username="takenusername"
        )
        
        from account_management.api import update_profile
        
        with pytest.raises(HTTPException) as exc_info:
            update_profile(update_data, current_user, db)
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Username already taken" in str(exc_info.value.detail)

    def test_update_profile_same_username(self, db: Session, current_user: AccountUser):
        """Test updating profile with same username (should work)"""
        update_data = UserUpdate(
            username="testuser",  # Same as current username
            full_name="Updated Name"
        )
        
        from account_management.api import update_profile
        result = update_profile(update_data, current_user, db)
        
        assert result.username == "testuser"
        assert result.full_name == "Updated Name"

    def test_change_password_success(self, db: Session, current_user: AccountUser):
        """Test successful password change"""
        # Set current password hash
        current_user.password_hash = "current_hashed_password"
        db.commit()
        
        change_data = PasswordChange(
            current_password="current_password",
            new_password="NewSecurePass123!"
        )
        
        with patch('account_management.api.AuthService.verify_password') as mock_verify, \
             patch('account_management.api.AuthService.hash_password') as mock_hash:
            
            mock_verify.return_value = True
            mock_hash.return_value = "new_hashed_password"
            
            from account_management.api import change_password
            result = change_password(change_data, current_user, db)
            
            assert result["message"] == "Password changed successfully"
            
            # Verify password was updated
            db.refresh(current_user)
            assert current_user.password_hash == "new_hashed_password"

    def test_change_password_wrong_current(self, db: Session, current_user: AccountUser):
        """Test password change with wrong current password"""
        change_data = PasswordChange(
            current_password="wrong_password",
            new_password="NewSecurePass123!"
        )
        
        with patch('account_management.api.AuthService.verify_password') as mock_verify:
            mock_verify.return_value = False
            
            from account_management.api import change_password
            
            with pytest.raises(HTTPException) as exc_info:
                change_password(change_data, current_user, db)
            
            assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
            assert "Current password is incorrect" in str(exc_info.value.detail)

    def test_get_user_sessions(self, db: Session, current_user: AccountUser):
        """Test getting user sessions"""
        # Create some sessions (mock since UserSession is imported in the function)
        with patch('account_management.api.UserSession') as mock_session_class:
            mock_sessions = [
                MagicMock(id="session1", created_at=datetime.now()),
                MagicMock(id="session2", created_at=datetime.now())
            ]
            
            # Mock the query chain
            mock_query = MagicMock()
            mock_query.filter.return_value.all.return_value = mock_sessions
            db.query = MagicMock(return_value=mock_query)
            
            from account_management.api import get_user_sessions
            result = get_user_sessions(current_user, db)
            
            # Verify query was called correctly
            db.query.assert_called_once()
            assert len(result) == 2


class TestOrganizationEndpoints:
    """Test organization management endpoints"""

    @pytest.fixture
    def org_user(self, db: Session):
        """Create user with organization"""
        org = Organization(
            id="org123",
            name="Test Organization",
            slug="test-org",
            billing_email="billing@test.com"
        )
        db.add(org)
        db.flush()
        
        user = AccountUser(
            id="user123",
            email="test@example.com",
            organization_id=org.id,
            status=UserStatus.ACTIVE
        )
        db.add(user)
        db.commit()
        
        # Refresh to get relationships
        db.refresh(user)
        return user

    @pytest.fixture
    def no_org_user(self, db: Session):
        """Create user without organization"""
        user = AccountUser(
            id="user456",
            email="noorg@example.com",
            status=UserStatus.ACTIVE
        )
        db.add(user)
        db.commit()
        return user

    def test_get_current_organization_success(self, db: Session, org_user: AccountUser):
        """Test getting current organization"""
        from account_management.api import get_current_organization
        result = get_current_organization(org_user, db)
        
        assert result.name == "Test Organization"
        assert result.slug == "test-org"

    def test_get_current_organization_no_org(self, db: Session, no_org_user: AccountUser):
        """Test getting current organization when user has none"""
        from account_management.api import get_current_organization
        
        with pytest.raises(HTTPException) as exc_info:
            get_current_organization(no_org_user, db)
        
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "User is not part of an organization" in str(exc_info.value.detail)

    def test_create_organization_success(self, db: Session, no_org_user: AccountUser):
        """Test successful organization creation"""
        org_data = OrganizationCreate(
            name="New Organization",
            slug="new-org",
            billing_email="billing@new.com"
        )
        
        from account_management.api import create_organization
        result = create_organization(org_data, no_org_user, db)
        
        assert result.name == "New Organization"
        assert result.slug == "new-org"
        
        # Verify user was added to organization
        db.refresh(no_org_user)
        assert no_org_user.organization_id == result.id
        
        # Verify default team was created
        team = db.query(Team).filter(Team.organization_id == result.id, Team.is_default == True).first()
        assert team is not None
        assert team.name == "Default Team"

    def test_create_organization_user_has_org(self, db: Session, org_user: AccountUser):
        """Test creating organization when user already has one"""
        org_data = OrganizationCreate(
            name="Another Organization",
            slug="another-org",
            billing_email="billing@another.com"
        )
        
        from account_management.api import create_organization
        
        with pytest.raises(HTTPException) as exc_info:
            create_organization(org_data, org_user, db)
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "User already belongs to an organization" in str(exc_info.value.detail)

    def test_create_organization_slug_exists(self, db: Session, no_org_user: AccountUser):
        """Test creating organization with existing slug"""
        # Create existing organization
        existing_org = Organization(
            name="Existing Org",
            slug="existing-slug",
            billing_email="existing@test.com"
        )
        db.add(existing_org)
        db.commit()
        
        org_data = OrganizationCreate(
            name="New Organization",
            slug="existing-slug",  # Same slug
            billing_email="billing@new.com"
        )
        
        from account_management.api import create_organization
        
        with pytest.raises(HTTPException) as exc_info:
            create_organization(org_data, no_org_user, db)
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Organization slug already exists" in str(exc_info.value.detail)

    def test_get_organization_stats(self, db: Session, org_user: AccountUser):
        """Test getting organization statistics"""
        # Add some more users and API keys to the organization
        user2 = AccountUser(
            id="user2",
            email="user2@test.com",
            organization_id=org_user.organization_id,
            status=UserStatus.ACTIVE
        )
        user3 = AccountUser(
            id="user3",
            email="user3@test.com",
            organization_id=org_user.organization_id,
            status=UserStatus.INACTIVE  # Inactive user
        )
        db.add_all([user2, user3])
        
        # Add teams
        team1 = Team(
            name="Team 1",
            slug="team1",
            organization_id=org_user.organization_id
        )
        team2 = Team(
            name="Team 2",
            slug="team2",
            organization_id=org_user.organization_id
        )
        db.add_all([team1, team2])
        
        # Add API keys
        api_key1 = APIKey(
            id="key1",
            name="Key 1",
            user_id=org_user.id,
            organization_id=org_user.organization_id,
            is_active=True
        )
        api_key2 = APIKey(
            id="key2",
            name="Key 2",
            user_id=org_user.id,
            organization_id=org_user.organization_id,
            is_active=False  # Inactive key
        )
        db.add_all([api_key1, api_key2])
        db.commit()
        
        from account_management.api import get_organization_stats
        result = get_organization_stats(org_user, db)
        
        assert result.total_users == 3  # org_user + user2 + user3
        assert result.active_users == 2  # org_user + user2 (user3 is inactive)
        assert result.total_teams == 2  # team1 + team2
        assert result.total_api_keys == 2  # api_key1 + api_key2
        assert result.active_api_keys == 1  # Only api_key1 is active

    def test_get_organization_stats_no_org(self, db: Session, no_org_user: AccountUser):
        """Test getting organization stats when user has no organization"""
        from account_management.api import get_organization_stats
        
        with pytest.raises(HTTPException) as exc_info:
            get_organization_stats(no_org_user, db)
        
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "User is not part of an organization" in str(exc_info.value.detail)


class TestTeamEndpoints:
    """Test team management endpoints"""

    @pytest.fixture
    def org_user_with_teams(self, db: Session):
        """Create user with organization and teams"""
        org = Organization(
            id="org123",
            name="Test Organization",
            slug="test-org"
        )
        db.add(org)
        db.flush()
        
        user = AccountUser(
            id="user123",
            email="test@example.com",
            organization_id=org.id,
            status=UserStatus.ACTIVE
        )
        db.add(user)
        
        team1 = Team(
            id="team1",
            name="Team Alpha",
            slug="alpha",
            organization_id=org.id
        )
        team2 = Team(
            id="team2",
            name="Team Beta",
            slug="beta",
            organization_id=org.id
        )
        db.add_all([team1, team2])
        db.commit()
        
        db.refresh(user)
        return user

    def test_list_teams_with_org(self, db: Session, org_user_with_teams: AccountUser):
        """Test listing teams for user with organization"""
        from account_management.api import list_teams
        result = list_teams(org_user_with_teams, db)
        
        assert len(result) == 2
        team_names = [team.name for team in result]
        assert "Team Alpha" in team_names
        assert "Team Beta" in team_names

    def test_list_teams_no_org(self, db: Session):
        """Test listing teams for user without organization"""
        user = AccountUser(
            id="user456",
            email="noorg@example.com",
            status=UserStatus.ACTIVE
        )
        db.add(user)
        db.commit()
        
        from account_management.api import list_teams
        result = list_teams(user, db)
        
        assert result == []

    def test_create_team_success(self, db: Session, org_user_with_teams: AccountUser):
        """Test successful team creation"""
        team_data = TeamCreate(
            name="New Team",
            slug="new-team",
            description="A new team for testing"
        )
        
        from account_management.api import create_team
        result = create_team(team_data, org_user_with_teams, db)
        
        assert result.name == "New Team"
        assert result.slug == "new-team"
        assert result.description == "A new team for testing"
        
        # Verify team was created in database
        team = db.query(Team).filter(Team.name == "New Team").first()
        assert team is not None
        assert team.organization_id == org_user_with_teams.organization_id

    def test_create_team_no_org(self, db: Session):
        """Test creating team when user has no organization"""
        user = AccountUser(
            id="user456",
            email="noorg@example.com",
            status=UserStatus.ACTIVE
        )
        db.add(user)
        db.commit()
        
        team_data = TeamCreate(
            name="New Team",
            slug="new-team"
        )
        
        from account_management.api import create_team
        
        with pytest.raises(HTTPException) as exc_info:
            create_team(team_data, user, db)
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "User must belong to an organization" in str(exc_info.value.detail)

    def test_create_team_slug_exists(self, db: Session, org_user_with_teams: AccountUser):
        """Test creating team with existing slug in same organization"""
        team_data = TeamCreate(
            name="Another Alpha",
            slug="alpha"  # Slug already exists
        )
        
        from account_management.api import create_team
        
        with pytest.raises(HTTPException) as exc_info:
            create_team(team_data, org_user_with_teams, db)
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Team slug already exists in organization" in str(exc_info.value.detail)

    def test_get_team_success(self, db: Session, org_user_with_teams: AccountUser):
        """Test getting team details"""
        from account_management.api import get_team
        result = get_team("team1", org_user_with_teams, db)
        
        assert result.name == "Team Alpha"
        assert result.slug == "alpha"

    def test_get_team_not_found(self, db: Session, org_user_with_teams: AccountUser):
        """Test getting non-existent team"""
        from account_management.api import get_team
        
        with pytest.raises(HTTPException) as exc_info:
            get_team("nonexistent", org_user_with_teams, db)
        
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "Team not found" in str(exc_info.value.detail)

    def test_get_team_wrong_org(self, db: Session):
        """Test getting team from different organization"""
        # Create another organization and team
        other_org = Organization(
            id="other_org",
            name="Other Org",
            slug="other"
        )
        db.add(other_org)
        db.flush()
        
        other_team = Team(
            id="other_team",
            name="Other Team",
            slug="other",
            organization_id=other_org.id
        )
        db.add(other_team)
        
        # Create user in different organization
        user = AccountUser(
            id="user456",
            email="other@example.com",
            organization_id="org123",  # Different org
            status=UserStatus.ACTIVE
        )
        db.add(user)
        db.commit()
        
        from account_management.api import get_team
        
        with pytest.raises(HTTPException) as exc_info:
            get_team("other_team", user, db)
        
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "Team not found" in str(exc_info.value.detail)


class TestAPIKeyEndpoints:
    """Test API key management endpoints"""

    @pytest.fixture
    def org_user_with_keys(self, db: Session):
        """Create user with organization and API keys"""
        org = Organization(
            id="org123",
            name="Test Organization",
            slug="test-org"
        )
        db.add(org)
        db.flush()
        
        user = AccountUser(
            id="user123",
            email="test@example.com",
            organization_id=org.id,
            status=UserStatus.ACTIVE
        )
        db.add(user)
        
        key1 = APIKey(
            id="key1",
            name="Test Key 1",
            user_id=user.id,
            organization_id=org.id,
            is_active=True,
            scopes=["read", "write"]
        )
        key2 = APIKey(
            id="key2",
            name="Test Key 2",
            user_id=user.id,
            organization_id=org.id,
            is_active=False,  # Inactive key
            scopes=["read"]
        )
        db.add_all([key1, key2])
        db.commit()
        
        db.refresh(user)
        return user

    def test_list_api_keys(self, db: Session, org_user_with_keys: AccountUser):
        """Test listing user's active API keys"""
        from account_management.api import list_api_keys
        result = list_api_keys(org_user_with_keys, db)
        
        assert len(result) == 1  # Only active keys
        assert result[0].name == "Test Key 1"
        assert result[0].is_active == True

    def test_create_api_key_success(self, db: Session, org_user_with_keys: AccountUser):
        """Test successful API key creation"""
        key_data = APIKeyCreate(
            name="New API Key",
            scopes=["read", "write"],
            expires_in_days=30
        )
        
        with patch('account_management.api.AuthService.create_api_key') as mock_create:
            mock_api_key = APIKey(
                id="new_key",
                name="New API Key",
                user_id=org_user_with_keys.id,
                organization_id=org_user_with_keys.organization_id,
                scopes=["read", "write"],
                is_active=True
            )
            mock_create.return_value = ("raw_key_123", mock_api_key)
            
            from account_management.api import create_api_key
            result = create_api_key(key_data, org_user_with_keys, db)
            
            assert result.name == "New API Key"
            assert result.key == "raw_key_123"
            assert result.scopes == ["read", "write"]

    def test_create_api_key_no_org(self, db: Session):
        """Test creating API key when user has no organization"""
        user = AccountUser(
            id="user456",
            email="noorg@example.com",
            status=UserStatus.ACTIVE
        )
        db.add(user)
        db.commit()
        
        key_data = APIKeyCreate(
            name="New API Key",
            scopes=["read"]
        )
        
        from account_management.api import create_api_key
        
        with pytest.raises(HTTPException) as exc_info:
            create_api_key(key_data, user, db)
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "User must belong to an organization" in str(exc_info.value.detail)

    def test_create_api_key_with_expiration(self, db: Session, org_user_with_keys: AccountUser):
        """Test creating API key with expiration"""
        key_data = APIKeyCreate(
            name="Expiring Key",
            scopes=["read"],
            expires_in_days=7
        )
        
        with patch('account_management.api.AuthService.create_api_key') as mock_create, \
             patch('account_management.api.utc_now') as mock_now:
            
            mock_now.return_value = datetime(2025, 1, 1, tzinfo=UTC)
            expected_expiry = datetime(2025, 1, 8, tzinfo=UTC)
            
            mock_api_key = APIKey(
                id="expiring_key",
                name="Expiring Key",
                expires_at=expected_expiry
            )
            mock_create.return_value = ("raw_key", mock_api_key)
            
            from account_management.api import create_api_key
            result = create_api_key(key_data, org_user_with_keys, db)
            
            # Verify expiration was calculated correctly
            mock_create.assert_called_once()
            call_args = mock_create.call_args
            assert call_args[0][4] == expected_expiry  # expires_at parameter

    def test_revoke_api_key_success(self, db: Session, org_user_with_keys: AccountUser):
        """Test successful API key revocation"""
        from account_management.api import revoke_api_key
        result = revoke_api_key("key1", org_user_with_keys, db)
        
        assert result["message"] == "API key revoked successfully"
        
        # Verify key was deactivated
        key = db.query(APIKey).filter(APIKey.id == "key1").first()
        assert key.is_active == False
        assert key.revoked_at is not None

    def test_revoke_api_key_not_found(self, db: Session, org_user_with_keys: AccountUser):
        """Test revoking non-existent API key"""
        from account_management.api import revoke_api_key
        
        with pytest.raises(HTTPException) as exc_info:
            revoke_api_key("nonexistent", org_user_with_keys, db)
        
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "API key not found" in str(exc_info.value.detail)

    def test_revoke_api_key_wrong_user(self, db: Session):
        """Test revoking API key belonging to different user"""
        # Create another user
        other_user = AccountUser(
            id="other_user",
            email="other@example.com",
            status=UserStatus.ACTIVE
        )
        db.add(other_user)
        db.commit()
        
        from account_management.api import revoke_api_key
        
        with pytest.raises(HTTPException) as exc_info:
            revoke_api_key("key1", other_user, db)  # key1 belongs to org_user_with_keys
        
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "API key not found" in str(exc_info.value.detail)