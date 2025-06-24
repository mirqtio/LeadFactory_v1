"""
Test Scoring Models - Task 045

Tests for scoring models ensuring all acceptance criteria are met:
- Scoring result model
- Tier enumeration
- Score breakdown stored
- Version tracking
"""

import sys
from datetime import datetime, timedelta
from decimal import Decimal

import pytest

sys.path.insert(0, "/app")

from d5_scoring.models import (
    ScoreBreakdown,
    ScoreHistory,
    ScoringEngine,
    D5ScoringResult,
)
from d5_scoring.types import ScoreComponent, ScoringStatus, ScoringTier, ScoringVersion


class TestTask045AcceptanceCriteria:
    """Test that Task 045 meets all acceptance criteria"""

    def test_scoring_result_model(self):
        """
        Test that scoring result model works properly

        Acceptance Criteria: Scoring result model
        """
        # Test scoring result creation
        result = D5ScoringResult(
            business_id="test_biz_001",
            overall_score=Decimal("85.5"),
            tier=ScoringTier.GOLD.value,
            confidence=Decimal("0.9"),
            scoring_version="v1.0.0",
            algorithm_version="baseline_v1",
        )

        # Verify core fields
        assert result.business_id == "test_biz_001"
        assert result.overall_score == Decimal("85.5")
        assert result.tier == ScoringTier.GOLD.value
        assert result.confidence == Decimal("0.9")
        assert result.scoring_version == "v1.0.0"

        # Test tier enum property
        assert result.tier_enum == ScoringTier.GOLD

        # Test tier update from score
        result.overall_score = Decimal("95.0")
        result.update_tier_from_score()
        assert result.tier == ScoringTier.PLATINUM.value

        # Test expiration logic
        assert not result.is_expired  # Fresh result

        # Test dictionary conversion
        result_dict = result.to_dict()
        assert isinstance(result_dict, dict)
        assert result_dict["business_id"] == "test_biz_001"
        assert result_dict["overall_score"] == 95.0
        assert "age_days" in result_dict
        assert "is_expired" in result_dict

        print("✓ Scoring result model works correctly")

    def test_tier_enumeration(self):
        """
        Test that tier enumeration works properly

        Acceptance Criteria: Tier enumeration
        """
        # Test tier classification from scores
        assert ScoringTier.from_score(95.0) == ScoringTier.PLATINUM
        assert ScoringTier.from_score(85.0) == ScoringTier.GOLD
        assert ScoringTier.from_score(75.0) == ScoringTier.SILVER
        assert ScoringTier.from_score(65.0) == ScoringTier.BRONZE
        assert ScoringTier.from_score(55.0) == ScoringTier.BASIC
        assert ScoringTier.from_score(45.0) == ScoringTier.UNQUALIFIED

        # Test edge cases
        assert ScoringTier.from_score(90.0) == ScoringTier.PLATINUM
        assert ScoringTier.from_score(89.9) == ScoringTier.GOLD
        assert ScoringTier.from_score(0.0) == ScoringTier.UNQUALIFIED
        assert ScoringTier.from_score(100.0) == ScoringTier.PLATINUM

        # Test tier properties
        assert ScoringTier.PLATINUM.min_score == 90.0
        assert ScoringTier.PLATINUM.max_score == 100.0
        assert ScoringTier.GOLD.min_score == 80.0
        assert ScoringTier.GOLD.max_score == 89.9

        print("✓ Tier enumeration works correctly")

    def test_score_breakdown_stored(self):
        """
        Test that score breakdown storage works properly

        Acceptance Criteria: Score breakdown stored
        """
        # Create main scoring result
        scoring_result = D5ScoringResult(
            business_id="test_biz_002",
            overall_score=Decimal("78.5"),
            tier=ScoringTier.SILVER.value,
            scoring_version="v1.0.0",
            algorithm_version="baseline_v1",
        )

        # Create score breakdown components
        breakdown1 = ScoreBreakdown(
            scoring_result_id=scoring_result.id,
            component=ScoreComponent.COMPANY_INFO.value,
            component_score=Decimal("7.5"),
            max_possible_score=Decimal("8.0"),
            weight=Decimal("0.15"),
            confidence=Decimal("0.9"),
            data_quality="good",
            calculation_method="completeness_analysis",
        )

        breakdown2 = ScoreBreakdown(
            scoring_result_id=scoring_result.id,
            component=ScoreComponent.REVENUE_INDICATORS.value,
            component_score=Decimal("10.0"),
            max_possible_score=Decimal("12.0"),
            weight=Decimal("0.20"),
            confidence=Decimal("0.8"),
            data_quality="excellent",
            calculation_method="revenue_analysis",
        )

        # Test breakdown properties
        assert breakdown1.component_enum == ScoreComponent.COMPANY_INFO
        assert breakdown1.score_percentage == 93.75  # 7.5/8.0 * 100
        assert breakdown2.score_percentage == 83.33  # 10.0/12.0 * 100 (rounded)

        # Test breakdown dictionary conversion
        breakdown_dict = breakdown1.to_dict()
        assert isinstance(breakdown_dict, dict)
        assert breakdown_dict["component"] == ScoreComponent.COMPANY_INFO.value
        assert breakdown_dict["component_score"] == 7.5
        assert breakdown_dict["score_percentage"] == 93.75
        assert "calculated_at" in breakdown_dict

        # Test that breakdowns store calculation details
        assert breakdown1.calculation_method == "completeness_analysis"
        assert breakdown1.data_quality == "good"
        assert breakdown1.confidence == Decimal("0.9")

        print("✓ Score breakdown storage works correctly")

    def test_version_tracking(self):
        """
        Test that version tracking works properly

        Acceptance Criteria: Version tracking
        """
        # Test ScoringVersion creation
        version = ScoringVersion(
            version="v1.2.3",
            created_at=datetime.utcnow(),
            algorithm_version="advanced_v2",
            weights_version="custom_v1",
            data_schema_version="2025_v2",
            changelog="Added new scoring components",
        )

        # Test version properties
        assert version.version == "v1.2.3"
        assert version.algorithm_version == "advanced_v2"
        assert version.changelog == "Added new scoring components"
        assert not version.deprecated

        # Test current version factory
        current = ScoringVersion.current()
        assert current.version == "v1.0.0"
        assert current.algorithm_version == "baseline_v1"
        assert isinstance(current.created_at, datetime)

        # Test compatibility checking
        version1 = ScoringVersion(
            version="v1.5.0",
            created_at=datetime.utcnow(),
            algorithm_version="test",
            weights_version="test",
            data_schema_version="test",
        )

        version2 = ScoringVersion(
            version="v1.8.0",
            created_at=datetime.utcnow(),
            algorithm_version="test",
            weights_version="test",
            data_schema_version="test",
        )

        version3 = ScoringVersion(
            version="v2.0.0",
            created_at=datetime.utcnow(),
            algorithm_version="test",
            weights_version="test",
            data_schema_version="test",
        )

        # Same major version should be compatible
        assert version1.is_compatible_with(version2)
        # Different major version should not be compatible
        assert not version1.is_compatible_with(version3)

        # Test dictionary conversion
        version_dict = version.to_dict()
        assert isinstance(version_dict, dict)
        assert version_dict["version"] == "v1.2.3"
        assert "created_at" in version_dict
        assert version_dict["deprecated"] == False

        # Test from dictionary
        recreated = ScoringVersion.from_dict(version_dict)
        assert recreated.version == version.version
        assert recreated.algorithm_version == version.algorithm_version

        print("✓ Version tracking works correctly")

    def test_score_history_tracking(self):
        """Test score history tracking functionality"""
        # Create scoring result
        scoring_result = D5ScoringResult(
            business_id="test_biz_003",
            overall_score=Decimal("75.0"),
            tier=ScoringTier.SILVER.value,
            scoring_version="v1.0.0",
            algorithm_version="baseline_v1",
        )

        # Create score history entry
        history = ScoreHistory(
            scoring_result_id=scoring_result.id,
            business_id=scoring_result.business_id,
            previous_score=Decimal("70.0"),
            new_score=Decimal("75.0"),
            previous_tier=ScoringTier.SILVER.value,
            new_tier=ScoringTier.SILVER.value,
            change_reason="Updated company data",
            change_type="automatic",
        )

        # Test calculated fields
        assert history.score_change == Decimal("5.0")
        assert not history.tier_changed
        assert history.score_improvement

        # Test dictionary conversion
        history_dict = history.to_dict()
        assert history_dict["score_change"] == 5.0
        assert history_dict["score_improvement"] == True
        assert history_dict["tier_changed"] == False

        print("✓ Score history tracking works correctly")

    def test_scoring_engine(self):
        """Test scoring engine calculation logic"""
        # Create scoring engine
        engine = ScoringEngine()

        # Test with sample business data
        business_data = {
            "id": "test_engine_001",
            "company_name": "Test Corporation",
            "industry": "Technology",
            "website": "https://test.com",
            "phone": "555-1234",
            "address": "123 Test St, Test City, TC 12345",
            "employee_count": 50,
            "annual_revenue": 1000000,
            "business_status": "active",
            "data_version": "v2025.1",
        }

        # Calculate score
        result = engine.calculate_score(business_data)

        # Verify result structure
        assert isinstance(result, D5ScoringResult)
        assert result.business_id == "test_engine_001"
        assert 0 <= float(result.overall_score) <= 100
        assert result.tier in [tier.value for tier in ScoringTier]
        assert result.status == ScoringStatus.COMPLETED.value
        assert result.algorithm_version == "baseline_v1"

        # Test scoring summary
        summary = engine.get_scoring_summary(result)
        assert isinstance(summary, dict)
        assert "overall_score" in summary
        assert "tier_description" in summary
        assert "confidence" in summary

        print("✓ Scoring engine works correctly")

    def test_score_components(self):
        """Test score component enumeration and properties"""
        # Test that all components have required properties
        for component in ScoreComponent:
            assert component.max_points > 0
            assert isinstance(component.description, str)
            assert len(component.description) > 10

        # Test specific component properties
        assert ScoreComponent.REVENUE_INDICATORS.max_points == 12.0  # High weight
        assert ScoreComponent.COMPANY_INFO.max_points == 8.0
        assert ScoreComponent.TECHNOLOGY_STACK.max_points == 4.0  # Lower weight

        # Test component descriptions
        assert "revenue" in ScoreComponent.REVENUE_INDICATORS.description.lower()
        assert "company" in ScoreComponent.COMPANY_INFO.description.lower()

        print("✓ Score components work correctly")

    def test_comprehensive_acceptance_criteria(self):
        """Comprehensive test covering all acceptance criteria together"""
        # This test verifies all four acceptance criteria work together

        # 1. Scoring result model - create and validate
        scoring_result = D5ScoringResult(
            business_id="comprehensive_test_001",
            overall_score=Decimal("82.7"),
            tier=ScoringTier.GOLD.value,
            confidence=Decimal("0.85"),
            scoring_version="v1.0.0",
            algorithm_version="baseline_v1",
            status=ScoringStatus.COMPLETED.value,
        )

        assert isinstance(
            scoring_result, D5ScoringResult
        ), "Scoring result model failed"
        assert scoring_result.overall_score == Decimal("82.7"), "Score storage failed"

        # 2. Tier enumeration - verify tier classification
        assert scoring_result.tier_enum == ScoringTier.GOLD, "Tier enumeration failed"
        assert (
            ScoringTier.from_score(82.7) == ScoringTier.GOLD
        ), "Tier calculation failed"

        # 3. Score breakdown stored - create and validate breakdown
        breakdown = ScoreBreakdown(
            scoring_result_id=scoring_result.id,
            component=ScoreComponent.COMPANY_INFO.value,
            component_score=Decimal("7.0"),
            max_possible_score=Decimal("8.0"),
            weight=Decimal("0.15"),
            confidence=Decimal("0.9"),
        )

        assert (
            breakdown.component_enum == ScoreComponent.COMPANY_INFO
        ), "Score breakdown storage failed"
        assert breakdown.score_percentage == 87.5, "Score breakdown calculation failed"

        # 4. Version tracking - create and validate version
        version = ScoringVersion.current()
        assert version.version == "v1.0.0", "Version tracking failed"
        assert isinstance(version.created_at, datetime), "Version timestamp failed"

        # Test integration between components
        scoring_result.scoring_version = version.version
        assert (
            scoring_result.scoring_version == version.version
        ), "Version integration failed"

        # Test engine calculation with version
        engine = ScoringEngine(version=version)
        test_data = {
            "id": "integration_test",
            "company_name": "Integration Test Corp",
            "industry": "Testing",
        }

        calculated_result = engine.calculate_score(test_data)
        assert (
            calculated_result.scoring_version == version.version
        ), "Engine version integration failed"

        print("✓ All acceptance criteria working together successfully")


# Allow running this test file directly
if __name__ == "__main__":

    def run_tests():
        test_instance = TestTask045AcceptanceCriteria()

        print("🏆 Running Task 045 Scoring Models Tests...")
        print()

        try:
            # Run all acceptance criteria tests
            test_instance.test_scoring_result_model()
            test_instance.test_tier_enumeration()
            test_instance.test_score_breakdown_stored()
            test_instance.test_version_tracking()
            test_instance.test_score_history_tracking()
            test_instance.test_scoring_engine()
            test_instance.test_score_components()
            test_instance.test_comprehensive_acceptance_criteria()

            print()
            print("🎉 All Task 045 acceptance criteria tests pass!")
            print("   - Scoring result model: ✓")
            print("   - Tier enumeration: ✓")
            print("   - Score breakdown stored: ✓")
            print("   - Version tracking: ✓")

        except Exception as e:
            print(f"❌ Test failed: {e}")
            import traceback

            traceback.print_exc()

    # Run tests
    run_tests()
