"""
Test D4 Enrichment Coordinator Properties and Edge Cases

Focused tests to improve coordinator.py coverage by testing:
1. Property methods with edge cases (completion_percentage, success_rate)
2. Cache key generation
3. Data merging logic
4. Cleanup operations
5. Statistics and progress tracking
"""

from datetime import datetime, timedelta
from unittest.mock import Mock, patch

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


class TestEnrichmentProgressProperties:
    """Test EnrichmentProgress property methods for edge cases"""

    def test_completion_percentage_zero_total_businesses(self):
        """Test completion percentage when total_businesses is 0"""
        progress = EnrichmentProgress(request_id="test-001", total_businesses=0, processed_businesses=5)

        # Should return 0.0 to avoid division by zero
        assert progress.completion_percentage == 0.0

    def test_completion_percentage_normal_calculation(self):
        """Test completion percentage with normal values"""
        progress = EnrichmentProgress(request_id="test-002", total_businesses=100, processed_businesses=25)

        assert progress.completion_percentage == 25.0

    def test_success_rate_zero_processed_businesses(self):
        """Test success rate when processed_businesses is 0"""
        progress = EnrichmentProgress(
            request_id="test-003", total_businesses=10, processed_businesses=0, enriched_businesses=5
        )

        # Should return 0.0 to avoid division by zero
        assert progress.success_rate == 0.0

    def test_success_rate_normal_calculation(self):
        """Test success rate with normal values"""
        progress = EnrichmentProgress(
            request_id="test-004", total_businesses=50, processed_businesses=40, enriched_businesses=30
        )

        assert progress.success_rate == 75.0

    def test_success_rate_perfect_success(self):
        """Test success rate with 100% success"""
        progress = EnrichmentProgress(
            request_id="test-005", total_businesses=20, processed_businesses=20, enriched_businesses=20
        )

        assert progress.success_rate == 100.0


class TestCoordinatorCacheKeyGeneration:
    """Test cache key generation methods"""

    def test_generate_cache_key_with_timestamp(self):
        """Test cache key generation with explicit timestamp"""
        coordinator = EnrichmentCoordinator()

        timestamp = datetime(2023, 1, 1, 12, 0, 0)
        cache_key = coordinator.generate_cache_key(business_id="biz-123", provider="gbp", timestamp=timestamp)

        # Should include business_id, provider, and timestamp
        assert "biz-123" in cache_key
        assert "gbp" in cache_key
        assert isinstance(cache_key, str)
        assert len(cache_key) > 0

    def test_generate_cache_key_without_timestamp(self):
        """Test cache key generation without timestamp (uses current time)"""
        coordinator = EnrichmentCoordinator()

        cache_key = coordinator.generate_cache_key(business_id="biz-456", provider="hunter")

        # Should include business_id and provider
        assert "biz-456" in cache_key
        assert "hunter" in cache_key
        assert isinstance(cache_key, str)
        assert len(cache_key) > 0

    def test_generate_cache_key_consistency(self):
        """Test that same inputs generate same cache key"""
        coordinator = EnrichmentCoordinator()

        timestamp = datetime(2023, 1, 1, 12, 0, 0)

        key1 = coordinator.generate_cache_key("biz-789", "dataaxle", timestamp)
        key2 = coordinator.generate_cache_key("biz-789", "dataaxle", timestamp)

        assert key1 == key2


class TestCoordinatorDataMerging:
    """Test data merging logic"""

    def test_merge_enrichment_data_empty_existing(self):
        """Test merging when existing data is empty"""
        coordinator = EnrichmentCoordinator()

        existing_data = {}
        new_data = {"phone": "555-1234", "website": "example.com"}

        merged = coordinator.merge_enrichment_data(existing_data, new_data)

        assert merged == new_data

    def test_merge_enrichment_data_empty_new(self):
        """Test merging when new data is empty"""
        coordinator = EnrichmentCoordinator()

        existing_data = {"email": "test@example.com", "address": "123 Main St"}
        new_data = {}

        merged = coordinator.merge_enrichment_data(existing_data, new_data)

        assert merged == existing_data

    def test_merge_enrichment_data_overlapping_keys(self):
        """Test merging with overlapping keys (new data should take precedence)"""
        coordinator = EnrichmentCoordinator()

        existing_data = {"phone": "555-0000", "email": "old@example.com", "address": "123 Main St"}
        new_data = {"phone": "555-1234", "website": "example.com"}

        merged = coordinator.merge_enrichment_data(existing_data, new_data)

        # New data should overwrite existing data for same keys
        assert merged["phone"] == "555-1234"  # Updated
        assert merged["email"] == "old@example.com"  # Preserved
        assert merged["address"] == "123 Main St"  # Preserved
        assert merged["website"] == "example.com"  # Added

    def test_merge_enrichment_data_both_empty(self):
        """Test merging when both datasets are empty"""
        coordinator = EnrichmentCoordinator()

        merged = coordinator.merge_enrichment_data({}, {})

        assert merged == {}

    def test_merge_enrichment_data_nested_structures(self):
        """Test merging with nested data structures"""
        coordinator = EnrichmentCoordinator()

        existing_data = {"contact": {"phone": "555-0000"}, "location": {"city": "New York"}}
        new_data = {"contact": {"email": "new@example.com"}, "social": {"facebook": "fb.com/page"}}

        merged = coordinator.merge_enrichment_data(existing_data, new_data)

        # Should merge top-level keys
        assert "contact" in merged
        assert "location" in merged
        assert "social" in merged


class TestCoordinatorProgressAndStatistics:
    """Test progress tracking and statistics methods"""

    def test_get_progress_existing_request(self):
        """Test getting progress for existing request"""
        coordinator = EnrichmentCoordinator()

        # Add a request to track
        progress = EnrichmentProgress(request_id="active-001", total_businesses=50, processed_businesses=25)
        coordinator.active_requests["active-001"] = progress

        retrieved_progress = coordinator.get_progress("active-001")

        assert retrieved_progress is not None
        assert retrieved_progress.request_id == "active-001"
        assert retrieved_progress.total_businesses == 50

    def test_get_progress_nonexistent_request(self):
        """Test getting progress for non-existent request"""
        coordinator = EnrichmentCoordinator()

        progress = coordinator.get_progress("nonexistent-123")

        assert progress is None

    def test_get_all_active_progress(self):
        """Test getting all active progress"""
        coordinator = EnrichmentCoordinator()

        # Add multiple active requests
        progress1 = EnrichmentProgress(request_id="req-001", total_businesses=10)
        progress2 = EnrichmentProgress(request_id="req-002", total_businesses=20)

        coordinator.active_requests["req-001"] = progress1
        coordinator.active_requests["req-002"] = progress2

        all_progress = coordinator.get_all_active_progress()

        assert len(all_progress) == 2
        assert "req-001" in all_progress
        assert "req-002" in all_progress

    def test_get_statistics_empty_coordinator(self):
        """Test getting statistics from empty coordinator"""
        coordinator = EnrichmentCoordinator()

        stats = coordinator.get_statistics()

        assert isinstance(stats, dict)
        assert "active_requests" in stats
        assert "total_enrichers" in stats
        assert stats["active_requests"] == 0

    def test_get_statistics_with_data(self):
        """Test getting statistics with active requests and enrichers"""
        coordinator = EnrichmentCoordinator()

        # Add some active requests
        progress1 = EnrichmentProgress(request_id="stat-001", total_businesses=100)
        progress2 = EnrichmentProgress(request_id="stat-002", total_businesses=50)

        coordinator.active_requests["stat-001"] = progress1
        coordinator.active_requests["stat-002"] = progress2

        stats = coordinator.get_statistics()

        assert stats["active_requests"] == 2
        assert stats["total_enrichers"] >= 1  # At least GBP enricher


class TestCoordinatorEnricherManagement:
    """Test enricher addition and removal"""

    async def test_add_enricher_success(self):
        """Test successfully adding an enricher"""
        coordinator = EnrichmentCoordinator()

        # Create a mock enricher
        mock_enricher = Mock()

        await coordinator.add_enricher(EnrichmentSource.HUNTER_IO, mock_enricher)

        assert EnrichmentSource.HUNTER_IO in coordinator.enrichers
        assert coordinator.enrichers[EnrichmentSource.HUNTER_IO] == mock_enricher

    async def test_remove_enricher_existing(self):
        """Test removing an existing enricher"""
        coordinator = EnrichmentCoordinator()

        # Add an enricher first
        mock_enricher = Mock()
        await coordinator.add_enricher(EnrichmentSource.DATA_AXLE, mock_enricher)

        # Verify it was added
        assert EnrichmentSource.DATA_AXLE in coordinator.enrichers

        # Remove it
        await coordinator.remove_enricher(EnrichmentSource.DATA_AXLE)

        # Verify it was removed
        assert EnrichmentSource.DATA_AXLE not in coordinator.enrichers

    async def test_remove_enricher_nonexistent(self):
        """Test removing a non-existent enricher (should not raise error)"""
        coordinator = EnrichmentCoordinator()

        # Try to remove enricher that doesn't exist
        await coordinator.remove_enricher(EnrichmentSource.HUNTER_IO)

        # Should complete without error
        assert EnrichmentSource.HUNTER_IO not in coordinator.enrichers


class TestCoordinatorCleanup:
    """Test cleanup operations"""

    async def test_cleanup_old_requests_with_old_data(self):
        """Test cleanup removes old completed requests"""
        coordinator = EnrichmentCoordinator()

        # Add old request (older than default 24 hours)
        old_progress = EnrichmentProgress(request_id="old-req", total_businesses=10, processed_businesses=10)
        old_progress.started_at = datetime.utcnow() - timedelta(hours=25)
        coordinator.completed_requests = {"old-req": old_progress}

        # Add recent request
        recent_progress = EnrichmentProgress(request_id="recent-req", total_businesses=5, processed_businesses=5)
        recent_progress.started_at = datetime.utcnow() - timedelta(hours=1)
        coordinator.completed_requests["recent-req"] = recent_progress

        # Run cleanup
        await coordinator.cleanup_old_requests()

        # Old request should be removed, recent should remain
        assert "old-req" not in coordinator.completed_requests
        assert "recent-req" in coordinator.completed_requests

    async def test_cleanup_old_requests_custom_max_age(self):
        """Test cleanup with custom max age"""
        coordinator = EnrichmentCoordinator()

        # Add request that's 2 hours old
        progress = EnrichmentProgress(request_id="test-cleanup", total_businesses=1, processed_businesses=1)
        progress.started_at = datetime.utcnow() - timedelta(hours=2)
        coordinator.completed_requests = {"test-cleanup": progress}

        # Cleanup with 1 hour max age
        await coordinator.cleanup_old_requests(max_age_hours=1)

        # Should be removed since it's older than 1 hour
        assert "test-cleanup" not in coordinator.completed_requests

    async def test_cleanup_old_requests_no_started_at(self):
        """Test cleanup handles requests without started_at gracefully"""
        coordinator = EnrichmentCoordinator()

        # Add request without started_at timestamp
        progress = EnrichmentProgress(request_id="no-timestamp", total_businesses=1, processed_businesses=1)
        # started_at defaults to None
        coordinator.completed_requests = {"no-timestamp": progress}

        # Should not crash
        await coordinator.cleanup_old_requests()

        # Request should remain since we can't determine its age
        assert "no-timestamp" in coordinator.completed_requests


class TestCoordinatorCancelRequest:
    """Test request cancellation functionality"""

    def test_cancel_request_active_request(self):
        """Test cancelling an active request"""
        coordinator = EnrichmentCoordinator()

        # Add active request
        progress = EnrichmentProgress(request_id="cancel-001", total_businesses=100, processed_businesses=50)
        coordinator.active_requests["cancel-001"] = progress

        # Cancel the request
        result = coordinator.cancel_request("cancel-001")

        assert result is True
        assert "cancel-001" not in coordinator.active_requests

    def test_cancel_request_nonexistent_request(self):
        """Test cancelling non-existent request"""
        coordinator = EnrichmentCoordinator()

        result = coordinator.cancel_request("nonexistent-456")

        assert result is False

    def test_cancel_request_completed_request(self):
        """Test cancelling already completed request"""
        coordinator = EnrichmentCoordinator()

        # Add completed request
        progress = EnrichmentProgress(request_id="completed-001", total_businesses=10, processed_businesses=10)
        coordinator.completed_requests["completed-001"] = progress

        # Try to cancel completed request
        result = coordinator.cancel_request("completed-001")

        # Should return False since it's already completed
        assert result is False
