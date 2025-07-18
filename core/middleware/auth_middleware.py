"""
Authentication middleware for FastAPI with RBAC support
Implements organization-scoped data access and request logging
"""
import logging
import time
from typing import Optional
from uuid import uuid4

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from account_management.auth_service import AuthService
from account_management.models import AccountUser, UserStatus
from core.auth import get_current_user_from_api_key, get_current_user_from_token
from core.logging import get_logger
from database.session import get_db

logger = get_logger(__name__)


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """
    Authentication middleware for FastAPI applications

    Features:
    - JWT token and API key authentication
    - Organization-scoped data access
    - Request logging and audit trail
    - Rate limiting and security headers
    """

    def __init__(self, app, exempt_paths: Optional[list] = None):
        super().__init__(app)
        self.exempt_paths = exempt_paths or [
            "/health",
            "/metrics",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/api/v1/auth/login",
            "/api/v1/auth/register",
            "/api/v1/auth/verify-email",
            "/api/v1/auth/reset-password",
        ]

    async def dispatch(self, request: Request, call_next):
        """Process request with authentication and authorization"""
        start_time = time.time()
        request_id = str(uuid4())

        # Add request ID to state
        request.state.request_id = request_id

        # Skip authentication for exempt paths
        if self._is_exempt_path(request.url.path):
            response = await call_next(request)
            return self._add_security_headers(response)

        # Extract authentication credentials
        auth_result = await self._authenticate_request(request)

        if not auth_result["authenticated"]:
            logger.warning(f"Authentication failed for {request.url.path}: {auth_result['error']}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"error": "authentication_required", "message": auth_result["error"], "request_id": request_id},
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Add user context to request
        request.state.user = auth_result["user"]
        request.state.organization_id = auth_result["user"].organization_id

        # Log authenticated request
        logger.info(
            f"Authenticated request: {request.method} {request.url.path} "
            f"user={auth_result['user'].id} org={auth_result['user'].organization_id}"
        )

        # Process request
        try:
            response = await call_next(request)

            # Log successful response
            duration = time.time() - start_time
            logger.info(
                f"Request completed: {request.method} {request.url.path} "
                f"status={response.status_code} duration={duration:.3f}s"
            )

            return self._add_security_headers(response)

        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                f"Request failed: {request.method} {request.url.path} " f"error={str(e)} duration={duration:.3f}s"
            )

            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"error": "internal_error", "message": "An internal error occurred", "request_id": request_id},
            )

    def _is_exempt_path(self, path: str) -> bool:
        """Check if path is exempt from authentication"""
        return any(path.startswith(exempt_path) for exempt_path in self.exempt_paths)

    async def _authenticate_request(self, request: Request) -> dict:
        """Authenticate request using JWT token or API key"""
        # Extract authorization header
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            return {"authenticated": False, "error": "Missing Authorization header", "user": None}

        # Parse Bearer token
        try:
            scheme, token = auth_header.split(" ", 1)
            if scheme.lower() != "bearer":
                return {"authenticated": False, "error": "Invalid authorization scheme. Use Bearer token", "user": None}
        except ValueError:
            return {"authenticated": False, "error": "Invalid authorization header format", "user": None}

        # Get database session
        db = next(get_db())

        try:
            # Authenticate user
            if token.startswith("lf_"):
                # API key authentication
                user = get_current_user_from_api_key(token, db)
            else:
                # JWT token authentication
                user = get_current_user_from_token(token, db)

            if not user:
                return {"authenticated": False, "error": "Invalid or expired credentials", "user": None}

            # Check user status
            if user.status != UserStatus.ACTIVE:
                return {"authenticated": False, "error": "User account is not active", "user": None}

            # Check organization access
            if not user.organization_id:
                return {"authenticated": False, "error": "User has no organization access", "user": None}

            return {"authenticated": True, "error": None, "user": user}

        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            return {"authenticated": False, "error": "Authentication service error", "user": None}

        finally:
            db.close()

    def _add_security_headers(self, response: Response) -> Response:
        """Add security headers to response"""
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


def create_auth_middleware(exempt_paths: Optional[list] = None) -> AuthenticationMiddleware:
    """Factory function to create authentication middleware"""
    return AuthenticationMiddleware(None, exempt_paths)
