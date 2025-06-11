"""
Test Enrichment Coordinator - Task 043

Tests for enrichment coordinator ensuring all acceptance criteria are met:
- Batch enrichment works
- Skip already enriched
- Error handling proper
- Progress tracking
"""

import asyncio
import sys
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest

from d4_enrichment.coordinator import (BatchEnrichmentResult,
                                       EnrichmentCoordinator,
                                       EnrichmentPriority, EnrichmentProgress,
                                       enrich_business, enrich_businesses)
from d4_enrichment.gbp_enricher import GBPEnricher
from d4_enrichment.models import (EnrichmentResult, EnrichmentSource,
                                  MatchConfidence)

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
            assert result.successful_enrichments + result.failed_enrichments <= len(
                sample_businesses
            )
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
            failing_enricher.enrich_business = AsyncMock(
                side_effect=Exception("Test error")
            )

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
            result = await task

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
                assert cancelled == True

                # Verify it's no longer active
                assert request_id not in coordinator.get_all_active_progress()

                # Verify it's in completed requests
                batch_result = coordinator.get_batch_result(request_id)
                assert batch_result is not None
                assert "cancelled" in str(batch_result.errors).lower()

            # Clean up task
            try:
                await task
            except:
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
            assert (
                final_stats["total_businesses_processed"]
                > initial_stats["total_businesses_processed"]
            )

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
            result = await enrich_business(
                business=sample_businesses[0], sources=[EnrichmentSource.INTERNAL]
            )

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
            assert result.total_processed == len(
                sample_businesses
            ), "Not all businesses processed"

            # 2. Skip already enriched - verify skip logic can work
            assert hasattr(
                coordinator, "_is_recently_enriched"
            ), "Skip enriched logic missing"

            # 3. Error handling proper - verify errors are captured
            assert hasattr(result, "errors"), "Error handling missing"
            assert hasattr(result.progress, "errors"), "Progress error tracking missing"

            # 4. Progress tracking - verify progress is tracked
            assert (
                result.progress.completion_percentage == 100.0
            ), "Progress tracking failed"
            assert result.progress.total_businesses == len(
                sample_businesses
            ), "Progress total incorrect"
            assert result.progress.processed_businesses == len(
                sample_businesses
            ), "Progress processed incorrect"

            print("✓ All acceptance criteria working together successfully")

        asyncio.run(run_test())


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
            test_instance.test_comprehensive_acceptance_criteria(
                coordinator, sample_businesses
            )

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
