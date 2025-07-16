"""
Authentication Service for Account Management
Handles password hashing, token generation, and authentication logic
"""
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import bcrypt
import jwt
from sqlalchemy.orm import Session

from account_management.models import (
    AccountUser,
    APIKey,
    EmailVerificationToken,
    PasswordResetToken,
    UserSession,
    UserStatus,
)
from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


def make_aware(dt: datetime) -> datetime:
    """Ensure datetime is timezone-aware (UTC)"""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def utc_now() -> datetime:
    """Get current UTC datetime (timezone-aware)"""
    return datetime.now(timezone.utc)


# JWT Settings - these should be class attributes to avoid circular imports


class AuthService:
    """Service for handling authentication operations"""

    # JWT Configuration
    JWT_SECRET_KEY = settings.secret_key
    JWT_ALGORITHM = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS = 30

    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash a password using bcrypt

        Args:
            password: Plain text password

        Returns:
            str: Hashed password
        """
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
        return hashed.decode("utf-8")

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """
        Verify a password against its hash

        Args:
            plain_password: Plain text password
            hashed_password: Hashed password to compare against

        Returns:
            bool: True if password matches, False otherwise
        """
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

    @staticmethod
    def generate_access_token(user_id: str, email: str) -> str:
        """
        Generate a JWT access token

        Args:
            user_id: User ID
            email: User email

        Returns:
            str: JWT access token
        """
        expire = utc_now() + timedelta(minutes=AuthService.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
        payload = {"sub": user_id, "email": email, "exp": expire, "iat": utc_now(), "type": "access"}
        return jwt.encode(payload, AuthService.JWT_SECRET_KEY, algorithm=AuthService.JWT_ALGORITHM)

    @staticmethod
    def generate_refresh_token(user_id: str) -> str:
        """
        Generate a JWT refresh token

        Args:
            user_id: User ID

        Returns:
            str: JWT refresh token
        """
        expire = utc_now() + timedelta(days=AuthService.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
        payload = {
            "sub": user_id,
            "exp": expire,
            "iat": utc_now(),
            "type": "refresh",
            "jti": secrets.token_urlsafe(32),  # Unique token ID
        }
        return jwt.encode(payload, AuthService.JWT_SECRET_KEY, algorithm=AuthService.JWT_ALGORITHM)

    @staticmethod
    def decode_token(token: str) -> dict:
        """
        Decode and validate a JWT token

        Args:
            token: JWT token

        Returns:
            dict: Token payload

        Raises:
            jwt.ExpiredSignatureError: If token is expired
            jwt.InvalidTokenError: If token is invalid
        """
        return jwt.decode(token, AuthService.JWT_SECRET_KEY, algorithms=[AuthService.JWT_ALGORITHM])

    @staticmethod
    def create_session(
        db: Session,
        user: AccountUser,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        device_id: Optional[str] = None,
    ) -> Tuple[str, str, UserSession]:
        """
        Create a new user session

        Args:
            db: Database session
            user: User object
            ip_address: Client IP address
            user_agent: Client user agent
            device_id: Device identifier

        Returns:
            Tuple of (access_token, refresh_token, session)
        """
        # Generate tokens
        access_token = AuthService.generate_access_token(user.id, user.email)
        refresh_token = AuthService.generate_refresh_token(user.id)

        # Hash tokens for storage
        access_token_hash = AuthService.hash_token(access_token)
        refresh_token_hash = AuthService.hash_token(refresh_token)

        # Create session
        session = UserSession(
            user_id=user.id,
            session_token_hash=access_token_hash,
            refresh_token_hash=refresh_token_hash,
            ip_address=ip_address,
            user_agent=user_agent,
            device_id=device_id,
            expires_at=utc_now() + timedelta(minutes=AuthService.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
            refresh_expires_at=utc_now() + timedelta(days=AuthService.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
            is_active=True,
        )

        db.add(session)
        db.commit()

        # Update last login
        user.last_login_at = utc_now()
        user.last_login_ip = ip_address
        db.commit()

        return access_token, refresh_token, session

    @staticmethod
    def hash_token(token: str) -> str:
        """
        Hash a token for secure storage

        Args:
            token: Token to hash

        Returns:
            str: Hashed token
        """
        import hashlib

        return hashlib.sha256(token.encode()).hexdigest()

    @staticmethod
    def authenticate_user(db: Session, email: str, password: str) -> Optional[AccountUser]:
        """
        Authenticate a user by email and password

        Args:
            db: Database session
            email: User email
            password: User password

        Returns:
            AccountUser if authentication successful, None otherwise
        """
        user = (
            db.query(AccountUser)
            .filter(AccountUser.email == email.lower(), AccountUser.status == UserStatus.ACTIVE)
            .first()
        )

        if not user:
            return None

        # Check if account is locked
        if user.locked_until and make_aware(user.locked_until) > utc_now():
            logger.warning(f"Login attempt for locked account: {email}")
            return None

        # Verify password
        if not user.password_hash or not AuthService.verify_password(password, user.password_hash):
            # Increment failed attempts
            user.failed_login_attempts += 1

            # Lock account after 5 failed attempts
            if user.failed_login_attempts >= 5:
                user.locked_until = utc_now() + timedelta(hours=1)
                logger.warning(f"Account locked due to failed attempts: {email}")

            db.commit()
            return None

        # Reset failed attempts on successful login
        user.failed_login_attempts = 0
        user.locked_until = None
        db.commit()

        return user

    @staticmethod
    def create_email_verification_token(db: Session, user: AccountUser) -> str:
        """
        Create an email verification token

        Args:
            db: Database session
            user: User object

        Returns:
            str: Verification token
        """
        token = secrets.token_urlsafe(32)
        token_hash = AuthService.hash_token(token)

        verification = EmailVerificationToken(
            user_id=user.id,
            email=user.email,
            token_hash=token_hash,
            expires_at=utc_now() + timedelta(hours=24),
        )

        db.add(verification)
        db.commit()

        return token

    @staticmethod
    def verify_email_token(db: Session, token: str) -> Optional[AccountUser]:
        """
        Verify an email verification token

        Args:
            db: Database session
            token: Verification token

        Returns:
            AccountUser if token is valid, None otherwise
        """
        token_hash = AuthService.hash_token(token)

        verification = (
            db.query(EmailVerificationToken)
            .filter(
                EmailVerificationToken.token_hash == token_hash,
                EmailVerificationToken.used_at.is_(None),
                EmailVerificationToken.expires_at > utc_now(),
            )
            .first()
        )

        if not verification:
            return None

        # Mark token as used
        verification.used_at = utc_now()

        # Update user
        user = db.query(AccountUser).filter(AccountUser.id == verification.user_id).first()

        if user:
            user.email_verified = True
            user.email_verified_at = utc_now()

        db.commit()

        return user

    @staticmethod
    def create_password_reset_token(db: Session, email: str) -> Optional[str]:
        """
        Create a password reset token

        Args:
            db: Database session
            email: User email

        Returns:
            str: Reset token if user exists, None otherwise
        """
        user = (
            db.query(AccountUser)
            .filter(AccountUser.email == email.lower(), AccountUser.status == UserStatus.ACTIVE)
            .first()
        )

        if not user:
            return None

        token = secrets.token_urlsafe(32)
        token_hash = AuthService.hash_token(token)

        reset = PasswordResetToken(user_id=user.id, token_hash=token_hash, expires_at=utc_now() + timedelta(hours=1))

        db.add(reset)
        db.commit()

        return token

    @staticmethod
    def reset_password(db: Session, token: str, new_password: str) -> Optional[AccountUser]:
        """
        Reset a user's password using a reset token

        Args:
            db: Database session
            token: Reset token
            new_password: New password

        Returns:
            AccountUser if successful, None otherwise
        """
        token_hash = AuthService.hash_token(token)

        reset = (
            db.query(PasswordResetToken)
            .filter(
                PasswordResetToken.token_hash == token_hash,
                PasswordResetToken.used_at.is_(None),
                PasswordResetToken.expires_at > utc_now(),
            )
            .first()
        )

        if not reset:
            return None

        # Mark token as used
        reset.used_at = utc_now()

        # Update user password
        user = db.query(AccountUser).filter(AccountUser.id == reset.user_id).first()

        if user:
            user.password_hash = AuthService.hash_password(new_password)
            user.failed_login_attempts = 0
            user.locked_until = None

        db.commit()

        return user

    @staticmethod
    def create_api_key(
        db: Session, user: AccountUser, name: str, scopes: list, expires_at: Optional[datetime] = None
    ) -> Tuple[str, APIKey]:
        """
        Create a new API key

        Args:
            db: Database session
            user: User object
            name: API key name
            scopes: List of permission scopes
            expires_at: Optional expiration date

        Returns:
            Tuple of (raw_key, api_key_object)
        """
        # Generate secure API key
        raw_key = f"lf_{secrets.token_urlsafe(32)}"
        key_hash = AuthService.hash_token(raw_key)
        key_prefix = raw_key[:8]

        api_key = APIKey(
            name=name,
            key_hash=key_hash,
            key_prefix=key_prefix,
            user_id=user.id,
            organization_id=user.organization_id,
            scopes=scopes,
            expires_at=expires_at,
            is_active=True,
        )

        db.add(api_key)
        db.commit()

        return raw_key, api_key

    @staticmethod
    def validate_api_key(db: Session, api_key: str) -> Optional[APIKey]:
        """
        Validate an API key

        Args:
            db: Database session
            api_key: Raw API key

        Returns:
            APIKey if valid, None otherwise
        """
        key_hash = AuthService.hash_token(api_key)

        key = db.query(APIKey).filter(APIKey.key_hash == key_hash, APIKey.is_active == True).first()

        if not key:
            return None

        # Check expiration
        if key.expires_at and make_aware(key.expires_at) < utc_now():
            return None

        # Update usage
        key.last_used_at = utc_now()
        key.usage_count += 1
        db.commit()

        return key
