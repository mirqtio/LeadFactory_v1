"""
RBAC Security Middleware for FastAPI

Provides comprehensive security enforcement at the middleware level:
- Automatic detection of unprotected endpoints
- Fallback authentication requirements
- Security audit logging
- Endpoint classification and risk assessment
"""

import re
import time

from fastapi import HTTPException, Request, status
from fastapi.security.utils import get_authorization_scheme_param
from starlette.middleware.base import BaseHTTPMiddleware

from core.auth import get_current_user_from_api_key, get_current_user_from_token, verify_internal_token
from core.logging import get_logger
from database.session import get_db

logger = get_logger("rbac_middleware", domain="security")


class RBACSecurityMiddleware(BaseHTTPMiddleware):
    """
    RBAC Security Middleware for comprehensive endpoint protection

    Features:
    - Automatic authentication requirement for sensitive endpoints
    - Whitelist for public endpoints
    - Security audit logging
    - Fallback protection for unprotected endpoints
    """

    # Public endpoints that don't require authentication
    PUBLIC_ENDPOINTS: set[str] = {
        "/",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/metrics",
        "/favicon.ico",
        # Health check endpoints (limited)
        "/api/v1/health",
        "/api/v1/gateway/health",
        # Authentication endpoints
        "/api/v1/auth/login",
        "/api/v1/auth/register",
        "/api/v1/auth/refresh",
        "/api/v1/auth/password-reset-request",
        "/api/v1/auth/password-reset",
        "/api/v1/auth/verify-email",
        # Static files
        "/static",
    }

    # Patterns for public endpoint matching
    PUBLIC_PATTERNS: list[str] = [
        r"^/static/.*",
        r"^/favicon\.ico$",
        r"^/robots\.txt$",
        r"^/_health$",
    ]

    # Internal endpoints that use internal token authentication
    INTERNAL_ENDPOINTS: set[str] = {
        "/api/internal",
    }

    INTERNAL_PATTERNS: list[str] = [
        r"^/api/internal/.*",
        r"^/admin/.*",
    ]

    # High-risk endpoints that require special attention
    HIGH_RISK_ENDPOINTS: set[str] = {
        "/api/v1/users",
        "/api/v1/organizations",
        "/api/v1/costs",
        "/api/v1/admin",
    }

    HIGH_RISK_PATTERNS: list[str] = [
        r"^/api/v1/users/.*",
        r"^/api/v1/organizations/.*",
        r"^/api/v1/admin/.*",
        r".*/(delete|remove|destroy)/.*",
        r".*/api-keys/.*",
    ]

    def __init__(self, app, enforce_auth: bool = True, audit_mode: bool = False):
        """
        Initialize RBAC Security Middleware

        Args:
            app: FastAPI application
            enforce_auth: Whether to enforce authentication (False for development)
            audit_mode: Log security violations without blocking (for transition)
        """
        super().__init__(app)
        self.enforce_auth = enforce_auth
        self.audit_mode = audit_mode
        self.compiled_public_patterns = [re.compile(pattern) for pattern in self.PUBLIC_PATTERNS]
        self.compiled_internal_patterns = [re.compile(pattern) for pattern in self.INTERNAL_PATTERNS]
        self.compiled_risk_patterns = [re.compile(pattern) for pattern in self.HIGH_RISK_PATTERNS]

    async def dispatch(self, request: Request, call_next):
        """
        Process request through RBAC security middleware

        Args:
            request: FastAPI request
            call_next: Next middleware in chain

        Returns:
            Response: Processed response
        """
        start_time = time.time()
        path = request.url.path
        method = request.method

        # Skip OPTIONS requests (CORS preflight)
        if method == "OPTIONS":
            return await call_next(request)

        # Classify endpoint
        endpoint_type = self._classify_endpoint(path, method)

        # Log request for audit
        self._log_request(request, endpoint_type)

        # Apply security checks based on endpoint type
        try:
            if endpoint_type == "public":
                # Public endpoints - no authentication required
                pass
            elif endpoint_type == "internal":
                # Internal endpoints - require internal token
                await self._verify_internal_access(request)
            elif endpoint_type == "protected":
                # Protected endpoints - require user authentication
                await self._verify_user_access(request)
            elif endpoint_type == "high_risk":
                # High-risk endpoints - require authentication + additional checks
                await self._verify_high_risk_access(request)
            else:
                # Unknown endpoints - apply fallback protection
                await self._apply_fallback_protection(request, path, method)

        except HTTPException as e:
            if self.audit_mode:
                logger.warning(
                    f"RBAC violation (audit mode): {method} {path} - {e.detail}",
                    extra={
                        "security_event": "rbac_violation",
                        "method": method,
                        "path": path,
                        "status_code": e.status_code,
                        "detail": e.detail,
                        "audit_mode": True,
                    },
                )
                # In audit mode, log but don't block
            else:
                # In enforcement mode, block the request
                logger.error(
                    f"RBAC violation (blocked): {method} {path} - {e.detail}",
                    extra={
                        "security_event": "rbac_violation_blocked",
                        "method": method,
                        "path": path,
                        "status_code": e.status_code,
                        "detail": e.detail,
                    },
                )
                raise

        # Process request
        response = await call_next(request)

        # Log completion
        duration = time.time() - start_time
        logger.info(
            f"Request completed: {method} {path} - {response.status_code} ({duration:.3f}s)",
            extra={
                "security_event": "request_completed",
                "method": method,
                "path": path,
                "status_code": response.status_code,
                "duration": duration,
                "endpoint_type": endpoint_type,
            },
        )

        return response

    def _classify_endpoint(self, path: str, method: str) -> str:
        """
        Classify endpoint based on path and method

        Args:
            path: Request path
            method: HTTP method

        Returns:
            str: Endpoint classification
        """
        # Check public endpoints
        if path in self.PUBLIC_ENDPOINTS:
            return "public"

        for pattern in self.compiled_public_patterns:
            if pattern.match(path):
                return "public"

        # Check internal endpoints
        if path in self.INTERNAL_ENDPOINTS:
            return "internal"

        for pattern in self.compiled_internal_patterns:
            if pattern.match(path):
                return "internal"

        # Check high-risk endpoints
        if path in self.HIGH_RISK_ENDPOINTS:
            return "high_risk"

        for pattern in self.compiled_risk_patterns:
            if pattern.match(path):
                return "high_risk"

        # Check if it's an API endpoint
        if path.startswith("/api/"):
            return "protected"

        # Default classification
        return "unknown"

    def _log_request(self, request: Request, endpoint_type: str):
        """
        Log request for security audit

        Args:
            request: FastAPI request
            endpoint_type: Classified endpoint type
        """
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("User-Agent", "unknown")

        logger.info(
            f"Security audit: {request.method} {request.url.path}",
            extra={
                "security_event": "request_audit",
                "method": request.method,
                "path": request.url.path,
                "endpoint_type": endpoint_type,
                "client_ip": client_ip,
                "user_agent": user_agent,
                "query_params": dict(request.query_params),
            },
        )

    async def _verify_internal_access(self, request: Request):
        """
        Verify internal token for internal endpoints

        Args:
            request: FastAPI request

        Raises:
            HTTPException: If internal token is invalid
        """
        # Get internal token from header
        internal_token = request.headers.get("X-Internal-Token")

        if not internal_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Internal token required for this endpoint"
            )

        if not verify_internal_token(internal_token):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid internal token")

    async def _verify_user_access(self, request: Request):
        """
        Verify user authentication for protected endpoints

        Args:
            request: FastAPI request

        Raises:
            HTTPException: If authentication fails
        """
        if not self.enforce_auth:
            return  # Skip in development mode

        # Get authorization header
        authorization = request.headers.get("Authorization")

        if not authorization:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization header required",
                headers={"WWW-Authenticate": "Bearer"},
            )

        scheme, token = get_authorization_scheme_param(authorization)

        if scheme.lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Bearer token required",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token required",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Verify token (simplified - in real implementation, get DB session)
        # This is a basic check - detailed RBAC is handled by endpoint dependencies
        db = next(get_db())
        try:
            if token.startswith("lf_"):
                user = get_current_user_from_api_key(token, db)
            else:
                user = get_current_user_from_token(token, db)

            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        finally:
            db.close()

    async def _verify_high_risk_access(self, request: Request):
        """
        Verify enhanced security for high-risk endpoints

        Args:
            request: FastAPI request

        Raises:
            HTTPException: If security requirements not met
        """
        # First verify basic user access
        await self._verify_user_access(request)

        # Additional high-risk checks
        client_ip = request.client.host if request.client else "unknown"

        # Log high-risk access attempt
        logger.warning(
            f"High-risk endpoint access: {request.method} {request.url.path}",
            extra={
                "security_event": "high_risk_access",
                "method": request.method,
                "path": request.url.path,
                "client_ip": client_ip,
                "headers": dict(request.headers),
            },
        )

        # Additional checks could include:
        # - Rate limiting
        # - IP allowlisting
        # - Multi-factor authentication
        # - Session validation

    async def _apply_fallback_protection(self, request: Request, path: str, method: str):
        """
        Apply fallback protection for unknown endpoints

        Args:
            request: FastAPI request
            path: Request path
            method: HTTP method

        Raises:
            HTTPException: If fallback protection fails
        """
        logger.warning(
            f"Unknown endpoint detected: {method} {path}",
            extra={
                "security_event": "unknown_endpoint",
                "method": method,
                "path": path,
                "requires_classification": True,
            },
        )

        # For unknown endpoints, require authentication by default
        if self.enforce_auth and method in ["POST", "PUT", "PATCH", "DELETE"]:
            await self._verify_user_access(request)
        elif self.enforce_auth and path.startswith("/api/"):
            # All API endpoints require authentication
            await self._verify_user_access(request)
