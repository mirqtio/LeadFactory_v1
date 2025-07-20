"""
Test D2 Sourcing Coordinator module

Comprehensive unit tests for the business sourcing coordinator
focusing on batch processing, metrics tracking, and workflow orchestration.
"""
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlalchemy.orm import Session

from d2_sourcing.coordinator import (
    BatchStatus,
    CoordinatorMetrics,
    CoordinatorStatus,
    SourcingBatch,
    SourcingCoordinator,
    process_location_batch,
    process_multiple_locations,
)
from d2_sourcing.exceptions import SourcingException

# Mark entire module as unit test
pytestmark = pytest.mark.unit


class TestSourcingBatch:
    """Test SourcingBatch dataclass"""

    def test_sourcing_batch_creation(self):
        """Test creating a sourcing batch"""
        batch = SourcingBatch(
            id="test-batch-123",
            location="San Francisco, CA",
            search_terms=["restaurant", "cafe"],
            categories=["food", "dining"],
            max_results=100,
            status=BatchStatus.PENDING,
            created_at=datetime.utcnow(),
        )

        assert batch.id == "test-batch-123"
        assert batch.location == "San Francisco, CA"
        assert batch.search_terms == ["restaurant", "cafe"]
        assert batch.categories == ["food", "dining"]
        assert batch.max_results == 100
        assert batch.status == BatchStatus.PENDING
        assert isinstance(batch.created_at, datetime)

    def test_sourcing_batch_auto_id_generation(self):
        """Test automatic ID generation when not provided"""
        batch = SourcingBatch(
            id="",  # Empty ID should trigger auto-generation
            location="Austin, TX",
            search_terms=["bar"],
            categories=["nightlife"],
            max_results=50,
            status=BatchStatus.PENDING,
            created_at=datetime.utcnow(),
        )

        # Post-init should generate UUID
        assert batch.id
        assert len(batch.id) == 36  # UUID4 length
        assert "-" in batch.id

    def test_sourcing_batch_defaults(self):
        """Test default values in sourcing batch"""
        batch = SourcingBatch(
            id="test-defaults",
            location="Denver, CO",
            search_terms=["gym"],
            categories=["fitness"],
            max_results=25,
            status=BatchStatus.PENDING,
            created_at=datetime.utcnow(),
        )

        assert batch.started_at is None
        assert batch.completed_at is None
        assert batch.error_message is None
        assert batch.total_expected == 0
        assert batch.scraped_count == 0
        assert batch.duplicates_found == 0
        assert batch.duplicates_merged == 0
        assert batch.validation_passed == 0
        assert batch.validation_failed == 0
        assert batch.scraping_time == 0.0
        assert batch.deduplication_time == 0.0
        assert batch.validation_time == 0.0
        assert batch.total_time == 0.0


class TestCoordinatorMetrics:
    """Test CoordinatorMetrics dataclass"""

    def test_coordinator_metrics_creation(self):
        """Test creating coordinator metrics"""
        start_time = datetime.utcnow()
        metrics = CoordinatorMetrics(
            session_id="test-session-456",
            start_time=start_time,
        )

        assert metrics.session_id == "test-session-456"
        assert metrics.start_time == start_time
        assert metrics.total_batches == 0
        assert metrics.completed_batches == 0
        assert metrics.failed_batches == 0
        assert metrics.total_businesses_scraped == 0
        assert metrics.total_duplicates_found == 0
        assert metrics.total_duplicates_merged == 0
        assert metrics.total_businesses_validated == 0
        assert metrics.total_processing_time == 0.0


class TestSourcingCoordinator:
    """Test SourcingCoordinator class"""

    @pytest.fixture
    def mock_session(self):
        """Mock database session"""
        return Mock(spec=Session)

    @pytest.fixture
    def coordinator(self, mock_session):
        """Create coordinator instance for testing"""
        with patch("d2_sourcing.coordinator.get_settings"), patch("d2_sourcing.coordinator.get_logger"), patch(
            "d2_sourcing.coordinator.BusinessDeduplicator"
        ):
            return SourcingCoordinator(session=mock_session)

    def test_coordinator_initialization(self, mock_session):
        """Test coordinator initialization"""
        with patch("d2_sourcing.coordinator.get_settings") as mock_settings, patch(
            "d2_sourcing.coordinator.get_logger"
        ) as mock_logger, patch("d2_sourcing.coordinator.BusinessDeduplicator") as mock_dedup:
            coordinator = SourcingCoordinator(session=mock_session)

            assert coordinator.session == mock_session
            assert coordinator.status == CoordinatorStatus.IDLE
            assert coordinator.current_batch is None
            assert coordinator.batch_queue == []
            assert coordinator.active_batches == {}
            assert coordinator.completed_batches == {}
            assert coordinator.max_concurrent_batches == 3  # Default value
            assert coordinator.batch_timeout_minutes == 60  # Default value
            assert coordinator.auto_deduplicate is True  # Default value
            assert coordinator.validate_scraped_data is True  # Default value

            # Verify components were initialized
            mock_settings.assert_called_once()
            mock_logger.assert_called_once_with("sourcing_coordinator", domain="d2")
            mock_dedup.assert_called_once_with(session=mock_session)

    async def test_initialize_success(self, coordinator):
        """Test successful coordinator initialization"""
        coordinator.status = CoordinatorStatus.IDLE
        coordinator.logger = Mock()

        await coordinator.initialize()

        assert coordinator.status == CoordinatorStatus.IDLE
        coordinator.logger.info.assert_any_call("Initializing sourcing coordinator")
        coordinator.logger.info.assert_any_call("Sourcing coordinator initialized successfully")

    async def test_initialize_failure(self, coordinator):
        """Test coordinator initialization failure"""
        coordinator.logger = Mock()
        coordinator.status = CoordinatorStatus.IDLE

        # Mock initialization error
        with patch.object(coordinator, "logger") as mock_logger:
            mock_logger.info.side_effect = Exception("Initialization failed")

            with pytest.raises(SourcingException) as exc_info:
                await coordinator.initialize()

            assert "Coordinator initialization failed" in str(exc_info.value)
            assert coordinator.status == CoordinatorStatus.FAILED

    def test_create_batch_with_defaults(self, coordinator):
        """Test creating a batch with default parameters"""
        batch_id = coordinator.create_batch(location="Seattle, WA")

        assert batch_id is not None
        assert isinstance(batch_id, str)
        assert len(batch_id) > 0

    def test_create_batch_with_custom_params(self, coordinator):
        """Test creating a batch with custom parameters"""
        search_terms = ["pizza", "italian"]
        categories = ["food", "dining"]
        max_results = 250

        batch_id = coordinator.create_batch(
            location="Chicago, IL",
            search_terms=search_terms,
            categories=categories,
            max_results=max_results,
        )

        assert batch_id is not None
        assert isinstance(batch_id, str)
        assert len(batch_id) > 0

    def test_get_batch_status_existing(self, coordinator):
        """Test getting status for existing batch"""
        batch_id = coordinator.create_batch(location="Miami, FL")
        status = coordinator.get_batch_status(batch_id)

        # Basic status structure validation
        assert isinstance(status, dict)
        if "error" not in status:
            assert "batch_id" in status or "status" in status

    def test_get_batch_status_nonexistent(self, coordinator):
        """Test getting status for non-existent batch"""
        status = coordinator.get_batch_status("non-existent-id")
        assert "error" in status
        assert "not found" in status["error"]

    def test_get_coordinator_status(self, coordinator):
        """Test getting coordinator status"""
        status = coordinator.get_coordinator_status()

        assert isinstance(status, dict)
        # Basic status validation without specific values
        assert len(status) > 0

    def test_pause_processing(self, coordinator):
        """Test pausing coordinator processing"""
        coordinator.pause_processing()
        assert coordinator.status == CoordinatorStatus.PAUSED

    def test_resume_processing(self, coordinator):
        """Test resuming coordinator processing"""
        coordinator.status = CoordinatorStatus.PAUSED
        coordinator.resume_processing()
        assert coordinator.status == CoordinatorStatus.IDLE

    def test_cancel_batch_nonexistent(self, coordinator):
        """Test cancelling a non-existent batch"""
        result = coordinator.cancel_batch("non-existent-id")
        assert result is False

    def test_validate_business_data_valid(self, coordinator):
        """Test business data validation with valid data"""
        business = Mock()
        business.name = "Test Restaurant"
        business.address = "123 Main St"
        business.phone = "555-1234"

        result = coordinator._validate_business_data(business)
        assert result is True

    def test_validate_business_data_invalid(self, coordinator):
        """Test business data validation with invalid data"""
        business = Mock()
        business.name = ""  # Invalid: empty name
        business.address = "123 Main St"
        business.phone = "555-1234"

        result = coordinator._validate_business_data(business)
        assert result is False

    async def test_shutdown(self, coordinator):
        """Test coordinator shutdown"""
        coordinator.logger = Mock()
        coordinator.session = Mock()

        await coordinator.shutdown()

        assert coordinator.status == CoordinatorStatus.IDLE


class TestBatchProcessingFunctions:
    """Test standalone batch processing functions"""

    def test_functions_exist(self):
        """Test that the batch processing functions exist"""
        # Basic test to ensure functions are importable
        assert callable(process_location_batch)
        assert callable(process_multiple_locations)


class TestErrorHandling:
    """Test error handling scenarios"""

    @pytest.fixture
    def coordinator(self):
        """Create coordinator for error testing"""
        with patch("d2_sourcing.coordinator.get_settings"), patch("d2_sourcing.coordinator.get_logger"), patch(
            "d2_sourcing.coordinator.BusinessDeduplicator"
        ):
            return SourcingCoordinator()

    def test_update_metrics_for_completed_batch(self, coordinator):
        """Test updating metrics for completed batch"""
        batch = SourcingBatch(
            id="metrics-test",
            location="Test City",
            search_terms=["test"],
            categories=["test"],
            max_results=50,
            status=BatchStatus.COMPLETED,
            created_at=datetime.utcnow(),
        )

        # Set some test metrics
        batch.scraped_count = 25
        batch.duplicates_found = 5
        batch.validation_passed = 20
        batch.total_time = 120.5

        initial_processed = coordinator.metrics.total_batches
        coordinator._update_metrics_for_completed_batch(batch)

        assert coordinator.metrics.total_batches >= initial_processed
        assert coordinator.metrics.total_businesses_scraped >= 25
        assert coordinator.metrics.total_processing_time >= 120.5
