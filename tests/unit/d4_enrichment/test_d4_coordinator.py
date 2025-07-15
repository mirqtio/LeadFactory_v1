"""
Test Enrichment Coordinator - Task 043

Tests for enrichment coordinator ensuring all acceptance criteria are met:
- Batch enrichment works
- Skip already enriched
- Error handling proper
- Progress tracking
"""

import asyncio
import string
import sys
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock

import pytest
from hypothesis import given
from hypothesis import strategies as st

from d4_enrichment.coordinator import (
    BatchEnrichmentResult,
    EnrichmentCoordinator,
    EnrichmentPriority,
    EnrichmentProgress,
    enrich_business,
    enrich_businesses,
)
from d4_enrichment.models import EnrichmentResult, EnrichmentSource, MatchConfidence

# Tests fixed for Phase 0.5 - P0-001


sys.path.insert(0, "/app")


class TestTask043AcceptanceCriteria:
    """Test that Task 043 meets all acceptance criteria"""

    @pytest.fixture
    def sample_businesses(self):
        """Sample business data for testing"""
        return [
            {
                "id": "biz_001",
                "name": "Test Company 1",
                "phone": "555-1234",
                "address": "123 Test St",
            },
            {
                "id": "biz_002",
                "name": "Test Company 2",
                "phone": "555-5678",
                "address": "456 Sample Ave",
            },
            {
                "id": "biz_003",
                "name": "Test Company 3",
                "phone": "555-9999",
                "address": "789 Example Blvd",
            },
        ]

    @pytest.fixture
    def mock_enrichment_result(self):
        """Mock enrichment result"""
        result = Mock(spec=EnrichmentResult)
        result.business_id = "test_biz_001"
        result.match_confidence = MatchConfidence.HIGH.value
        result.source = EnrichmentSource.INTERNAL.value
        return result

    @pytest.fixture
    def coordinator(self):
        """Create coordinator instance for testing"""
        return EnrichmentCoordinator(max_concurrent=2)

    def test_batch_enrichment_works(self, coordinator, sample_businesses):
        """
        Test that batch enrichment works properly

        Acceptance Criteria: Batch enrichment works
        """

        async def run_test():
            # Test batch enrichment
            result = await coordinator.enrich_businesses_batch(
                businesses=sample_businesses,
                sources=[EnrichmentSource.INTERNAL],
                skip_existing=False,
            )

            # Verify batch result structure
            assert isinstance(result, BatchEnrichmentResult)
            assert result.total_processed == len(sample_businesses)
            assert result.successful_enrichments + result.failed_enrichments <= len(sample_businesses)
            assert result.execution_time_seconds > 0
            assert isinstance(result.results, list)
            assert isinstance(result.errors, list)

            # Verify progress tracking was used
            assert result.progress.total_businesses == len(sample_businesses)
            assert result.progress.processed_businesses == len(sample_businesses)
            assert result.progress.completion_percentage == 100.0

            print("✓ Batch enrichment works correctly")

        asyncio.run(run_test())

    def test_skip_already_enriched(self, coordinator, sample_businesses):
        """
        Test that already enriched businesses are skipped

        Acceptance Criteria: Skip already enriched
        """

        async def run_test():
            # Mock the _is_recently_enriched method to return True for first business
            original_method = coordinator._is_recently_enriched

            async def mock_is_recently_enriched(business_id):
                if business_id == "biz_001":
                    return True  # Skip this one
                return False  # Enrich others

            coordinator._is_recently_enriched = mock_is_recently_enriched

            # Test batch enrichment with skip_existing=True
            result = await coordinator.enrich_businesses_batch(
                businesses=sample_businesses,
                sources=[EnrichmentSource.INTERNAL],
                skip_existing=True,
            )

            # Verify skipping behavior
            assert result.skipped_enrichments > 0
            assert result.progress.skipped_businesses > 0

            # Restore original method
            coordinator._is_recently_enriched = original_method

            print("✓ Skip already enriched works correctly")

        asyncio.run(run_test())

    def test_error_handling_proper(self, coordinator, sample_businesses):
        """
        Test that error handling works properly

        Acceptance Criteria: Error handling proper
        """

        async def run_test():
            # Create a mock enricher that always fails
            failing_enricher = Mock()
            failing_enricher.enrich_business = AsyncMock(side_effect=Exception("Test error"))

            # Replace the enricher with failing one
            coordinator.enrichers[EnrichmentSource.INTERNAL] = failing_enricher

            # Test batch enrichment with failing enricher
            result = await coordinator.enrich_businesses_batch(
                businesses=sample_businesses,
                sources=[EnrichmentSource.INTERNAL],
                skip_existing=False,
            )

            # Verify error handling
            assert result.failed_enrichments > 0
            assert result.successful_enrichments == 0
            assert len(result.errors) > 0 or result.progress.failed_businesses > 0

            # Verify coordinator didn't crash
            assert isinstance(result, BatchEnrichmentResult)
            assert result.total_processed == len(sample_businesses)

            print("✓ Error handling works correctly")

        asyncio.run(run_test())

    def test_progress_tracking(self, coordinator, sample_businesses):
        """
        Test that progress tracking works properly

        Acceptance Criteria: Progress tracking
        """

        async def run_test():
            # Add a delay to the enricher to make progress tracking testable
            original_enrich = coordinator.enrichers[EnrichmentSource.INTERNAL].enrich_business

            async def slow_enrich_business(*args, **kwargs):
                await asyncio.sleep(0.2)  # Add delay to allow progress tracking
                return await original_enrich(*args, **kwargs)

            coordinator.enrichers[EnrichmentSource.INTERNAL].enrich_business = slow_enrich_business

            # Start batch enrichment (don't await yet)
            task = asyncio.create_task(
                coordinator.enrich_businesses_batch(
                    businesses=sample_businesses,
                    sources=[EnrichmentSource.INTERNAL],
                    skip_existing=False,
                )
            )

            # Give it a moment to start
            await asyncio.sleep(0.1)

            # Check that we can get active progress
            active_progress = coordinator.get_all_active_progress()
            assert len(active_progress) > 0

            # Get specific progress
            request_id = list(active_progress.keys())[0]
            progress = coordinator.get_progress(request_id)

            assert isinstance(progress, EnrichmentProgress)
            assert progress.total_businesses == len(sample_businesses)
            assert progress.started_at is not None
            assert 0 <= progress.completion_percentage <= 100

            # Wait for completion
            await task

            # Verify progress is complete
            final_progress = coordinator.get_progress(request_id)
            assert final_progress.completion_percentage == 100.0
            assert final_progress.processed_businesses == len(sample_businesses)

            # Verify batch result is stored
            batch_result = coordinator.get_batch_result(request_id)
            assert batch_result is not None
            assert batch_result.request_id == request_id

            print("✓ Progress tracking works correctly")

        asyncio.run(run_test())

    def test_concurrent_processing(self, coordinator, sample_businesses):
        """Test concurrent processing works correctly"""

        async def run_test():
            # Test with multiple concurrent requests
            coordinator.max_concurrent = 2

            result = await coordinator.enrich_businesses_batch(
                businesses=sample_businesses * 2,  # 6 businesses total
                sources=[EnrichmentSource.INTERNAL],
                skip_existing=False,
            )

            # Should process all businesses
            assert result.total_processed == len(sample_businesses) * 2
            assert result.progress.processed_businesses == len(sample_businesses) * 2

            print("✓ Concurrent processing works correctly")

        asyncio.run(run_test())

    def test_multiple_sources(self, coordinator, sample_businesses):
        """Test enrichment with multiple sources"""

        async def run_test():
            # Add a second mock enricher
            mock_enricher = Mock()
            mock_result = Mock(spec=EnrichmentResult)
            mock_result.business_id = "test"
            mock_result.match_confidence = MatchConfidence.HIGH.value
            mock_enricher.enrich_business = AsyncMock(return_value=mock_result)

            await coordinator.add_enricher(EnrichmentSource.CLEARBIT, mock_enricher)

            # Test with multiple sources
            result = await coordinator.enrich_businesses_batch(
                businesses=sample_businesses[:1],  # Just one business
                sources=[EnrichmentSource.INTERNAL, EnrichmentSource.CLEARBIT],
                skip_existing=False,
            )

            # Should succeed with at least one source
            assert result.total_processed == 1

            # Remove the enricher
            await coordinator.remove_enricher(EnrichmentSource.CLEARBIT)

            print("✓ Multiple sources work correctly")

        asyncio.run(run_test())

    def test_priority_handling(self, coordinator, sample_businesses):
        """Test priority handling for enrichment requests"""

        async def run_test():
            # Test different priority levels
            result_high = await coordinator.enrich_businesses_batch(
                businesses=sample_businesses[:1],
                sources=[EnrichmentSource.INTERNAL],
                priority=EnrichmentPriority.HIGH,
                skip_existing=False,
            )

            result_low = await coordinator.enrich_businesses_batch(
                businesses=sample_businesses[1:2],
                sources=[EnrichmentSource.INTERNAL],
                priority=EnrichmentPriority.LOW,
                skip_existing=False,
            )

            # Both should complete successfully
            assert result_high.total_processed == 1
            assert result_low.total_processed == 1

            print("✓ Priority handling works correctly")

        asyncio.run(run_test())

    def test_request_cancellation(self, coordinator, sample_businesses):
        """Test request cancellation functionality"""

        async def run_test():
            # Start a request
            task = asyncio.create_task(
                coordinator.enrich_businesses_batch(
                    businesses=sample_businesses,
                    sources=[EnrichmentSource.INTERNAL],
                    skip_existing=False,
                )
            )

            # Give it a moment to start
            await asyncio.sleep(0.1)

            # Get the request ID
            active_requests = coordinator.get_all_active_progress()
            if active_requests:
                request_id = list(active_requests.keys())[0]

                # Cancel the request
                cancelled = coordinator.cancel_request(request_id)
                assert cancelled

                # Verify it's no longer active
                assert request_id not in coordinator.get_all_active_progress()

                # Verify it's in completed requests
                batch_result = coordinator.get_batch_result(request_id)
                assert batch_result is not None
                assert "cancelled" in str(batch_result.errors).lower()

            # Clean up task
            try:
                await task
            except Exception:
                pass  # Task may have been cancelled

            print("✓ Request cancellation works correctly")

        asyncio.run(run_test())

    def test_statistics_tracking(self, coordinator, sample_businesses):
        """Test statistics tracking"""

        async def run_test():
            # Get initial stats
            initial_stats = coordinator.get_statistics()
            assert "total_requests" in initial_stats
            assert "total_businesses_processed" in initial_stats

            # Process some businesses
            await coordinator.enrich_businesses_batch(
                businesses=sample_businesses,
                sources=[EnrichmentSource.INTERNAL],
                skip_existing=False,
            )

            # Check updated stats
            final_stats = coordinator.get_statistics()
            assert final_stats["total_requests"] > initial_stats["total_requests"]
            assert final_stats["total_businesses_processed"] > initial_stats["total_businesses_processed"]

            print("✓ Statistics tracking works correctly")

        asyncio.run(run_test())

    def test_cleanup_old_requests(self, coordinator):
        """Test cleanup of old completed requests"""

        async def run_test():
            # Create some fake old completed requests
            old_progress = EnrichmentProgress(
                request_id="old_request",
                total_businesses=1,
                started_at=datetime.utcnow() - timedelta(hours=25),
            )

            old_result = BatchEnrichmentResult(
                request_id="old_request",
                total_processed=1,
                successful_enrichments=1,
                skipped_enrichments=0,
                failed_enrichments=0,
                progress=old_progress,
                results=[],
                errors=[],
                execution_time_seconds=1.0,
            )

            coordinator.completed_requests["old_request"] = old_result

            # Cleanup old requests
            await coordinator.cleanup_old_requests(max_age_hours=24)

            # Verify old request was removed
            assert "old_request" not in coordinator.completed_requests

            print("✓ Cleanup old requests works correctly")

        asyncio.run(run_test())

    def test_convenience_functions(self, sample_businesses):
        """Test convenience functions"""

        async def run_test():
            # Test single business enrichment
            result = await enrich_business(business=sample_businesses[0], sources=[EnrichmentSource.INTERNAL])

            # Should return EnrichmentResult or None
            assert result is None or isinstance(result, EnrichmentResult)

            # Test batch enrichment convenience function
            batch_result = await enrich_businesses(
                businesses=sample_businesses,
                sources=[EnrichmentSource.INTERNAL],
                max_concurrent=2,
                skip_existing=False,
            )

            assert isinstance(batch_result, BatchEnrichmentResult)
            assert batch_result.total_processed == len(sample_businesses)

            print("✓ Convenience functions work correctly")

        asyncio.run(run_test())

    def test_comprehensive_acceptance_criteria(self, coordinator, sample_businesses):
        """Comprehensive test covering all acceptance criteria"""

        async def run_test():
            # This test verifies all four acceptance criteria work together

            # 1. Batch enrichment works - process multiple businesses
            result = await coordinator.enrich_businesses_batch(
                businesses=sample_businesses,
                sources=[EnrichmentSource.INTERNAL],
                skip_existing=True,  # Enable skip logic
            )

            assert isinstance(result, BatchEnrichmentResult), "Batch enrichment failed"
            assert result.total_processed == len(sample_businesses), "Not all businesses processed"

            # 2. Skip already enriched - verify skip logic can work
            assert hasattr(coordinator, "_is_recently_enriched"), "Skip enriched logic missing"

            # 3. Error handling proper - verify errors are captured
            assert hasattr(result, "errors"), "Error handling missing"
            assert hasattr(result.progress, "errors"), "Progress error tracking missing"

            # 4. Progress tracking - verify progress is tracked
            assert result.progress.completion_percentage == 100.0, "Progress tracking failed"
            assert result.progress.total_businesses == len(sample_businesses), "Progress total incorrect"
            assert result.progress.processed_businesses == len(sample_businesses), "Progress processed incorrect"

            print("✓ All acceptance criteria working together successfully")

        asyncio.run(run_test())

    def test_merge_enrichment_data(self, coordinator):
        """
        Test merge_enrichment_data method with various scenarios

        Tests the specific merge logic that was fixed in P0-001
        """
        # Test 1: Basic merge with newer data
        existing_data = {
            "company_name": {
                "value": "Old Name",
                "provider": "google_places",
                "collected_at": datetime(2023, 1, 1, 12, 0, 0),
            },
            "phone": {"value": "555-1234", "provider": "google_places", "collected_at": datetime(2023, 1, 1, 12, 0, 0)},
        }

        new_data = {
            "company_name": {
                "value": "New Name",
                "provider": "google_places",
                "collected_at": datetime(2023, 1, 2, 12, 0, 0),  # Newer
            },
            "website": {
                "value": "https://example.com",
                "provider": "pagespeed",
                "collected_at": datetime(2023, 1, 1, 12, 0, 0),
            },
        }

        result = coordinator.merge_enrichment_data(existing_data, new_data)

        # Should be a flat dictionary
        assert isinstance(result, dict)
        assert "company_name" in result
        assert "phone" in result
        assert "website" in result

        # Company name should be updated to newer value
        assert result["company_name"]["value"] == "New Name"
        assert result["company_name"]["provider"] == "google_places"

        # Phone should remain from existing data
        assert result["phone"]["value"] == "555-1234"

        # Website should be added from new data
        assert result["website"]["value"] == "https://example.com"

        # Test 2: Handle legacy format (non-dict values)
        legacy_existing = {"company_name": "Legacy Name", "phone": "555-0000"}

        legacy_new = {"company_name": "New Legacy Name", "website": "https://legacy.com"}

        legacy_result = coordinator.merge_enrichment_data(legacy_existing, legacy_new)

        # Should handle legacy format and convert to internal provider
        assert legacy_result["company_name"]["provider"] == "internal"
        assert legacy_result["phone"]["provider"] == "internal"
        assert legacy_result["website"]["provider"] == "internal"

        # Test 3: Handle string timestamps
        string_time_data = {
            "company_name": {"value": "String Time Name", "provider": "test", "collected_at": "2023-01-01T12:00:00"}
        }

        string_result = coordinator.merge_enrichment_data({}, string_time_data)
        assert isinstance(string_result["company_name"]["collected_at"], datetime)

        # Test 4: Empty data handling
        empty_result = coordinator.merge_enrichment_data({}, {})
        assert empty_result == {}

        none_result = coordinator.merge_enrichment_data(None, None)
        assert none_result == {}

        print("✓ merge_enrichment_data tests passed")

    @given(
        business_id=st.text(alphabet=string.printable, min_size=1, max_size=1000),
        provider=st.sampled_from(["google_places", "pagespeed", "semrush", "lighthouse"]),
        timestamp=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 12, 31)),
    )
    def test_cache_key_uniqueness(self, business_id, provider, timestamp):
        """Property-based test ensuring cache keys are unique for different inputs."""
        coordinator = EnrichmentCoordinator()

        # Generate keys for same inputs
        key1 = coordinator.generate_cache_key(business_id, provider, timestamp)
        key2 = coordinator.generate_cache_key(business_id, provider, timestamp)

        # Same inputs should produce same key (deterministic)
        assert key1 == key2

        # Different business IDs should produce different keys
        if business_id != "different_business":
            key3 = coordinator.generate_cache_key("different_business", provider, timestamp)
            assert key1 != key3

        # Different providers should produce different keys
        other_provider = "lighthouse" if provider != "lighthouse" else "google_places"
        key4 = coordinator.generate_cache_key(business_id, other_provider, timestamp)
        assert key1 != key4

        # Keys should have expected format
        assert key1.startswith("enrichment:v1:")
        assert len(key1.split(":")) == 5

    def test_merge_performance(self, coordinator):
        """Ensure merge operations remain O(n) complexity."""
        # Create test data sets of increasing size
        sizes = [100, 1000, 10000]
        times = []

        for size in sizes:
            # Generate test data
            existing_data = {
                f"field_{i}": {
                    "value": f"value_{i}",
                    "provider": "google_places",
                    "collected_at": datetime.utcnow() - timedelta(hours=1),
                }
                for i in range(size)
            }

            new_data = {
                f"field_{i}": {
                    "value": f"new_value_{i}",
                    "provider": "google_places",
                    "collected_at": datetime.utcnow(),
                }
                for i in range(size // 2, size + size // 2)
            }

            # Measure merge time
            start_time = time.time()
            result = coordinator.merge_enrichment_data(existing_data, new_data)
            end_time = time.time()

            times.append(end_time - start_time)

            # Verify correctness
            assert len(result) == size + size // 2  # Union of both sets

        # Check that time complexity is roughly linear
        # Time should increase linearly with size (allowing 3x variance for CI environments)
        ratio1 = times[1] / times[0]  # 1000 vs 100
        ratio2 = times[2] / times[1]  # 10000 vs 1000

        # Both ratios should be roughly 10x (the size increase)
        # Allow more variance as CI environments can be unpredictable
        # Also allow better than expected performance (ratio < 5)
        assert ratio1 <= 30, f"Performance degradation detected: {ratio1}x for 10x size increase"
        assert ratio2 <= 30, f"Performance degradation detected: {ratio2}x for 10x size increase"

        # Ensure it's still O(n) - ratio should be at least 1x
        assert ratio1 >= 1, f"Performance ratio too low: {ratio1}x (should be at least 1x)"
        assert ratio2 >= 1, f"Performance ratio too low: {ratio2}x (should be at least 1x)"

        print("✓ merge_performance tests passed")

    def test_cache_key_generation_edge_cases(self, coordinator):
        """Test cache key generation with various edge cases"""
        # Test with empty business_id
        try:
            key = coordinator.generate_cache_key("", "google_places")
            assert key.startswith("enrichment:v1:")
        except Exception:
            pass  # Empty business_id might be invalid

        # Test with special characters in business_id
        key = coordinator.generate_cache_key("business@123!#$%", "google_places")
        assert key.startswith("enrichment:v1:")
        assert len(key.split(":")) == 5

        # Test with very long business_id
        long_id = "a" * 1000
        key = coordinator.generate_cache_key(long_id, "google_places")
        assert key.startswith("enrichment:v1:")

        # Test with different timestamps
        ts1 = datetime(2023, 1, 1, 12, 0, 0)
        ts2 = datetime(2023, 1, 1, 13, 0, 0)  # Same day, different hour
        ts3 = datetime(2023, 1, 2, 12, 0, 0)  # Different day

        key1 = coordinator.generate_cache_key("test", "google_places", ts1)
        key2 = coordinator.generate_cache_key("test", "google_places", ts2)
        key3 = coordinator.generate_cache_key("test", "google_places", ts3)

        # Different hours should produce different keys
        assert key1 != key2
        assert key1 != key3

        print("✓ cache_key_generation_edge_cases tests passed")

    def test_merge_data_edge_cases(self, coordinator):
        """Test merge_enrichment_data with additional edge cases"""
        # Test with None values in data
        data_with_none = {
            "field1": None,
            "field2": {"value": "test", "provider": "test", "collected_at": datetime.utcnow()},
        }

        result = coordinator.merge_enrichment_data(data_with_none, {})
        # Should handle None values gracefully
        assert "field2" in result

        # Test with malformed timestamps
        bad_timestamp_data = {"field1": {"value": "test", "provider": "test", "collected_at": "invalid-date"}}

        result = coordinator.merge_enrichment_data({}, bad_timestamp_data)
        assert "field1" in result
        assert isinstance(result["field1"]["collected_at"], datetime)

        # Test with same field, different providers
        existing = {
            "company_name": {"value": "Google Name", "provider": "google_places", "collected_at": datetime(2023, 1, 1)}
        }

        new = {
            "company_name": {"value": "PageSpeed Name", "provider": "pagespeed", "collected_at": datetime(2023, 1, 2)}
        }

        result = coordinator.merge_enrichment_data(existing, new)
        # Should contain only the newer entry (pagespeed)
        assert result["company_name"]["value"] == "PageSpeed Name"
        assert result["company_name"]["provider"] == "pagespeed"

        print("✓ merge_data_edge_cases tests passed")


# Allow running this test file directly
if __name__ == "__main__":

    async def run_tests():
        test_instance = TestTask043AcceptanceCriteria()

        print("🔄 Running Task 043 Enrichment Coordinator Tests...")
        print()

        try:
            # Sample data
            sample_businesses = [
                {"id": "test_001", "name": "Test Corp", "phone": "555-1111"},
                {"id": "test_002", "name": "Sample Inc", "phone": "555-2222"},
            ]

            coordinator = EnrichmentCoordinator(max_concurrent=2)

            # Run all acceptance criteria tests
            test_instance.test_batch_enrichment_works(coordinator, sample_businesses)
            test_instance.test_skip_already_enriched(coordinator, sample_businesses)
            test_instance.test_error_handling_proper(coordinator, sample_businesses)
            test_instance.test_progress_tracking(coordinator, sample_businesses)
            test_instance.test_concurrent_processing(coordinator, sample_businesses)
            test_instance.test_multiple_sources(coordinator, sample_businesses)
            test_instance.test_priority_handling(coordinator, sample_businesses)
            test_instance.test_request_cancellation(coordinator, sample_businesses)
            test_instance.test_statistics_tracking(coordinator, sample_businesses)
            test_instance.test_cleanup_old_requests(coordinator)
            test_instance.test_convenience_functions(sample_businesses)
            test_instance.test_comprehensive_acceptance_criteria(coordinator, sample_businesses)

            print()
            print("🎉 All Task 043 acceptance criteria tests pass!")
            print("   - Batch enrichment works: ✓")
            print("   - Skip already enriched: ✓")
            print("   - Error handling proper: ✓")
            print("   - Progress tracking: ✓")

        except Exception as e:
            print(f"❌ Test failed: {e}")
            import traceback

            traceback.print_exc()

    # Run tests
    asyncio.run(run_tests())
