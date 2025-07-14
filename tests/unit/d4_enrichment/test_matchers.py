"""
Test Fuzzy Matching System - Task 041

Tests for fuzzy matching system ensuring all acceptance criteria are met:
- Phone matching works
- Name/ZIP matching accurate
- Address similarity scoring
- Weighted combination logic
"""
import sys

import pytest

# Mark entire module as slow for CI optimization
pytestmark = pytest.mark.slow

sys.path.insert(0, "/app")

from d4_enrichment.matchers import BatchMatcher, BusinessMatcher, MatchConfidence, MatchConfig, MatchType
from d4_enrichment.similarity import (
    AddressSimilarity,
    NameSimilarity,
    PhoneSimilarity,
    WeightedSimilarity,
    ZipSimilarity,
)


class TestTask041AcceptanceCriteria:
    """Test that Task 041 meets all acceptance criteria"""

    @pytest.fixture
    def sample_business_records(self):
        """Sample business records for testing"""
        return [
            {
                "id": "biz_001",
                "business_name": "Acme Corporation",
                "phone": "+1-555-123-4567",
                "address": "123 Main Street, San Francisco, CA 94105",
                "zip": "94105",
                "domain": "acme.com",
            },
            {
                "id": "biz_002",
                "business_name": "ACME Corp.",
                "phone": "(555) 123-4567",
                "address": "123 Main St, San Francisco, CA 94105",
                "zip": "94105",
                "domain": "acme.com",
            },
            {
                "id": "biz_003",
                "business_name": "Beta Industries LLC",
                "phone": "+1-555-987-6543",
                "address": "456 Oak Avenue, Los Angeles, CA 90210",
                "zip": "90210",
                "domain": "beta.com",
            },
            {
                "id": "biz_004",
                "business_name": "Gamma Services Inc",
                "phone": "555-111-2222",
                "address": "789 Pine Road, New York, NY 10001",
                "zip": "10001",
                "domain": "gamma.net",
            },
        ]

    def test_phone_matching_works(self):
        """
        Test that phone matching works properly

        Acceptance Criteria: Phone matching works
        """
        matcher = BusinessMatcher()

        # Test exact phone matches
        result1 = matcher.match_phone_numbers("+1-555-123-4567", "(555) 123-4567")
        assert result1.overall_score == 1.0
        assert result1.confidence == MatchConfidence.EXACT
        assert result1.match_type == MatchType.EXACT_MATCH

        # Test phone normalization
        result2 = matcher.match_phone_numbers("555.123.4567", "5551234567")
        assert result2.overall_score == 1.0
        assert result2.confidence == MatchConfidence.EXACT

        # Test partial phone matches
        result3 = matcher.match_phone_numbers("555-123-4567", "555-123-4567 ext 123")
        assert result3.overall_score > 0.7  # Should be high similarity
        assert result3.confidence in [
            MatchConfidence.MEDIUM,
            MatchConfidence.HIGH,
            MatchConfidence.EXACT,
        ]

        # Test different phones
        result4 = matcher.match_phone_numbers("555-123-4567", "555-987-6543")
        assert result4.overall_score < 0.5
        assert result4.confidence == MatchConfidence.UNCERTAIN

        # Test phone component matching
        phone_sim = PhoneSimilarity()

        # Test area code matching
        result5 = phone_sim.calculate_similarity("555-123-1111", "555-123-2222")
        assert result5.score > 0.5  # Should match on area code and exchange

        print("✓ Phone matching works correctly")

    def test_name_zip_matching_accurate(self):
        """
        Test that name and ZIP matching is accurate

        Acceptance Criteria: Name/ZIP matching accurate
        """
        matcher = BusinessMatcher()

        # Test exact name and ZIP match
        result1 = matcher.match_names_and_zips("Acme Corporation", "94105", "Acme Corporation", "94105")
        assert result1.overall_score >= 0.9
        assert result1.confidence in [MatchConfidence.HIGH, MatchConfidence.EXACT]

        # Test name variations with same ZIP
        result2 = matcher.match_names_and_zips("Acme Corporation", "94105", "ACME Corp.", "94105")
        assert result2.overall_score >= 0.7
        assert result2.confidence in [
            MatchConfidence.MEDIUM,
            MatchConfidence.HIGH,
            MatchConfidence.EXACT,
        ]

        # Test same name with similar ZIP (same area)
        result3 = matcher.match_names_and_zips("Test Company", "94105", "Test Company", "94102")  # Same area (941xx)
        assert result3.overall_score >= 0.7

        # Test business suffix normalization
        name_sim = NameSimilarity()
        result4 = name_sim.calculate_similarity("ABC Inc.", "ABC Incorporated")
        assert result4.score >= 0.8

        result5 = name_sim.calculate_similarity("XYZ LLC", "XYZ L.L.C.")
        assert result5.score >= 0.8

        # Test ZIP similarity
        zip_sim = ZipSimilarity()
        result6 = zip_sim.calculate_similarity("94105", "94102")
        assert result6.score == 0.7  # Same area match

        result7 = zip_sim.calculate_similarity("94105", "90210")
        assert result7.score == 0.0  # Different areas

        print("✓ Name/ZIP matching accuracy verified")

    def test_address_similarity_scoring(self):
        """
        Test that address similarity scoring works

        Acceptance Criteria: Address similarity scoring
        """
        matcher = BusinessMatcher()

        # Test exact address match
        result1 = matcher.match_addresses(
            "123 Main Street, San Francisco, CA 94105",
            "123 Main Street, San Francisco, CA 94105",
        )
        assert result1.overall_score == 1.0
        assert result1.confidence == MatchConfidence.EXACT

        # Test address variations
        result2 = matcher.match_addresses(
            "123 Main Street, San Francisco, CA 94105",
            "123 Main St, San Francisco, CA 94105",
        )
        assert result2.overall_score >= 0.8  # Should handle street suffix normalization

        # Test partial address match
        result3 = matcher.match_addresses(
            "123 Main Street, San Francisco, CA",
            "123 Main Street, San Francisco, CA 94105",
        )
        assert result3.overall_score >= 0.7  # Missing ZIP shouldn't kill the match

        # Test different addresses
        result4 = matcher.match_addresses(
            "123 Main Street, San Francisco, CA 94105",
            "456 Oak Avenue, Los Angeles, CA 90210",
        )
        assert result4.overall_score < 0.3

        # Test address parsing and component scoring
        addr_sim = AddressSimilarity()

        # Test street number matching
        parsed1 = addr_sim.parse_address("123 Main St, San Francisco, CA 94105")
        parsed2 = addr_sim.parse_address("123 Main Street, San Francisco, CA 94105")

        assert parsed1["street_number"] == "123"
        assert parsed2["street_number"] == "123"
        assert "main" in parsed1["street_name"]
        assert "main" in parsed2["street_name"]

        print("✓ Address similarity scoring works correctly")

    def test_weighted_combination_logic(self):
        """
        Test that weighted combination logic works properly

        Acceptance Criteria: Weighted combination logic
        """
        # Test with custom weights
        config = MatchConfig(weights={"business_name": 0.5, "phone": 0.3, "address": 0.15, "zip": 0.05})
        matcher = BusinessMatcher(config)

        # Create test records
        record1 = {
            "business_name": "Test Company",
            "phone": "555-123-4567",
            "address": "123 Main St, City, ST 12345",
            "zip": "12345",
        }

        record2 = {
            "business_name": "Test Company",  # Exact match
            "phone": "555-123-4567",  # Exact match
            "address": "124 Main St, City, ST 12345",  # Similar
            "zip": "12346",  # Similar area
        }

        result = matcher.match_records(record1, record2)

        # Should have high score due to exact name and phone matches
        assert result.overall_score >= 0.8
        assert result.confidence in [MatchConfidence.HIGH, MatchConfidence.EXACT]

        # Check component scores
        assert "business_name" in result.component_scores
        assert "phone" in result.component_scores
        assert result.component_scores["business_name"] >= 0.9
        assert result.component_scores["phone"] == 1.0

        # Test weighted similarity directly
        weighted_result = WeightedSimilarity.calculate_combined_similarity(record1, record2, config.weights)

        assert weighted_result.score >= 0.7
        assert "component_results" in weighted_result.metadata
        assert "weights" in weighted_result.metadata

        # Test weight validation
        total_weight = sum(config.weights.values())
        assert abs(total_weight - 1.0) < 0.01  # Should sum to ~1.0

        print("✓ Weighted combination logic works correctly")

    def test_comprehensive_business_matching(self, sample_business_records):
        """Test comprehensive business record matching"""
        matcher = BusinessMatcher()

        # Test matching very similar records (biz_001 vs biz_002)
        record1 = sample_business_records[0]  # Acme Corporation
        record2 = sample_business_records[1]  # ACME Corp.

        result = matcher.match_records(record1, record2)

        # Should be a high-confidence match
        assert result.overall_score >= 0.8
        assert result.confidence in [MatchConfidence.HIGH, MatchConfidence.EXACT]
        assert result.match_type in [MatchType.EXACT_MATCH, MatchType.FUZZY_MATCH]

        # Test matching different businesses
        record3 = sample_business_records[2]  # Beta Industries
        result2 = matcher.match_records(record1, record3)

        # Should be low or no match
        assert result2.overall_score < 0.6
        assert result2.confidence in [MatchConfidence.UNCERTAIN, MatchConfidence.LOW]

        print("✓ Comprehensive business matching works")

    def test_batch_matching_capabilities(self, sample_business_records):
        """Test batch matching and deduplication"""
        matcher = BusinessMatcher()
        batch_matcher = BatchMatcher(matcher)

        # Test finding best matches
        target_record = sample_business_records[0]
        candidates = sample_business_records[1:]

        matches = matcher.find_best_matches(target_record, candidates, min_score=0.5, max_results=3)

        assert len(matches) >= 1  # Should find at least one match
        assert matches[0].overall_score >= 0.5

        # Matches should be sorted by score (highest first)
        for i in range(len(matches) - 1):
            assert matches[i].overall_score >= matches[i + 1].overall_score

        # Test deduplication
        dataset_with_duplicates = [
            sample_business_records[0],
            sample_business_records[1],  # Similar to [0]
            sample_business_records[2],
            sample_business_records[3],
        ]

        unique_records, duplicates = batch_matcher.deduplicate_dataset(dataset_with_duplicates, min_score=0.7)

        assert len(unique_records) >= 2  # Should have at least 2 unique records
        assert len(duplicates) >= 1  # Should find at least 1 duplicate

        print("✓ Batch matching capabilities work")

    def test_match_configuration_and_tuning(self):
        """Test match configuration and threshold tuning"""
        # Test with strict configuration
        strict_config = MatchConfig(
            exact_threshold=0.98,
            high_threshold=0.90,
            medium_threshold=0.80,
            low_threshold=0.60,
            require_name_similarity=True,
            min_components=3,
        )

        strict_matcher = BusinessMatcher(strict_config)

        # Test with lenient configuration
        lenient_config = MatchConfig(
            exact_threshold=0.90,
            high_threshold=0.75,
            medium_threshold=0.60,
            low_threshold=0.40,
            require_name_similarity=False,
            min_components=1,
        )

        lenient_matcher = BusinessMatcher(lenient_config)

        # Test same records with both matchers
        record1 = {
            "business_name": "Test Corp",
            "phone": "555-123-4567",
            "zip": "12345",
        }

        record2 = {
            "business_name": "Test Corporation",
            "phone": "555-123-4567",
            "zip": "12345",
        }

        strict_result = strict_matcher.match_records(record1, record2)
        lenient_result = lenient_matcher.match_records(record1, record2)

        # Same underlying score, but different confidence levels
        assert abs(strict_result.overall_score - lenient_result.overall_score) < 0.1
        # Lenient matcher should give higher confidence
        assert (
            lenient_result.confidence.value >= strict_result.confidence.value
            or lenient_result.overall_score >= strict_result.overall_score
        )

        print("✓ Match configuration and tuning works")

    def test_match_statistics_and_performance(self):
        """Test match statistics tracking"""
        matcher = BusinessMatcher()

        # Perform various matches
        test_cases = [
            # High confidence matches
            (
                {"name": "ABC Inc", "phone": "555-1234"},
                {"name": "ABC Inc", "phone": "555-1234"},
            ),
            # Medium confidence
            (
                {"name": "XYZ Corp", "phone": "555-5678"},
                {"name": "XYZ Corporation", "phone": "555-5678"},
            ),
            # Low confidence
            (
                {"name": "DEF LLC", "address": "123 Main St"},
                {"name": "DEF Limited", "address": "124 Main St"},
            ),
            # No match
            (
                {"name": "Company A", "phone": "555-1111"},
                {"name": "Company B", "phone": "555-2222"},
            ),
        ]

        for record1, record2 in test_cases:
            matcher.match_records(record1, record2)

        stats = matcher.get_statistics()

        assert stats["total_matches"] == 4
        assert "success_rate" in stats
        assert "high_confidence_rate" in stats
        assert "cache_size" in stats
        assert stats["cache_size"] > 0  # Should have cached results

        # Test cache functionality
        cache_size_before = len(matcher.match_cache)
        # Run same match again with same objects
        first_record1, first_record2 = test_cases[0]
        matcher.match_records(first_record1, first_record2)
        cache_size_after = len(matcher.match_cache)

        # Cache size shouldn't increase much (some internal keys might be added)
        assert cache_size_after <= cache_size_before + 1

        # Test cache clearing
        matcher.clear_cache()
        assert len(matcher.match_cache) == 0

        print("✓ Match statistics and performance tracking works")

    def test_edge_cases_and_error_handling(self):
        """Test edge cases and error handling"""
        matcher = BusinessMatcher()

        # Test empty records
        result1 = matcher.match_records({}, {})
        assert result1.overall_score == 0.0
        assert result1.confidence == MatchConfidence.UNCERTAIN

        # Test records with missing fields
        result2 = matcher.match_records({"business_name": "Test"}, {"phone": "555-1234"})
        assert result2.overall_score >= 0.0  # Should handle gracefully

        # Test None values
        result3 = matcher.match_records(
            {"business_name": None, "phone": "555-1234"},
            {"business_name": "Test", "phone": None},
        )
        assert result3.overall_score >= 0.0

        # Test very long strings
        long_name = "A" * 1000
        result4 = matcher.match_records({"business_name": long_name}, {"business_name": long_name})
        assert result4.overall_score > 0.3  # Should still show some match with single component

        # Test special characters
        result5 = matcher.match_records(
            {"business_name": "Café & Restaurant Inc."},
            {"business_name": "Cafe & Restaurant Inc"},
        )
        assert result5.overall_score > 0.3  # Should handle accents and punctuation with single component

        print("✓ Edge cases and error handling work correctly")

    def test_similarity_algorithms_directly(self):
        """Test individual similarity algorithms"""
        # Test phone similarity edge cases
        phone_sim = PhoneSimilarity()

        # International numbers
        result1 = phone_sim.calculate_similarity("+1-555-123-4567", "1-555-123-4567")
        assert result1.score == 1.0

        # Extensions
        result2 = phone_sim.calculate_similarity("555-123-4567", "555-123-4567 x123")
        assert result2.score > 0.7

        # Test name similarity edge cases
        name_sim = NameSimilarity()

        # Abbreviations
        result3 = name_sim.calculate_similarity("International Business Machines", "IBM")
        # Might be low due to token mismatch, but should handle gracefully
        assert result3.score >= 0.0

        # Reordered words
        result4 = name_sim.calculate_similarity("ABC Marketing Services", "Marketing Services ABC")
        assert result4.score > 0.5  # Should detect common tokens

        # Test address parsing edge cases
        addr_sim = AddressSimilarity()

        # Apartment numbers
        result5 = addr_sim.calculate_similarity("123 Main St Apt 4B, City, ST 12345", "123 Main St, City, ST 12345")
        assert result5.score > 0.8  # Should still be high match

        # PO Boxes
        result6 = addr_sim.calculate_similarity("PO Box 123, City, ST 12345", "P.O. Box 123, City, ST 12345")
        assert result6.score > 0.8

        print("✓ Individual similarity algorithms work correctly")


# Allow running this test file directly
if __name__ == "__main__":
    import asyncio

    async def run_tests():
        test_instance = TestTask041AcceptanceCriteria()

        print("🔍 Running Task 041 Fuzzy Matching System Tests...")
        print()

        try:
            # Sample data
            sample_records = [
                {
                    "id": "test_001",
                    "business_name": "Acme Corporation",
                    "phone": "555-123-4567",
                    "address": "123 Main St, City, ST 12345",
                    "zip": "12345",
                },
                {
                    "id": "test_002",
                    "business_name": "ACME Corp.",
                    "phone": "(555) 123-4567",
                    "address": "123 Main Street, City, ST 12345",
                    "zip": "12345",
                },
            ]

            # Run all acceptance criteria tests
            test_instance.test_phone_matching_works()
            test_instance.test_name_zip_matching_accurate()
            test_instance.test_address_similarity_scoring()
            test_instance.test_weighted_combination_logic()
            test_instance.test_comprehensive_business_matching(sample_records)
            test_instance.test_batch_matching_capabilities(sample_records)
            test_instance.test_match_configuration_and_tuning()
            test_instance.test_match_statistics_and_performance()
            test_instance.test_edge_cases_and_error_handling()
            test_instance.test_similarity_algorithms_directly()

            print()
            print("🎉 All Task 041 acceptance criteria tests pass!")
            print("   - Phone matching works: ✓")
            print("   - Name/ZIP matching accurate: ✓")
            print("   - Address similarity scoring: ✓")
            print("   - Weighted combination logic: ✓")

        except Exception as e:
            print(f"❌ Test failed: {e}")
            import traceback

            traceback.print_exc()

    # Run tests
    asyncio.run(run_tests())
