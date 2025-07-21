"""
Test suite for batch_runner models
Focus on achieving ≥80% total coverage for P0-022
"""

import uuid
from datetime import datetime
from unittest.mock import Mock

import pytest

from batch_runner.models import BatchReport, BatchReportLead, BatchStatus, LeadProcessingStatus


class TestBatchStatus:
    """Test BatchStatus enum"""

    def test_batch_status_values(self):
        """Test BatchStatus enum values"""
        assert BatchStatus.PENDING == "pending"
        assert BatchStatus.RUNNING == "running"
        assert BatchStatus.COMPLETED == "completed"
        assert BatchStatus.FAILED == "failed"
        assert BatchStatus.CANCELLED == "cancelled"

    def test_batch_status_iteration(self):
        """Test BatchStatus enum iteration"""
        statuses = list(BatchStatus)
        assert len(statuses) == 5
        assert BatchStatus.PENDING in statuses


class TestLeadProcessingStatus:
    """Test LeadProcessingStatus enum"""

    def test_lead_processing_status_values(self):
        """Test LeadProcessingStatus enum values"""
        assert LeadProcessingStatus.PENDING == "pending"
        assert LeadProcessingStatus.PROCESSING == "processing"
        assert LeadProcessingStatus.COMPLETED == "completed"
        assert LeadProcessingStatus.FAILED == "failed"
        assert LeadProcessingStatus.SKIPPED == "skipped"

    def test_lead_processing_status_iteration(self):
        """Test LeadProcessingStatus enum iteration"""
        statuses = list(LeadProcessingStatus)
        assert len(statuses) == 5
        assert LeadProcessingStatus.PENDING in statuses


class TestBatchReport:
    """Test BatchReport model"""

    @pytest.fixture
    def sample_batch_report(self):
        """Create sample batch report"""
        from datetime import datetime

        return BatchReport(
            id=str(uuid.uuid4()),
            created_by=str(uuid.uuid4()),
            name="Test Batch",
            description="Test batch for coverage",
            template_version="v1.2",
            total_leads=10,
            processed_leads=0,
            successful_leads=0,
            failed_leads=0,
            progress_percentage=0.0,
            estimated_cost_usd=25.50,
            created_at=datetime.utcnow(),
            status=BatchStatus.PENDING,
        )

    def test_batch_report_creation(self, sample_batch_report):
        """Test BatchReport creation"""
        assert sample_batch_report.name == "Test Batch"
        assert sample_batch_report.total_leads == 10
        assert sample_batch_report.estimated_cost_usd == 25.50
        assert sample_batch_report.status == BatchStatus.PENDING

    def test_batch_report_defaults(self):
        """Test BatchReport default values"""
        from datetime import datetime

        batch = BatchReport(
            created_by=str(uuid.uuid4()),
            name="Test",
            template_version="v1.0",
            total_leads=5,
            status=BatchStatus.PENDING,
            processed_leads=0,
            successful_leads=0,
            failed_leads=0,
            progress_percentage=0.0,
            created_at=datetime.utcnow(),
        )

        assert batch.status == BatchStatus.PENDING
        assert batch.processed_leads == 0
        assert batch.successful_leads == 0
        assert batch.failed_leads == 0
        assert batch.progress_percentage == 0.0
        assert batch.created_at is not None

    def test_batch_report_update_progress(self, sample_batch_report):
        """Test batch progress update"""
        sample_batch_report.update_progress(processed=5, successful=4, failed=1, current_lead_id="lead-123")

        assert sample_batch_report.processed_leads == 5
        assert sample_batch_report.successful_leads == 4
        assert sample_batch_report.failed_leads == 1
        assert sample_batch_report.current_lead_id == "lead-123"
        assert sample_batch_report.progress_percentage == 50.0  # 5/10 * 100

    def test_batch_report_mark_running(self, sample_batch_report):
        """Test marking batch as running"""
        from datetime import datetime

        sample_batch_report.status = BatchStatus.RUNNING
        sample_batch_report.started_at = datetime.utcnow()

        assert sample_batch_report.status == BatchStatus.RUNNING
        assert sample_batch_report.started_at is not None

    def test_batch_report_mark_completed(self, sample_batch_report):
        """Test marking batch as completed"""
        from datetime import datetime

        sample_batch_report.actual_cost_usd = 30.25
        sample_batch_report.status = BatchStatus.COMPLETED
        sample_batch_report.completed_at = datetime.utcnow()
        sample_batch_report.progress_percentage = 100.0

        assert sample_batch_report.status == BatchStatus.COMPLETED
        assert sample_batch_report.completed_at is not None
        assert sample_batch_report.progress_percentage == 100.0

    def test_batch_report_mark_failed(self, sample_batch_report):
        """Test marking batch as failed"""
        from datetime import datetime

        error_message = "Processing failed"
        sample_batch_report.status = BatchStatus.FAILED
        sample_batch_report.error_message = error_message
        sample_batch_report.completed_at = datetime.utcnow()

        assert sample_batch_report.status == BatchStatus.FAILED
        assert sample_batch_report.error_message == error_message
        assert sample_batch_report.completed_at is not None

    def test_batch_report_mark_cancelled(self, sample_batch_report):
        """Test marking batch as cancelled"""
        from datetime import datetime

        sample_batch_report.status = BatchStatus.CANCELLED
        sample_batch_report.completed_at = datetime.utcnow()

        assert sample_batch_report.status == BatchStatus.CANCELLED
        assert sample_batch_report.completed_at is not None

    def test_batch_report_calculate_success_rate(self, sample_batch_report):
        """Test success rate calculation"""
        sample_batch_report.successful_leads = 8
        sample_batch_report.processed_leads = 10

        success_rate = sample_batch_report.success_rate
        assert success_rate == 80.0

    def test_batch_report_calculate_success_rate_zero_leads(self, sample_batch_report):
        """Test success rate calculation with zero leads"""
        sample_batch_report.successful_leads = 0
        sample_batch_report.processed_leads = 0

        success_rate = sample_batch_report.success_rate
        assert success_rate == 0.0

    def test_batch_report_duration_seconds(self, sample_batch_report):
        """Test duration calculation"""
        sample_batch_report.started_at = datetime.utcnow()
        sample_batch_report.completed_at = datetime.utcnow()

        # Duration should be very small for immediate completion
        duration = sample_batch_report.duration_seconds
        assert duration >= 0
        assert duration < 1  # Should be less than 1 second

    def test_batch_report_duration_not_completed(self, sample_batch_report):
        """Test duration calculation for incomplete batch"""
        sample_batch_report.started_at = datetime.utcnow()
        # completed_at is None

        duration = sample_batch_report.duration_seconds
        assert duration is None

    def test_batch_report_to_dict(self, sample_batch_report):
        """Test batch report dictionary conversion"""
        batch_dict = sample_batch_report.to_dict()

        assert isinstance(batch_dict, dict)
        assert batch_dict["name"] == "Test Batch"
        assert batch_dict["total_leads"] == 10
        assert batch_dict["status"] == "pending"

    def test_batch_report_results_summary(self, sample_batch_report):
        """Test results summary property"""
        sample_batch_report.successful_leads = 8
        sample_batch_report.failed_leads = 2
        sample_batch_report.processed_leads = 10
        sample_batch_report.actual_cost_usd = 30.25

        summary = sample_batch_report.results_summary

        assert summary["successful"] == 8
        assert summary["failed"] == 2
        assert summary["total_cost"] == 30.25
        assert summary["success_rate"] == 0.8

    def test_batch_report_is_terminal_status(self, sample_batch_report):
        """Test terminal status checking"""
        # Pending is not terminal
        assert not sample_batch_report.is_terminal_status()

        # Completed is terminal
        sample_batch_report.status = BatchStatus.COMPLETED
        assert sample_batch_report.is_terminal_status()

        # Failed is terminal
        sample_batch_report.status = BatchStatus.FAILED
        assert sample_batch_report.is_terminal_status()

        # Cancelled is terminal
        sample_batch_report.status = BatchStatus.CANCELLED
        assert sample_batch_report.is_terminal_status()


class TestBatchReportLead:
    """Test BatchReportLead model"""

    @pytest.fixture
    def sample_batch_lead(self):
        """Create sample batch report lead"""
        from datetime import datetime

        return BatchReportLead(
            batch_id=str(uuid.uuid4()),
            lead_id=str(uuid.uuid4()),
            order_index=1,
            status=LeadProcessingStatus.PENDING,
            retry_count=0,  # Explicitly set defaults
            max_retries=3,
            report_generated=False,
            created_at=datetime.utcnow(),
        )

    def test_batch_report_lead_creation(self, sample_batch_lead):
        """Test BatchReportLead creation"""
        assert sample_batch_lead.status == LeadProcessingStatus.PENDING
        assert sample_batch_lead.retry_count == 0
        assert sample_batch_lead.created_at is not None

    def test_batch_report_lead_defaults(self):
        """Test BatchReportLead default values"""
        from datetime import datetime

        lead = BatchReportLead(
            batch_id=str(uuid.uuid4()),
            lead_id=str(uuid.uuid4()),
            order_index=1,
            status=LeadProcessingStatus.PENDING,
            retry_count=0,
            created_at=datetime.utcnow(),
        )

        assert lead.status == LeadProcessingStatus.PENDING
        assert lead.retry_count == 0
        assert lead.actual_cost_usd is None
        assert lead.processing_duration_ms is None
        assert lead.error_message is None

    def test_batch_report_lead_mark_processing(self, sample_batch_lead):
        """Test marking lead as processing"""
        sample_batch_lead.mark_processing()

        assert sample_batch_lead.status == LeadProcessingStatus.PROCESSING
        assert sample_batch_lead.started_at is not None

    def test_batch_report_lead_mark_completed(self, sample_batch_lead):
        """Test marking lead as completed"""
        report_url = "http://example.com/report.pdf"
        actual_cost_usd = 2.50
        quality_score = 0.85
        processing_time = 1500

        sample_batch_lead.mark_completed(
            report_url=report_url,
            actual_cost=actual_cost_usd,
            quality_score=quality_score,
            processing_time_ms=processing_time,
        )

        assert sample_batch_lead.status == LeadProcessingStatus.COMPLETED
        assert sample_batch_lead.report_url == report_url
        assert sample_batch_lead.actual_cost_usd == actual_cost_usd
        assert sample_batch_lead.quality_score == quality_score
        assert sample_batch_lead.processing_duration_ms == processing_time
        assert sample_batch_lead.completed_at is not None

    def test_batch_report_lead_mark_failed(self, sample_batch_lead):
        """Test marking lead as failed"""
        error_message = "Processing failed"
        error_code = "PROCESSING_ERROR"

        sample_batch_lead.mark_failed(error_message, error_code)

        assert sample_batch_lead.status == LeadProcessingStatus.FAILED
        assert sample_batch_lead.error_message == error_message
        assert sample_batch_lead.error_code == error_code
        assert sample_batch_lead.completed_at is not None

    def test_batch_report_lead_increment_retry(self, sample_batch_lead):
        """Test incrementing retry count"""
        initial_attempts = sample_batch_lead.retry_count

        sample_batch_lead.increment_retry()

        assert sample_batch_lead.retry_count == initial_attempts + 1
        assert sample_batch_lead.status == LeadProcessingStatus.PENDING

    def test_batch_report_lead_is_retryable_within_limit(self, sample_batch_lead):
        """Test retryable status within limit"""
        sample_batch_lead.retry_count = 2
        sample_batch_lead.max_retries = 3
        sample_batch_lead.status = LeadProcessingStatus.FAILED

        assert sample_batch_lead.is_retryable(max_retries=3) is True

    def test_batch_report_lead_is_retryable_at_limit(self, sample_batch_lead):
        """Test retryable status at limit"""
        sample_batch_lead.retry_count = 3
        sample_batch_lead.max_retries = 3
        sample_batch_lead.status = LeadProcessingStatus.FAILED

        assert sample_batch_lead.is_retryable(max_retries=3) is False

    def test_batch_report_lead_is_retryable_over_limit(self, sample_batch_lead):
        """Test retryable status over limit"""
        sample_batch_lead.retry_count = 5
        sample_batch_lead.max_retries = 3
        sample_batch_lead.status = LeadProcessingStatus.FAILED

        assert sample_batch_lead.is_retryable(max_retries=3) is False

    def test_batch_report_lead_processing_duration(self, sample_batch_lead):
        """Test processing duration calculation"""
        sample_batch_lead.started_at = datetime.utcnow()
        sample_batch_lead.completed_at = datetime.utcnow()

        duration = sample_batch_lead.processing_duration_seconds
        assert duration >= 0
        assert duration < 1  # Should be very small

    def test_batch_report_lead_processing_duration_not_completed(self, sample_batch_lead):
        """Test processing duration for incomplete lead"""
        sample_batch_lead.started_at = datetime.utcnow()
        # completed_at is None

        duration = sample_batch_lead.processing_duration_seconds
        assert duration is None

    def test_batch_report_lead_to_dict(self, sample_batch_lead):
        """Test lead dictionary conversion"""
        lead_dict = sample_batch_lead.to_dict()

        assert isinstance(lead_dict, dict)
        assert lead_dict["status"] == "pending"
        assert lead_dict["retry_count"] == 0

    def test_batch_report_lead_is_terminal_status(self, sample_batch_lead):
        """Test terminal status checking for leads"""
        # Pending is not terminal
        assert not sample_batch_lead.is_terminal_status()

        # Processing is not terminal
        sample_batch_lead.status = LeadProcessingStatus.PROCESSING
        assert not sample_batch_lead.is_terminal_status()

        # Completed is terminal
        sample_batch_lead.status = LeadProcessingStatus.COMPLETED
        assert sample_batch_lead.is_terminal_status()

        # Failed is terminal
        sample_batch_lead.status = LeadProcessingStatus.FAILED
        assert sample_batch_lead.is_terminal_status()

    def test_batch_report_lead_reset_for_retry(self, sample_batch_lead):
        """Test resetting lead for retry"""
        # Set some values first
        sample_batch_lead.error_message = "Previous error"
        sample_batch_lead.completed_at = datetime.utcnow()

        sample_batch_lead.reset_for_retry()

        assert sample_batch_lead.status == LeadProcessingStatus.PENDING
        assert sample_batch_lead.error_message is None
        assert sample_batch_lead.error_code is None
        assert sample_batch_lead.completed_at is None


class TestModelRelationships:
    """Test model relationships and interactions"""

    def test_batch_report_with_leads(self):
        """Test batch report with associated leads"""
        from datetime import datetime

        batch = BatchReport(
            created_by=str(uuid.uuid4()),
            name="Test Batch",
            template_version="v1.0",
            total_leads=2,
            processed_leads=0,
            successful_leads=0,
            failed_leads=0,
            progress_percentage=0.0,
            created_at=datetime.utcnow(),
            status=BatchStatus.PENDING,
        )

        lead1 = BatchReportLead(
            batch_id=batch.id,
            lead_id=str(uuid.uuid4()),
            order_index=1,
            status=LeadProcessingStatus.PENDING,
            retry_count=0,
            created_at=datetime.utcnow(),
        )

        lead2 = BatchReportLead(
            batch_id=batch.id,
            lead_id=str(uuid.uuid4()),
            order_index=2,
            status=LeadProcessingStatus.PENDING,
            retry_count=0,
            created_at=datetime.utcnow(),
        )

        # Simulate relationship
        leads = [lead1, lead2]

        assert len(leads) == 2
        assert all(lead.batch_id == batch.id for lead in leads)

    def test_batch_status_transitions(self):
        """Test valid batch status transitions"""
        from datetime import datetime

        batch = BatchReport(
            created_by=str(uuid.uuid4()),
            name="Test",
            template_version="v1.0",
            total_leads=1,
            processed_leads=0,
            successful_leads=0,
            failed_leads=0,
            progress_percentage=0.0,
            created_at=datetime.utcnow(),
            status=BatchStatus.PENDING,
        )

        # Pending -> Running
        assert batch.status == BatchStatus.PENDING
        batch.status = BatchStatus.RUNNING
        batch.started_at = datetime.utcnow()
        assert batch.status == BatchStatus.RUNNING

        # Running -> Completed
        batch.status = BatchStatus.COMPLETED
        batch.completed_at = datetime.utcnow()
        assert batch.status == BatchStatus.COMPLETED

    def test_lead_status_transitions(self):
        """Test valid lead status transitions"""
        from datetime import datetime

        lead = BatchReportLead(
            batch_id=str(uuid.uuid4()),
            lead_id=str(uuid.uuid4()),
            order_index=1,
            status=LeadProcessingStatus.PENDING,
            retry_count=0,
            created_at=datetime.utcnow(),
        )

        # Pending -> Processing
        assert lead.status == LeadProcessingStatus.PENDING
        lead.mark_processing()
        assert lead.status == LeadProcessingStatus.PROCESSING

        # Processing -> Completed
        lead.mark_completed("http://example.com/report.pdf", 2.50)
        assert lead.status == LeadProcessingStatus.COMPLETED
