"""
Comprehensive tests for audit logging middleware.

Tests critical audit infrastructure including:
- Automatic mutation logging for POST/PUT/PATCH/DELETE operations
- Request body capture and processing
- User context extraction and authentication
- Path filtering and exclusion rules
- Object type and ID extraction from API paths
- Error handling and failure scenarios
- Performance timing and logging integration
"""

import json
import time
from unittest.mock import AsyncMock, Mock, patch

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.testclient import TestClient

from api.audit_middleware import AuditLoggingMiddleware


class TestAuditLoggingMiddleware:
    """Test AuditLoggingMiddleware class."""

    def test_middleware_initialization(self):
        """Test middleware initialization."""
        middleware = AuditLoggingMiddleware(Mock())

        assert middleware.MUTATION_METHODS == ["POST", "PUT", "PATCH", "DELETE"]
        assert "/health" in middleware.EXCLUDED_PATHS
        assert "/metrics" in middleware.EXCLUDED_PATHS
        assert "/api/governance/audit" in middleware.EXCLUDED_PATHS

    @pytest.mark.asyncio
    async def test_dispatch_get_request_skipped(self):
        """Test that GET requests are skipped."""
        middleware = AuditLoggingMiddleware(Mock())

        # Mock request
        request = Mock(spec=Request)
        request.method = "GET"
        request.url.path = "/api/v1/leads"

        # Mock call_next
        expected_response = JSONResponse({"data": "test"})
        call_next = AsyncMock(return_value=expected_response)

        result = await middleware.dispatch(request, call_next)

        assert result == expected_response
        call_next.assert_called_once_with(request)

    @pytest.mark.asyncio
    async def test_dispatch_excluded_path_skipped(self):
        """Test that excluded paths are skipped."""
        middleware = AuditLoggingMiddleware(Mock())

        # Mock request
        request = Mock(spec=Request)
        request.method = "POST"
        request.url.path = "/health"

        # Mock call_next
        expected_response = JSONResponse({"status": "ok"})
        call_next = AsyncMock(return_value=expected_response)

        result = await middleware.dispatch(request, call_next)

        assert result == expected_response
        call_next.assert_called_once_with(request)

    @pytest.mark.asyncio
    async def test_dispatch_metrics_excluded(self):
        """Test that metrics endpoint is excluded."""
        middleware = AuditLoggingMiddleware(Mock())

        request = Mock(spec=Request)
        request.method = "GET"
        request.url.path = "/metrics"

        expected_response = Response("metrics data")
        call_next = AsyncMock(return_value=expected_response)

        result = await middleware.dispatch(request, call_next)

        assert result == expected_response
        call_next.assert_called_once_with(request)

    @pytest.mark.asyncio
    async def test_dispatch_post_request_with_body(self):
        """Test POST request with body capture."""
        middleware = AuditLoggingMiddleware(Mock())

        # Mock request
        request = Mock(spec=Request)
        request.method = "POST"
        request.url.path = "/api/v1/leads"
        request.state = Mock()
        request.state.user = Mock()
        request.state.user.id = "user123"

        # Mock request body
        test_body = {"name": "Test Lead", "email": "test@example.com"}
        body_bytes = json.dumps(test_body).encode()
        request.body = AsyncMock(return_value=body_bytes)

        # Mock successful response
        response = Mock(spec=Response)
        response.status_code = 201
        call_next = AsyncMock(return_value=response)

        with (
            patch("api.audit_middleware.SessionLocal") as mock_session_local,
            patch("api.audit_middleware.create_audit_log") as mock_create_audit,
            patch("time.time", side_effect=[1000.0, 1000.5]),
        ):
            mock_db = Mock()
            mock_session_local.return_value = mock_db
            mock_create_audit.return_value = None

            result = await middleware.dispatch(request, call_next)

            assert result == response
            call_next.assert_called_once_with(request)
            mock_create_audit.assert_called_once()

            # Check audit log call arguments
            call_args = mock_create_audit.call_args
            assert call_args[1]["db"] == mock_db
            assert call_args[1]["request"] == request
            assert call_args[1]["response"] == response
            assert call_args[1]["user"] == request.state.user
            assert call_args[1]["start_time"] == 1000.0
            assert call_args[1]["request_body"] == test_body
            assert call_args[1]["object_type"] == "Lead"

    @pytest.mark.asyncio
    async def test_dispatch_put_request_with_body(self):
        """Test PUT request with body capture."""
        middleware = AuditLoggingMiddleware(Mock())

        request = Mock(spec=Request)
        request.method = "PUT"
        request.url.path = "/api/v1/users/123"
        request.state = Mock()
        request.state.user = Mock()
        request.state.user.id = "admin456"

        # Mock request body
        test_body = {"role": "admin", "permissions": ["read", "write"]}
        body_bytes = json.dumps(test_body).encode()
        request.body = AsyncMock(return_value=body_bytes)

        response = Mock(spec=Response)
        response.status_code = 200
        call_next = AsyncMock(return_value=response)

        with (
            patch("api.audit_middleware.SessionLocal") as mock_session_local,
            patch("api.audit_middleware.create_audit_log") as mock_create_audit,
            patch("time.time", side_effect=[1000.0, 1000.25]),
        ):
            mock_db = Mock()
            mock_session_local.return_value = mock_db

            result = await middleware.dispatch(request, call_next)

            assert result == response
            mock_create_audit.assert_called_once()

            call_args = mock_create_audit.call_args
            assert call_args[1]["object_type"] == "User"
            assert call_args[1]["object_id"] == "123"
            assert call_args[1]["request_body"] == test_body

    @pytest.mark.asyncio
    async def test_dispatch_delete_request_no_body(self):
        """Test DELETE request without body."""
        middleware = AuditLoggingMiddleware(Mock())

        request = Mock(spec=Request)
        request.method = "DELETE"
        request.url.path = "/api/v1/reports/abc-123"
        request.state = Mock()
        request.state.user = Mock()
        request.state.user.id = "user789"

        response = Mock(spec=Response)
        response.status_code = 204
        call_next = AsyncMock(return_value=response)

        with (
            patch("api.audit_middleware.SessionLocal") as mock_session_local,
            patch("api.audit_middleware.create_audit_log") as mock_create_audit,
        ):
            mock_db = Mock()
            mock_session_local.return_value = mock_db

            result = await middleware.dispatch(request, call_next)

            assert result == response
            mock_create_audit.assert_called_once()

            call_args = mock_create_audit.call_args
            assert call_args[1]["object_type"] == "Report"
            assert call_args[1]["object_id"] == "abc-123"
            assert call_args[1]["request_body"] is None

    @pytest.mark.asyncio
    async def test_dispatch_no_user_context(self):
        """Test request without user context (no audit log created)."""
        middleware = AuditLoggingMiddleware(Mock())

        request = Mock(spec=Request)
        request.method = "POST"
        request.url.path = "/api/v1/leads"
        request.state = Mock()
        request.state.user = None  # No user context

        body_bytes = json.dumps({"name": "Test"}).encode()
        request.body = AsyncMock(return_value=body_bytes)

        response = Mock(spec=Response)
        response.status_code = 201
        call_next = AsyncMock(return_value=response)

        with patch("api.audit_middleware.create_audit_log") as mock_create_audit:
            result = await middleware.dispatch(request, call_next)

            assert result == response
            mock_create_audit.assert_not_called()

    @pytest.mark.asyncio
    async def test_dispatch_failed_response_no_audit(self):
        """Test that failed responses (non-2xx) don't create audit logs."""
        middleware = AuditLoggingMiddleware(Mock())

        request = Mock(spec=Request)
        request.method = "POST"
        request.url.path = "/api/v1/leads"
        request.state = Mock()
        request.state.user = Mock()
        request.state.user.id = "user123"

        body_bytes = json.dumps({"name": "Test"}).encode()
        request.body = AsyncMock(return_value=body_bytes)

        # Mock failed response
        response = Mock(spec=Response)
        response.status_code = 400  # Bad request
        call_next = AsyncMock(return_value=response)

        with patch("api.audit_middleware.create_audit_log") as mock_create_audit:
            result = await middleware.dispatch(request, call_next)

            assert result == response
            mock_create_audit.assert_not_called()

    @pytest.mark.asyncio
    async def test_dispatch_server_error_no_audit(self):
        """Test that server errors (5xx) don't create audit logs."""
        middleware = AuditLoggingMiddleware(Mock())

        request = Mock(spec=Request)
        request.method = "DELETE"
        request.url.path = "/api/v1/users/123"
        request.state = Mock()
        request.state.user = Mock()
        request.state.user.id = "admin456"

        response = Mock(spec=Response)
        response.status_code = 500  # Server error
        call_next = AsyncMock(return_value=response)

        with patch("api.audit_middleware.create_audit_log") as mock_create_audit:
            result = await middleware.dispatch(request, call_next)

            assert result == response
            mock_create_audit.assert_not_called()

    @pytest.mark.asyncio
    async def test_dispatch_body_capture_error(self):
        """Test error handling during request body capture."""
        middleware = AuditLoggingMiddleware(Mock())

        request = Mock(spec=Request)
        request.method = "POST"
        request.url.path = "/api/v1/leads"
        request.state = Mock()
        request.state.user = Mock()
        request.state.user.id = "user123"

        # Mock body() to raise exception
        request.body = AsyncMock(side_effect=Exception("Body read failed"))

        response = Mock(spec=Response)
        response.status_code = 201
        call_next = AsyncMock(return_value=response)

        with (
            patch("api.audit_middleware.SessionLocal") as mock_session_local,
            patch("api.audit_middleware.create_audit_log") as mock_create_audit,
            patch("api.audit_middleware.logger") as mock_logger,
        ):
            mock_db = Mock()
            mock_session_local.return_value = mock_db

            result = await middleware.dispatch(request, call_next)

            assert result == response
            mock_logger.warning.assert_called_once()
            mock_create_audit.assert_called_once()

            # Should still create audit log with None body
            call_args = mock_create_audit.call_args
            assert call_args[1]["request_body"] is None

    @pytest.mark.asyncio
    async def test_dispatch_invalid_json_body(self):
        """Test handling of invalid JSON in request body."""
        middleware = AuditLoggingMiddleware(Mock())

        request = Mock(spec=Request)
        request.method = "POST"
        request.url.path = "/api/v1/leads"
        request.state = Mock()
        request.state.user = Mock()
        request.state.user.id = "user123"

        # Mock invalid JSON body
        body_bytes = b"invalid json {"
        request.body = AsyncMock(return_value=body_bytes)

        response = Mock(spec=Response)
        response.status_code = 201
        call_next = AsyncMock(return_value=response)

        with (
            patch("api.audit_middleware.SessionLocal") as mock_session_local,
            patch("api.audit_middleware.create_audit_log") as mock_create_audit,
            patch("api.audit_middleware.logger") as mock_logger,
        ):
            mock_db = Mock()
            mock_session_local.return_value = mock_db

            result = await middleware.dispatch(request, call_next)

            assert result == response
            mock_logger.warning.assert_called_once()
            mock_create_audit.assert_called_once()

            # Should still create audit log with None body
            call_args = mock_create_audit.call_args
            assert call_args[1]["request_body"] is None

    @pytest.mark.asyncio
    async def test_dispatch_empty_body(self):
        """Test handling of empty request body."""
        middleware = AuditLoggingMiddleware(Mock())

        request = Mock(spec=Request)
        request.method = "POST"
        request.url.path = "/api/v1/leads"
        request.state = Mock()
        request.state.user = Mock()
        request.state.user.id = "user123"

        # Mock empty body
        request.body = AsyncMock(return_value=b"")

        response = Mock(spec=Response)
        response.status_code = 201
        call_next = AsyncMock(return_value=response)

        with (
            patch("api.audit_middleware.SessionLocal") as mock_session_local,
            patch("api.audit_middleware.create_audit_log") as mock_create_audit,
        ):
            mock_db = Mock()
            mock_session_local.return_value = mock_db

            result = await middleware.dispatch(request, call_next)

            assert result == response
            mock_create_audit.assert_called_once()

            # Should create audit log with None body for empty body
            call_args = mock_create_audit.call_args
            assert call_args[1]["request_body"] is None

    @pytest.mark.asyncio
    async def test_dispatch_audit_log_creation_error(self):
        """Test error handling during audit log creation."""
        middleware = AuditLoggingMiddleware(Mock())

        request = Mock(spec=Request)
        request.method = "POST"
        request.url.path = "/api/v1/leads"
        request.state = Mock()
        request.state.user = Mock()
        request.state.user.id = "user123"

        body_bytes = json.dumps({"name": "Test"}).encode()
        request.body = AsyncMock(return_value=body_bytes)

        response = Mock(spec=Response)
        response.status_code = 201
        call_next = AsyncMock(return_value=response)

        with (
            patch("api.audit_middleware.SessionLocal") as mock_session_local,
            patch("api.audit_middleware.create_audit_log") as mock_create_audit,
            patch("api.audit_middleware.logger") as mock_logger,
        ):
            mock_db = Mock()
            mock_session_local.return_value = mock_db
            mock_create_audit.side_effect = Exception("Audit log creation failed")

            result = await middleware.dispatch(request, call_next)

            assert result == response
            mock_logger.error.assert_called_once()
            mock_db.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_dispatch_database_session_cleanup(self):
        """Test that database session is properly cleaned up."""
        middleware = AuditLoggingMiddleware(Mock())

        request = Mock(spec=Request)
        request.method = "POST"
        request.url.path = "/api/v1/leads"
        request.state = Mock()
        request.state.user = Mock()
        request.state.user.id = "user123"

        body_bytes = json.dumps({"name": "Test"}).encode()
        request.body = AsyncMock(return_value=body_bytes)

        response = Mock(spec=Response)
        response.status_code = 201
        call_next = AsyncMock(return_value=response)

        with (
            patch("api.audit_middleware.SessionLocal") as mock_session_local,
            patch("api.audit_middleware.create_audit_log") as mock_create_audit,
        ):
            mock_db = Mock()
            mock_session_local.return_value = mock_db

            result = await middleware.dispatch(request, call_next)

            assert result == response
            mock_db.close.assert_called_once()

    def test_extract_object_info_leads(self):
        """Test object info extraction for leads."""
        middleware = AuditLoggingMiddleware(Mock())

        # Test leads with ID
        object_type, object_id = middleware._extract_object_info("/api/v1/leads/123")
        assert object_type == "Lead"
        assert object_id == "123"

        # Test leads without ID
        object_type, object_id = middleware._extract_object_info("/api/v1/leads")
        assert object_type == "Lead"
        assert object_id is None

    def test_extract_object_info_users(self):
        """Test object info extraction for users."""
        middleware = AuditLoggingMiddleware(Mock())

        # Test users with ID
        object_type, object_id = middleware._extract_object_info("/api/v1/users/abc-123")
        assert object_type == "User"
        assert object_id == "abc-123"

        # Test users with role modification
        object_type, object_id = middleware._extract_object_info("/api/governance/users/456/role")
        assert object_type == "User"
        assert object_id == "456"

    def test_extract_object_info_reports(self):
        """Test object info extraction for reports."""
        middleware = AuditLoggingMiddleware(Mock())

        object_type, object_id = middleware._extract_object_info("/api/v1/reports/report-789")
        assert object_type == "Report"
        assert object_id == "report-789"

    def test_extract_object_info_templates(self):
        """Test object info extraction for templates."""
        middleware = AuditLoggingMiddleware(Mock())

        object_type, object_id = middleware._extract_object_info("/api/template-studio/templates/template-456")
        assert object_type == "Template"
        assert object_id == "template-456"

    def test_extract_object_info_weights(self):
        """Test object info extraction for weights."""
        middleware = AuditLoggingMiddleware(Mock())

        # Test weights import (no ID)
        object_type, object_id = middleware._extract_object_info("/api/scoring-playground/weights/import")
        assert object_type == "Weight"
        assert object_id is None

    def test_extract_object_info_batch(self):
        """Test object info extraction for batch operations."""
        middleware = AuditLoggingMiddleware(Mock())

        object_type, object_id = middleware._extract_object_info("/api/v1/batch/batch-run-123")
        assert object_type == "BatchRun"
        assert object_id is None  # batch doesn't match "batches" pattern

    def test_extract_object_info_unknown(self):
        """Test object info extraction for unknown paths."""
        middleware = AuditLoggingMiddleware(Mock())

        object_type, object_id = middleware._extract_object_info("/api/v1/unknown/path")
        assert object_type == "Unknown"
        assert object_id is None

    def test_extract_object_info_complex_path(self):
        """Test object info extraction for complex paths."""
        middleware = AuditLoggingMiddleware(Mock())

        # Test nested resource path
        object_type, object_id = middleware._extract_object_info("/api/v1/leads/123/contacts/456")
        assert object_type == "Lead"
        assert object_id == "123"

    def test_extract_object_info_export_import_exclusion(self):
        """Test that export/import actions don't extract IDs."""
        middleware = AuditLoggingMiddleware(Mock())

        # Export should not extract ID
        object_type, object_id = middleware._extract_object_info("/api/v1/leads/export")
        assert object_type == "Lead"
        assert object_id is None

        # Import should not extract ID
        object_type, object_id = middleware._extract_object_info("/api/v1/templates/import")
        assert object_type == "Template"
        assert object_id is None

    def test_extract_object_info_query_exclusion(self):
        """Test that query actions don't extract IDs."""
        middleware = AuditLoggingMiddleware(Mock())

        object_type, object_id = middleware._extract_object_info("/api/v1/users/query")
        assert object_type == "User"
        assert object_id is None


class TestAuditMiddlewareIntegration:
    """Integration tests for audit middleware."""

    def test_middleware_with_starlette_app(self):
        """Test middleware integration with Starlette application."""
        app = Starlette()

        # Add middleware
        app.add_middleware(AuditLoggingMiddleware)

        # Add test route
        @app.route("/api/v1/test", methods=["POST"])
        async def test_endpoint(request):
            return JSONResponse({"result": "success"})

        client = TestClient(app)

        # Test that middleware is applied
        with patch("api.audit_middleware.create_audit_log") as mock_create_audit:
            response = client.post("/api/v1/test", json={"data": "test"})

            # Should not create audit log without user context
            assert response.status_code == 200
            mock_create_audit.assert_not_called()

    @pytest.mark.asyncio
    async def test_middleware_timing_accuracy(self):
        """Test that middleware accurately measures timing."""
        middleware = AuditLoggingMiddleware(Mock())

        request = Mock(spec=Request)
        request.method = "POST"
        request.url.path = "/api/v1/leads"
        request.state = Mock()
        request.state.user = Mock()
        request.state.user.id = "user123"

        body_bytes = json.dumps({"name": "Test"}).encode()
        request.body = AsyncMock(return_value=body_bytes)

        response = Mock(spec=Response)
        response.status_code = 201

        # Mock call_next to simulate processing time
        async def slow_call_next(req):
            await asyncio.sleep(0.1)  # Simulate 100ms processing
            return response

        with (
            patch("api.audit_middleware.SessionLocal") as mock_session_local,
            patch("api.audit_middleware.create_audit_log") as mock_create_audit,
            patch("time.time", side_effect=[1000.0, 1000.1]),
        ):
            mock_db = Mock()
            mock_session_local.return_value = mock_db

            result = await middleware.dispatch(request, slow_call_next)

            assert result == response
            mock_create_audit.assert_called_once()

            # Check that correct start time was recorded
            call_args = mock_create_audit.call_args
            assert call_args[1]["start_time"] == 1000.0

    @pytest.mark.asyncio
    async def test_middleware_with_different_methods(self):
        """Test middleware behavior with different HTTP methods."""
        middleware = AuditLoggingMiddleware(Mock())

        methods_to_test = [
            ("GET", False),  # Should not audit
            ("POST", True),  # Should audit
            ("PUT", True),  # Should audit
            ("PATCH", True),  # Should audit
            ("DELETE", True),  # Should audit
            ("HEAD", False),  # Should not audit
            ("OPTIONS", False),  # Should not audit
        ]

        for method, should_audit in methods_to_test:
            request = Mock(spec=Request)
            request.method = method
            request.url.path = "/api/v1/test"
            request.state = Mock()
            request.state.user = Mock()
            request.state.user.id = "user123"

            if method in ["POST", "PUT", "PATCH"]:
                body_bytes = json.dumps({"data": "test"}).encode()
                request.body = AsyncMock(return_value=body_bytes)

            response = Mock(spec=Response)
            response.status_code = 200
            call_next = AsyncMock(return_value=response)

            with (
                patch("api.audit_middleware.SessionLocal") as mock_session_local,
                patch("api.audit_middleware.create_audit_log") as mock_create_audit,
            ):
                mock_db = Mock()
                mock_session_local.return_value = mock_db

                result = await middleware.dispatch(request, call_next)

                assert result == response
                if should_audit:
                    mock_create_audit.assert_called_once()
                else:
                    mock_create_audit.assert_not_called()

    @pytest.mark.asyncio
    async def test_middleware_excluded_paths_comprehensive(self):
        """Test all excluded paths are properly handled."""
        middleware = AuditLoggingMiddleware(Mock())

        excluded_paths = [
            "/health",
            "/metrics",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/api/governance/audit",
        ]

        for path in excluded_paths:
            request = Mock(spec=Request)
            request.method = "POST"
            request.url.path = path

            response = Mock(spec=Response)
            response.status_code = 200
            call_next = AsyncMock(return_value=response)

            with patch("api.audit_middleware.create_audit_log") as mock_create_audit:
                result = await middleware.dispatch(request, call_next)

                assert result == response
                mock_create_audit.assert_not_called()

    @pytest.mark.asyncio
    async def test_middleware_body_reset_mechanism(self):
        """Test that request body is properly reset for downstream processing."""
        middleware = AuditLoggingMiddleware(Mock())

        request = Mock(spec=Request)
        request.method = "POST"
        request.url.path = "/api/v1/leads"
        request.state = Mock()
        request.state.user = Mock()
        request.state.user.id = "user123"

        # Mock request body
        test_body = {"name": "Test Lead"}
        body_bytes = json.dumps(test_body).encode()
        request.body = AsyncMock(return_value=body_bytes)

        response = Mock(spec=Response)
        response.status_code = 201

        # Mock call_next to verify body is available
        async def verify_body_call_next(req):
            # This simulates downstream middleware/handler accessing the body
            # The _receive function should provide the body
            receive_result = await req._receive()
            assert receive_result["type"] == "http.request"
            assert receive_result["body"] == body_bytes
            return response

        with (
            patch("api.audit_middleware.SessionLocal") as mock_session_local,
            patch("api.audit_middleware.create_audit_log") as mock_create_audit,
        ):
            mock_db = Mock()
            mock_session_local.return_value = mock_db

            result = await middleware.dispatch(request, verify_body_call_next)

            assert result == response
            mock_create_audit.assert_called_once()
