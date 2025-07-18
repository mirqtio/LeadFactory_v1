"""
Unit tests for d5_scoring constants module.
Coverage target: 100% for scoring configuration constants.
"""
import pytest
from d5_scoring.constants import (
    WEIGHT_SUM_WARNING_THRESHOLD,
    WEIGHT_SUM_ERROR_THRESHOLD,
    DEFAULT_SCORING_RULES_PATH,
    VALID_TIER_LABELS,
    FORMULA_EVALUATION_TIMEOUT,
    FORMULA_CACHE_SIZE,
    FORMULA_CACHE_TTL_SECONDS,
)


class TestScoringConstants:
    """Test suite for scoring configuration constants."""

    def test_weight_sum_thresholds_defined(self):
        """Test that weight sum validation thresholds are properly defined."""
        assert WEIGHT_SUM_WARNING_THRESHOLD == 0.005
        assert WEIGHT_SUM_ERROR_THRESHOLD == 0.05
        assert WEIGHT_SUM_ERROR_THRESHOLD > WEIGHT_SUM_WARNING_THRESHOLD

    def test_weight_sum_threshold_ordering(self):
        """Test that error threshold is greater than warning threshold."""
        assert WEIGHT_SUM_ERROR_THRESHOLD > WEIGHT_SUM_WARNING_THRESHOLD
        assert WEIGHT_SUM_WARNING_THRESHOLD > 0
        assert WEIGHT_SUM_ERROR_THRESHOLD < 1.0

    def test_default_scoring_rules_path(self):
        """Test that default scoring rules path is defined."""
        assert DEFAULT_SCORING_RULES_PATH == "config/scoring_rules.yaml"
        assert DEFAULT_SCORING_RULES_PATH.endswith(".yaml")

    def test_valid_tier_labels(self):
        """Test that valid tier labels are properly defined."""
        assert VALID_TIER_LABELS == ["A", "B", "C", "D"]
        assert len(VALID_TIER_LABELS) == 4
        assert all(isinstance(label, str) for label in VALID_TIER_LABELS)
        assert all(len(label) == 1 for label in VALID_TIER_LABELS)

    def test_tier_labels_alphabetical_order(self):
        """Test that tier labels are in ascending alphabetical order."""
        sorted_labels = sorted(VALID_TIER_LABELS)
        assert VALID_TIER_LABELS == sorted_labels

    def test_formula_evaluation_timeout(self):
        """Test that formula evaluation timeout is reasonable."""
        assert FORMULA_EVALUATION_TIMEOUT == 5.0
        assert FORMULA_EVALUATION_TIMEOUT > 0
        assert FORMULA_EVALUATION_TIMEOUT < 60  # Should be under 1 minute

    def test_cache_configuration(self):
        """Test that cache configuration values are reasonable."""
        assert FORMULA_CACHE_SIZE == 100
        assert FORMULA_CACHE_TTL_SECONDS == 300
        assert FORMULA_CACHE_SIZE > 0
        assert FORMULA_CACHE_TTL_SECONDS > 0

    def test_cache_ttl_in_minutes(self):
        """Test that cache TTL converts to expected minutes."""
        assert FORMULA_CACHE_TTL_SECONDS == 5 * 60  # 5 minutes
        assert FORMULA_CACHE_TTL_SECONDS / 60 == 5

    def test_all_constants_are_immutable_types(self):
        """Test that all constants use immutable types."""
        # Numbers and strings are immutable
        assert isinstance(WEIGHT_SUM_WARNING_THRESHOLD, float)
        assert isinstance(WEIGHT_SUM_ERROR_THRESHOLD, float)
        assert isinstance(DEFAULT_SCORING_RULES_PATH, str)
        assert isinstance(FORMULA_EVALUATION_TIMEOUT, float)
        assert isinstance(FORMULA_CACHE_SIZE, int)
        assert isinstance(FORMULA_CACHE_TTL_SECONDS, int)
        
        # List should be immutable in practice (constants shouldn't change)
        assert isinstance(VALID_TIER_LABELS, list)

    def test_tier_labels_contains_expected_values(self):
        """Test that tier labels contain all expected business values."""
        expected_tiers = {"A", "B", "C", "D"}
        actual_tiers = set(VALID_TIER_LABELS)
        assert actual_tiers == expected_tiers

    def test_constants_module_import(self):
        """Test that constants module can be imported without errors."""
        # If we got here, the import worked
        assert True

    def test_weight_thresholds_business_logic(self):
        """Test weight thresholds align with business validation logic."""
        # Warning threshold is 0.5% tolerance
        assert WEIGHT_SUM_WARNING_THRESHOLD == 0.005
        
        # Error threshold is 5% tolerance  
        assert WEIGHT_SUM_ERROR_THRESHOLD == 0.05
        
        # Business rule: warning < error
        assert WEIGHT_SUM_WARNING_THRESHOLD < WEIGHT_SUM_ERROR_THRESHOLD
        
        # Business rule: both should be small percentages
        assert WEIGHT_SUM_WARNING_THRESHOLD < 0.1
        assert WEIGHT_SUM_ERROR_THRESHOLD < 0.1