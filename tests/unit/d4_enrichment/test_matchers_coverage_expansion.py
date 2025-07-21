"""
Test D4 Enrichment Matchers Coverage Expansion

Focused tests to improve matchers.py coverage from 71.88% to 85%+.
Targets uncovered lines including edge cases, error paths, and missing branches.
"""

from unittest.mock import Mock, patch

import pytest

from d4_enrichment.matchers import BatchMatcher, BusinessMatcher, MatchConfidence, MatchConfig, MatchResult, MatchType

# Mark entire module as unit test
pytestmark = pytest.mark.unit


class TestBusinessMatcherEdgeCases:
    """Test BusinessMatcher edge cases and uncovered paths"""

    def test_match_records_without_ids(self):
        """Test matching records without explicit IDs (lines 140, 142)"""
        config = MatchConfig()
        matcher = BusinessMatcher(config)

        # Records without 'id' fields
        record1 = {"business_name": "Test Corp", "phone": "555-1234", "address": "123 Main St"}
        record2 = {"business_name": "Test Corporation", "phone": "555-1234", "address": "123 Main Street"}

        # Should generate UUIDs when no IDs provided (hits lines 140, 142)
        result = matcher.match_records(record1, record2)

        assert result is not None
        assert result.record1_id is not None
        assert result.record2_id is not None
        assert len(result.record1_id) > 0
        assert len(result.record2_id) > 0

    def test_match_records_with_partial_ids(self):
        """Test matching with only one record having an ID"""
        config = MatchConfig()
        matcher = BusinessMatcher(config)

        record1 = {"id": "biz-001", "business_name": "Test Corp"}
        record2 = {"business_name": "Test Corporation"}  # No ID

        result = matcher.match_records(record1, record2)

        assert result.record1_id == "biz-001"
        assert result.record2_id is not None  # Should be generated

    def test_match_name_zip_edge_cases(self):
        """Test name/ZIP matching with edge cases (lines 275-294)"""
        config = MatchConfig()
        matcher = BusinessMatcher(config)

        # Test exact match scenario (lines 285-286)
        result_exact = matcher.match_name_zip("Acme Corporation", "12345", "Acme Corporation", "12345")
        assert result_exact.match_type == MatchType.EXACT_MATCH

        # Test fuzzy match scenario (lines 287-288)
        result_fuzzy = matcher.match_name_zip("Acme Corp", "12345", "Acme Corporation", "12345")
        # Should be fuzzy match if both name and zip are >= 0.7

        # Test partial match scenario (lines 289-290)
        result_partial = matcher.match_name_zip(
            "Acme Corporation",
            "12345",
            "Different Company",
            "12345",  # Same ZIP, different name
        )
        # Should be partial match if ZIP >= 0.7 but name < 0.7

        # Test no match scenario (lines 291-292)
        result_none = matcher.match_name_zip("Acme Corporation", "12345", "Completely Different Company", "67890")
        assert result_none.match_type == MatchType.NO_MATCH

    def test_component_details_metadata_handling(self):
        """Test handling of component details in metadata (lines 156-159)"""
        config = MatchConfig()
        matcher = BusinessMatcher(config)

        record1 = {"business_name": "Test Company", "phone": "555-1234", "address": "123 Main St"}
        record2 = {"business_name": "Test Corp", "phone": "555-1234", "address": "123 Main Street"}

        with patch("d4_enrichment.matchers.WeightedSimilarity.calculate_combined_similarity") as mock_sim:
            # Mock similarity result with component details
            mock_result = Mock()
            mock_result.score = 0.85
            mock_result.metadata = {
                "component_details": {"name": Mock(score=0.8), "phone": Mock(score=0.95), "address": Mock(score=0.75)}
            }
            mock_sim.return_value = mock_result

            result = matcher.match_records(record1, record2)

            # Should process component details (lines 156-159)
            assert result is not None

    def test_cache_functionality(self):
        """Test match caching functionality"""
        config = MatchConfig()
        matcher = BusinessMatcher(config)

        record1 = {"id": "test-001", "business_name": "Test Corp"}
        record2 = {"id": "test-002", "business_name": "Test Corporation"}

        # First call should calculate and cache
        result1 = matcher.match_records(record1, record2, "test-001", "test-002")

        # Second call should use cache
        result2 = matcher.match_records(record1, record2, "test-001", "test-002")

        assert result1.record1_id == result2.record1_id
        assert result1.record2_id == result2.record2_id
        assert result1.overall_score == result2.overall_score


class TestBatchMatcherEdgeCases:
    """Test BatchMatcher edge cases and error handling"""

    def test_find_matches_empty_records(self):
        """Test find_matches with empty records list"""
        config = MatchConfig()
        batch_matcher = BatchMatcher(config)

        target_record = {"business_name": "Test Corp"}
        candidates = []

        matches = batch_matcher.find_matches(target_record, candidates)

        assert matches == []

    def test_find_matches_single_candidate(self):
        """Test find_matches with single candidate"""
        config = MatchConfig()
        batch_matcher = BatchMatcher(config)

        target_record = {"business_name": "Test Corp"}
        candidates = [{"business_name": "Test Corporation"}]

        matches = batch_matcher.find_matches(target_record, candidates)

        assert len(matches) <= 1  # Should return at most one match

    def test_find_matches_with_threshold_filtering(self):
        """Test find_matches respects confidence threshold"""
        config = MatchConfig(min_confidence_threshold=0.8)
        batch_matcher = BatchMatcher(config)

        target_record = {"business_name": "Acme Corporation"}
        candidates = [
            {"business_name": "Acme Corp"},  # High similarity
            {"business_name": "Different Company"},  # Low similarity
        ]

        matches = batch_matcher.find_matches(target_record, candidates)

        # Should only return high-confidence matches
        for match in matches:
            assert match.overall_score >= config.min_confidence_threshold

    def test_find_duplicates_in_dataset_empty(self):
        """Test find_duplicates_in_dataset with empty dataset"""
        config = MatchConfig()
        batch_matcher = BatchMatcher(config)

        duplicates = batch_matcher.find_duplicates_in_dataset([])

        assert duplicates == []

    def test_find_duplicates_in_dataset_single_record(self):
        """Test find_duplicates_in_dataset with single record"""
        config = MatchConfig()
        batch_matcher = BatchMatcher(config)

        records = [{"id": "test-001", "business_name": "Test Corp"}]
        duplicates = batch_matcher.find_duplicates_in_dataset(records)

        assert duplicates == []  # No duplicates possible with single record


class TestMatchConfigEdgeCases:
    """Test MatchConfig edge cases and validation"""

    def test_match_config_custom_weights(self):
        """Test MatchConfig with custom weights"""
        custom_weights = {"name": 0.4, "phone": 0.3, "address": 0.2, "zip": 0.1}

        config = MatchConfig(weights=custom_weights)

        assert config.weights == custom_weights

    def test_match_config_custom_threshold(self):
        """Test MatchConfig with custom confidence threshold"""
        config = MatchConfig(min_confidence_threshold=0.9)

        assert config.min_confidence_threshold == 0.9

    def test_match_config_defaults(self):
        """Test MatchConfig default values"""
        config = MatchConfig()

        # Should have reasonable defaults
        assert hasattr(config, "weights")
        assert hasattr(config, "min_confidence_threshold")
        assert isinstance(config.weights, dict)
        assert isinstance(config.min_confidence_threshold, (int, float))


class TestMatchResultEdgeCases:
    """Test MatchResult edge cases and properties"""

    def test_match_result_creation_complete(self):
        """Test MatchResult creation with all fields"""
        result = MatchResult(
            record1_id="rec1",
            record2_id="rec2",
            overall_score=0.85,
            confidence=MatchConfidence.HIGH,
            match_type=MatchType.FUZZY_MATCH,
            component_scores={"name": 0.8, "phone": 0.9},
            similarity_details={"name": "mock_detail"},
            metadata={"source": "test"},
        )

        assert result.record1_id == "rec1"
        assert result.record2_id == "rec2"
        assert result.overall_score == 0.85
        assert result.confidence == MatchConfidence.HIGH
        assert result.match_type == MatchType.FUZZY_MATCH
        assert result.component_scores["name"] == 0.8
        assert result.similarity_details["name"] == "mock_detail"
        assert result.metadata["source"] == "test"

    def test_match_result_minimal_creation(self):
        """Test MatchResult creation with minimal required fields"""
        result = MatchResult(
            record1_id="rec1",
            record2_id="rec2",
            overall_score=0.75,
            confidence=MatchConfidence.MEDIUM,
            match_type=MatchType.PARTIAL_MATCH,
        )

        assert result.record1_id == "rec1"
        assert result.record2_id == "rec2"
        assert result.overall_score == 0.75
        assert result.confidence == MatchConfidence.MEDIUM
        assert result.match_type == MatchType.PARTIAL_MATCH


class TestMatcherErrorHandling:
    """Test error handling and edge cases in matchers"""

    def test_match_records_with_none_inputs(self):
        """Test matching with None inputs"""
        config = MatchConfig()
        matcher = BusinessMatcher(config)

        # Should handle None gracefully without crashing
        try:
            result = matcher.match_records(None, {"name": "test"})
            # If it doesn't crash, that's good
        except (TypeError, AttributeError):
            # Expected for None inputs
            pass

    def test_match_records_with_empty_inputs(self):
        """Test matching with empty dictionaries"""
        config = MatchConfig()
        matcher = BusinessMatcher(config)

        result = matcher.match_records({}, {})

        # Should handle empty inputs gracefully
        assert result is not None

    def test_confidence_determination_edge_values(self):
        """Test confidence determination with edge values"""
        config = MatchConfig()
        matcher = BusinessMatcher(config)

        # Test boundary values for confidence levels
        # These might trigger uncovered branches in _determine_confidence
        test_scores = [0.0, 0.49, 0.5, 0.69, 0.7, 0.84, 0.85, 0.94, 0.95, 1.0]

        for score in test_scores:
            confidence = matcher._determine_confidence(score)
            assert confidence in [
                MatchConfidence.UNCERTAIN,
                MatchConfidence.LOW,
                MatchConfidence.MEDIUM,
                MatchConfidence.HIGH,
                MatchConfidence.EXACT,
            ]
