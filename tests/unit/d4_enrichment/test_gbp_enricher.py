"""
Test GBP Enricher - Task 042

Tests for GBP enricher ensuring all acceptance criteria are met:
- GBP data extraction
- Best match selection
- Business data merge
- Confidence scoring
"""

import asyncio
import sys

import pytest

# Mark entire module as slow for CI optimization
pytestmark = pytest.mark.slow

from d4_enrichment.gbp_enricher import (
    BatchGBPEnricher,
    GBPDataQuality,
    GBPEnricher,
    GBPSearchResult,
)
from d4_enrichment.matchers import BusinessMatcher, MatchConfidence
from d4_enrichment.models import EnrichmentResult, EnrichmentSource

sys.path.insert(0, "/app")


class TestTask042AcceptanceCriteria:
    """Test that Task 042 meets all acceptance criteria"""

    @pytest.fixture
    def sample_business_data(self):
        """Sample business data for testing"""
        return {
            "id": "biz_test_001",
            "name": "Acme Corporation",
            "business_name": "Acme Corporation",
            "phone": "+1-555-123-4567",
            "address": "123 Main Street, San Francisco, CA 94105",
            "city": "San Francisco",
            "state": "CA",
            "zip": "94105",
            "website": "https://acme.com",
        }

    @pytest.fixture
    def sample_gbp_result(self):
        """Sample GBP search result"""
        return GBPSearchResult(
            place_id="ChIJN1t_tDeuEmsRUsoyG83frY4",
            name="Acme Corporation",
            formatted_address="123 Main St, San Francisco, CA 94105, USA",
            phone_number="+1-555-123-4567",
            website="https://acme.com",
            rating=4.5,
            user_ratings_total=120,
            business_status="OPERATIONAL",
            types=["establishment", "point_of_interest"],
            search_confidence=0.9,
            data_quality=GBPDataQuality.GOOD,
            raw_data={"test": True},
        )

    @pytest.fixture
    def gbp_enricher(self):
        """Create GBP enricher instance"""
        return GBPEnricher(api_key=None)  # Use mock data

    def test_gbp_data_extraction(self, gbp_enricher, sample_business_data):
        """
        Test that GBP data extraction works properly

        Acceptance Criteria: GBP data extraction
        """

        async def run_test():
            # Test mock data extraction
            gbp_results = await gbp_enricher._search_gbp_data(sample_business_data)

            assert len(gbp_results) > 0
            assert isinstance(gbp_results[0], GBPSearchResult)
            assert gbp_results[0].place_id is not None
            assert gbp_results[0].name == sample_business_data["name"]

            # Test different search strategies
            results_by_name = await gbp_enricher._search_by_name_and_location(
                sample_business_data
            )
            assert len(results_by_name) > 0
            assert results_by_name[0].search_confidence == 0.8

            results_by_phone = await gbp_enricher._search_by_phone(sample_business_data)
            assert len(results_by_phone) > 0
            assert results_by_phone[0].search_confidence == 0.9

            results_by_address = await gbp_enricher._search_by_address(
                sample_business_data
            )
            assert len(results_by_address) > 0
            assert results_by_address[0].search_confidence == 0.7

            # Test cache functionality
            cache_key = gbp_enricher._generate_cache_key(sample_business_data)
            assert isinstance(cache_key, str)
            assert len(cache_key) == 32  # MD5 hash length

            print("✓ GBP data extraction works correctly")

        asyncio.run(run_test())

    def test_best_match_selection(
        self, gbp_enricher, sample_business_data, sample_gbp_result
    ):
        """
        Test that best match selection works properly

        Acceptance Criteria: Best match selection
        """

        async def run_test():
            # Create multiple GBP results with different confidence levels
            gbp_results = [
                GBPSearchResult(
                    place_id="place_1",
                    name="Similar Company",
                    search_confidence=0.6,
                    data_quality=GBPDataQuality.FAIR,
                ),
                sample_gbp_result,  # Should be the best match
                GBPSearchResult(
                    place_id="place_3",
                    name="Different Business",
                    search_confidence=0.4,
                    data_quality=GBPDataQuality.POOR,
                ),
            ]

            best_match = await gbp_enricher._select_best_match(
                sample_business_data, gbp_results
            )

            assert best_match is not None
            assert best_match.place_id == sample_gbp_result.place_id
            assert best_match.search_confidence >= 0.7  # Should have high confidence

            # Test with no suitable matches
            low_quality_results = [
                GBPSearchResult(
                    place_id="place_low",
                    name="Completely Different",
                    search_confidence=0.3,
                    data_quality=GBPDataQuality.POOR,
                )
            ]

            no_match = await gbp_enricher._select_best_match(
                sample_business_data, low_quality_results
            )
            assert no_match is None  # Should reject low-quality matches

            # Test with empty results
            empty_match = await gbp_enricher._select_best_match(
                sample_business_data, []
            )
            assert empty_match is None

            print("✓ Best match selection works correctly")

        asyncio.run(run_test())

    def test_business_data_merge(
        self, gbp_enricher, sample_business_data, sample_gbp_result
    ):
        """
        Test that business data merge works properly

        Acceptance Criteria: Business data merge
        """
        # Test merging with complete original data
        merged_data = gbp_enricher._merge_business_data(
            sample_business_data, sample_gbp_result
        )

        # Original data should be preserved where present
        assert merged_data["name"] == sample_business_data["name"]
        assert merged_data["phone"] == sample_business_data["phone"]

        # GBP data should enhance missing fields
        assert merged_data["rating"] == sample_gbp_result.rating
        assert merged_data["user_ratings_total"] == sample_gbp_result.user_ratings_total
        assert merged_data["business_status"] == sample_gbp_result.business_status
        assert merged_data["types"] == sample_gbp_result.types

        # Test merging with incomplete original data
        incomplete_data = {
            "id": "biz_test_002",
            "name": "Partial Company",
            # Missing phone, address, etc.
        }

        merged_incomplete = gbp_enricher._merge_business_data(
            incomplete_data, sample_gbp_result
        )

        # Should use GBP data for missing fields
        assert merged_incomplete["phone"] == sample_gbp_result.phone_number
        assert (
            merged_incomplete["formatted_address"]
            == sample_gbp_result.formatted_address
        )
        assert merged_incomplete["website"] == sample_gbp_result.website

        # Test address component parsing
        address_components = gbp_enricher._parse_address_components(
            "123 Main St, San Francisco, CA 94105, USA"
        )
        assert "street_address" in address_components
        assert address_components["city"] == "San Francisco"

        # Test data quality assessment
        assert gbp_enricher._is_gbp_data_better("", "new_value", "any_field") is True
        assert (
            gbp_enricher._is_gbp_data_better(
                "http://old.com", "https://new.com", "website"
            )
            is True
        )
        assert (
            gbp_enricher._is_gbp_data_better("555-1234", "+1-555-123-4567", "phone")
            is True
        )

        print("✓ Business data merge works correctly")

    def test_confidence_scoring(
        self, gbp_enricher, sample_business_data, sample_gbp_result
    ):
        """
        Test that confidence scoring works properly

        Acceptance Criteria: Confidence scoring
        """
        # Test confidence score calculation
        confidence_score = gbp_enricher._calculate_confidence_score(
            sample_business_data, sample_gbp_result
        )

        assert 0.0 <= confidence_score <= 1.0
        assert confidence_score >= 0.7  # Should be high for good match

        # Test confidence level mapping
        exact_confidence = gbp_enricher._map_confidence_to_level(0.95)
        assert exact_confidence == MatchConfidence.EXACT

        high_confidence = gbp_enricher._map_confidence_to_level(0.80)
        assert high_confidence == MatchConfidence.HIGH

        medium_confidence = gbp_enricher._map_confidence_to_level(0.65)
        assert medium_confidence == MatchConfidence.MEDIUM

        low_confidence = gbp_enricher._map_confidence_to_level(0.45)
        assert low_confidence == MatchConfidence.LOW

        uncertain_confidence = gbp_enricher._map_confidence_to_level(0.25)
        assert uncertain_confidence == MatchConfidence.UNCERTAIN

        # Test completeness factor calculation
        completeness = gbp_enricher._calculate_completeness_factor(sample_gbp_result)
        assert 0.0 <= completeness <= 1.0
        assert completeness >= 0.8  # Should be high for complete result

        # Test with incomplete result
        incomplete_result = GBPSearchResult(
            place_id="incomplete",
            name="Test Business",
            # Missing most fields
        )

        incomplete_completeness = gbp_enricher._calculate_completeness_factor(
            incomplete_result
        )
        assert incomplete_completeness < completeness

        print("✓ Confidence scoring works correctly")

    def test_end_to_end_enrichment(self, gbp_enricher, sample_business_data):
        """Test complete end-to-end enrichment process"""

        async def run_test():
            # Test successful enrichment
            result = await gbp_enricher.enrich_business(sample_business_data)

            assert isinstance(result, EnrichmentResult)
            assert result.business_id == sample_business_data["id"]
            assert result.company_name == sample_business_data["name"]
            assert result.match_confidence in [conf.value for conf in MatchConfidence]
            assert 0.0 <= result.match_score <= 1.0
            assert result.source == EnrichmentSource.INTERNAL.value
            assert result.data_version.startswith("gbp_")
            assert result.enrichment_cost_usd > 0
            assert result.api_calls_used >= 0

            # Verify processed data
            assert (
                "status" not in result.processed_data
                or result.processed_data.get("status") != "failed"
            )

            # Test statistics tracking
            stats = gbp_enricher.get_statistics()
            assert stats["total_requests"] >= 1
            assert stats["successful_enrichments"] >= 1
            assert "success_rate" in stats
            assert "cache_hit_rate" in stats

            print("✓ End-to-end enrichment works correctly")

        asyncio.run(run_test())

    def test_error_handling_and_edge_cases(self, gbp_enricher):
        """Test error handling and edge cases"""

        async def run_test():
            # Test with empty business data
            empty_result = await gbp_enricher.enrich_business({})
            assert isinstance(empty_result, EnrichmentResult)
            assert empty_result.match_confidence == MatchConfidence.UNCERTAIN.value

            # Test with None values
            none_data = {"name": None, "phone": None, "address": None}
            none_result = await gbp_enricher.enrich_business(none_data)
            assert isinstance(none_result, EnrichmentResult)

            # Test cache expiration
            old_result = GBPSearchResult(place_id="old", name="Old Business")
            gbp_enricher._add_to_cache("test_key", old_result)

            # Manually expire cache
            import datetime

            gbp_enricher._cache["test_key"] = (
                datetime.datetime.utcnow() - datetime.timedelta(hours=25),
                old_result,
            )

            expired_result = gbp_enricher._get_from_cache("test_key")
            assert expired_result is None  # Should be expired

            # Test cache clearing
            gbp_enricher.clear_cache()
            assert len(gbp_enricher._cache) == 0

            print("✓ Error handling and edge cases work correctly")

        asyncio.run(run_test())

    def test_utility_functions(self, gbp_enricher):
        """Test utility functions"""
        # Test domain extraction
        assert (
            gbp_enricher._extract_domain("https://www.example.com/path")
            == "example.com"
        )
        assert (
            gbp_enricher._extract_domain("http://subdomain.example.com")
            == "subdomain.example.com"
        )
        assert gbp_enricher._extract_domain("example.com") == "example.com"
        assert gbp_enricher._extract_domain(None) is None
        assert gbp_enricher._extract_domain("") is None

        # Test data quality calculation
        high_quality_data = {
            "business_name": "Test Company",
            "phone": "+1-555-123-4567",
            "formatted_address": "123 Main St",
            "website": "https://test.com",
            "rating": 4.5,
            "user_ratings_total": 100,
            "business_status": "OPERATIONAL",
        }

        quality_score = gbp_enricher._calculate_data_quality(high_quality_data)
        assert quality_score >= 0.8

        low_quality_data = {"business_name": "Test"}

        low_quality_score = gbp_enricher._calculate_data_quality(low_quality_data)
        assert low_quality_score < quality_score

        print("✓ Utility functions work correctly")

    def test_gbp_search_result_dataclass(self):
        """Test GBPSearchResult dataclass functionality"""
        result = GBPSearchResult(
            place_id="test_place",
            name="Test Business",
            formatted_address="123 Test St",
            rating=4.2,
            data_quality=GBPDataQuality.GOOD,
        )

        # Test to_dict conversion
        result_dict = result.to_dict()
        assert result_dict["place_id"] == "test_place"
        assert result_dict["name"] == "Test Business"
        assert result_dict["rating"] == 4.2
        assert result_dict["data_quality"] == "good"

        # Test default values
        assert result.search_confidence == 0.0
        assert result.types == []
        assert result.photos == []
        assert result.reviews == []
        assert result.raw_data == {}

        print("✓ GBPSearchResult dataclass works correctly")

    def test_batch_gbp_enricher(self, gbp_enricher):
        """Test batch GBP enrichment functionality"""

        async def run_test():
            batch_enricher = BatchGBPEnricher(
                enricher=gbp_enricher, max_concurrent=2, batch_size=3
            )

            # Test businesses data
            businesses = [
                {"id": "biz_1", "name": "Business One"},
                {"id": "biz_2", "name": "Business Two"},
                {"id": "biz_3", "name": "Business Three"},
                {"id": "biz_4", "name": "Business Four"},
                {"id": "biz_5", "name": "Business Five"},
            ]

            # Test batch enrichment
            results = await batch_enricher.enrich_businesses(businesses)

            assert len(results) == len(businesses)
            assert all(isinstance(result, EnrichmentResult) for result in results)

            # Verify each business was processed
            result_ids = [result.business_id for result in results]
            expected_ids = [biz["id"] for biz in businesses]
            assert set(result_ids) == set(expected_ids)

            print("✓ Batch GBP enricher works correctly")

        asyncio.run(run_test())

    def test_mock_data_generation(self, gbp_enricher):
        """Test mock data generation for testing"""
        business_data = {"name": "Mock Test Business", "city": "Test City"}

        mock_results = gbp_enricher._get_mock_gbp_data(business_data)

        assert len(mock_results) == 1
        mock_result = mock_results[0]

        assert mock_result.name == business_data["name"]
        assert mock_result.place_id.startswith("mock_place_")
        assert mock_result.search_confidence == 0.85
        assert mock_result.data_quality == GBPDataQuality.GOOD
        assert mock_result.raw_data["mock"] is True

        # Test create_mock_result
        custom_mock = gbp_enricher._create_mock_result(
            "Custom Business", "Test Location", 0.95
        )

        assert custom_mock.name == "Custom Business"
        assert custom_mock.search_confidence == 0.95
        assert custom_mock.website == "https://custombusiness.com"

        print("✓ Mock data generation works correctly")

    def test_integration_with_fuzzy_matcher(self, sample_business_data):
        """Test integration with fuzzy matching system"""
        # Create enricher with custom matcher
        custom_matcher = BusinessMatcher()
        enricher = GBPEnricher(matcher=custom_matcher)

        async def run_test():
            # Test that the enricher uses the provided matcher
            assert enricher.matcher is custom_matcher

            # Test enrichment process uses fuzzy matching
            result = await enricher.enrich_business(sample_business_data)

            # Should have used fuzzy matching for match selection
            assert isinstance(result, EnrichmentResult)
            assert result.match_score >= 0.0

            # Test matcher statistics were updated
            matcher_stats = custom_matcher.get_statistics()
            assert matcher_stats["total_matches"] > 0

            print("✓ Integration with fuzzy matcher works correctly")

        asyncio.run(run_test())

    def test_comprehensive_acceptance_criteria(
        self, gbp_enricher, sample_business_data
    ):
        """Comprehensive test covering all acceptance criteria"""

        async def run_test():
            # This test verifies all four acceptance criteria work together

            # 1. GBP data extraction - verify data is extracted from multiple sources
            gbp_results = await gbp_enricher._search_gbp_data(sample_business_data)
            assert len(gbp_results) > 0, "GBP data extraction failed"

            # 2. Best match selection - verify best match is selected using
            # fuzzy matching
            best_match = await gbp_enricher._select_best_match(
                sample_business_data, gbp_results
            )
            assert best_match is not None, "Best match selection failed"
            assert best_match.search_confidence >= 0.5, "Best match quality too low"

            # 3. Business data merge - verify original and GBP data are properly merged
            merged_data = gbp_enricher._merge_business_data(
                sample_business_data, best_match
            )
            assert (
                "business_name" in merged_data or "name" in merged_data
            ), "Name merge failed"
            assert len(merged_data) >= len(
                sample_business_data
            ), "Data merge lost information"

            # 4. Confidence scoring - verify confidence is calculated and mapped
            # correctly
            confidence_score = gbp_enricher._calculate_confidence_score(
                sample_business_data, best_match
            )
            assert 0.0 <= confidence_score <= 1.0, "Confidence score out of range"

            confidence_level = gbp_enricher._map_confidence_to_level(confidence_score)
            assert confidence_level in MatchConfidence, "Invalid confidence level"

            # End-to-end test - all criteria working together
            final_result = await gbp_enricher.enrich_business(sample_business_data)
            assert isinstance(
                final_result, EnrichmentResult
            ), "End-to-end enrichment failed"
            assert final_result.match_confidence in [
                conf.value for conf in MatchConfidence
            ], "Invalid final confidence"

            print("✓ All acceptance criteria working together successfully")

        asyncio.run(run_test())


# Allow running this test file directly
if __name__ == "__main__":

    async def run_tests():
        test_instance = TestTask042AcceptanceCriteria()

        print("🏢 Running Task 042 GBP Enricher Tests...")
        print()

        try:
            # Sample data
            sample_business = {
                "id": "test_biz_001",
                "name": "Test Corporation",
                "phone": "555-123-4567",
                "address": "123 Test St, Test City, TS 12345",
            }

            sample_gbp = GBPSearchResult(
                place_id="test_place_123",
                name="Test Corporation",
                formatted_address="123 Test St, Test City, TS 12345, USA",
                phone_number="555-123-4567",
                rating=4.0,
                data_quality=GBPDataQuality.GOOD,
            )

            enricher = GBPEnricher(api_key=None)  # Use mock data

            # Run all acceptance criteria tests
            test_instance.test_gbp_data_extraction(enricher, sample_business)
            test_instance.test_best_match_selection(
                enricher, sample_business, sample_gbp
            )
            test_instance.test_business_data_merge(
                enricher, sample_business, sample_gbp
            )
            test_instance.test_confidence_scoring(enricher, sample_business, sample_gbp)
            test_instance.test_end_to_end_enrichment(enricher, sample_business)
            test_instance.test_error_handling_and_edge_cases(enricher)
            test_instance.test_utility_functions(enricher)
            test_instance.test_gbp_search_result_dataclass()
            test_instance.test_batch_gbp_enricher(enricher)
            test_instance.test_mock_data_generation(enricher)
            test_instance.test_integration_with_fuzzy_matcher(sample_business)
            test_instance.test_comprehensive_acceptance_criteria(
                enricher, sample_business
            )

            print()
            print("🎉 All Task 042 acceptance criteria tests pass!")
            print("   - GBP data extraction: ✓")
            print("   - Best match selection: ✓")
            print("   - Business data merge: ✓")
            print("   - Confidence scoring: ✓")

        except Exception as e:
            print(f"❌ Test failed: {e}")
            import traceback

            traceback.print_exc()

    # Run tests
    asyncio.run(run_tests())
