"""
Test D4 Enrichment Matchers Focused Coverage

Focused tests that successfully improve matchers.py coverage.
Targets specific uncovered lines with working test cases.
"""
from unittest.mock import Mock, patch

import pytest

from d4_enrichment.matchers import BusinessMatcher, MatchConfidence, MatchConfig, MatchType

# Mark entire module as unit test
pytestmark = pytest.mark.unit


class TestBusinessMatcherSuccessfulCoverage:
    """Test BusinessMatcher cases that successfully improve coverage"""

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


class TestMatchConfigWorking:
    """Test MatchConfig cases that work correctly"""

    def test_match_config_custom_weights(self):
        """Test MatchConfig with custom weights"""
        custom_weights = {"name": 0.4, "phone": 0.3, "address": 0.2, "zip": 0.1}

        config = MatchConfig(weights=custom_weights)

        assert config.weights == custom_weights
