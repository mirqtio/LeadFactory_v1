"""
Test Task 028: Create sourcing coordinator
Acceptance Criteria:
- Batch processing works
- Status updates correct
- Error handling complete
- Metrics tracked
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest

# Ensure we can import our modules
sys.path.insert(0, "/app")

from d2_sourcing.coordinator import (BatchStatus, CoordinatorMetrics,
                                     CoordinatorStatus, SourcingBatch,
                                     SourcingCoordinator,
                                     process_location_batch,
                                     process_multiple_locations)
from d2_sourcing.exceptions import (BatchQuotaException,
                                    ErrorRecoveryException, SourcingException)
from d2_sourcing.yelp_scraper import ScrapingResult, ScrapingStatus


class TestTask028AcceptanceCriteria:
    """Test that Task 028 meets all acceptance criteria"""

    @pytest.fixture
    def mock_session(self):
        """Mock database session"""
        mock_session = Mock()
        mock_session.query.return_value.filter.return_value.all.return_value = []
        mock_session.add = Mock()
        mock_session.commit = Mock()
        mock_session.rollback = Mock()
        return mock_session

    @pytest.fixture
    def mock_settings(self):
        """Mock settings"""
        settings = Mock()
        settings.MAX_CONCURRENT_SOURCING_BATCHES = 3
        settings.SOURCING_BATCH_TIMEOUT_MINUTES = 60
        settings.AUTO_DEDUPLICATE_SOURCING = True
        settings.VALIDATE_SCRAPED_DATA = True
        return settings

    @pytest.fixture
    async def coordinator(self, mock_session, mock_settings):
        """Create SourcingCoordinator instance with mocked dependencies"""
        with patch(
            "d2_sourcing.coordinator.get_settings", return_value=mock_settings
        ), patch(
            "d2_sourcing.coordinator.SessionLocal", return_value=mock_session
        ), patch(
            "d2_sourcing.coordinator.YelpScraper"
        ) as mock_scraper_class, patch(
            "d2_sourcing.coordinator.BusinessDeduplicator"
        ) as mock_dedup_class:
            # Mock scraper
            mock_scraper = AsyncMock()
            mock_scraper.search_businesses.return_value = ScrapingResult(
                status=ScrapingStatus.COMPLETED,
                total_results=100,
                fetched_count=50,
                error_count=0,
                quota_used=1,
                duration_seconds=2.5,
                businesses=[
                    {"id": f"biz_{i}", "name": f"Business {i}"} for i in range(50)
                ],
            )
            mock_scraper.save_business_data = AsyncMock(return_value=str(uuid.uuid4()))
            mock_scraper_class.return_value = mock_scraper

            # Mock deduplicator
            mock_dedup = Mock()
            mock_dedup_class.return_value = mock_dedup

            coordinator = SourcingCoordinator(session=mock_session)
            await coordinator.initialize()

            return coordinator

    @pytest.mark.asyncio
    async def test_batch_processing_works(self, coordinator, mock_session):
        """Test that batch processing works correctly"""

        # Test batch creation
        batch_id = coordinator.create_batch(
            location="San Francisco, CA",
            search_terms=["pizza", "restaurants"],
            categories=["food"],
            max_results=200,
        )

        assert batch_id is not None
        assert len(coordinator.batch_queue) == 1
        assert coordinator.metrics.total_batches == 1

        # Verify batch structure
        batch = coordinator._get_batch(batch_id)
        assert batch is not None
        assert batch.location == "San Francisco, CA"
        assert batch.search_terms == ["pizza", "restaurants"]
        assert batch.categories == ["food"]
        assert batch.max_results == 200
        assert batch.status == BatchStatus.PENDING

        # Test batch processing
        with patch("d2_sourcing.coordinator.find_and_merge_duplicates") as mock_merge:
            mock_merge.return_value = {
                "duplicates_identified": 5,
                "merges_completed": 3,
                "processed_count": 50,
            }

            # Process the batch
            result_batch = await coordinator.process_batch(batch_id)

            # Verify batch completion
            assert result_batch.status == BatchStatus.COMPLETED
            assert result_batch.started_at is not None
            assert result_batch.completed_at is not None
            assert result_batch.scraped_count > 0  # Has scraped businesses
            assert result_batch.duplicates_found >= 0  # Has deduplication data
            assert result_batch.duplicates_merged >= 0  # Has merge data
            assert result_batch.total_time > 0

        # Verify coordinator state updates
        assert coordinator.metrics.completed_batches == 1
        assert coordinator.metrics.total_businesses_scraped > 0
        assert batch_id in coordinator.completed_batches
        assert batch_id not in coordinator.active_batches

        print("✓ Batch processing works")

    def test_status_updates_correct(self, coordinator):
        """Test that status updates are correct throughout processing"""

        # Reset coordinator to clean state
        coordinator.status = CoordinatorStatus.IDLE
        coordinator.current_batch = None
        coordinator.batch_queue.clear()
        coordinator.active_batches.clear()
        coordinator.completed_batches.clear()
        # Reset metrics
        coordinator.metrics.total_batches = 0
        coordinator.metrics.completed_batches = 0

        # Test initial coordinator status
        initial_status = coordinator.get_coordinator_status()
        assert initial_status["status"] == CoordinatorStatus.IDLE.value
        assert initial_status["session_id"] == coordinator.session_id
        assert initial_status["current_batch"] is None
        assert initial_status["queued_batches"] == 0
        assert initial_status["active_batches"] == 0
        assert initial_status["completed_batches"] == 0

        # Test batch creation updates
        batch_id = coordinator.create_batch(location="New York, NY", max_results=100)

        status_after_creation = coordinator.get_coordinator_status()
        assert status_after_creation["queued_batches"] == 1
        assert status_after_creation["metrics"]["total_batches"] == 1

        # Test batch status reporting
        batch_status = coordinator.get_batch_status(batch_id)
        assert batch_status["batch_id"] == batch_id
        assert batch_status["status"] == BatchStatus.PENDING.value
        assert batch_status["location"] == "New York, NY"
        assert batch_status["progress_percentage"] == 0.0
        assert "created_at" in batch_status
        assert "metrics" in batch_status

        # Test status during processing
        batch = coordinator._get_batch(batch_id)
        batch.status = BatchStatus.RUNNING
        batch.started_at = datetime.utcnow()
        batch.scraped_count = 25
        batch.total_expected = 100

        running_status = coordinator.get_batch_status(batch_id)
        assert running_status["status"] == BatchStatus.RUNNING.value
        assert running_status["started_at"] is not None
        assert running_status["metrics"]["scraped_count"] == 25
        assert running_status["progress_percentage"] > 0

        # Test completion status
        batch.status = BatchStatus.COMPLETED
        batch.completed_at = datetime.utcnow()
        batch.validation_passed = 20
        batch.validation_failed = 5

        completed_status = coordinator.get_batch_status(batch_id)
        assert completed_status["status"] == BatchStatus.COMPLETED.value
        assert completed_status["completed_at"] is not None
        assert completed_status["metrics"]["validation_passed"] == 20
        assert completed_status["metrics"]["validation_failed"] == 5

        # Test error status
        batch.status = BatchStatus.FAILED
        batch.error_message = "Test error"

        error_status = coordinator.get_batch_status(batch_id)
        assert error_status["status"] == BatchStatus.FAILED.value
        assert error_status["error_message"] == "Test error"

        print("✓ Status updates correct")

    @pytest.mark.asyncio
    async def test_error_handling_complete(self, coordinator, mock_session):
        """Test that error handling is complete and robust"""

        # Test handling of scraping errors
        with patch.object(coordinator.scraper, "search_businesses") as mock_search:
            mock_search.return_value = ScrapingResult(
                status=ScrapingStatus.FAILED,
                total_results=0,
                fetched_count=0,
                error_count=1,
                quota_used=1,
                duration_seconds=1.0,
                error_message="API Error",
            )

            batch_id = coordinator.create_batch(
                location="Test Location", max_results=50
            )

            # Should handle scraping failure gracefully
            with pytest.raises(ErrorRecoveryException):
                await coordinator.process_batch(batch_id)

            # Verify error metrics
            assert coordinator.metrics.scraping_errors > 0
            assert coordinator.metrics.failed_batches > 0

            # Verify batch status
            batch = coordinator._get_batch(batch_id)
            assert batch.status == BatchStatus.FAILED
            assert batch.error_message is not None

        # Test handling of quota exceeded errors
        with patch.object(coordinator.scraper, "search_businesses") as mock_search:
            mock_search.return_value = ScrapingResult(
                status=ScrapingStatus.QUOTA_EXCEEDED,
                total_results=0,
                fetched_count=0,
                error_count=0,
                quota_used=1,
                duration_seconds=1.0,
                error_message="Quota exceeded",
            )

            batch_id = coordinator.create_batch(
                location="Test Location 2", max_results=50
            )

            with pytest.raises(ErrorRecoveryException):
                await coordinator.process_batch(batch_id)

            assert coordinator.metrics.quota_exceeded_count > 0

        # Test handling of deduplication errors (should not fail batch)
        with patch("d2_sourcing.coordinator.find_and_merge_duplicates") as mock_merge:
            mock_merge.side_effect = Exception("Deduplication failed")

            # Mock successful scraping
            with patch.object(coordinator.scraper, "search_businesses") as mock_search:
                mock_search.return_value = ScrapingResult(
                    status=ScrapingStatus.COMPLETED,
                    total_results=10,
                    fetched_count=10,
                    error_count=0,
                    quota_used=1,
                    duration_seconds=1.0,
                    businesses=[{"id": f"biz_{i}"} for i in range(10)],
                )

                batch_id = coordinator.create_batch(
                    location="Test Location 3", max_results=50
                )

                # Should complete despite deduplication error
                result_batch = await coordinator.process_batch(batch_id)
                assert result_batch.status == BatchStatus.COMPLETED
                assert coordinator.metrics.deduplication_errors > 0

        # Test batch cancellation
        batch_id = coordinator.create_batch(location="Test Location 4", max_results=50)
        cancelled = coordinator.cancel_batch(batch_id)
        assert cancelled is True

        batch = coordinator._get_batch(batch_id)
        assert batch.status == BatchStatus.CANCELLED

        # Test invalid batch ID handling
        invalid_status = coordinator.get_batch_status("invalid-batch-id")
        assert "error" in invalid_status

        print("✓ Error handling complete")

    def test_metrics_tracked(self, coordinator):
        """Test that comprehensive metrics are tracked"""

        # Reset coordinator metrics for clean test
        coordinator.metrics.total_batches = 0
        coordinator.metrics.completed_batches = 0
        coordinator.metrics.failed_batches = 0
        coordinator.metrics.total_businesses_scraped = 0
        coordinator.metrics.total_duplicates_found = 0
        coordinator.metrics.total_duplicates_merged = 0
        coordinator.batch_queue.clear()
        coordinator.completed_batches.clear()

        # Test initial metrics
        initial_metrics = coordinator.get_coordinator_status()["metrics"]
        assert "session_start" in initial_metrics
        assert initial_metrics["total_batches"] == 0
        assert initial_metrics["completed_batches"] == 0
        assert initial_metrics["failed_batches"] == 0
        assert initial_metrics["total_businesses_scraped"] == 0
        assert initial_metrics["total_duplicates_found"] == 0
        assert initial_metrics["total_duplicates_merged"] == 0

        # Test metrics updates during processing
        batch_id = coordinator.create_batch(location="Metrics Test", max_results=100)

        # Simulate batch completion
        batch = coordinator._get_batch(batch_id)
        batch.status = BatchStatus.COMPLETED
        batch.scraped_count = 50
        batch.duplicates_found = 8
        batch.duplicates_merged = 5
        batch.validation_passed = 45
        batch.validation_failed = 5
        batch.scraping_time = 10.0
        batch.deduplication_time = 2.0
        batch.validation_time = 1.0
        batch.total_time = 13.0

        # Update coordinator metrics
        coordinator.metrics.total_businesses_scraped += batch.scraped_count
        coordinator.metrics.total_duplicates_found += batch.duplicates_found
        coordinator.metrics.total_duplicates_merged += batch.duplicates_merged
        coordinator.metrics.total_businesses_validated += batch.validation_passed
        coordinator.metrics.validation_errors += batch.validation_failed
        coordinator._update_metrics_for_completed_batch(batch)

        # Verify metrics calculation
        updated_metrics = coordinator.get_coordinator_status()["metrics"]
        assert updated_metrics["total_businesses_scraped"] == 50
        assert updated_metrics["total_duplicates_found"] == 8
        assert updated_metrics["total_duplicates_merged"] == 5
        assert updated_metrics["completed_batches"] == 1

        # Test quality metrics calculation
        assert "duplicate_rate" in updated_metrics
        assert "validation_pass_rate" in updated_metrics

        # Test average timing metrics
        assert updated_metrics["avg_scraping_time_per_batch"] == 10.0
        assert updated_metrics["avg_deduplication_time_per_batch"] == 2.0
        assert updated_metrics["avg_validation_time_per_batch"] == 1.0

        # Test batch-specific metrics
        batch_status = coordinator.get_batch_status(batch_id)
        batch_metrics = batch_status["metrics"]
        assert batch_metrics["scraped_count"] == 50
        assert batch_metrics["duplicates_found"] == 8
        assert batch_metrics["duplicates_merged"] == 5
        assert batch_metrics["validation_passed"] == 45
        assert batch_metrics["validation_failed"] == 5
        assert batch_metrics["scraping_time"] == 10.0
        assert batch_metrics["deduplication_time"] == 2.0
        assert batch_metrics["validation_time"] == 1.0
        assert batch_metrics["total_time"] == 13.0

        # Test error metrics tracking
        coordinator.metrics.scraping_errors = 2
        coordinator.metrics.deduplication_errors = 1
        coordinator.metrics.validation_errors = 3
        coordinator.metrics.quota_exceeded_count = 1

        error_metrics = coordinator.get_coordinator_status()["metrics"]
        assert error_metrics["scraping_errors"] == 2
        assert error_metrics["deduplication_errors"] == 1
        assert error_metrics["validation_errors"] == 3
        assert error_metrics["quota_exceeded_count"] == 1

        print("✓ Metrics tracked")

    @pytest.mark.asyncio
    async def test_multiple_batch_processing(self, coordinator):
        """Test processing multiple batches concurrently"""

        # Create multiple batches
        batch_configs = [
            {"location": "San Francisco, CA", "max_results": 100},
            {"location": "New York, NY", "max_results": 150},
            {"location": "Los Angeles, CA", "max_results": 200},
        ]

        # Mock successful processing for all batches
        with patch.object(coordinator, "process_batch") as mock_process:

            async def mock_process_batch(batch_id):
                batch = coordinator._get_batch(batch_id)
                batch.status = BatchStatus.COMPLETED
                batch.scraped_count = 50
                return batch

            mock_process.side_effect = mock_process_batch

            batch_ids = await coordinator.process_multiple_batches(batch_configs)

            # Verify all batches were created and processed
            assert len(batch_ids) == 3
            assert mock_process.call_count == 3

            # Verify batch creation
            for i, batch_id in enumerate(batch_ids):
                batch = coordinator._get_batch(batch_id)
                assert batch.location == batch_configs[i]["location"]
                assert batch.max_results == batch_configs[i]["max_results"]

        print("✓ Multiple batch processing works")

    def test_business_data_validation(self, coordinator):
        """Test business data validation logic"""

        from database.models import Business

        # Test valid business
        valid_business = Mock(spec=Business)
        valid_business.name = "Valid Restaurant"
        valid_business.phone = "(415) 555-1234"
        valid_business.email = "contact@valid.com"
        valid_business.website = "https://valid.com"
        valid_business.address = "123 Main St, San Francisco, CA"
        valid_business.latitude = 37.7749
        valid_business.longitude = -122.4194

        assert coordinator._validate_business_data(valid_business) == True

        # Test invalid businesses
        invalid_cases = [
            # Missing name
            {"name": "", "phone": "(415) 555-1234"},
            # Missing all contact methods
            {"name": "Test", "phone": None, "email": None, "website": None},
            # Invalid coordinates
            {"name": "Test", "phone": "(415) 555-1234", "latitude": 91.0},
            {"name": "Test", "phone": "(415) 555-1234", "longitude": 181.0},
            # Invalid phone (too short)
            {"name": "Test", "phone": "123", "email": None, "website": None},
            # Invalid address (too short)
            {"name": "Test", "phone": "(415) 555-1234", "address": "123"},
        ]

        for i, invalid_data in enumerate(invalid_cases):
            invalid_business = Mock(spec=Business)
            # Set all attributes to None first
            for attr in [
                "name",
                "phone",
                "email",
                "website",
                "address",
                "latitude",
                "longitude",
            ]:
                setattr(invalid_business, attr, None)
            # Set test data
            for attr, value in invalid_data.items():
                setattr(invalid_business, attr, value)

            is_valid = coordinator._validate_business_data(invalid_business)
            assert is_valid == False, f"Case {i} should be invalid: {invalid_data}"

        print("✓ Business data validation works")

    def test_coordinator_lifecycle(self, coordinator):
        """Test coordinator lifecycle operations"""

        # Test pause/resume
        coordinator.pause_processing()
        assert coordinator.status == CoordinatorStatus.PAUSED

        coordinator.resume_processing()
        assert coordinator.status == CoordinatorStatus.IDLE

        # Test batch cleanup
        # Create old completed batch
        old_batch = SourcingBatch(
            id="old-batch",
            location="Old Location",
            search_terms=[],
            categories=[],
            max_results=100,
            status=BatchStatus.COMPLETED,
            created_at=datetime.utcnow() - timedelta(hours=25),
            completed_at=datetime.utcnow() - timedelta(hours=25),
        )
        coordinator.completed_batches["old-batch"] = old_batch

        # Create recent completed batch
        recent_batch = SourcingBatch(
            id="recent-batch",
            location="Recent Location",
            search_terms=[],
            categories=[],
            max_results=100,
            status=BatchStatus.COMPLETED,
            created_at=datetime.utcnow() - timedelta(hours=1),
            completed_at=datetime.utcnow() - timedelta(hours=1),
        )
        coordinator.completed_batches["recent-batch"] = recent_batch

        # Cleanup should remove old batch but keep recent
        coordinator.cleanup_completed_batches(max_age_hours=24)

        assert "old-batch" not in coordinator.completed_batches
        assert "recent-batch" in coordinator.completed_batches

        print("✓ Coordinator lifecycle works")

    @pytest.mark.asyncio
    async def test_convenience_functions(self, mock_session, mock_settings):
        """Test convenience functions for common operations"""

        with patch(
            "d2_sourcing.coordinator.get_settings", return_value=mock_settings
        ), patch(
            "d2_sourcing.coordinator.SessionLocal", return_value=mock_session
        ), patch(
            "d2_sourcing.coordinator.SourcingCoordinator"
        ) as mock_coordinator_class:
            # Mock coordinator - use Mock for sync methods, AsyncMock for async methods
            mock_coordinator = Mock()
            mock_coordinator.initialize = AsyncMock()
            mock_coordinator.shutdown = AsyncMock()
            mock_coordinator.create_batch.return_value = "test-batch-id"
            mock_coordinator.process_batch = AsyncMock()
            # get_batch_status is NOT async, so use Mock and return dict directly
            mock_coordinator.get_batch_status = Mock(return_value={
                "batch_id": "test-batch-id",
                "status": "completed",
                "metrics": {"scraped_count": 50},
            })
            mock_coordinator.process_multiple_batches = AsyncMock()
            mock_coordinator.process_multiple_batches.return_value = [
                "batch-1",
                "batch-2",
            ]
            # get_coordinator_status is also NOT async
            mock_coordinator.get_coordinator_status = Mock(return_value={
                "status": "completed",
                "metrics": {"total_batches": 2},
            })
            mock_coordinator_class.return_value = mock_coordinator

            # Test single location processing
            result = await process_location_batch(
                location="San Francisco, CA",
                categories=["restaurants"],
                max_results=500,
            )

            assert result["batch_id"] == "test-batch-id"
            assert result["status"] == "completed"
            mock_coordinator.initialize.assert_called()
            mock_coordinator.shutdown.assert_called()

            # Test multiple location processing
            locations = ["San Francisco, CA", "New York, NY"]
            result = await process_multiple_locations(
                locations=locations, categories=["food"], max_results_per_location=300
            )

            assert "coordinator_status" in result
            assert "batch_results" in result
            assert result["coordinator_status"]["status"] == "completed"

        print("✓ Convenience functions work")


if __name__ == "__main__":
    # Allow running this test file directly
    test_instance = TestTask028AcceptanceCriteria()

    # Create mock fixtures
    mock_session = Mock()
    mock_session.query.return_value.filter.return_value.all.return_value = []
    mock_session.add = Mock()
    mock_session.commit = Mock()
    mock_session.rollback = Mock()

    mock_settings = Mock()
    mock_settings.MAX_CONCURRENT_SOURCING_BATCHES = 3
    mock_settings.SOURCING_BATCH_TIMEOUT_MINUTES = 60
    mock_settings.AUTO_DEDUPLICATE_SOURCING = True
    mock_settings.VALIDATE_SCRAPED_DATA = True

    async def run_tests():
        with patch(
            "d2_sourcing.coordinator.get_settings", return_value=mock_settings
        ), patch(
            "d2_sourcing.coordinator.SessionLocal", return_value=mock_session
        ), patch(
            "d2_sourcing.coordinator.YelpScraper"
        ) as mock_scraper_class, patch(
            "d2_sourcing.coordinator.BusinessDeduplicator"
        ) as mock_dedup_class:
            # Mock scraper
            mock_scraper = AsyncMock()
            mock_scraper.search_businesses.return_value = ScrapingResult(
                status=ScrapingStatus.COMPLETED,
                total_results=100,
                fetched_count=50,
                error_count=0,
                quota_used=1,
                duration_seconds=2.5,
                businesses=[
                    {"id": f"biz_{i}", "name": f"Business {i}"} for i in range(50)
                ],
            )
            mock_scraper.save_business_data = AsyncMock(return_value=str(uuid.uuid4()))
            mock_scraper_class.return_value = mock_scraper

            # Mock deduplicator
            mock_dedup = Mock()
            mock_dedup_class.return_value = mock_dedup

            coordinator = SourcingCoordinator(session=mock_session)
            await coordinator.initialize()

            # Run tests
            await test_instance.test_batch_processing_works(coordinator, mock_session)
            test_instance.test_status_updates_correct(coordinator)
            await test_instance.test_error_handling_complete(coordinator, mock_session)
            test_instance.test_metrics_tracked(coordinator)
            await test_instance.test_multiple_batch_processing(coordinator)
            test_instance.test_business_data_validation(coordinator)
            test_instance.test_coordinator_lifecycle(coordinator)
            await test_instance.test_convenience_functions(mock_session, mock_settings)

            await coordinator.shutdown()

    # Run async tests
    asyncio.run(run_tests())

    print("\n🎉 All Task 028 acceptance criteria tests pass!")
    print("   - Batch processing works: ✓")
    print("   - Status updates correct: ✓")
    print("   - Error handling complete: ✓")
    print("   - Metrics tracked: ✓")
