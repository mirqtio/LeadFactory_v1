"""
Additional tests for batch processor to achieve ≥80% coverage
P0-022 requirement: comprehensive test coverage on all batch_runner modules
"""
import asyncio
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError

from batch_runner.models import BatchReport, BatchReportLead, BatchStatus, LeadProcessingStatus
from batch_runner.processor import BatchProcessingResult, BatchProcessor, LeadProcessingResult


class TestBatchProcessorCoverage:
    """Additional tests to achieve ≥80% coverage for BatchProcessor"""

    @pytest.fixture
    def mock_batch_processor(self):
        """Create a mock batch processor with all dependencies mocked"""
        with patch("batch_runner.processor.get_settings") as mock_settings, patch(
            "batch_runner.processor.get_connection_manager"
        ) as mock_conn, patch("batch_runner.processor.get_cost_calculator") as mock_cost, patch(
            "batch_runner.processor.ReportGenerator"
        ) as mock_report, patch(
            "batch_runner.processor.ThreadPoolExecutor"
        ) as mock_thread:
            # Setup mock settings
            mock_settings_obj = MagicMock()
            mock_settings_obj.BATCH_MAX_CONCURRENT_LEADS = 5
            mock_settings.return_value = mock_settings_obj

            # Setup other mocks
            mock_conn.return_value = MagicMock()
            mock_cost.return_value = MagicMock()
            mock_report.return_value = MagicMock()
            mock_thread.return_value = MagicMock()

            processor = BatchProcessor()

            # Store mocks for access in tests
            processor._mock_settings = mock_settings_obj
            processor._mock_conn = mock_conn.return_value
            processor._mock_cost = mock_cost.return_value
            processor._mock_report = mock_report.return_value
            processor._mock_thread = mock_thread.return_value

            return processor

    @patch("batch_runner.processor.SessionLocal")
    async def test_process_batch_not_found(self, mock_session, mock_batch_processor):
        """Test process_batch with non-existent batch"""
        # Setup mock database session
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db
        mock_db.query.return_value.filter_by.return_value.first.return_value = None

        batch_id = str(uuid.uuid4())

        # Test that ValueError is raised for non-existent batch
        with pytest.raises(ValueError, match=f"Batch {batch_id} not found"):
            await mock_batch_processor.process_batch(batch_id)

    @patch("batch_runner.processor.SessionLocal")
    async def test_process_batch_invalid_status(self, mock_session, mock_batch_processor):
        """Test process_batch with batch in wrong status"""
        # Setup mock database session
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db

        # Mock batch with wrong status
        mock_batch = MagicMock()
        mock_batch.status = BatchStatus.RUNNING  # Not PENDING
        mock_db.query.return_value.filter_by.return_value.first.return_value = mock_batch

        batch_id = str(uuid.uuid4())

        # Test that ValueError is raised for wrong status
        with pytest.raises(ValueError, match=f"Batch {batch_id} is not in pending status"):
            await mock_batch_processor.process_batch(batch_id)

    @patch("batch_runner.processor.SessionLocal")
    async def test_process_batch_database_error(self, mock_session, mock_batch_processor):
        """Test process_batch with database error"""
        # Setup mock database session to raise SQLAlchemyError
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db
        mock_db.query.side_effect = SQLAlchemyError("Database connection failed")

        batch_id = str(uuid.uuid4())

        # Test that SQLAlchemyError is properly handled
        with pytest.raises(SQLAlchemyError):
            await mock_batch_processor.process_batch(batch_id)

    @patch("batch_runner.processor.SessionLocal")
    async def test_process_batch_success_flow(self, mock_session, mock_batch_processor):
        """Test successful batch processing flow"""
        # Setup mock database session
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db

        # Mock batch and leads
        batch_id = str(uuid.uuid4())
        mock_batch = MagicMock()
        mock_batch.id = batch_id
        mock_batch.status = BatchStatus.PENDING
        mock_batch.total_leads = 2
        mock_batch.estimated_cost = Decimal("10.00")

        mock_leads = [
            MagicMock(id=str(uuid.uuid4()), lead_id=str(uuid.uuid4()), status=LeadProcessingStatus.PENDING),
            MagicMock(id=str(uuid.uuid4()), lead_id=str(uuid.uuid4()), status=LeadProcessingStatus.PENDING),
        ]

        mock_db.query.return_value.filter_by.return_value.first.return_value = mock_batch
        mock_db.query.return_value.filter_by.return_value.all.return_value = mock_leads

        # Mock successful lead processing
        with patch.object(mock_batch_processor, "_process_single_lead") as mock_process:
            mock_process.return_value = LeadProcessingResult(
                lead_id=mock_leads[0].lead_id,
                success=True,
                report_url="http://example.com/report.pdf",
                actual_cost=5.0,
                processing_time_ms=1500,
                quality_score=0.85,
            )

            # Test successful processing
            result = await mock_batch_processor.process_batch(batch_id)

            # Verify result
            assert isinstance(result, BatchProcessingResult)
            assert result.batch_id == batch_id
            assert result.total_leads == 2

    async def test_process_single_lead_success(self, mock_batch_processor):
        """Test successful processing of a single lead"""
        lead_id = str(uuid.uuid4())
        batch_id = str(uuid.uuid4())

        # Mock report generator
        mock_report_result = MagicMock()
        mock_report_result.success = True
        mock_report_result.report_url = "http://example.com/report.pdf"
        mock_report_result.processing_cost = 2.50
        mock_report_result.quality_score = 0.90

        mock_batch_processor._mock_report.generate_report = AsyncMock(return_value=mock_report_result)

        # Test successful lead processing
        result = await mock_batch_processor._process_single_lead(lead_id, batch_id)

        # Verify result
        assert isinstance(result, LeadProcessingResult)
        assert result.lead_id == lead_id
        assert result.success == True
        assert result.report_url == "http://example.com/report.pdf"
        assert result.actual_cost == 2.50
        assert result.quality_score == 0.90

    async def test_process_single_lead_failure(self, mock_batch_processor):
        """Test failed processing of a single lead"""
        lead_id = str(uuid.uuid4())
        batch_id = str(uuid.uuid4())

        # Mock report generator to raise exception
        mock_batch_processor._mock_report.generate_report = AsyncMock(side_effect=Exception("Report generation failed"))

        # Test failed lead processing
        result = await mock_batch_processor._process_single_lead(lead_id, batch_id)

        # Verify failure result
        assert isinstance(result, LeadProcessingResult)
        assert result.lead_id == lead_id
        assert result.success == False
        assert "Report generation failed" in result.error_message
        assert result.error_code == "GENERATION_ERROR"

    async def test_process_single_lead_timeout(self, mock_batch_processor):
        """Test timeout during lead processing"""
        lead_id = str(uuid.uuid4())
        batch_id = str(uuid.uuid4())

        # Mock report generator to timeout
        async def slow_generation(*args, **kwargs):
            await asyncio.sleep(2)  # Longer than default timeout
            return MagicMock()

        mock_batch_processor._mock_report.generate_report = slow_generation
        mock_batch_processor.default_timeout_seconds = 1  # Short timeout for test

        # Test timeout handling
        result = await mock_batch_processor._process_single_lead(lead_id, batch_id)

        # Verify timeout result
        assert isinstance(result, LeadProcessingResult)
        assert result.lead_id == lead_id
        assert result.success == False
        assert "timeout" in result.error_message.lower()
        assert result.error_code == "TIMEOUT_ERROR"

    @patch("batch_runner.processor.SessionLocal")
    async def test_update_lead_status_success(self, mock_session, mock_batch_processor):
        """Test successful lead status update"""
        # Setup mock database session
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db

        mock_lead = MagicMock()
        mock_db.query.return_value.filter_by.return_value.first.return_value = mock_lead

        # Test status update
        await mock_batch_processor._update_lead_status(
            "lead-123",
            "batch-456",
            LeadProcessingStatus.COMPLETED,
            report_url="http://example.com/report.pdf",
            actual_cost=3.50,
            processing_time_ms=2000,
            quality_score=0.88,
        )

        # Verify lead was updated
        assert mock_lead.status == LeadProcessingStatus.COMPLETED
        assert mock_lead.report_url == "http://example.com/report.pdf"
        assert mock_lead.actual_cost == 3.50
        assert mock_lead.processing_time_ms == 2000
        assert mock_lead.quality_score == 0.88
        assert mock_lead.processed_at is not None
        mock_db.commit.assert_called_once()

    @patch("batch_runner.processor.SessionLocal")
    async def test_update_batch_progress(self, mock_session, mock_batch_processor):
        """Test batch progress update"""
        # Setup mock database session
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db

        mock_batch = MagicMock()
        mock_batch.total_leads = 10
        mock_batch.processed_leads = 7
        mock_batch.successful_leads = 5
        mock_batch.failed_leads = 2
        mock_db.query.return_value.filter_by.return_value.first.return_value = mock_batch

        # Test progress update
        await mock_batch_processor._update_batch_progress("batch-123")

        # Verify progress calculation
        expected_percentage = (7 / 10) * 100  # 70%
        assert mock_batch.progress_percentage == expected_percentage
        mock_db.commit.assert_called_once()

    async def test_send_progress_update(self, mock_batch_processor):
        """Test WebSocket progress update"""
        batch_id = "batch-123"
        progress_data = {"processed": 5, "total": 10, "percentage": 50.0, "success_count": 4, "failure_count": 1}

        # Test progress broadcast
        await mock_batch_processor._send_progress_update(batch_id, progress_data)

        # Verify connection manager was called
        mock_batch_processor._mock_conn.broadcast_progress.assert_called_once_with(batch_id, progress_data)

    @patch("batch_runner.processor.SessionLocal")
    async def test_finalize_batch_success(self, mock_session, mock_batch_processor):
        """Test successful batch finalization"""
        # Setup mock database session
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db

        mock_batch = MagicMock()
        mock_batch.total_leads = 5
        mock_batch.successful_leads = 4
        mock_batch.failed_leads = 1
        mock_db.query.return_value.filter_by.return_value.first.return_value = mock_batch

        batch_id = "batch-123"
        total_cost = 25.75

        # Test batch finalization
        await mock_batch_processor._finalize_batch(batch_id, total_cost)

        # Verify batch was finalized
        assert mock_batch.status == BatchStatus.COMPLETED_WITH_ERRORS  # Due to failed leads
        assert mock_batch.actual_cost == total_cost
        assert mock_batch.completed_at is not None
        mock_db.commit.assert_called_once()

    @patch("batch_runner.processor.SessionLocal")
    async def test_finalize_batch_all_success(self, mock_session, mock_batch_processor):
        """Test batch finalization with all leads successful"""
        # Setup mock database session
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db

        mock_batch = MagicMock()
        mock_batch.total_leads = 5
        mock_batch.successful_leads = 5
        mock_batch.failed_leads = 0
        mock_db.query.return_value.filter_by.return_value.first.return_value = mock_batch

        batch_id = "batch-123"
        total_cost = 25.75

        # Test batch finalization
        await mock_batch_processor._finalize_batch(batch_id, total_cost)

        # Verify batch was marked as fully completed
        assert mock_batch.status == BatchStatus.COMPLETED
        assert mock_batch.actual_cost == total_cost
        mock_db.commit.assert_called_once()

    def test_batch_processing_result_creation(self):
        """Test BatchProcessingResult creation and attributes"""
        result = BatchProcessingResult(
            batch_id="test-batch",
            total_leads=100,
            successful=85,
            failed=10,
            skipped=5,
            total_cost=42.50,
            duration_seconds=125.5,
        )

        # Verify all attributes
        assert result.batch_id == "test-batch"
        assert result.total_leads == 100
        assert result.successful == 85
        assert result.failed == 10
        assert result.skipped == 5
        assert result.total_cost == 42.50
        assert result.duration_seconds == 125.5
        assert result.error_message is None

    def test_lead_processing_result_creation(self):
        """Test LeadProcessingResult creation and attributes"""
        result = LeadProcessingResult(
            lead_id="lead-123",
            success=True,
            report_url="http://example.com/report.pdf",
            actual_cost=2.75,
            processing_time_ms=1850,
            quality_score=0.92,
        )

        # Verify all attributes
        assert result.lead_id == "lead-123"
        assert result.success == True
        assert result.report_url == "http://example.com/report.pdf"
        assert result.actual_cost == 2.75
        assert result.processing_time_ms == 1850
        assert result.quality_score == 0.92
        assert result.error_message is None
        assert result.error_code is None

    def test_lead_processing_result_failure(self):
        """Test LeadProcessingResult for failed processing"""
        result = LeadProcessingResult(
            lead_id="lead-456",
            success=False,
            error_message="Generation timeout after 30 seconds",
            error_code="TIMEOUT_ERROR",
        )

        # Verify failure attributes
        assert result.lead_id == "lead-456"
        assert result.success == False
        assert result.error_message == "Generation timeout after 30 seconds"
        assert result.error_code == "TIMEOUT_ERROR"
        assert result.report_url is None
        assert result.actual_cost is None
