"""
Unit tests for d5_scoring types module.
Coverage target: 100% for type definitions and enumerations.
"""
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from d5_scoring.types import ScoreComponent, ScoringStatus, ScoringTier, ScoringVersion


class TestScoringTier:
    """Test suite for ScoringTier enumeration."""

    def test_tier_values_defined(self):
        """Test that all tier values are properly defined."""
        assert ScoringTier.PLATINUM.value == "platinum"
        assert ScoringTier.GOLD.value == "gold"
        assert ScoringTier.SILVER.value == "silver"
        assert ScoringTier.BRONZE.value == "bronze"
        assert ScoringTier.BASIC.value == "basic"
        assert ScoringTier.UNQUALIFIED.value == "unqualified"

    def test_tier_enumeration_complete(self):
        """Test that tier enumeration includes expected values."""
        tier_values = [tier.value for tier in ScoringTier]
        expected_values = ["platinum", "gold", "silver", "bronze", "basic", "unqualified"]

        assert len(tier_values) == len(expected_values)
        for expected in expected_values:
            assert expected in tier_values

    @patch("logging.warning")
    def test_from_score_platinum_range(self, mock_warning):
        """Test from_score returns PLATINUM for high scores."""
        assert ScoringTier.from_score(90.0) == ScoringTier.PLATINUM
        assert ScoringTier.from_score(100.0) == ScoringTier.PLATINUM
        assert ScoringTier.from_score(80.0) == ScoringTier.PLATINUM

        # Verify deprecation warning is logged
        mock_warning.assert_called()

    @patch("logging.warning")
    def test_from_score_gold_range(self, mock_warning):
        """Test from_score returns GOLD for mid-high scores."""
        assert ScoringTier.from_score(75.0) == ScoringTier.GOLD
        assert ScoringTier.from_score(60.0) == ScoringTier.GOLD
        assert ScoringTier.from_score(65.0) == ScoringTier.GOLD

        mock_warning.assert_called()

    @patch("logging.warning")
    def test_from_score_silver_range(self, mock_warning):
        """Test from_score returns SILVER for mid scores."""
        assert ScoringTier.from_score(50.0) == ScoringTier.SILVER
        assert ScoringTier.from_score(40.0) == ScoringTier.SILVER
        assert ScoringTier.from_score(45.0) == ScoringTier.SILVER

        mock_warning.assert_called()

    @patch("logging.warning")
    def test_from_score_bronze_range(self, mock_warning):
        """Test from_score returns BRONZE for low scores."""
        assert ScoringTier.from_score(30.0) == ScoringTier.BRONZE
        assert ScoringTier.from_score(0.0) == ScoringTier.BRONZE
        assert ScoringTier.from_score(39.9) == ScoringTier.BRONZE

        mock_warning.assert_called()

    @patch("logging.warning")
    def test_from_score_edge_cases(self, mock_warning):
        """Test from_score edge cases and boundaries."""
        # Boundary cases
        assert ScoringTier.from_score(79.9) == ScoringTier.GOLD
        assert ScoringTier.from_score(59.9) == ScoringTier.SILVER
        assert ScoringTier.from_score(39.9) == ScoringTier.BRONZE

        # Negative scores
        assert ScoringTier.from_score(-10.0) == ScoringTier.BRONZE

        mock_warning.assert_called()

    @patch("logging.warning")
    def test_min_score_deprecated(self, mock_warning):
        """Test min_score property logs deprecation warning."""
        tier = ScoringTier.PLATINUM
        result = tier.min_score

        assert result == 0.0  # Default value
        mock_warning.assert_called_with("ScoringTier.min_score is deprecated. Use YAML configuration instead.")

    @patch("logging.warning")
    def test_max_score_deprecated(self, mock_warning):
        """Test max_score property logs deprecation warning."""
        tier = ScoringTier.GOLD
        result = tier.max_score

        assert result == 100.0  # Default value
        mock_warning.assert_called_with("ScoringTier.max_score is deprecated. Use YAML configuration instead.")

    def test_tier_string_representation(self):
        """Test tier string representation."""
        assert str(ScoringTier.PLATINUM).endswith("PLATINUM")
        assert str(ScoringTier.GOLD).endswith("GOLD")


class TestScoreComponent:
    """Test suite for ScoreComponent enumeration."""

    def test_component_values_defined(self):
        """Test that all component values are properly defined."""
        # Company data quality
        assert ScoreComponent.COMPANY_INFO.value == "company_info"
        assert ScoreComponent.CONTACT_INFO.value == "contact_info"
        assert ScoreComponent.LOCATION_DATA.value == "location_data"

        # Business validation
        assert ScoreComponent.BUSINESS_VALIDATION.value == "business_validation"
        assert ScoreComponent.ONLINE_PRESENCE.value == "online_presence"
        assert ScoreComponent.SOCIAL_SIGNALS.value == "social_signals"

        # Financial indicators
        assert ScoreComponent.REVENUE_INDICATORS.value == "revenue_indicators"
        assert ScoreComponent.EMPLOYEE_COUNT.value == "employee_count"
        assert ScoreComponent.FUNDING_STATUS.value == "funding_status"

        # Industry and market
        assert ScoreComponent.INDUSTRY_RELEVANCE.value == "industry_relevance"
        assert ScoreComponent.MARKET_POSITION.value == "market_position"
        assert ScoreComponent.GROWTH_INDICATORS.value == "growth_indicators"

        # Engagement potential
        assert ScoreComponent.TECHNOLOGY_STACK.value == "technology_stack"
        assert ScoreComponent.DECISION_MAKER_ACCESS.value == "decision_maker_access"
        assert ScoreComponent.TIMING_INDICATORS.value == "timing_indicators"

    def test_component_enumeration_complete(self):
        """Test that component enumeration includes all expected values."""
        component_values = [comp.value for comp in ScoreComponent]
        expected_values = [
            # Company data quality
            "company_info",
            "contact_info",
            "location_data",
            # Business validation
            "business_validation",
            "online_presence",
            "social_signals",
            # Financial indicators
            "revenue_indicators",
            "employee_count",
            "funding_status",
            # Industry and market
            "industry_relevance",
            "market_position",
            "growth_indicators",
            # Engagement potential
            "technology_stack",
            "decision_maker_access",
            "timing_indicators",
        ]

        assert len(component_values) == len(expected_values)
        for expected in expected_values:
            assert expected in component_values

    @patch("logging.warning")
    def test_max_points_deprecated(self, mock_warning):
        """Test max_points property logs deprecation warning."""
        component = ScoreComponent.COMPANY_INFO
        result = component.max_points

        assert result == 10.0  # Default value
        mock_warning.assert_called()
        warning_call = mock_warning.call_args[0][0]
        assert "max_points is deprecated" in warning_call
        assert "company_info" in warning_call

    @patch("logging.warning")
    def test_description_deprecated(self, mock_warning):
        """Test description property logs deprecation warning."""
        component = ScoreComponent.ONLINE_PRESENCE
        result = component.description

        assert result == "Score component: online_presence"
        mock_warning.assert_called()
        warning_call = mock_warning.call_args[0][0]
        assert "description is deprecated" in warning_call
        assert "online_presence" in warning_call

    def test_component_categories_coverage(self):
        """Test that components cover all major categories."""
        # Verify we have components from each major category
        company_data = [ScoreComponent.COMPANY_INFO, ScoreComponent.CONTACT_INFO, ScoreComponent.LOCATION_DATA]

        business_validation = [
            ScoreComponent.BUSINESS_VALIDATION,
            ScoreComponent.ONLINE_PRESENCE,
            ScoreComponent.SOCIAL_SIGNALS,
        ]

        financial = [ScoreComponent.REVENUE_INDICATORS, ScoreComponent.EMPLOYEE_COUNT, ScoreComponent.FUNDING_STATUS]

        industry = [ScoreComponent.INDUSTRY_RELEVANCE, ScoreComponent.MARKET_POSITION, ScoreComponent.GROWTH_INDICATORS]

        engagement = [
            ScoreComponent.TECHNOLOGY_STACK,
            ScoreComponent.DECISION_MAKER_ACCESS,
            ScoreComponent.TIMING_INDICATORS,
        ]

        # Verify each category has components
        assert len(company_data) == 3
        assert len(business_validation) == 3
        assert len(financial) == 3
        assert len(industry) == 3
        assert len(engagement) == 3


class TestScoringStatus:
    """Test suite for ScoringStatus enumeration."""

    def test_status_values_defined(self):
        """Test that all status values are properly defined."""
        assert ScoringStatus.PENDING.value == "pending"
        assert ScoringStatus.IN_PROGRESS.value == "in_progress"
        assert ScoringStatus.COMPLETED.value == "completed"
        assert ScoringStatus.FAILED.value == "failed"
        assert ScoringStatus.EXPIRED.value == "expired"
        assert ScoringStatus.MANUAL_REVIEW.value == "manual_review"

    def test_status_enumeration_complete(self):
        """Test that status enumeration includes all expected values."""
        status_values = [status.value for status in ScoringStatus]
        expected_values = ["pending", "in_progress", "completed", "failed", "expired", "manual_review"]

        assert len(status_values) == len(expected_values)
        for expected in expected_values:
            assert expected in status_values


class TestScoringVersion:
    """Test suite for ScoringVersion dataclass."""

    def test_scoring_version_creation(self):
        """Test ScoringVersion creation with all fields."""
        created_at = datetime(2025, 1, 15, 12, 0, 0)
        version = ScoringVersion(
            version="v2.1.0",
            created_at=created_at,
            algorithm_version="advanced_v2",
            weights_version="enhanced_v1",
            data_schema_version="2025_v2",
            changelog="Enhanced scoring algorithm",
            deprecated=False,
        )

        assert version.version == "v2.1.0"
        assert version.created_at == created_at
        assert version.algorithm_version == "advanced_v2"
        assert version.weights_version == "enhanced_v1"
        assert version.data_schema_version == "2025_v2"
        assert version.changelog == "Enhanced scoring algorithm"
        assert version.deprecated is False

    def test_scoring_version_minimal_creation(self):
        """Test ScoringVersion creation with minimal fields."""
        created_at = datetime(2025, 1, 15, 12, 0, 0)
        version = ScoringVersion(
            version="v1.0.0",
            created_at=created_at,
            algorithm_version="baseline_v1",
            weights_version="standard_v1",
            data_schema_version="2025_v1",
        )

        assert version.changelog is None
        assert version.deprecated is False

    def test_post_init_auto_version(self):
        """Test __post_init__ generates version when empty."""
        created_at = datetime(2025, 1, 15, 12, 30, 45)
        version = ScoringVersion(
            version="",  # Empty version
            created_at=created_at,
            algorithm_version="test_v1",
            weights_version="test_v1",
            data_schema_version="test_v1",
        )

        # Should auto-generate version from timestamp
        assert version.version == "v20250115_123045"

    def test_post_init_preserves_existing_version(self):
        """Test __post_init__ preserves non-empty version."""
        created_at = datetime(2025, 1, 15, 12, 30, 45)
        version = ScoringVersion(
            version="v3.0.0",  # Non-empty version
            created_at=created_at,
            algorithm_version="test_v1",
            weights_version="test_v1",
            data_schema_version="test_v1",
        )

        # Should preserve existing version
        assert version.version == "v3.0.0"

    def test_current_class_method(self):
        """Test current() class method creates default version."""
        version = ScoringVersion.current()

        assert version.version == "v1.0.0"
        assert version.algorithm_version == "baseline_v1"
        assert version.weights_version == "standard_v1"
        assert version.data_schema_version == "2025_v1"
        assert version.changelog == "Initial scoring system implementation"
        assert version.deprecated is False

        # created_at should be recent (within last minute)
        now = datetime.utcnow()
        time_diff = (now - version.created_at).total_seconds()
        assert time_diff < 60

    def test_is_compatible_with_same_major(self):
        """Test compatibility with same major version."""
        version1 = ScoringVersion(
            version="v2.1.0",
            created_at=datetime.utcnow(),
            algorithm_version="test",
            weights_version="test",
            data_schema_version="test",
        )

        version2 = ScoringVersion(
            version="v2.3.5",
            created_at=datetime.utcnow(),
            algorithm_version="test",
            weights_version="test",
            data_schema_version="test",
        )

        assert version1.is_compatible_with(version2)
        assert version2.is_compatible_with(version1)

    def test_is_compatible_with_different_major(self):
        """Test incompatibility with different major version."""
        version1 = ScoringVersion(
            version="v1.0.0",
            created_at=datetime.utcnow(),
            algorithm_version="test",
            weights_version="test",
            data_schema_version="test",
        )

        version2 = ScoringVersion(
            version="v2.0.0",
            created_at=datetime.utcnow(),
            algorithm_version="test",
            weights_version="test",
            data_schema_version="test",
        )

        assert not version1.is_compatible_with(version2)
        assert not version2.is_compatible_with(version1)

    def test_is_compatible_with_invalid_version(self):
        """Test compatibility check with invalid version format."""
        version1 = ScoringVersion(
            version="v1.0.0",
            created_at=datetime.utcnow(),
            algorithm_version="test",
            weights_version="test",
            data_schema_version="test",
        )

        version2 = ScoringVersion(
            version="invalid_version",
            created_at=datetime.utcnow(),
            algorithm_version="test",
            weights_version="test",
            data_schema_version="test",
        )

        assert not version1.is_compatible_with(version2)
        assert not version2.is_compatible_with(version1)

    def test_to_dict_conversion(self):
        """Test conversion to dictionary."""
        created_at = datetime(2025, 1, 15, 12, 0, 0)
        version = ScoringVersion(
            version="v2.1.0",
            created_at=created_at,
            algorithm_version="advanced_v2",
            weights_version="enhanced_v1",
            data_schema_version="2025_v2",
            changelog="Enhanced scoring algorithm",
            deprecated=True,
        )

        result = version.to_dict()

        expected = {
            "version": "v2.1.0",
            "created_at": "2025-01-15T12:00:00",
            "algorithm_version": "advanced_v2",
            "weights_version": "enhanced_v1",
            "data_schema_version": "2025_v2",
            "changelog": "Enhanced scoring algorithm",
            "deprecated": True,
        }

        assert result == expected

    def test_to_dict_with_none_changelog(self):
        """Test to_dict conversion with None changelog."""
        created_at = datetime(2025, 1, 15, 12, 0, 0)
        version = ScoringVersion(
            version="v1.0.0",
            created_at=created_at,
            algorithm_version="baseline_v1",
            weights_version="standard_v1",
            data_schema_version="2025_v1",
        )

        result = version.to_dict()
        assert result["changelog"] is None
        assert result["deprecated"] is False

    def test_from_dict_creation(self):
        """Test creation from dictionary."""
        data = {
            "version": "v2.1.0",
            "created_at": "2025-01-15T12:00:00",
            "algorithm_version": "advanced_v2",
            "weights_version": "enhanced_v1",
            "data_schema_version": "2025_v2",
            "changelog": "Enhanced scoring algorithm",
            "deprecated": True,
        }

        version = ScoringVersion.from_dict(data)

        assert version.version == "v2.1.0"
        assert version.created_at == datetime(2025, 1, 15, 12, 0, 0)
        assert version.algorithm_version == "advanced_v2"
        assert version.weights_version == "enhanced_v1"
        assert version.data_schema_version == "2025_v2"
        assert version.changelog == "Enhanced scoring algorithm"
        assert version.deprecated is True

    def test_from_dict_with_defaults(self):
        """Test from_dict creation with missing optional fields."""
        data = {
            "version": "v1.0.0",
            "created_at": "2025-01-15T12:00:00",
            "algorithm_version": "baseline_v1",
            "weights_version": "standard_v1",
            "data_schema_version": "2025_v1",
        }

        version = ScoringVersion.from_dict(data)

        assert version.changelog is None
        assert version.deprecated is False

    def test_round_trip_serialization(self):
        """Test round-trip to_dict -> from_dict conversion."""
        original = ScoringVersion(
            version="v2.1.0",
            created_at=datetime(2025, 1, 15, 12, 0, 0),
            algorithm_version="advanced_v2",
            weights_version="enhanced_v1",
            data_schema_version="2025_v2",
            changelog="Enhanced scoring algorithm",
            deprecated=True,
        )

        # Convert to dict and back
        data = original.to_dict()
        restored = ScoringVersion.from_dict(data)

        # Should be equivalent
        assert restored.version == original.version
        assert restored.created_at == original.created_at
        assert restored.algorithm_version == original.algorithm_version
        assert restored.weights_version == original.weights_version
        assert restored.data_schema_version == original.data_schema_version
        assert restored.changelog == original.changelog
        assert restored.deprecated == original.deprecated

    def test_timezone_aware_datetime(self):
        """Test handling timezone-aware datetime."""
        tz_aware_dt = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        version = ScoringVersion(
            version="v1.0.0",
            created_at=tz_aware_dt,
            algorithm_version="test",
            weights_version="test",
            data_schema_version="test",
        )

        # Should handle timezone-aware datetime
        assert version.created_at == tz_aware_dt

        # Should serialize and deserialize properly
        data = version.to_dict()
        restored = ScoringVersion.from_dict(data)

        # Note: from_dict creates naive datetime, so compare just the values
        assert restored.created_at.replace(tzinfo=timezone.utc) == tz_aware_dt
