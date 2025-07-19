"""
Test suite for batch_runner API endpoints
Focus on achieving ≥80% total coverage for P0-022
"""
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError

from batch_runner.api import (
    batch_runner_health_check,
    cancel_batch,
    get_batch_analytics,
    get_batch_status,
    get_user_context,
    list_batches,
    preview_batch_cost,
    start_batch_processing_endpoint,
)
from batch_runner.models import BatchReport, BatchStatus
from batch_runner.schemas import BatchFilterSchema, CreateBatchSchema, PaginationSchema, StartBatchSchema


class TestBatchRunnerAPI:
    """Test suite for batch runner API endpoints"""

    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock()

    @pytest.fixture
    def mock_user_context(self):
        """Mock user context"""
        return {"user_id": "test-user-123", "organization_id": "test-org-456"}

    @pytest.fixture
    def sample_create_request(self):
        """Sample batch creation request"""
        return CreateBatchSchema(
            lead_ids=["lead1", "lead2", "lead3"],
            template_version="v1.2",
            name="Test Batch",
            description="Test batch for coverage",
        )

    @pytest.fixture
    def sample_start_request(self):
        """Sample batch start request"""
        return StartBatchSchema(
            lead_ids=["lead1", "lead2", "lead3"],
            name="Test Start Batch",
            description="Test batch start",
            template_version="v1.2",
            estimated_cost_usd=25.50,
            cost_approved=True,
            max_concurrent=5,
            retry_failed=True,
            retry_count=3,
            created_by="test-user",
        )

    def test_get_user_context(self):
        """Test user context extraction"""
        # Mock request with headers
        mock_request = Mock()
        mock_request.headers = {"X-User-ID": "user123", "User-Agent": "test-agent"}
        mock_request.client.host = "127.0.0.1"

        result = get_user_context(mock_request)

        assert result["user_id"] == "user123"
        assert result["user_agent"] == "test-agent"
        assert result["user_ip"] == "127.0.0.1"

    def test_get_user_context_missing_headers(self):
        """Test user context with missing headers"""
        mock_request = Mock()
        mock_request.headers = {}
        mock_request.client = None

        result = get_user_context(mock_request)

        assert result["user_id"] is None
        assert result["user_agent"] is None
        assert result["user_ip"] is None

    async def test_batch_health_check_success(self, mock_db):
        """Test health check endpoint"""
        mock_db.execute.return_value = Mock()
        mock_db.query.return_value.count.return_value = 5
        mock_db.query.return_value.filter_by.return_value.count.return_value = 2

        with patch("batch_runner.api.get_connection_manager") as mock_get_manager:
            mock_manager = Mock()
            mock_manager.get_stats.return_value = {"active_connections": 3}
            mock_get_manager.return_value = mock_manager

            result = await batch_runner_health_check(mock_db)

            assert result.status == "ok"
            assert result.timestamp is not None

    async def test_batch_health_check_database_error(self, mock_db):
        """Test health check with database error"""
        mock_db.execute.side_effect = SQLAlchemyError("Database error")

        with pytest.raises(HTTPException) as exc_info:
            await batch_runner_health_check(mock_db)

        assert exc_info.value.status_code == 503

    @patch("batch_runner.api.get_cost_calculator")
    @patch("lead_explorer.repository.LeadRepository")
    async def test_preview_batch_cost_success(
        self, mock_repo_class, mock_get_calculator, sample_create_request, mock_db
    ):
        """Test successful cost preview"""
        # Setup mocks
        mock_repo = Mock()
        mock_repo.get_leads_by_ids.return_value = [Mock(id="lead1"), Mock(id="lead2")]
        mock_repo_class.return_value = mock_repo

        mock_calculator = Mock()
        mock_calculator.calculate_batch_preview.return_value = {
            "cost_breakdown": {"total_cost": 15.50},
            "provider_breakdown": {},
            "estimated_duration_minutes": 20,
            "cost_per_lead": 5.17,
            "accuracy_note": "Within ±5%",
        }
        mock_calculator.validate_budget.return_value = {"is_within_budget": True, "warning_message": None}
        mock_get_calculator.return_value = mock_calculator

        result = await preview_batch_cost(sample_create_request, mock_db)

        assert result.lead_count == 2
        assert result.estimated_cost_usd == 15.50
        assert result.is_within_budget is True

    @patch("batch_runner.api.get_cost_calculator")
    @patch("lead_explorer.repository.LeadRepository")
    async def test_preview_batch_cost_no_valid_leads(
        self, mock_repo_class, mock_get_calculator, sample_create_request, mock_db
    ):
        """Test cost preview with no valid leads"""
        mock_repo = Mock()
        mock_repo.get_leads_by_ids.return_value = []
        mock_repo_class.return_value = mock_repo

        with pytest.raises(HTTPException) as exc_info:
            await preview_batch_cost(sample_create_request, mock_db)

        assert exc_info.value.status_code == 422
        assert "No valid leads found" in str(exc_info.value.detail)

    async def test_get_batch_status_success(self, mock_db):
        """Test successful batch status retrieval"""
        batch_id = "test-batch-123"
        mock_batch = Mock()
        mock_batch.id = batch_id
        mock_batch.status = BatchStatus.RUNNING
        mock_batch.progress_percentage = 50.0
        mock_batch.total_leads = 10
        mock_batch.processed_leads = 5
        mock_batch.successful_leads = 4
        mock_batch.failed_leads = 1
        mock_batch.current_lead_id = "lead-5"
        mock_batch.estimated_cost_usd = 25.50
        mock_batch.actual_cost_usd = 12.75
        mock_batch.started_at = datetime.now()
        mock_batch.websocket_url = f"/api/v1/batch/{batch_id}/progress"

        mock_db.query.return_value.filter_by.return_value.first.return_value = mock_batch
        mock_db.query.return_value.filter_by.return_value.order_by.return_value.limit.return_value.all.return_value = []
        mock_db.query.return_value.filter_by.return_value.group_by.return_value.all.return_value = []

        result = await get_batch_status(batch_id, mock_db)

        assert result.batch_id == batch_id
        assert result.status == "running"
        assert result.progress_percentage == 50.0

    async def test_get_batch_status_not_found(self, mock_db):
        """Test batch status with non-existent ID"""
        batch_id = "nonexistent-batch"
        mock_db.query.return_value.filter_by.return_value.first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await get_batch_status(batch_id, mock_db)

        assert exc_info.value.status_code == 404

    async def test_list_batches_success(self, mock_db):
        """Test successful batch list retrieval"""
        # Mock query setup
        mock_batches = []
        for i in range(3):
            batch = Mock()
            batch.id = f"batch-{i}"
            batch.name = f"Batch {i}"
            batch.description = f"Description {i}"
            batch.status = BatchStatus.PENDING
            batch.total_leads = 10
            batch.processed_leads = 0
            batch.successful_leads = 0
            batch.failed_leads = 0
            batch.progress_percentage = 0.0
            batch.estimated_cost_usd = 25.50
            batch.actual_cost_usd = None
            batch.template_version = "v1.2"
            batch.websocket_url = f"/api/v1/batch/{batch.id}/progress"
            batch.created_at = datetime.now()
            batch.started_at = None
            batch.completed_at = None
            batch.created_by = "test-user"
            batch.error_message = None
            mock_batches.append(batch)

        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_batches
        mock_query.count.return_value = 3

        mock_db.query.return_value = mock_query

        # Create filter and pagination objects
        filters = BatchFilterSchema()
        pagination = PaginationSchema(skip=0, limit=10)

        result = await list_batches(filters, pagination, mock_db)

        assert result.total_count == 3
        assert len(result.batches) == 3
        assert result.batches[0].id == "batch-0"

    @patch("batch_runner.api.start_batch_processing")
    @patch("lead_explorer.repository.LeadRepository")
    async def test_start_batch_processing_endpoint_success(
        self, mock_repo_class, mock_start_processing, sample_start_request, mock_db
    ):
        """Test successful batch processing start"""
        # Setup lead repository mock
        mock_repo = Mock()
        mock_repo.get_leads_by_ids.return_value = [Mock(id="lead1"), Mock(id="lead2"), Mock(id="lead3")]
        mock_repo_class.return_value = mock_repo

        # Mock BatchReport creation and BatchReportLead creation
        with patch("batch_runner.api.BatchReport") as mock_batch_class, patch(
            "batch_runner.api.BatchReportLead"
        ) as mock_batch_lead_class:
            mock_batch = Mock()
            mock_batch.id = "new-batch-123"
            mock_batch.name = sample_start_request.name
            mock_batch.description = sample_start_request.description
            mock_batch.status = BatchStatus.PENDING
            mock_batch.total_leads = 3
            mock_batch.processed_leads = 0
            mock_batch.successful_leads = 0
            mock_batch.failed_leads = 0
            mock_batch.progress_percentage = 0.0
            mock_batch.estimated_cost_usd = sample_start_request.estimated_cost_usd
            mock_batch.actual_cost_usd = None
            mock_batch.template_version = sample_start_request.template_version
            mock_batch.websocket_url = f"/api/v1/batch/{mock_batch.id}/progress"
            mock_batch.created_at = datetime.now()
            mock_batch.started_at = None
            mock_batch.completed_at = None
            mock_batch.created_by = sample_start_request.created_by
            mock_batch.error_message = None

            mock_batch_class.return_value = mock_batch
            mock_batch_lead_class.return_value = Mock()

            mock_db.add.return_value = None
            mock_db.commit.return_value = None
            mock_db.refresh.return_value = None

            # Mock background task
            mock_background_tasks = Mock()

            result = await start_batch_processing_endpoint(sample_start_request, mock_background_tasks, mock_db)

            assert result.id == mock_batch.id
            assert result.name == sample_start_request.name
            assert result.total_leads == 3

    @patch("lead_explorer.repository.LeadRepository")
    async def test_start_batch_processing_endpoint_no_valid_leads(self, mock_repo_class, sample_start_request, mock_db):
        """Test batch processing start with no valid leads"""
        mock_repo = Mock()
        mock_repo.get_leads_by_ids.return_value = []
        mock_repo_class.return_value = mock_repo

        mock_background_tasks = Mock()

        with pytest.raises(HTTPException) as exc_info:
            await start_batch_processing_endpoint(sample_start_request, mock_background_tasks, mock_db)

        assert exc_info.value.status_code == 422
        assert "No valid leads found" in str(exc_info.value.detail)

    @patch("batch_runner.api.get_connection_manager")
    async def test_cancel_batch_success(self, mock_get_manager, mock_db):
        """Test successful batch cancellation"""
        batch_id = "test-batch-123"
        mock_batch = Mock()
        mock_batch.status = BatchStatus.RUNNING
        mock_batch.id = batch_id
        mock_db.query.return_value.filter_by.return_value.first.return_value = mock_batch
        mock_db.query.return_value.filter_by.return_value.all.return_value = []

        mock_manager = Mock()
        mock_manager.broadcast_error = AsyncMock()
        mock_get_manager.return_value = mock_manager

        result = await cancel_batch(batch_id, mock_db)

        assert result["message"] == "Batch cancelled successfully"
        assert mock_batch.status == BatchStatus.CANCELLED

    async def test_cancel_batch_not_found(self, mock_db):
        """Test cancelling non-existent batch"""
        batch_id = "nonexistent-batch"
        mock_db.query.return_value.filter_by.return_value.first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await cancel_batch(batch_id, mock_db)

        assert exc_info.value.status_code == 404

    async def test_get_batch_analytics_success(self, mock_db):
        """Test batch analytics retrieval"""
        # Mock statistics query
        stats_result = Mock()
        stats_result.total_batches = 10
        stats_result.avg_successful = 8.5
        stats_result.avg_progress = 85.0
        stats_result.total_cost = 250.75
        stats_result.avg_duration_seconds = 300.0

        mock_db.query.return_value.filter.return_value.first.return_value = stats_result
        mock_db.query.return_value.filter.return_value.group_by.return_value.all.return_value = [
            (BatchStatus.COMPLETED, 8),
            (BatchStatus.FAILED, 2),
        ]

        result = await get_batch_analytics(days=7, db=mock_db)

        assert result["period_days"] == 7
        assert result["statistics"]["total_batches"] == 10
        assert result["statistics"]["average_successful_leads"] == 8.5
        assert result["status_breakdown"]["completed"] == 8
        assert result["status_breakdown"]["failed"] == 2


class TestErrorHandling:
    """Test error handling scenarios"""

    async def test_validation_error_handling(self):
        """Test pydantic validation error handling"""
        with pytest.raises(Exception):
            CreateBatchSchema(lead_ids=[], template_version="v1.2", name="Test")  # Empty list should fail validation

    async def test_sqlalchemy_error_handling(self, mock_db):
        """Test SQLAlchemy error handling in endpoints"""
        mock_db.execute.side_effect = SQLAlchemyError("Database connection failed")

        with pytest.raises(HTTPException):
            await batch_runner_health_check(mock_db)
