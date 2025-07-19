"""
Focused tests for batch processor to achieve ≥80% coverage
P0-022 requirement: comprehensive test coverage on all batch_runner modules
"""
import asyncio
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError

from batch_runner.models import BatchReport, BatchReportLead, BatchStatus, LeadProcessingStatus
from batch_runner.processor import BatchProcessingResult, BatchProcessor, LeadProcessingResult


class TestBatchProcessorFocused:
    """Focused tests for BatchProcessor methods"""

    @pytest.fixture
    def mock_processor(self):
        """Create a processor with all dependencies mocked"""
        with patch("batch_runner.processor.get_settings"), patch(
            "batch_runner.processor.get_connection_manager"
        ), patch("batch_runner.processor.get_cost_calculator"), patch("batch_runner.processor.ReportGenerator"), patch(
            "batch_runner.processor.ThreadPoolExecutor"
        ):
            processor = BatchProcessor()
            # Mock internal methods that we're not testing
            processor._get_batch_leads = AsyncMock()
            processor._process_leads_concurrently = AsyncMock()
            processor._complete_batch = AsyncMock()
            processor._fail_batch = AsyncMock()
            processor.connection_manager.broadcast_progress = AsyncMock()
            processor.connection_manager.broadcast_completion = AsyncMock()
            processor.connection_manager.broadcast_error = AsyncMock()

            return processor

    @pytest.fixture
    def mock_batch_lead(self):
        """Create a mock BatchReportLead object"""
        lead = Mock()
        lead.id = str(uuid.uuid4())
        lead.lead_id = str(uuid.uuid4())
        lead.is_retryable = True
        return lead

    async def test_process_batch_not_found(self, mock_processor):
        """Test process_batch with non-existent batch"""
        batch_id = str(uuid.uuid4())

        with patch("batch_runner.processor.SessionLocal") as mock_session:
            mock_db = Mock()
            mock_session.return_value.__enter__.return_value = mock_db
            mock_db.query.return_value.filter_by.return_value.first.return_value = None

            result = await mock_processor.process_batch(batch_id)

            # Should return error result instead of raising
            assert result.batch_id == batch_id
            assert result.total_leads == 0
            assert result.error_message is not None

    async def test_process_batch_invalid_status(self, mock_processor):
        """Test process_batch with batch in wrong status"""
        batch_id = str(uuid.uuid4())

        with patch("batch_runner.processor.SessionLocal") as mock_session:
            mock_db = Mock()
            mock_session.return_value.__enter__.return_value = mock_db

            mock_batch = Mock()
            mock_batch.status = BatchStatus.RUNNING  # Not PENDING
            mock_db.query.return_value.filter_by.return_value.first.return_value = mock_batch

            result = await mock_processor.process_batch(batch_id)

            # Should return error result instead of raising
            assert result.batch_id == batch_id
            assert result.total_leads == 0
            assert result.error_message is not None

    async def test_get_batch_leads_success(self):
        """Test _get_batch_leads method"""
        # Create actual processor to test this method
        with patch("batch_runner.processor.get_settings"), patch(
            "batch_runner.processor.get_connection_manager"
        ), patch("batch_runner.processor.get_cost_calculator"), patch("batch_runner.processor.ReportGenerator"), patch(
            "batch_runner.processor.ThreadPoolExecutor"
        ):
            processor = BatchProcessor()
            batch_id = str(uuid.uuid4())

            # Mock database
            with patch("batch_runner.processor.SessionLocal") as mock_session:
                mock_db = Mock()
                mock_session.return_value.__enter__.return_value = mock_db

                # Mock leads
                mock_lead1 = Mock(id="lead1", lead_id="lead1", status=LeadProcessingStatus.PENDING)
                mock_lead2 = Mock(id="lead2", lead_id="lead2", status=LeadProcessingStatus.PENDING)
                mock_leads = [mock_lead1, mock_lead2]

                mock_db.query.return_value.filter_by.return_value.filter_by.return_value.order_by.return_value.all.return_value = (
                    mock_leads
                )

                # Test
                result = await processor._get_batch_leads(batch_id)

                # Verify
                assert len(result) == 2
                assert result[0].id == "lead1"
                assert result[1].id == "lead2"

    async def test_get_lead_data_success(self):
        """Test _get_lead_data method"""
        with patch("batch_runner.processor.get_settings"), patch(
            "batch_runner.processor.get_connection_manager"
        ), patch("batch_runner.processor.get_cost_calculator"), patch("batch_runner.processor.ReportGenerator"), patch(
            "batch_runner.processor.ThreadPoolExecutor"
        ):
            processor = BatchProcessor()
            lead_id = str(uuid.uuid4())

            with patch("batch_runner.processor.SessionLocal") as mock_session, patch(
                "batch_runner.processor.LeadRepository"
            ) as mock_repo_class:
                mock_db = Mock()
                mock_session.return_value.__enter__.return_value = mock_db

                # Mock lead data
                mock_lead = Mock()
                mock_lead.id = lead_id
                mock_lead.email = "test@example.com"
                mock_lead.domain = "example.com"
                mock_lead.company_name = "Test Company"
                mock_lead.contact_name = "John Doe"
                mock_lead.enrichment_status.value = "completed"
                mock_lead.source = "import"

                mock_repo = Mock()
                mock_repo.get_lead_by_id.return_value = mock_lead
                mock_repo_class.return_value = mock_repo

                # Test
                result = await processor._get_lead_data(lead_id)

                # Verify
                assert result is not None
                assert result["id"] == lead_id
                assert result["email"] == "test@example.com"
                assert result["domain"] == "example.com"

    async def test_get_lead_data_not_found(self):
        """Test _get_lead_data with missing lead"""
        with patch("batch_runner.processor.get_settings"), patch(
            "batch_runner.processor.get_connection_manager"
        ), patch("batch_runner.processor.get_cost_calculator"), patch("batch_runner.processor.ReportGenerator"), patch(
            "batch_runner.processor.ThreadPoolExecutor"
        ):
            processor = BatchProcessor()
            lead_id = str(uuid.uuid4())

            with patch("batch_runner.processor.SessionLocal") as mock_session, patch(
                "batch_runner.processor.LeadRepository"
            ) as mock_repo_class:
                mock_db = Mock()
                mock_session.return_value.__enter__.return_value = mock_db

                mock_repo = Mock()
                mock_repo.get_lead_by_id.return_value = None
                mock_repo_class.return_value = mock_repo

                # Test
                result = await processor._get_lead_data(lead_id)

                # Verify
                assert result is None

    async def test_calculate_actual_cost(self):
        """Test _calculate_actual_cost method"""
        with patch("batch_runner.processor.get_settings"), patch(
            "batch_runner.processor.get_connection_manager"
        ), patch("batch_runner.processor.get_cost_calculator"), patch("batch_runner.processor.ReportGenerator"), patch(
            "batch_runner.processor.ThreadPoolExecutor"
        ):
            processor = BatchProcessor()

            lead_data = {"enrichment_status": "completed"}
            report_result = {"report_url": "http://example.com/report.pdf"}

            # Test
            result = await processor._calculate_actual_cost(lead_data, report_result)

            # Verify
            assert isinstance(result, float)
            assert result > 0

    async def test_update_lead_status(self):
        """Test _update_lead_status method"""
        with patch("batch_runner.processor.get_settings"), patch(
            "batch_runner.processor.get_connection_manager"
        ), patch("batch_runner.processor.get_cost_calculator"), patch("batch_runner.processor.ReportGenerator"), patch(
            "batch_runner.processor.ThreadPoolExecutor"
        ):
            processor = BatchProcessor()
            batch_lead_id = str(uuid.uuid4())

            with patch("batch_runner.processor.SessionLocal") as mock_session:
                mock_db = Mock()
                mock_session.return_value.__enter__.return_value = mock_db

                mock_lead = Mock()
                mock_db.query.return_value.filter_by.return_value.first.return_value = mock_lead

                # Test
                await processor._update_lead_status(batch_lead_id, LeadProcessingStatus.PROCESSING, datetime.utcnow())

                # Verify
                assert mock_lead.status == LeadProcessingStatus.PROCESSING
                mock_db.commit.assert_called_once()

    async def test_update_lead_completion(self):
        """Test _update_lead_completion method"""
        with patch("batch_runner.processor.get_settings"), patch(
            "batch_runner.processor.get_connection_manager"
        ), patch("batch_runner.processor.get_cost_calculator"), patch("batch_runner.processor.ReportGenerator"), patch(
            "batch_runner.processor.ThreadPoolExecutor"
        ):
            processor = BatchProcessor()
            batch_lead_id = str(uuid.uuid4())

            with patch("batch_runner.processor.SessionLocal") as mock_session:
                mock_db = Mock()
                mock_session.return_value.__enter__.return_value = mock_db

                mock_lead = Mock()
                mock_db.query.return_value.filter_by.return_value.first.return_value = mock_lead

                # Test
                await processor._update_lead_completion(
                    batch_lead_id, "http://example.com/report.pdf", 2.50, 0.85, datetime.utcnow()
                )

                # Verify
                mock_lead.mark_completed.assert_called_once()
                mock_db.commit.assert_called_once()

    def test_batch_processing_result_creation(self):
        """Test BatchProcessingResult dataclass"""
        result = BatchProcessingResult(
            batch_id="test-batch",
            total_leads=100,
            successful=90,
            failed=8,
            skipped=2,
            total_cost=125.50,
            duration_seconds=300.0,
        )

        assert result.batch_id == "test-batch"
        assert result.total_leads == 100
        assert result.successful == 90
        assert result.failed == 8
        assert result.skipped == 2
        assert result.total_cost == 125.50
        assert result.duration_seconds == 300.0
        assert result.error_message is None

    def test_lead_processing_result_success(self):
        """Test LeadProcessingResult for successful processing"""
        result = LeadProcessingResult(
            lead_id="lead-123",
            success=True,
            report_url="http://example.com/report.pdf",
            actual_cost=2.75,
            processing_time_ms=1500,
            quality_score=0.88,
        )

        assert result.lead_id == "lead-123"
        assert result.success is True
        assert result.report_url == "http://example.com/report.pdf"
        assert result.actual_cost == 2.75
        assert result.processing_time_ms == 1500
        assert result.quality_score == 0.88
        assert result.error_message is None
        assert result.error_code is None

    def test_lead_processing_result_failure(self):
        """Test LeadProcessingResult for failed processing"""
        result = LeadProcessingResult(
            lead_id="lead-456", success=False, error_message="Processing timeout", error_code="TIMEOUT_ERROR"
        )

        assert result.lead_id == "lead-456"
        assert result.success is False
        assert result.error_message == "Processing timeout"
        assert result.error_code == "TIMEOUT_ERROR"
        assert result.report_url is None
        assert result.actual_cost is None

    async def test_generate_report_sync(self):
        """Test _generate_report_sync method"""
        with patch("batch_runner.processor.get_settings"), patch(
            "batch_runner.processor.get_connection_manager"
        ), patch("batch_runner.processor.get_cost_calculator"), patch("batch_runner.processor.ReportGenerator"), patch(
            "batch_runner.processor.ThreadPoolExecutor"
        ):
            processor = BatchProcessor()

            lead_data = {"id": "test-lead", "email": "test@example.com"}

            with patch("batch_runner.processor.GenerationOptions") as mock_options:
                mock_options_instance = Mock()
                mock_options.return_value = mock_options_instance

                # Test
                result = processor._generate_report_sync(lead_data, mock_options_instance)

                # Verify
                assert result["success"] is True
                assert "report_url" in result
                assert result["quality_score"] == 0.85

    def test_get_batch_processor_singleton(self):
        """Test get_batch_processor singleton function"""
        from batch_runner.processor import get_batch_processor

        with patch("batch_runner.processor.BatchProcessor") as mock_class:
            mock_instance = Mock()
            mock_class.return_value = mock_instance

            # First call creates instance
            result1 = get_batch_processor()
            assert result1 == mock_instance
            mock_class.assert_called_once()

            # Second call returns same instance
            result2 = get_batch_processor()
            assert result2 == result1
            # Class should not be called again
            mock_class.assert_called_once()

    async def test_start_batch_processing_function(self):
        """Test start_batch_processing convenience function"""
        from batch_runner.processor import start_batch_processing

        batch_id = "test-batch"
        expected_result = BatchProcessingResult(
            batch_id=batch_id, total_leads=5, successful=4, failed=1, skipped=0, total_cost=12.50, duration_seconds=60.0
        )

        with patch("batch_runner.processor.get_batch_processor") as mock_get:
            mock_processor = Mock()
            mock_processor.process_batch = AsyncMock(return_value=expected_result)
            mock_get.return_value = mock_processor

            # Test
            result = await start_batch_processing(batch_id)

            # Verify
            assert result == expected_result
            mock_processor.process_batch.assert_called_once_with(batch_id)
