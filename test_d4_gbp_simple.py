#!/usr/bin/env python3
"""
Simple test runner for d4_enrichment GBP enricher without pytest dependency
"""
import asyncio
import sys
import traceback

sys.path.insert(0, "/app")


def run_simple_tests():
    """Run basic tests for d4_enrichment GBP enricher"""
    try:
        # Test imports
        from d4_enrichment.gbp_enricher import (BatchGBPEnricher,
                                                GBPDataQuality, GBPEnricher,
                                                GBPSearchResult)
        from d4_enrichment.matchers import MatchConfidence
        from d4_enrichment.models import EnrichmentResult

        print("✓ All imports successful")

        async def run_async_tests():
            # Test GBP data extraction
            enricher = GBPEnricher(api_key=None)  # Use mock data

            business_data = {
                "id": "test_biz_001",
                "name": "Test Corporation",
                "phone": "555-123-4567",
                "address": "123 Test St, Test City, TS 12345",
            }

            gbp_results = await enricher._search_gbp_data(business_data)
            assert len(gbp_results) > 0
            assert isinstance(gbp_results[0], GBPSearchResult)
            print("✓ GBP data extraction works")

            # Test best match selection
            sample_gbp = GBPSearchResult(
                place_id="test_place_123",
                name="Test Corporation",
                formatted_address="123 Test St, Test City, TS 12345, USA",
                phone_number="555-123-4567",
                rating=4.0,
                data_quality=GBPDataQuality.GOOD,
                search_confidence=0.9,
            )

            best_match = await enricher._select_best_match(business_data, [sample_gbp])
            assert best_match is not None
            assert best_match.search_confidence >= 0.5
            print("✓ Best match selection works")

            # Test business data merge
            merged_data = enricher._merge_business_data(business_data, sample_gbp)
            assert "business_name" in merged_data or "name" in merged_data
            assert len(merged_data) >= len(business_data)
            print("✓ Business data merge works")

            # Test confidence scoring
            confidence_score = enricher._calculate_confidence_score(
                business_data, sample_gbp
            )
            assert 0.0 <= confidence_score <= 1.0

            confidence_level = enricher._map_confidence_to_level(confidence_score)
            assert confidence_level in MatchConfidence
            print("✓ Confidence scoring works")

            # Test end-to-end enrichment
            result = await enricher.enrich_business(business_data)
            assert isinstance(result, EnrichmentResult)
            assert result.business_id == business_data["id"]
            assert result.match_confidence in [conf.value for conf in MatchConfidence]
            print("✓ End-to-end enrichment works")

            # Test batch enrichment
            batch_enricher = BatchGBPEnricher(
                enricher=enricher, max_concurrent=2, batch_size=3
            )
            businesses = [
                {"id": "biz_1", "name": "Business One"},
                {"id": "biz_2", "name": "Business Two"},
            ]

            batch_results = await batch_enricher.enrich_businesses(businesses)
            assert len(batch_results) == len(businesses)
            print("✓ Batch enrichment works")

            # Test utility functions
            assert (
                enricher._extract_domain("https://www.example.com/path")
                == "example.com"
            )
            assert enricher._extract_domain(None) is None

            cache_key = enricher._generate_cache_key(business_data)
            assert isinstance(cache_key, str)
            assert len(cache_key) == 32  # MD5 hash
            print("✓ Utility functions work")

            # Test statistics
            stats = enricher.get_statistics()
            assert "total_requests" in stats
            assert "success_rate" in stats
            print("✓ Statistics tracking works")

        # Run async tests
        asyncio.run(run_async_tests())

        print("\n🎉 All Task 042 acceptance criteria verified!")
        print("   - GBP data extraction: ✓")
        print("   - Best match selection: ✓")
        print("   - Business data merge: ✓")
        print("   - Confidence scoring: ✓")
        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_simple_tests()
    sys.exit(0 if success else 1)
