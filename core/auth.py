"""Authentication utilities for FastAPI routes with RBAC support"""
import os
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from account_management.auth_service import AuthService
from account_management.models import AccountUser, APIKey, UserStatus
from core.config import settings
from core.logging import get_logger
from database.session import get_db

logger = get_logger(__name__)
security = HTTPBearer()


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
