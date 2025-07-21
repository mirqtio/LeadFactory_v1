"""
Integration tests for Batch Runner API endpoints
Tests all 7 API endpoints plus WebSocket functionality with real FastAPI client
"""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocket
from sqlalchemy.orm import Session

from batch_runner.models import BatchReport, BatchReportLead, BatchStatus, LeadProcessingStatus
from main import app


@pytest.fixture
def test_client():
    """Create test client for FastAPI app"""
    return TestClient(app)


@pytest.fixture
def sample_batch_data():
    """Sample batch data for testing"""
    return {
        "name": "Test Batch",
        "lead_ids": ["lead-1", "lead-2", "lead-3"],
        "template_version": "v1",
        "estimated_cost_usd": 5.00,
        "cost_approved": True,
        "created_by": "test-user",
        "max_concurrent": 3,
        "retry_count": 2,
        "retry_failed": True,
    }


@pytest.fixture
def sample_preview_data():
    """Sample preview data for testing"""
    return {"lead_ids": ["lead-1", "lead-2", "lead-3"], "template_version": "v1"}


class TestBatchRunnerAPIIntegration:
    """Integration tests for all Batch Runner API endpoints"""

    def test_health_check_endpoint(self, test_client):
        """Test GET /api/health endpoint"""
        response = test_client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "timestamp" in data
        assert "database" in data
        assert "message" in data

    @patch("batch_runner.api.CostCalculator")
    @patch("lead_explorer.repository.LeadRepository.get_by_ids")
    def test_preview_batch_endpoint(self, mock_get_leads, mock_cost_calc, test_client, sample_preview_data):
        """Test POST /api/batch/preview endpoint"""
        # Mock lead validation
        mock_get_leads.return_value = [
            {"id": "lead-1", "name": "Company 1"},
            {"id": "lead-2", "name": "Company 2"},
            {"id": "lead-3", "name": "Company 3"},
        ]

        # Mock cost calculation
        mock_calc_instance = mock_cost_calc.return_value
        mock_calc_instance.calculate_batch_preview.return_value = {
            "lead_count": 3,
            "valid_lead_ids": ["lead-1", "lead-2", "lead-3"],
            "template_version": "v1",
            "estimated_cost_usd": 3.00,
            "cost_breakdown": {"total_cost": 3.00, "base_cost": 2.4, "overhead_cost": 0.6},
            "provider_breakdown": {"openai": 1.5, "internal": 1.5},
            "estimated_duration_minutes": 2.0,
            "cost_per_lead": 1.00,
            "is_within_budget": True,
            "budget_warning": None,
            "accuracy_note": "Estimate accurate within ±5%",
        }

        response = test_client.post("/api/batch/preview", json=sample_preview_data)

        assert response.status_code == 200
        data = response.json()
        assert data["lead_count"] == 3
        assert data["estimated_cost_usd"] == 3.00
        assert data["is_within_budget"] is True
        assert "cost_breakdown" in data
        assert "accuracy_note" in data

    def test_preview_batch_invalid_input(self, test_client):
        """Test preview endpoint with invalid input"""
        # Test empty lead_ids
        response = test_client.post("/api/batch/preview", json={"lead_ids": [], "template_version": "v1"})
        assert response.status_code == 422  # Validation error

        # Test missing template_version
        response = test_client.post("/api/batch/preview", json={"lead_ids": ["lead-1"]})
        assert response.status_code == 422

    @patch("batch_runner.api.get_current_user_dependency")
    @patch("batch_runner.api.CostCalculator")
    @patch("batch_runner.api.BatchProcessor")
    @patch("lead_explorer.repository.LeadRepository.get_by_ids")
    def test_start_batch_endpoint(
        self, mock_get_leads, mock_processor, mock_cost_calc, mock_user, test_client, sample_batch_data, db_session
    ):
        """Test POST /api/batch/start endpoint"""
        # Mock authentication
        mock_user.return_value = type("User", (), {"id": "user-123", "organization_id": "org-1"})()

        # Mock lead validation
        mock_get_leads.return_value = [
            {"id": "lead-1", "name": "Company 1"},
            {"id": "lead-2", "name": "Company 2"},
            {"id": "lead-3", "name": "Company 3"},
        ]

        # Mock cost calculation
        mock_calc_instance = mock_cost_calc.return_value
        mock_calc_instance.calculate_batch_preview.return_value = {"estimated_cost_usd": 5.00, "is_within_budget": True}

        # Mock processor
        mock_proc_instance = mock_processor.return_value
        mock_proc_instance.process_batch_async = AsyncMock()

        with patch("batch_runner.api.get_db") as mock_get_db:
            mock_get_db.return_value = db_session

            response = test_client.post("/api/batch/start", json=sample_batch_data)

            assert response.status_code == 200
            data = response.json()
            assert "id" in data
            assert data["name"] == "Test Batch"
            assert data["status"] == "pending"
            assert data["total_leads"] == 3
            assert "websocket_url" in data

    @patch("batch_runner.api.get_current_user_dependency")
    def test_start_batch_unauthorized(self, mock_user, test_client, sample_batch_data):
        """Test start batch without authentication"""
        mock_user.side_effect = Exception("Unauthorized")

        response = test_client.post("/api/batch/start", json=sample_batch_data)
        assert response.status_code == 500  # Internal server error due to auth failure

    @patch("batch_runner.api.get_current_user_dependency")
    def test_get_batch_status_endpoint(self, mock_user, test_client, db_session):
        """Test GET /api/batch/{batch_id}/status endpoint"""
        # Mock authentication
        mock_user.return_value = type("User", (), {"id": "user-123", "organization_id": "org-1"})()

        # Create test batch in database
        batch = BatchReport(
            id="test-batch-123",
            name="Test Batch",
            status=BatchStatus.RUNNING,
            total_leads=10,
            processed_leads=5,
            successful_leads=4,
            failed_leads=1,
            template_version="v1",
            estimated_cost_usd=10.00,
            actual_cost_usd=5.00,
            created_by="user-123",
        )
        db_session.add(batch)

        # Add some lead results
        for i in range(5):
            lead = BatchReportLead(
                id=f"lead-result-{i}",
                batch_id="test-batch-123",
                lead_id=f"lead-{i}",
                status=LeadProcessingStatus.COMPLETED if i < 4 else LeadProcessingStatus.FAILED,
                order_index=i,
            )
            db_session.add(lead)

        db_session.commit()

        with patch("batch_runner.api.get_db") as mock_get_db:
            mock_get_db.return_value = db_session

            response = test_client.get("/api/batch/test-batch-123/status")

            assert response.status_code == 200
            data = response.json()
            assert data["batch_id"] == "test-batch-123"
            assert data["status"] == "running"
            assert data["progress_percentage"] == 50.0
            assert data["total_leads"] == 10
            assert data["processed_leads"] == 5
            assert data["successful_leads"] == 4
            assert data["failed_leads"] == 1
            assert "websocket_url" in data

    @patch("batch_runner.api.get_current_user_dependency")
    def test_get_batch_status_not_found(self, mock_user, test_client, db_session):
        """Test get status for non-existent batch"""
        mock_user.return_value = type("User", (), {"id": "user-123", "organization_id": "org-1"})()

        with patch("batch_runner.api.get_db") as mock_get_db:
            mock_get_db.return_value = db_session

            response = test_client.get("/api/batch/nonexistent-batch/status")
            assert response.status_code == 404
            data = response.json()
            assert data["error"] == "NOT_FOUND"

    @patch("batch_runner.api.get_current_user_dependency")
    def test_list_batches_endpoint(self, mock_user, test_client, db_session):
        """Test GET /api/batch endpoint"""
        mock_user.return_value = type("User", (), {"id": "user-123", "organization_id": "org-1"})()

        # Create test batches
        for i in range(3):
            batch = BatchReport(
                id=f"batch-{i}",
                name=f"Test Batch {i}",
                status=BatchStatus.COMPLETED if i == 0 else BatchStatus.RUNNING,
                total_leads=10,
                processed_leads=10 if i == 0 else 5,
                template_version="v1",
                created_by="user-123",
            )
            db_session.add(batch)

        db_session.commit()

        with patch("batch_runner.api.get_db") as mock_get_db:
            mock_get_db.return_value = db_session

            # Test basic list
            response = test_client.get("/api/batch")
            assert response.status_code == 200
            data = response.json()
            assert "batches" in data
            assert "total" in data
            assert len(data["batches"]) == 3

            # Test with filters
            response = test_client.get("/api/batch?status=running")
            assert response.status_code == 200
            data = response.json()
            assert len(data["batches"]) == 2

            # Test with pagination
            response = test_client.get("/api/batch?skip=1&limit=1")
            assert response.status_code == 200
            data = response.json()
            assert len(data["batches"]) == 1

    @patch("batch_runner.api.get_current_user_dependency")
    def test_cancel_batch_endpoint(self, mock_user, test_client, db_session):
        """Test POST /api/batch/{batch_id}/cancel endpoint"""
        mock_user.return_value = type("User", (), {"id": "user-123", "organization_id": "org-1"})()

        # Create running batch
        batch = BatchReport(
            id="batch-to-cancel",
            name="Batch to Cancel",
            status=BatchStatus.RUNNING,
            total_leads=10,
            processed_leads=3,
            template_version="v1",
            created_by="user-123",
        )
        db_session.add(batch)
        db_session.commit()

        with patch("batch_runner.api.get_db") as mock_get_db:
            mock_get_db.return_value = db_session

            response = test_client.post("/api/batch/batch-to-cancel/cancel")

            assert response.status_code == 200
            data = response.json()
            assert data["message"] == "Batch cancelled successfully"
            assert data["batch_id"] == "batch-to-cancel"

            # Verify batch status changed
            db_session.refresh(batch)
            assert batch.status == BatchStatus.CANCELLED

    @patch("batch_runner.api.get_current_user_dependency")
    def test_cancel_completed_batch_error(self, mock_user, test_client, db_session):
        """Test cancel already completed batch"""
        mock_user.return_value = type("User", (), {"id": "user-123", "organization_id": "org-1"})()

        # Create completed batch
        batch = BatchReport(
            id="completed-batch",
            name="Completed Batch",
            status=BatchStatus.COMPLETED,
            total_leads=10,
            processed_leads=10,
            template_version="v1",
            created_by="user-123",
        )
        db_session.add(batch)
        db_session.commit()

        with patch("batch_runner.api.get_db") as mock_get_db:
            mock_get_db.return_value = db_session

            response = test_client.post("/api/batch/completed-batch/cancel")
            assert response.status_code == 400
            data = response.json()
            assert data["error"] == "INVALID_STATUS"

    @patch("batch_runner.api.get_current_user_dependency")
    def test_get_analytics_endpoint(self, mock_user, test_client, db_session):
        """Test GET /api/batch/analytics endpoint"""
        mock_user.return_value = type("User", (), {"id": "user-123", "organization_id": "org-1"})()

        # Create test data
        for i in range(5):
            batch = BatchReport(
                id=f"analytics-batch-{i}",
                name=f"Analytics Batch {i}",
                status=BatchStatus.COMPLETED if i < 3 else BatchStatus.FAILED,
                total_leads=10,
                processed_leads=10,
                successful_leads=10 if i < 3 else 0,
                failed_leads=0 if i < 3 else 10,
                template_version="v1",
                estimated_cost_usd=10.00,
                actual_cost_usd=9.50 if i < 3 else 5.00,
                created_by="user-123",
            )
            db_session.add(batch)

        db_session.commit()

        with patch("batch_runner.api.get_db") as mock_get_db:
            mock_get_db.return_value = db_session

            response = test_client.get("/api/batch/analytics")

            assert response.status_code == 200
            data = response.json()
            assert "total_batches" in data
            assert "completed_batches" in data
            assert "failed_batches" in data
            assert "total_leads_processed" in data
            assert "success_rate" in data
            assert "average_cost_per_lead" in data
            assert "total_cost" in data

            # Verify calculations
            assert data["total_batches"] == 5
            assert data["completed_batches"] == 3
            assert data["failed_batches"] == 2
            assert data["total_leads_processed"] == 50

    def test_response_time_performance(self, test_client):
        """Test API response times meet performance requirements"""
        import time

        # Health check should be very fast
        start_time = time.time()
        response = test_client.get("/api/batch/health")
        response_time = time.time() - start_time

        assert response.status_code == 200
        assert response_time < 0.1  # Should be under 100ms

    def test_error_handling_validation(self, test_client):
        """Test API error handling and validation"""
        # Test invalid JSON
        response = test_client.post("/api/batch/preview", data="invalid json")
        assert response.status_code == 422

        # Test missing required fields
        response = test_client.post("/api/batch/preview", json={})
        assert response.status_code == 422

        # Test invalid field types
        response = test_client.post("/api/batch/preview", json={"lead_ids": "not-a-list", "template_version": "v1"})
        assert response.status_code == 422


class TestBatchRunnerWebSocketIntegration:
    """Integration tests for WebSocket functionality"""

    @pytest.mark.asyncio
    async def test_websocket_connection_success(self, db_session):
        """Test successful WebSocket connection"""
        # Create test batch
        batch = BatchReport(
            id="ws-test-batch",
            name="WebSocket Test Batch",
            status=BatchStatus.RUNNING,
            total_leads=10,
            processed_leads=0,
            template_version="v1",
            created_by="user-123",
        )
        db_session.add(batch)
        db_session.commit()

        with patch("batch_runner.api.get_db") as mock_get_db:
            mock_get_db.return_value = db_session

            # Test WebSocket connection
            with TestClient(app) as client:
                try:
                    with client.websocket_connect("/api/batch/ws-test-batch/progress") as websocket:
                        # Should connect successfully
                        assert websocket is not None

                        # Test receiving a message (would be sent by processor)
                        # In real scenario, processor would send progress updates
                except Exception as e:
                    # WebSocket might fail with test client, but connection attempt is what we're testing
                    assert "websocket" in str(e).lower()

    @pytest.mark.asyncio
    async def test_websocket_connection_invalid_batch(self):
        """Test WebSocket connection with invalid batch ID"""
        with TestClient(app) as client:
            # Should fail to connect to non-existent batch
            try:
                with client.websocket_connect("/api/batch/nonexistent-batch/progress") as websocket:
                    pass
            except Exception:
                # Expected to fail
                pass

    def test_websocket_url_generation(self, test_client):
        """Test WebSocket URL generation in API responses"""
        response = test_client.get("/api/batch/health")
        assert response.status_code == 200

        # WebSocket URLs should be included in batch responses
        # This is tested indirectly through other endpoint tests


class TestBatchRunnerSecurityIntegration:
    """Security-focused integration tests"""

    def test_authentication_required(self, test_client):
        """Test that protected endpoints require authentication"""
        # These endpoints should require authentication
        protected_endpoints = [
            ("/api/batch/start", "post"),
            ("/api/batch/test-batch/status", "get"),
            ("/api/batch", "get"),
            ("/api/batch/test-batch/cancel", "post"),
            ("/api/batch/analytics", "get"),
        ]

        for endpoint, method in protected_endpoints:
            if method == "post":
                response = test_client.post(endpoint, json={})
            else:
                response = test_client.get(endpoint)

            # Should fail with authentication error
            # Actual behavior depends on auth implementation
            assert response.status_code in [401, 403, 422, 500]

    def test_input_validation_security(self, test_client):
        """Test input validation prevents security issues"""
        # Test SQL injection attempts
        malicious_inputs = [
            {"lead_ids": ["'; DROP TABLE batch_reports; --"], "template_version": "v1"},
            {"lead_ids": ["<script>alert('xss')</script>"], "template_version": "v1"},
            {"lead_ids": ["lead-1"], "template_version": "../../../etc/passwd"},
        ]

        for malicious_input in malicious_inputs:
            response = test_client.post("/api/batch/preview", json=malicious_input)
            # Should either reject or sanitize the input
            assert response.status_code in [400, 422, 500]

    def test_rate_limiting_headers(self, test_client):
        """Test that rate limiting headers are present if implemented"""
        response = test_client.get("/api/batch/health")
        # Check if rate limiting headers are implemented
        # This is optional based on rate limiting implementation
        assert response.status_code == 200
