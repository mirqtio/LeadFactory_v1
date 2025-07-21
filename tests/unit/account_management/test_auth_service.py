"""
Unit tests for authentication service
"""

from datetime import UTC, datetime, timedelta, timezone

import jwt
import pytest
from sqlalchemy.orm import Session

from account_management.auth_service import AuthService
from account_management.models import (
    AccountUser,
    APIKey,
    EmailVerificationToken,
    PasswordResetToken,
    UserSession,
    UserStatus,
)

# Mark entire module as unit test and critical - authentication is essential
pytestmark = [pytest.mark.unit, pytest.mark.critical]


class TestAuthService:
    """Test authentication service methods"""

    def test_hash_password(self):
        """Test password hashing"""
        password = "SecurePass123!"
        hashed = AuthService.hash_password(password)

        assert hashed != password
        assert len(hashed) > 0
        assert isinstance(hashed, str)

    def test_verify_password_correct(self):
        """Test verifying correct password"""
        password = "SecurePass123!"
        hashed = AuthService.hash_password(password)

        assert AuthService.verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Test verifying incorrect password"""
        password = "SecurePass123!"
        hashed = AuthService.hash_password(password)

        assert AuthService.verify_password("WrongPassword", hashed) is False

    def test_generate_access_token(self):
        """Test access token generation"""
        user_id = "test-user-id"
        email = "test@example.com"

        token = AuthService.generate_access_token(user_id, email)

        assert isinstance(token, str)
        assert len(token) > 0

        # Decode and verify
        payload = jwt.decode(token, AuthService.JWT_SECRET_KEY, algorithms=[AuthService.JWT_ALGORITHM])
        assert payload["sub"] == user_id
        assert payload["email"] == email
        assert payload["type"] == "access"
        assert "exp" in payload
        assert "iat" in payload

    def test_generate_refresh_token(self):
        """Test refresh token generation"""
        user_id = "test-user-id"

        token = AuthService.generate_refresh_token(user_id)

        assert isinstance(token, str)
        assert len(token) > 0

        # Decode and verify
        payload = jwt.decode(token, AuthService.JWT_SECRET_KEY, algorithms=[AuthService.JWT_ALGORITHM])
        assert payload["sub"] == user_id
        assert payload["type"] == "refresh"
        assert "exp" in payload
        assert "iat" in payload
        assert "jti" in payload  # Unique token ID

    def test_decode_valid_token(self):
        """Test decoding valid token"""
        user_id = "test-user-id"
        email = "test@example.com"

        token = AuthService.generate_access_token(user_id, email)
        payload = AuthService.decode_token(token)

        assert payload["sub"] == user_id
        assert payload["email"] == email

    def test_decode_expired_token(self):
        """Test decoding expired token"""
        # Create expired token
        expire = datetime.now(UTC) - timedelta(minutes=1)
        payload = {"sub": "test-user-id", "exp": expire, "iat": datetime.now(UTC)}
        token = jwt.encode(payload, AuthService.JWT_SECRET_KEY, algorithm=AuthService.JWT_ALGORITHM)

        with pytest.raises(jwt.ExpiredSignatureError):
            AuthService.decode_token(token)

    def test_decode_invalid_token(self):
        """Test decoding invalid token"""
        with pytest.raises(jwt.InvalidTokenError):
            AuthService.decode_token("invalid-token")

    def test_hash_token(self):
        """Test token hashing for storage"""
        token = "test-token-123"
        hashed = AuthService.hash_token(token)

        assert isinstance(hashed, str)
        assert len(hashed) == 64  # SHA256 hex length
        assert hashed != token

    def test_create_session(self, db: Session):
        """Test creating user session"""
        # Create test user
        user = AccountUser(
            id="test-user-id",
            email="test@example.com",
            password_hash=AuthService.hash_password("password"),
            status=UserStatus.ACTIVE,
        )
        db.add(user)
        db.commit()

        # Create session
        access_token, refresh_token, session = AuthService.create_session(
            db, user, ip_address="127.0.0.1", user_agent="Test Agent", device_id="test-device"
        )

        assert isinstance(access_token, str)
        assert isinstance(refresh_token, str)
        assert isinstance(session, UserSession)

        assert session.user_id == user.id
        assert session.ip_address == "127.0.0.1"
        assert session.user_agent == "Test Agent"
        assert session.device_id == "test-device"
        assert session.is_active is True

        # Verify user last login updated
        db.refresh(user)
        assert user.last_login_at is not None
        assert user.last_login_ip == "127.0.0.1"

    def test_authenticate_user_success(self, db: Session):
        """Test successful user authentication"""
        # Create test user
        password = "SecurePass123!"
        user = AccountUser(
            email="test@example.com", password_hash=AuthService.hash_password(password), status=UserStatus.ACTIVE
        )
        db.add(user)
        db.commit()

        # Authenticate
        authenticated = AuthService.authenticate_user(db, "test@example.com", password)

        assert authenticated is not None
        assert authenticated.id == user.id
        assert authenticated.failed_login_attempts == 0

    def test_authenticate_user_wrong_password(self, db: Session):
        """Test authentication with wrong password"""
        # Create test user
        user = AccountUser(
            email="test@example.com",
            password_hash=AuthService.hash_password("correct_password"),
            status=UserStatus.ACTIVE,
            failed_login_attempts=0,
        )
        db.add(user)
        db.commit()

        # Authenticate with wrong password
        authenticated = AuthService.authenticate_user(db, "test@example.com", "wrong_password")

        assert authenticated is None

        # Check failed attempts incremented
        db.refresh(user)
        assert user.failed_login_attempts == 1

    def test_authenticate_user_account_locked(self, db: Session):
        """Test authentication with locked account"""
        # Create locked user
        user = AccountUser(
            email="test@example.com",
            password_hash=AuthService.hash_password("password"),
            status=UserStatus.ACTIVE,
            locked_until=datetime.now(UTC) + timedelta(hours=1),
        )
        db.add(user)
        db.commit()

        # Try to authenticate
        authenticated = AuthService.authenticate_user(db, "test@example.com", "password")

        assert authenticated is None

    def test_authenticate_user_account_lockout(self, db: Session):
        """Test account lockout after failed attempts"""
        # Create test user
        password = "correct_password"
        user = AccountUser(
            email="test@example.com",
            password_hash=AuthService.hash_password(password),
            status=UserStatus.ACTIVE,
            failed_login_attempts=4,  # One away from lockout
        )
        db.add(user)
        db.commit()

        # Failed authentication should lock account
        authenticated = AuthService.authenticate_user(db, "test@example.com", "wrong_password")

        assert authenticated is None

        # Check account is locked
        db.refresh(user)
        assert user.failed_login_attempts == 5
        assert user.locked_until is not None
        assert user.locked_until > datetime.utcnow()

    def test_create_email_verification_token(self, db: Session):
        """Test creating email verification token"""
        # Create test user
        user = AccountUser(id="test-user-id", email="test@example.com", status=UserStatus.ACTIVE)
        db.add(user)
        db.commit()

        # Create token
        token = AuthService.create_email_verification_token(db, user)

        assert isinstance(token, str)
        assert len(token) > 0

        # Check token record created
        verification = db.query(EmailVerificationToken).filter(EmailVerificationToken.user_id == user.id).first()

        assert verification is not None
        assert verification.email == user.email
        assert verification.expires_at > datetime.utcnow()

    def test_verify_email_token_success(self, db: Session):
        """Test successful email verification"""
        # Create unverified user
        user = AccountUser(id="test-user-id", email="test@example.com", status=UserStatus.ACTIVE, email_verified=False)
        db.add(user)
        db.commit()

        # Create verification token
        token = AuthService.create_email_verification_token(db, user)

        # Verify token
        verified_user = AuthService.verify_email_token(db, token)

        assert verified_user is not None
        assert verified_user.id == user.id
        assert verified_user.email_verified is True
        assert verified_user.email_verified_at is not None

    def test_verify_email_token_invalid(self, db: Session):
        """Test verifying invalid email token"""
        result = AuthService.verify_email_token(db, "invalid-token")
        assert result is None

    def test_create_password_reset_token(self, db: Session):
        """Test creating password reset token"""
        # Create test user
        user = AccountUser(email="test@example.com", status=UserStatus.ACTIVE)
        db.add(user)
        db.commit()

        # Create token
        token = AuthService.create_password_reset_token(db, "test@example.com")

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

        # Check token record created
        reset = db.query(PasswordResetToken).filter(PasswordResetToken.user_id == user.id).first()

        assert reset is not None
        assert reset.expires_at > datetime.utcnow()

    def test_create_password_reset_token_no_user(self, db: Session):
        """Test creating reset token for non-existent user"""
        token = AuthService.create_password_reset_token(db, "nonexistent@example.com")
        assert token is None

    def test_reset_password_success(self, db: Session):
        """Test successful password reset"""
        # Create test user
        old_password = "OldPassword123!"
        user = AccountUser(
            email="test@example.com",
            password_hash=AuthService.hash_password(old_password),
            status=UserStatus.ACTIVE,
            failed_login_attempts=3,
        )
        db.add(user)
        db.commit()

        # Create reset token
        token = AuthService.create_password_reset_token(db, user.email)

        # Reset password
        new_password = "NewPassword123!"
        reset_user = AuthService.reset_password(db, token, new_password)

        assert reset_user is not None
        assert reset_user.id == user.id

        # Verify new password works
        assert AuthService.verify_password(new_password, reset_user.password_hash)
        assert not AuthService.verify_password(old_password, reset_user.password_hash)

        # Check failed attempts cleared
        assert reset_user.failed_login_attempts == 0
        assert reset_user.locked_until is None

    def test_reset_password_invalid_token(self, db: Session):
        """Test resetting password with invalid token"""
        result = AuthService.reset_password(db, "invalid-token", "NewPassword123!")
        assert result is None

    def test_create_api_key(self, db: Session):
        """Test creating API key"""
        # Create test user with organization
        user = AccountUser(
            id="test-user-id", email="test@example.com", organization_id="test-org-id", status=UserStatus.ACTIVE
        )
        db.add(user)
        db.commit()

        # Create API key
        raw_key, api_key = AuthService.create_api_key(
            db,
            user,
            "Test API Key",
            ["read:leads", "write:leads"],
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )

        assert raw_key.startswith("lf_")
        assert len(raw_key) > 10

        assert api_key.name == "Test API Key"
        assert api_key.user_id == user.id
        assert api_key.organization_id == user.organization_id
        assert api_key.scopes == ["read:leads", "write:leads"]
        assert api_key.is_active is True
        assert api_key.key_prefix == raw_key[:8]

    def test_validate_api_key_success(self, db: Session):
        """Test validating valid API key"""
        # Create test user
        user = AccountUser(
            id="test-user-id", email="test@example.com", organization_id="test-org-id", status=UserStatus.ACTIVE
        )
        db.add(user)
        db.commit()

        # Create API key
        raw_key, api_key = AuthService.create_api_key(db, user, "Test Key", [])

        # Validate key
        validated = AuthService.validate_api_key(db, raw_key)

        assert validated is not None
        assert validated.id == api_key.id
        assert validated.usage_count == 1
        assert validated.last_used_at is not None

    def test_validate_api_key_invalid(self, db: Session):
        """Test validating invalid API key"""
        result = AuthService.validate_api_key(db, "invalid-key")
        assert result is None

    def test_validate_api_key_expired(self, db: Session):
        """Test validating expired API key"""
        # Create test user
        user = AccountUser(
            id="test-user-id", email="test@example.com", organization_id="test-org-id", status=UserStatus.ACTIVE
        )
        db.add(user)
        db.commit()

        # Create expired API key
        raw_key, api_key = AuthService.create_api_key(
            db, user, "Expired Key", [], expires_at=datetime.now(UTC) - timedelta(days=1)
        )

        # Try to validate
        result = AuthService.validate_api_key(db, raw_key)
        assert result is None
