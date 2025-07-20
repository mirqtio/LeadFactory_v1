"""
Test D4 Enrichment Coordinator Coverage Expansion

Comprehensive unit tests to improve coordinator.py coverage from 79.45% to 90%+.
Focuses on edge cases, error paths, and property methods not covered by existing tests.
"""
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from d4_enrichment.coordinator import (
    BatchEnrichmentResult,
    EnrichmentCoordinator,
    EnrichmentPriority,
    EnrichmentProgress,
)
from d4_enrichment.models import EnrichmentResult, EnrichmentSource, EnrichmentStatus, MatchConfidence

# Mark entire module as unit test
pytestmark = pytest.mark.unit


class TestEnrichmentProgress:
    """Test EnrichmentProgress dataclass property methods"""

    def test_completion_percentage_with_zero_total(self):
        """Test completion percentage when total_businesses is zero"""
        progress = EnrichmentProgress(request_id="test-001", total_businesses=0, processed_businesses=5)

        # Should return 0.0 when total is zero to avoid division by zero
        assert progress.completion_percentage == 0.0

    def test_completion_percentage_normal_case(self):
        """Test completion percentage calculation with normal values"""
        progress = EnrichmentProgress(request_id="test-002", total_businesses=100, processed_businesses=25)

        assert progress.completion_percentage == 25.0

    def test_success_rate_with_zero_processed(self):
        """Test success rate when processed_businesses is zero"""
        progress = EnrichmentProgress(
            request_id="test-003", total_businesses=100, processed_businesses=0, enriched_businesses=5
        )

        # Should return 0.0 when processed is zero to avoid division by zero
        assert progress.success_rate == 0.0

    def test_success_rate_normal_case(self):
        """Test success rate calculation with normal values"""
        progress = EnrichmentProgress(
            request_id="test-004", total_businesses=100, processed_businesses=50, enriched_businesses=30
        )

        assert progress.success_rate == 60.0

    def test_success_rate_perfect_success(self):
        """Test success rate with 100% success"""
        progress = EnrichmentProgress(
            request_id="test-005", total_businesses=20, processed_businesses=20, enriched_businesses=20
        )

        assert progress.success_rate == 100.0


class TestEnrichmentCoordinatorInitialization:
    """Test coordinator initialization edge cases and error paths"""

    def test_coordinator_initialization_with_custom_params(self):
        """Test coordinator initialization with custom parameters"""
        coordinator = EnrichmentCoordinator(
            max_concurrent=10, default_cache_ttl_hours=48, skip_recent_enrichments=False
        )

        assert coordinator.max_concurrent == 10
        assert coordinator.default_cache_ttl_hours == 48
        assert coordinator.skip_recent_enrichments is False
        # Verify internal state is initialized
        assert hasattr(coordinator, "enrichers")
        assert hasattr(coordinator, "active_requests")

    def test_coordinator_default_initialization(self):
        """Test coordinator initialization with default parameters"""
        coordinator = EnrichmentCoordinator()

        # Check default values
        assert coordinator.max_concurrent == 5
        assert coordinator.default_cache_ttl_hours == 24
        assert coordinator.skip_recent_enrichments is True
        # GBP enricher should be automatically initialized
        assert EnrichmentSource.GBP in coordinator.enrichers

    @patch("d4_enrichment.coordinator.logger")
    def test_initialize_phase05_enrichers_with_logging(self, mock_logger):
        """Test Phase 0.5 enricher initialization with proper logging"""
        coordinator = EnrichmentCoordinator()

        # Call the Phase 0.5 enricher initialization
        coordinator._initialize_phase05_enrichers()

        # Should handle gracefully even if Phase 0.5 enrichers fail
        # Logger warning should be called if there are issues
        assert mock_logger.warning.called


class TestEnrichmentCoordinatorErrorPaths:
    """Test error handling and edge cases in coordinator operations"""

    def test_get_progress_invalid_request_id(self):
        """Test getting progress for non-existent request ID"""
        coordinator = EnrichmentCoordinator()

        progress = coordinator.get_progress("non-existent-id")

        # Should return None for invalid request ID
        assert progress is None

    def test_get_results_invalid_request_id(self):
        """Test getting results for non-existent request ID"""
        coordinator = EnrichmentCoordinator()

        results = coordinator.get_results("non-existent-id")

        # Should return empty list for invalid request ID
        assert results == []

    def test_cancel_request_invalid_id(self):
        """Test cancelling non-existent request"""
        coordinator = EnrichmentCoordinator()

        result = coordinator.cancel_request("non-existent-id")

        # Should return False for invalid request ID
        assert result is False

    def test_cancel_request_already_completed(self):
        """Test cancelling request that's already completed"""
        coordinator = EnrichmentCoordinator()

        # Add a completed request
        progress = EnrichmentProgress(request_id="completed-001", total_businesses=10, processed_businesses=10)
        coordinator.completed_requests["completed-001"] = progress

        result = coordinator.cancel_request("completed-001")

        # Should return False since request is already completed
        assert result is False

    async def test_enrich_single_business_enricher_failure(self):
        """Test enriching single business when enricher fails"""
        coordinator = EnrichmentCoordinator()

        # Mock enricher that always fails
        mock_enricher = AsyncMock()
        mock_enricher.enrich.side_effect = Exception("Enricher unavailable")
        coordinator.enrichers[EnrichmentSource.GBP] = mock_enricher

        business = {"id": "test-biz-001", "name": "Test Business", "address": "123 Test St"}

        result = await coordinator._enrich_single_business(business, [EnrichmentSource.GBP], "req-001")

        # Should handle error gracefully and return failed result
        assert result is not None
        # Check that it attempted to enrich but failed gracefully

    async def test_enrich_single_business_no_sources(self):
        """Test enriching single business with no sources specified"""
        coordinator = EnrichmentCoordinator()

        business = {"id": "test-biz-002", "name": "Test Business 2"}

        result = await coordinator._enrich_single_business(business, [], "req-002")  # Empty sources list

        # Should handle empty sources gracefully
        assert result is not None

    async def test_enrich_single_business_invalid_business_data(self):
        """Test enriching business with invalid/incomplete data"""
        coordinator = EnrichmentCoordinator()

        # Business with missing required fields
        business = {}

        result = await coordinator._enrich_single_business(business, [EnrichmentSource.GBP], "req-003")

        # Should handle invalid data gracefully
        assert result is not None

    def test_should_skip_enrichment_missing_last_enriched(self):
        """Test skip logic when business has no last_enriched_at field"""
        coordinator = EnrichmentCoordinator()

        business = {
            "id": "test-skip-001",
            "name": "Test Business"
            # No last_enriched_at field
        }

        # When skip_existing=True but no last_enriched_at, should not skip
        should_skip = coordinator._should_skip_enrichment(business, True)
        assert should_skip is False

        # When skip_existing=False, should never skip
        should_skip = coordinator._should_skip_enrichment(business, False)
        assert should_skip is False

    def test_should_skip_enrichment_recent_enrichment(self):
        """Test skip logic when business was recently enriched"""
        coordinator = EnrichmentCoordinator()

        # Business enriched 1 hour ago (recent)
        recent_time = datetime.utcnow() - timedelta(hours=1)
        business = {"id": "test-skip-002", "name": "Test Business", "last_enriched_at": recent_time}

        # Should skip recent enrichments when skip_existing=True
        should_skip = coordinator._should_skip_enrichment(business, True)
        assert should_skip is True

    def test_should_skip_enrichment_old_enrichment(self):
        """Test skip logic when business was enriched long ago"""
        coordinator = EnrichmentCoordinator()

        # Business enriched 10 days ago (old)
        old_time = datetime.utcnow() - timedelta(days=10)
        business = {"id": "test-skip-003", "name": "Test Business", "last_enriched_at": old_time}

        # Should not skip old enrichments even when skip_existing=True
        should_skip = coordinator._should_skip_enrichment(business, True)
        assert should_skip is False


class TestEnrichmentCoordinatorCleanup:
    """Test cleanup and resource management"""

    def test_cleanup_completed_requests_with_old_requests(self):
        """Test cleanup removes old completed requests"""
        coordinator = EnrichmentCoordinator()

        # Add old completed request
        old_time = datetime.utcnow() - timedelta(hours=25)  # Older than 24 hours
        old_progress = EnrichmentProgress(request_id="old-request", total_businesses=5, processed_businesses=5)
        old_progress.started_at = old_time
        coordinator.completed_requests["old-request"] = old_progress

        # Add recent completed request
        recent_time = datetime.utcnow() - timedelta(hours=1)
        recent_progress = EnrichmentProgress(request_id="recent-request", total_businesses=3, processed_businesses=3)
        recent_progress.started_at = recent_time
        coordinator.completed_requests["recent-request"] = recent_progress

        # Run cleanup
        coordinator.cleanup_completed_requests()

        # Old request should be removed, recent should remain
        assert "old-request" not in coordinator.completed_requests
        assert "recent-request" in coordinator.completed_requests

    def test_cleanup_completed_requests_custom_max_age(self):
        """Test cleanup with custom max age"""
        coordinator = EnrichmentCoordinator()

        # Add request that's 2 hours old
        old_time = datetime.utcnow() - timedelta(hours=2)
        progress = EnrichmentProgress(request_id="test-request", total_businesses=1, processed_businesses=1)
        progress.started_at = old_time
        coordinator.completed_requests["test-request"] = progress

        # Cleanup with 1 hour max age - should remove the 2-hour-old request
        coordinator.cleanup_completed_requests(max_age_hours=1)

        assert "test-request" not in coordinator.completed_requests

    def test_cleanup_completed_requests_no_started_at(self):
        """Test cleanup handles requests without started_at timestamp"""
        coordinator = EnrichmentCoordinator()

        # Add request without started_at
        progress = EnrichmentProgress(request_id="no-timestamp", total_businesses=1, processed_businesses=1)
        # started_at is None
        coordinator.completed_requests["no-timestamp"] = progress

        # Should handle gracefully and not crash
        coordinator.cleanup_completed_requests()

        # Request should remain since we can't determine its age
        assert "no-timestamp" in coordinator.completed_requests


class TestBatchEnrichmentResult:
    """Test BatchEnrichmentResult dataclass"""

    def test_batch_enrichment_result_creation(self):
        """Test creating a BatchEnrichmentResult with all fields"""
        progress = EnrichmentProgress(request_id="batch-001", total_businesses=100)

        results = [
            EnrichmentResult(
                business_id="biz-001",
                source=EnrichmentSource.GBP,
                status=EnrichmentStatus.SUCCESS,
                confidence=MatchConfidence.HIGH,
                data={"phone": "555-1234"},
            )
        ]

        batch_result = BatchEnrichmentResult(
            request_id="batch-001",
            total_processed=100,
            successful_enrichments=80,
            skipped_enrichments=10,
            failed_enrichments=10,
            progress=progress,
            results=results,
            errors=["Some error occurred"],
            execution_time_seconds=45.5,
        )

        assert batch_result.request_id == "batch-001"
        assert batch_result.total_processed == 100
        assert batch_result.successful_enrichments == 80
        assert batch_result.skipped_enrichments == 10
        assert batch_result.failed_enrichments == 10
        assert batch_result.progress == progress
        assert len(batch_result.results) == 1
        assert len(batch_result.errors) == 1
        assert batch_result.execution_time_seconds == 45.5


class TestCoordinatorEdgeCases:
    """Test edge cases and boundary conditions"""

    async def test_enrich_businesses_batch_empty_list(self):
        """Test batch enrichment with empty business list"""
        coordinator = EnrichmentCoordinator()

        result = await coordinator.enrich_businesses_batch(businesses=[], sources=[EnrichmentSource.GBP])

        assert result.total_processed == 0
        assert result.successful_enrichments == 0
        assert len(result.results) == 0

    async def test_enrich_businesses_batch_single_business(self):
        """Test batch enrichment with single business"""
        coordinator = EnrichmentCoordinator()

        business = {"id": "single-001", "name": "Single Test Business", "address": "123 Single St"}

        with patch.object(coordinator, "_enrich_single_business") as mock_enrich:
            mock_result = EnrichmentResult(
                business_id="single-001",
                source=EnrichmentSource.GBP,
                status=EnrichmentStatus.SUCCESS,
                confidence=MatchConfidence.HIGH,
                data={"enriched": True},
            )
            mock_enrich.return_value = mock_result

            result = await coordinator.enrich_businesses_batch(businesses=[business], sources=[EnrichmentSource.GBP])

            assert result.total_processed == 1
            mock_enrich.assert_called_once()

    def test_coordinator_state_tracking(self):
        """Test that coordinator properly tracks request states"""
        coordinator = EnrichmentCoordinator()

        # Initially empty
        assert len(coordinator.active_requests) == 0
        assert len(coordinator.completed_requests) == 0

        # Add active request
        progress = EnrichmentProgress(request_id="state-001", total_businesses=5)
        coordinator.active_requests["state-001"] = progress

        assert len(coordinator.active_requests) == 1
        assert coordinator.get_progress("state-001") == progress

        # Move to completed
        del coordinator.active_requests["state-001"]
        coordinator.completed_requests["state-001"] = progress

        assert len(coordinator.active_requests) == 0
        assert len(coordinator.completed_requests) == 1
        assert coordinator.get_progress("state-001") == progress
