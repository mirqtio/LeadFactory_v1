"""
Complete test coverage for batch processor P0-022
Focus on missing lines to achieve ≥80% coverage requirement
"""
import asyncio
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from batch_runner.models import BatchReport, BatchReportLead, BatchStatus, LeadProcessingStatus
from batch_runner.processor import BatchProcessingResult, BatchProcessor, LeadProcessingResult


class TestBatchProcessorComplete:
    """Complete test coverage for BatchProcessor"""

    @pytest.fixture
    def processor(self):
        """Create processor with mocked dependencies"""
        with patch("batch_runner.processor.get_settings") as mock_settings, patch(
            "batch_runner.processor.get_connection_manager"
        ) as mock_conn, patch("batch_runner.processor.get_cost_calculator") as mock_cost, patch(
            "batch_runner.processor.ReportGenerator"
        ) as mock_report, patch(
            "batch_runner.processor.ThreadPoolExecutor"
        ) as mock_thread:
            # Setup settings
            settings = Mock()
            settings.BATCH_MAX_CONCURRENT_LEADS = 3
            mock_settings.return_value = settings

            # Create processor
            processor = BatchProcessor()

            # Store mocks for access
            processor._test_connection_manager = mock_conn.return_value
            processor._test_cost_calculator = mock_cost.return_value
            processor._test_report_generator = mock_report.return_value
            processor._test_thread_pool = mock_thread.return_value

            return processor

    async def test_process_batch_full_success_flow(self, processor):
        """Test complete successful batch processing flow"""
        batch_id = str(uuid.uuid4())

        # Mock database operations
        with patch("batch_runner.processor.SessionLocal") as mock_session:
            mock_db = Mock()
            mock_session.return_value.__enter__.return_value = mock_db

            # Mock batch
            mock_batch = Mock()
            mock_batch.id = batch_id
            mock_batch.status = BatchStatus.PENDING
            mock_batch.total_leads = 2

            # Mock leads
            lead1_id = str(uuid.uuid4())
            lead2_id = str(uuid.uuid4())
            mock_leads = [
                Mock(id="batch_lead_1", lead_id=lead1_id, status=LeadProcessingStatus.PENDING),
                Mock(id="batch_lead_2", lead_id=lead2_id, status=LeadProcessingStatus.PENDING),
            ]

            # Setup database query chain
            mock_db.query.return_value.filter_by.return_value.first.return_value = mock_batch

            # Mock the async methods that will be called
            with patch.object(processor, "_get_batch_leads", return_value=mock_leads) as mock_get_leads, patch.object(
                processor, "_process_leads_concurrently"
            ) as mock_process_leads, patch.object(processor, "_complete_batch") as mock_complete:
                # Setup lead processing results
                results = [
                    LeadProcessingResult(lead_id=lead1_id, success=True, actual_cost=2.5),
                    LeadProcessingResult(lead_id=lead2_id, success=True, actual_cost=3.0),
                ]
                mock_process_leads.return_value = results

                # Test the full flow
                result = await processor.process_batch(batch_id)

                # Verify the flow was executed
                assert result.batch_id == batch_id
                assert result.total_leads == 2
                assert result.successful == 2
                assert result.failed == 0
                assert result.total_cost == 5.5
                assert result.error_message is None

                # Verify methods were called
                mock_get_leads.assert_called_once_with(batch_id)
                mock_process_leads.assert_called_once()
                mock_complete.assert_called_once()

    async def test_process_leads_concurrently_success(self, processor):
        """Test _process_leads_concurrently method"""
        batch_id = str(uuid.uuid4())

        # Create mock leads
        leads = [Mock(id="lead1", lead_id="lead1"), Mock(id="lead2", lead_id="lead2")]

        # Mock the single lead processing
        with patch.object(processor, "_process_single_lead_with_semaphore") as mock_process:
            # Mock async results
            result1 = LeadProcessingResult(lead_id="lead1", success=True, actual_cost=2.0)
            result2 = LeadProcessingResult(lead_id="lead2", success=True, actual_cost=3.0)

            # Create tasks that complete immediately
            async def mock_task_1(*args):
                return result1

            async def mock_task_2(*args):
                return result2

            mock_process.side_effect = [mock_task_1(), mock_task_2()]

            # Mock progress update methods
            with patch.object(processor, "_update_batch_progress") as mock_progress, patch.object(
                processor.connection_manager, "broadcast_progress"
            ) as mock_broadcast:
                # Test
                results = await processor._process_leads_concurrently(batch_id, leads)

                # Verify
                assert len(results) == 2
                assert all(r.success for r in results)
                assert mock_progress.call_count == 2
                assert mock_broadcast.call_count == 2

    async def test_process_single_lead_with_semaphore(self, processor):
        """Test _process_single_lead_with_semaphore concurrency control"""
        batch_id = str(uuid.uuid4())
        mock_lead = Mock(id="lead1", lead_id="lead1")
        semaphore = asyncio.Semaphore(1)

        expected_result = LeadProcessingResult(lead_id="lead1", success=True)

        with patch.object(processor, "_process_single_lead", return_value=expected_result) as mock_process:
            # Test
            result = await processor._process_single_lead_with_semaphore(semaphore, batch_id, mock_lead)

            # Verify
            assert result == expected_result
            mock_process.assert_called_once_with(batch_id, mock_lead)

    async def test_process_single_lead_success_flow(self, processor):
        """Test _process_single_lead successful processing"""
        batch_id = str(uuid.uuid4())
        lead_id = str(uuid.uuid4())

        mock_lead = Mock()
        mock_lead.id = "batch_lead_1"
        mock_lead.lead_id = lead_id
        mock_lead.is_retryable = True

        # Mock all the internal methods
        with patch.object(processor, "_update_lead_status") as mock_status, patch.object(
            processor, "_get_lead_data"
        ) as mock_get_data, patch.object(processor, "_generate_report_for_lead") as mock_report, patch.object(
            processor, "_calculate_actual_cost"
        ) as mock_cost, patch.object(
            processor, "_update_lead_completion"
        ) as mock_completion:
            # Setup return values
            mock_get_data.return_value = {"id": lead_id, "email": "test@example.com"}
            mock_report.return_value = {"report_url": "http://example.com/report.pdf", "quality_score": 0.85}
            mock_cost.return_value = 2.50

            # Test
            result = await processor._process_single_lead(batch_id, mock_lead)

            # Verify result
            assert result.lead_id == lead_id
            assert result.success is True
            assert result.report_url == "http://example.com/report.pdf"
            assert result.actual_cost == 2.50
            assert result.quality_score == 0.85

            # Verify methods called
            mock_status.assert_called_once()
            mock_get_data.assert_called_once_with(lead_id)
            mock_report.assert_called_once()
            mock_cost.assert_called_once()
            mock_completion.assert_called_once()

    async def test_process_single_lead_lead_not_found(self, processor):
        """Test _process_single_lead when lead data not found"""
        batch_id = str(uuid.uuid4())
        lead_id = str(uuid.uuid4())

        mock_lead = Mock()
        mock_lead.id = "batch_lead_1"
        mock_lead.lead_id = lead_id
        mock_lead.is_retryable = False

        with patch.object(processor, "_update_lead_status") as mock_status, patch.object(
            processor, "_get_lead_data", return_value=None
        ), patch.object(processor, "_update_lead_failure") as mock_failure:
            # Test
            result = await processor._process_single_lead(batch_id, mock_lead)

            # Verify failure result
            assert result.lead_id == lead_id
            assert result.success is False
            assert "not found or deleted" in result.error_message
            assert result.error_code == "PROCESSING_FAILED"

            # Verify failure was recorded
            mock_failure.assert_called_once()

    async def test_process_single_lead_with_retry(self, processor):
        """Test _process_single_lead retry logic"""
        batch_id = str(uuid.uuid4())
        lead_id = str(uuid.uuid4())

        mock_lead = Mock()
        mock_lead.id = "batch_lead_1"
        mock_lead.lead_id = lead_id
        mock_lead.is_retryable = True

        with patch.object(processor, "_update_lead_status"), patch.object(
            processor, "_get_lead_data", side_effect=Exception("Processing error")
        ), patch.object(processor, "_schedule_retry") as mock_retry:
            # Test
            result = await processor._process_single_lead(batch_id, mock_lead)

            # Verify retry was scheduled
            assert result.lead_id == lead_id
            assert result.success is False
            assert result.error_code == "RETRY_SCHEDULED"
            mock_retry.assert_called_once_with(mock_lead.id)

    async def test_generate_report_for_lead(self, processor):
        """Test _generate_report_for_lead method"""
        lead_data = {"id": "test-lead", "email": "test@example.com"}

        # Mock the executor
        mock_loop = Mock()
        expected_result = {"success": True, "report_url": "/reports/test-lead/report.pdf", "quality_score": 0.85}

        with patch("asyncio.get_event_loop", return_value=mock_loop):
            mock_loop.run_in_executor.return_value = expected_result

            # Test
            result = await processor._generate_report_for_lead(lead_data)

            # Verify
            assert result == expected_result
            mock_loop.run_in_executor.assert_called_once()

    async def test_schedule_retry(self, processor):
        """Test _schedule_retry method"""
        batch_lead_id = str(uuid.uuid4())

        with patch("batch_runner.processor.SessionLocal") as mock_session:
            mock_db = Mock()
            mock_session.return_value.__enter__.return_value = mock_db

            mock_lead = Mock()
            mock_lead.is_retryable = True
            mock_db.query.return_value.filter_by.return_value.first.return_value = mock_lead

            # Test
            await processor._schedule_retry(batch_lead_id)

            # Verify
            mock_lead.increment_retry.assert_called_once()
            mock_db.commit.assert_called_once()

    async def test_schedule_retry_not_retryable(self, processor):
        """Test _schedule_retry when lead is not retryable"""
        batch_lead_id = str(uuid.uuid4())

        with patch("batch_runner.processor.SessionLocal") as mock_session:
            mock_db = Mock()
            mock_session.return_value.__enter__.return_value = mock_db

            mock_lead = Mock()
            mock_lead.is_retryable = False
            mock_db.query.return_value.filter_by.return_value.first.return_value = mock_lead

            # Test
            await processor._schedule_retry(batch_lead_id)

            # Verify retry not called
            mock_lead.increment_retry.assert_not_called()

    async def test_update_batch_progress(self, processor):
        """Test _update_batch_progress method"""
        batch_id = str(uuid.uuid4())

        with patch("batch_runner.processor.SessionLocal") as mock_session:
            mock_db = Mock()
            mock_session.return_value.__enter__.return_value = mock_db

            mock_batch = Mock()
            mock_db.query.return_value.filter_by.return_value.first.return_value = mock_batch

            # Test
            await processor._update_batch_progress(
                batch_id, processed=5, successful=4, failed=1, progress_percentage=50.0, current_lead_id="lead-123"
            )

            # Verify
            mock_batch.update_progress.assert_called_once_with(5, 4, 1, "lead-123")
            mock_db.commit.assert_called_once()

    async def test_complete_batch(self, processor):
        """Test _complete_batch method"""
        batch_id = str(uuid.uuid4())

        with patch("batch_runner.processor.SessionLocal") as mock_session:
            mock_db = Mock()
            mock_session.return_value.__enter__.return_value = mock_db

            mock_batch = Mock()
            mock_batch.total_leads = 10
            mock_batch.success_rate = 0.8
            mock_batch.duration_seconds = 300
            mock_db.query.return_value.filter_by.return_value.first.return_value = mock_batch

            # Test
            await processor._complete_batch(
                batch_id, successful=8, failed=2, total_cost=25.50, completed_at=datetime.utcnow()
            )

            # Verify batch updated
            assert mock_batch.status == BatchStatus.COMPLETED
            assert mock_batch.successful_leads == 8
            assert mock_batch.failed_leads == 2
            assert mock_batch.actual_cost_usd == 25.50
            assert mock_batch.progress_percentage == 100.0

            # Verify results summary
            assert mock_batch.results_summary["successful"] == 8
            assert mock_batch.results_summary["failed"] == 2
            assert mock_batch.results_summary["total_cost"] == 25.50

            mock_db.commit.assert_called_once()

    async def test_fail_batch(self, processor):
        """Test _fail_batch method"""
        batch_id = str(uuid.uuid4())
        error_message = "Processing failed"

        with patch("batch_runner.processor.SessionLocal") as mock_session:
            mock_db = Mock()
            mock_session.return_value.__enter__.return_value = mock_db

            mock_batch = Mock()
            mock_db.query.return_value.filter_by.return_value.first.return_value = mock_batch

            # Test
            await processor._fail_batch(batch_id, error_message)

            # Verify
            assert mock_batch.status == BatchStatus.FAILED
            assert mock_batch.error_message == error_message
            assert mock_batch.completed_at is not None
            mock_db.commit.assert_called_once()

    async def test_update_lead_failure(self, processor):
        """Test _update_lead_failure method"""
        batch_lead_id = str(uuid.uuid4())

        with patch("batch_runner.processor.SessionLocal") as mock_session:
            mock_db = Mock()
            mock_session.return_value.__enter__.return_value = mock_db

            mock_lead = Mock()
            mock_db.query.return_value.filter_by.return_value.first.return_value = mock_lead

            # Test
            await processor._update_lead_failure(
                batch_lead_id, "Processing failed", "PROCESSING_ERROR", datetime.utcnow()
            )

            # Verify
            mock_lead.mark_failed.assert_called_once_with("Processing failed", "PROCESSING_ERROR")
            mock_db.commit.assert_called_once()

    def test_processor_initialization_complete(self):
        """Test complete processor initialization"""
        with patch("batch_runner.processor.get_settings") as mock_settings, patch(
            "batch_runner.processor.get_connection_manager"
        ) as mock_conn, patch("batch_runner.processor.get_cost_calculator") as mock_cost, patch(
            "batch_runner.processor.ReportGenerator"
        ) as mock_report, patch(
            "batch_runner.processor.ThreadPoolExecutor"
        ) as mock_thread:
            # Setup settings
            settings = Mock()
            settings.BATCH_MAX_CONCURRENT_LEADS = 7
            mock_settings.return_value = settings

            # Create processor
            processor = BatchProcessor()

            # Verify all components initialized
            assert processor.settings == settings
            assert processor.max_concurrent_leads == 7
            assert processor.default_timeout_seconds == 30
            assert processor.max_retries == 3

            # Verify thread pool created with correct workers
            mock_thread.assert_called_once_with(max_workers=7)
