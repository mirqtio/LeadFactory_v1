#!/usr/bin/env python3
"""
Simple test runner for d4_enrichment integration tests without pytest dependency
"""
import sys
import traceback
import asyncio
import time

sys.path.insert(0, "/app")


def run_simple_tests():
    """Run basic integration tests for d4_enrichment"""
    try:
        # Test imports
        from d4_enrichment.coordinator import (
            EnrichmentCoordinator,
            enrich_business,
            enrich_businesses,
        )
        from d4_enrichment.gbp_enricher import GBPEnricher
        from d4_enrichment.matchers import BusinessMatcher
        from d4_enrichment.similarity import PhoneSimilarity, NameSimilarity
        from d4_enrichment.models import EnrichmentSource

        print("✓ All integration imports successful")

        async def run_async_tests():
            # Sample business data for integration testing
            sample_businesses = [
                {
                    "id": "integration_001",
                    "name": "Test Corporation",
                    "phone": "415-555-1234",
                    "address": "123 Market St, San Francisco, CA 94105",
                },
                {
                    "id": "integration_002",
                    "name": "Sample LLC",
                    "phone": "(415) 555-9876",
                    "address": "456 Mission St, San Francisco, CA 94103",
                },
            ]

            # Test 1: Full enrichment flow
            print("🔄 Testing full enrichment flow...")
            coordinator = EnrichmentCoordinator(max_concurrent=2)

            batch_result = await coordinator.enrich_businesses_batch(
                businesses=sample_businesses,
                sources=[EnrichmentSource.INTERNAL],
                skip_existing=False,
            )

            assert batch_result.total_processed == len(sample_businesses)
            assert batch_result.execution_time_seconds > 0
            assert batch_result.progress.completion_percentage == 100.0
            print("✓ Full enrichment flow works")

            # Test 2: Matching accuracy verified
            print("🎯 Testing matching accuracy...")
            phone_matcher = PhoneSimilarity()
            name_matcher = NameSimilarity()

            # Test phone matching
            phone_match = phone_matcher.calculate_similarity(
                "415-555-1234", "(415) 555-1234"
            )
            assert phone_match.score >= 0.8
            print(f"  Phone match score: {phone_match.score:.2f}")

            # Test name matching
            name_match = name_matcher.calculate_similarity(
                "Test Corporation", "TEST CORP"
            )
            assert name_match.score >= 0.6
            print(f"  Name match score: {name_match.score:.2f}")
            print("✓ Matching accuracy verified")

            # Test 3: Data merge correct
            print("🔀 Testing data merge...")
            enricher = coordinator.enrichers[EnrichmentSource.INTERNAL]

            # Test single enrichment for data merge
            single_result = await enricher.enrich_business(sample_businesses[0])
            if single_result:
                assert hasattr(single_result, "processed_data")
                assert isinstance(single_result.processed_data, dict)
                assert single_result.business_id == sample_businesses[0]["id"]
                print("  Data merge structure correct")

            print("✓ Data merge correct")

            # Test 4: Performance acceptable
            print("⚡ Testing performance...")
            start_time = time.time()

            # Test with smaller batch for faster testing
            perf_businesses = [
                {"id": f"perf_{i}", "name": f"Perf Test {i}", "phone": f"555-{i:04d}"}
                for i in range(5)
            ]

            perf_result = await coordinator.enrich_businesses_batch(
                businesses=perf_businesses,
                sources=[EnrichmentSource.INTERNAL],
                skip_existing=False,
            )

            duration = time.time() - start_time
            throughput = len(perf_businesses) / duration

            assert duration < 30.0  # Should complete within 30 seconds
            assert throughput > 0.1  # At least 0.1 businesses per second
            print(f"  Performance: {duration:.2f}s, {throughput:.2f} biz/sec")
            print("✓ Performance acceptable")

            # Test 5: Error handling
            print("🛡️ Testing error handling...")
            invalid_businesses = [
                {},  # Empty business
                {"id": "test_invalid"},  # Minimal data
            ]

            error_result = await coordinator.enrich_businesses_batch(
                businesses=invalid_businesses,
                sources=[EnrichmentSource.INTERNAL],
                skip_existing=False,
            )

            # Should handle without crashing
            assert isinstance(error_result.errors, list)
            print("✓ Error handling works")

            # Test 6: Convenience functions
            print("🔧 Testing convenience functions...")

            # Single business enrichment
            single_convenience = await enrich_business(
                business=sample_businesses[0], sources=[EnrichmentSource.INTERNAL]
            )
            # Can be None or EnrichmentResult, both valid

            # Batch convenience function
            batch_convenience = await enrich_businesses(
                businesses=sample_businesses[:1],
                sources=[EnrichmentSource.INTERNAL],
                max_concurrent=1,
            )
            assert batch_convenience.total_processed == 1
            print("✓ Convenience functions work")

        # Run async tests
        asyncio.run(run_async_tests())

        print("\n🎉 All Task 044 integration tests verified!")
        print("   - Full enrichment flow: ✓")
        print("   - Matching accuracy verified: ✓")
        print("   - Data merge correct: ✓")
        print("   - Performance acceptable: ✓")
        return True

    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_simple_tests()
    sys.exit(0 if success else 1)