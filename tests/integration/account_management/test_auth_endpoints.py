"""
Integration tests for authentication endpoints
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from account_management.auth_service import AuthService
from account_management.models import AccountUser, Organization, UserStatus
from main import app


class TestAuthEndpoints:
    """Test authentication API endpoints"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    def test_register_new_user(self, client: TestClient, db: Session):
        """Test registering new user"""
        response = client.post(
            "/api/v1/accounts/register",
            json={
                "email": "newuser@example.com",
                "password": "SecurePass123!",
                "full_name": "New User",
                "username": "newuser",
                "organization_name": "New Company",
            },
        )

        assert response.status_code == 201
        data = response.json()

        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "Bearer"

        # Check user details
        user_data = data["user"]
        assert user_data["email"] == "newuser@example.com"
        assert user_data["username"] == "newuser"
        assert user_data["full_name"] == "New User"
        assert user_data["email_verified"] is False
        assert user_data["organization_id"] is not None

        # Verify user in database
        user = db.query(AccountUser).filter(AccountUser.email == "newuser@example.com").first()
        assert user is not None
        assert user.organization is not None
        assert user.organization.name == "New Company"

    def test_register_duplicate_email(self, client: TestClient, db: Session):
        """Test registering with duplicate email"""
        # Create existing user
        user = AccountUser(email="existing@example.com", password_hash="hash", status=UserStatus.ACTIVE)
        db.add(user)
        db.commit()

        # Try to register with same email
        response = client.post(
            "/api/v1/accounts/register", json={"email": "existing@example.com", "password": "SecurePass123!"}
        )

        assert response.status_code == 400
        assert "Email already registered" in response.json()["detail"]

    def test_register_duplicate_username(self, client: TestClient, db: Session):
        """Test registering with duplicate username"""
        # Create existing user
        user = AccountUser(email="user1@example.com", username="existinguser", status=UserStatus.ACTIVE)
        db.add(user)
        db.commit()

        # Try to register with same username
        response = client.post(
            "/api/v1/accounts/register",
            json={"email": "user2@example.com", "password": "SecurePass123!", "username": "existinguser"},
        )

        assert response.status_code == 400
        assert "Username already taken" in response.json()["detail"]

    def test_register_weak_password(self, client: TestClient):
        """Test registering with weak password"""
        response = client.post(
            "/api/v1/accounts/register",
            json={"email": "newuser@example.com", "password": "weak"},  # Too short, no uppercase, no digit
        )

        assert response.status_code == 422
        errors = response.json()["detail"]
        assert any("at least" in str(e) for e in errors)

    def test_login_success(self, client: TestClient, db: Session):
        """Test successful login"""
        # Create test user
        password = "TestPass123!"
        user = AccountUser(
            email="testuser@example.com",
            password_hash=AuthService.hash_password(password),
            status=UserStatus.ACTIVE,
            email_verified=True,
        )
        db.add(user)
        db.commit()

        # Login
        response = client.post(
            "/api/v1/accounts/login",
            json={"email": "testuser@example.com", "password": password, "device_id": "test-device"},
        )

        assert response.status_code == 200
        data = response.json()

        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["email"] == "testuser@example.com"

    def test_login_invalid_credentials(self, client: TestClient, db: Session):
        """Test login with invalid credentials"""
        # Create test user
        user = AccountUser(
            email="testuser@example.com",
            password_hash=AuthService.hash_password("correct_password"),
            status=UserStatus.ACTIVE,
        )
        db.add(user)
        db.commit()

        # Try wrong password
        response = client.post(
            "/api/v1/accounts/login", json={"email": "testuser@example.com", "password": "wrong_password"}
        )

        assert response.status_code == 401
        assert "Invalid email or password" in response.json()["detail"]

    def test_login_inactive_user(self, client: TestClient, db: Session):
        """Test login with inactive user"""
        # Create inactive user
        user = AccountUser(
            email="inactive@example.com",
            password_hash=AuthService.hash_password("password"),
            status=UserStatus.INACTIVE,
        )
        db.add(user)
        db.commit()

        # Try to login
        response = client.post("/api/v1/accounts/login", json={"email": "inactive@example.com", "password": "password"})

        assert response.status_code == 401

    def test_refresh_token(self, client: TestClient, db: Session):
        """Test refreshing access token"""
        # Create and login user
        password = "TestPass123!"
        user = AccountUser(
            email="testuser@example.com", password_hash=AuthService.hash_password(password), status=UserStatus.ACTIVE
        )
        db.add(user)
        db.commit()

        # Login to get tokens
        login_response = client.post(
            "/api/v1/accounts/login", json={"email": "testuser@example.com", "password": password}
        )

        refresh_token = login_response.json()["refresh_token"]

        # Refresh token
        response = client.post("/api/v1/accounts/refresh", json={"refresh_token": refresh_token})

        assert response.status_code == 200
        data = response.json()

        assert "access_token" in data
        assert "refresh_token" in data
        assert data["access_token"] != login_response.json()["access_token"]

    def test_refresh_invalid_token(self, client: TestClient):
        """Test refreshing with invalid token"""
        response = client.post("/api/v1/accounts/refresh", json={"refresh_token": "invalid-token"})

        assert response.status_code == 401
        assert "Invalid refresh token" in response.json()["detail"]

    def test_get_current_user(self, client: TestClient, db: Session):
        """Test getting current user profile"""
        # Create and login user
        org = Organization(name="Test Org", slug="test-org")
        db.add(org)
        db.flush()

        password = "TestPass123!"
        user = AccountUser(
            email="testuser@example.com",
            password_hash=AuthService.hash_password(password),
            full_name="Test User",
            organization_id=org.id,
            status=UserStatus.ACTIVE,
        )
        db.add(user)
        db.commit()

        # Login
        login_response = client.post(
            "/api/v1/accounts/login", json={"email": "testuser@example.com", "password": password}
        )

        access_token = login_response.json()["access_token"]

        # Get profile
        response = client.get("/api/v1/accounts/me", headers={"Authorization": f"Bearer {access_token}"})

        assert response.status_code == 200
        data = response.json()

        assert data["email"] == "testuser@example.com"
        assert data["full_name"] == "Test User"
        assert data["organization"]["name"] == "Test Org"

    def test_get_current_user_unauthorized(self, client: TestClient):
        """Test getting profile without auth"""
        response = client.get("/api/v1/accounts/me")
        assert response.status_code == 403  # No Authorization header

    def test_change_password(self, client: TestClient, db: Session):
        """Test changing password"""
        # Create and login user
        old_password = "OldPass123!"
        user = AccountUser(
            email="testuser@example.com",
            password_hash=AuthService.hash_password(old_password),
            status=UserStatus.ACTIVE,
        )
        db.add(user)
        db.commit()

        # Login
        login_response = client.post(
            "/api/v1/accounts/login", json={"email": "testuser@example.com", "password": old_password}
        )

        access_token = login_response.json()["access_token"]

        # Change password
        new_password = "NewPass123!"
        response = client.post(
            "/api/v1/accounts/me/change-password",
            json={"current_password": old_password, "new_password": new_password},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 200

        # Verify new password works
        login_response = client.post(
            "/api/v1/accounts/login", json={"email": "testuser@example.com", "password": new_password}
        )

        assert login_response.status_code == 200

    def test_verify_email(self, client: TestClient, db: Session):
        """Test email verification"""
        # Create unverified user
        user = AccountUser(
            id="test-user-id", email="unverified@example.com", status=UserStatus.ACTIVE, email_verified=False
        )
        db.add(user)
        db.commit()

        # Create verification token
        token = AuthService.create_email_verification_token(db, user)

        # Verify email
        response = client.post("/api/v1/accounts/verify-email", json={"token": token})

        assert response.status_code == 200

        # Check user is verified
        db.refresh(user)
        assert user.email_verified is True

    def test_password_reset_flow(self, client: TestClient, db: Session):
        """Test complete password reset flow"""
        # Create user
        user = AccountUser(
            email="resetuser@example.com",
            password_hash=AuthService.hash_password("OldPassword123!"),
            status=UserStatus.ACTIVE,
        )
        db.add(user)
        db.commit()

        # Request reset
        response = client.post("/api/v1/accounts/password-reset-request", json={"email": "resetuser@example.com"})

        assert response.status_code == 200

        # Get token from database (in real app, this would be sent via email)
        from account_management.models import PasswordResetToken

        reset_token = db.query(PasswordResetToken).filter(PasswordResetToken.user_id == user.id).first()

        # Reconstruct raw token (in real app, this would be in the email)
        # For testing, we'll create a new token
        token = AuthService.create_password_reset_token(db, user.email)

        # Reset password
        new_password = "NewPassword123!"
        response = client.post("/api/v1/accounts/password-reset", json={"token": token, "new_password": new_password})

        assert response.status_code == 200

        # Verify new password works
        login_response = client.post(
            "/api/v1/accounts/login", json={"email": "resetuser@example.com", "password": new_password}
        )

        assert login_response.status_code == 200
