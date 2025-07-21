"""
Audit logging middleware for all mutations (P0-026)

Automatically logs all POST/PUT/DELETE operations
"""

import json
import time
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from api.governance import create_audit_log
from core.logging import get_logger
from database.session import SessionLocal

logger = get_logger("audit_middleware", domain="governance")


class AuditLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to automatically audit all mutations"""

    MUTATION_METHODS = ["POST", "PUT", "PATCH", "DELETE"]
    EXCLUDED_PATHS = [
        "/health",
        "/metrics",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/api/governance/audit",  # Don't audit audit queries
    ]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and create audit log for mutations"""
        # Skip non-mutation methods
        if request.method not in self.MUTATION_METHODS:
            return await call_next(request)

        # Skip excluded paths
        path = str(request.url.path)
        if any(path.startswith(excluded) for excluded in self.EXCLUDED_PATHS):
            return await call_next(request)

        # Track timing
        start_time = time.time()

        # Capture request body
        request_body = None
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                body_bytes = await request.body()
                if body_bytes:
                    request_body = json.loads(body_bytes)

                # Reset body for downstream processing
                async def receive():
                    return {"type": "http.request", "body": body_bytes}

                request._receive = receive
            except Exception as e:
                logger.warning(f"Failed to capture request body: {e}")

        # Process request
        response = await call_next(request)

        # Only audit successful mutations (2xx status codes)
        if 200 <= response.status_code < 300:
            # Get current user from request state (set by auth middleware)
            user = getattr(request.state, "user", None)

            if user:
                # Create database session for audit logging
                db = SessionLocal()
                try:
                    # Extract object info from path
                    object_type, object_id = self._extract_object_info(path)

                    # Create audit log asynchronously
                    await create_audit_log(
                        db=db,
                        request=request,
                        response=response,
                        user=user,
                        start_time=start_time,
                        request_body=request_body,
                        response_body=None,  # Response body capture would be complex
                        object_type=object_type,
                        object_id=object_id,
                    )
                except Exception as e:
                    logger.error(f"Failed to create audit log: {e}")
                finally:
                    db.close()

        return response

    def _extract_object_info(self, path: str) -> tuple[str, str | None]:
        """Extract object type and ID from API path"""
        parts = path.strip("/").split("/")

        # Common patterns:
        # /api/v1/targeting/leads/{id} -> (Lead, id)
        # /api/scoring-playground/weights/import -> (Weight, None)
        # /api/governance/users/{id}/role -> (User, id)

        object_type = "Unknown"
        object_id = None

        # Try to extract meaningful object type
        if "leads" in path:
            object_type = "Lead"
        elif "users" in path:
            object_type = "User"
        elif "reports" in path:
            object_type = "Report"
        elif "templates" in path:
            object_type = "Template"
        elif "weights" in path:
            object_type = "Weight"
        elif "batch" in path:
            object_type = "BatchRun"

        # Try to extract ID (usually a UUID or number after the resource name)
        for i, part in enumerate(parts):
            if part in ["leads", "users", "reports", "templates", "batches"]:
                if i + 1 < len(parts) and parts[i + 1] not in ["import", "export", "query"]:
                    object_id = parts[i + 1]
                    break

        return object_type, object_id
