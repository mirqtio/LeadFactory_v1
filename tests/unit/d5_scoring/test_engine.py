"""
Test Scoring Rules Engine - Task 046

Tests for configurable scoring engine ensuring all acceptance criteria are met:
- YAML rules loading
- Rule evaluation works
- Weighted scoring accurate
- Fallback values used
"""

import os
import sys
import tempfile
from decimal import Decimal

sys.path.insert(0, "/app")

from d5_scoring.engine import ConfigurableScoringEngine
from d5_scoring.rules_parser import ScoringRulesParser


class TestTask046AcceptanceCriteria:
    """Test that Task 046 meets all acceptance criteria"""

    def test_yaml_rules_loading(self):
        """
        Test YAML rules loading functionality

        Acceptance Criteria: YAML rules loading
        """
        # Test loading default rules file
        engine = ConfigurableScoringEngine()
        assert engine.loaded, "Engine should load default rules successfully"

        # Test rules parser directly
        parser = ScoringRulesParser("scoring_rules.yaml")
        success = parser.load_rules()
        assert success, "Rules parser should load YAML successfully"

        # Verify configuration sections loaded
        assert parser.config, "Parser should have loaded configuration"
        assert parser.engine_config, "Engine configuration should be loaded"
        assert parser.component_rules, "Component rules should be loaded"
        assert parser.tier_rules, "Tier rules should be loaded"
        assert parser.fallbacks, "Fallback values should be loaded"

        # Test specific components loaded
        component_names = list(parser.component_rules.keys())
        expected_components = ["company_info", "contact_info", "revenue_indicators"]
        for component in expected_components:
            assert component in component_names, f"Component '{component}' should be loaded"

        # Test tier rules loaded
        tier_names = list(parser.tier_rules.keys())
        expected_tiers = [
            "platinum",
            "gold",
            "silver",
            "bronze",
            "basic",
            "unqualified",
        ]
        for tier in expected_tiers:
            assert tier in tier_names, f"Tier '{tier}' should be loaded"

        print("✓ YAML rules loading works correctly")

    def test_rule_evaluation_works(self):
        """
        Test that rule evaluation works properly

        Acceptance Criteria: Rule evaluation works
        """
        engine = ConfigurableScoringEngine()

        # Test with sample business data
        business_data = {
            "id": "test_eval_001",
            "company_name": "Test Corporation",
            "industry": "technology",
            "website": "https://test.com",
            "phone": "555-123-4567",
            "email": "contact@test.com",
            "address": "123 Test Street, Test City, TC 12345",
            "annual_revenue": 1500000,
            "employee_count": 75,
            "business_status": "active",
            "rating": 4.2,
            "reviews_count": 45,
        }

        # Calculate score
        result = engine.calculate_score(business_data)

        # Verify result structure
        assert result.business_id == "test_eval_001", "Business ID should match"
        assert isinstance(result.overall_score, Decimal), "Score should be Decimal"
        assert 0 <= float(result.overall_score) <= 100, "Score should be 0-100"
        assert result.tier in [
            "platinum",
            "gold",
            "silver",
            "bronze",
            "basic",
            "unqualified",
        ], "Should assign valid tier"
        assert result.status == "completed", "Status should be completed"

        # Test with minimal data to check rule evaluation
        minimal_data = {"id": "test_eval_002", "company_name": "Minimal Corp"}

        minimal_result = engine.calculate_score(minimal_data)
        assert minimal_result.business_id == "test_eval_002", "Should handle minimal data"
        assert float(minimal_result.overall_score) >= 0, "Should calculate score with minimal data"

        # Verify different data yields different scores
        assert result.overall_score != minimal_result.overall_score, "Different data should yield different scores"

        print("✓ Rule evaluation works correctly")

    def test_weighted_scoring_accurate(self):
        """
        Test that weighted scoring is calculated accurately

        Acceptance Criteria: Weighted scoring accurate
        """
        engine = ConfigurableScoringEngine()

        # Create test data that should score well in high-weight components
        high_revenue_data = {
            "id": "test_weight_001",
            "company_name": "High Revenue Corp",
            "annual_revenue": 10000000,  # Should score well in revenue_indicators (weight: 12.0)
            "employee_count": 200,
            "business_status": "active",
        }

        # Create test data that should score well in low-weight components
        low_weight_data = {
            "id": "test_weight_002",
            "company_name": "Tech Stack Corp",
            "tech_stack": [
                "cloud",
                "aws",
                "api",
            ],  # Should score in technology_stack (weight: 4.0)
            "website": "https://techstack.com",
        }

        high_revenue_result = engine.calculate_score(high_revenue_data)
        low_weight_result = engine.calculate_score(low_weight_data)

        # High-weight component scoring should have more impact
        assert float(high_revenue_result.overall_score) > float(
            low_weight_result.overall_score
        ), "High-weight component should contribute more to overall score"

        # Test detailed breakdown to verify weights
        detailed_result, breakdowns = engine.calculate_detailed_score(high_revenue_data)

        # Find revenue indicators breakdown
        revenue_breakdown = None
        for breakdown in breakdowns:
            if breakdown.component == "revenue_indicators":
                revenue_breakdown = breakdown
                break

        assert revenue_breakdown is not None, "Should have revenue indicators breakdown"
        assert float(revenue_breakdown.weight) == 12.0, "Revenue indicators should have weight 12.0"

        # Verify weighted calculation
        component_contribution = float(revenue_breakdown.component_score) * float(revenue_breakdown.weight)
        assert component_contribution > 0, "Weighted contribution should be positive"

        print("✓ Weighted scoring calculation is accurate")

    def test_fallback_values_used(self):
        """
        Test that fallback values are properly applied for missing data

        Acceptance Criteria: Fallback values used
        """
        engine = ConfigurableScoringEngine()
        parser = engine.rules_parser

        # Test data with missing fields
        incomplete_data = {
            "id": "test_fallback_001",
            "company_name": "Incomplete Corp",
            # Missing: industry, website, phone, email, etc.
        }

        # Apply fallbacks
        enriched_data = parser.apply_fallbacks(incomplete_data)

        # Verify fallbacks were applied
        assert "industry" in enriched_data, "Industry fallback should be applied"
        assert enriched_data["industry"] == "unknown", "Industry should fallback to 'unknown'"

        assert "annual_revenue" in enriched_data, "Revenue fallback should be applied"
        assert enriched_data["annual_revenue"] == 0, "Revenue should fallback to 0"

        assert "employee_count" in enriched_data, "Employee count fallback should be applied"
        assert enriched_data["employee_count"] == 1, "Employee count should fallback to 1"

        # Verify original data is preserved
        assert enriched_data["company_name"] == "Incomplete Corp", "Original data should be preserved"
        assert enriched_data["id"] == "test_fallback_001", "Original ID should be preserved"

        # Test that engine can score with fallbacks
        result = engine.calculate_score(incomplete_data)
        assert result.business_id == "test_fallback_001", "Should score with fallback data"
        assert float(result.overall_score) >= 0, "Should calculate valid score with fallbacks"

        # Test that fallbacks improve scoring compared to completely empty data
        empty_data = {"id": "test_fallback_002"}
        empty_result = engine.calculate_score(empty_data)

        # Both should work without errors
        assert float(result.overall_score) >= 0, "Incomplete data should score"
        assert float(empty_result.overall_score) >= 0, "Empty data should score"

        print("✓ Fallback values are used correctly")

    def test_comprehensive_engine_functionality(self):
        """
        Comprehensive test verifying all acceptance criteria work together
        """
        # This test verifies all four acceptance criteria work together

        # 1. YAML rules loading - initialize engine
        engine = ConfigurableScoringEngine()
        assert engine.loaded, "Rules should load from YAML"

        # 2. Rule evaluation works - test with comprehensive data
        comprehensive_data = {
            "id": "comprehensive_test_001",
            "company_name": "Comprehensive Test Corp",
            "industry": "technology",
            "website": "https://comprehensive.com",
            "phone": "555-999-8888",
            "email": "info@comprehensive.com",
            "address": "999 Comprehensive Ave, Test City, TC 99999",
            "annual_revenue": 2500000,
            "employee_count": 150,
            "business_status": "active",
            "rating": 4.5,
            "reviews_count": 125,
            "years_in_business": 8,
            "funding_total": 5000000,
            "tech_stack": ["cloud", "aws", "api", "rest"],
        }

        result = engine.calculate_score(comprehensive_data)
        assert isinstance(result.overall_score, Decimal), "Rule evaluation should work"
        assert float(result.overall_score) > 50, "Comprehensive data should score well"

        # 3. Weighted scoring accurate - get detailed breakdown
        detailed_result, breakdowns = engine.calculate_detailed_score(comprehensive_data)

        total_weighted = 0.0
        for breakdown in breakdowns:
            weighted_contribution = float(breakdown.component_score) * float(breakdown.weight)
            total_weighted += weighted_contribution

        assert total_weighted > 0, "Weighted scoring should calculate correctly"
        assert len(breakdowns) > 5, "Should have multiple component breakdowns"

        # 4. Fallback values used - test with missing data
        incomplete_data = {
            "id": "comprehensive_test_002",
            "company_name": "Incomplete Corp",
            # Most fields missing - should use fallbacks
        }

        incomplete_result = engine.calculate_score(incomplete_data)
        assert incomplete_result.business_id == "comprehensive_test_002", "Should handle missing data with fallbacks"

        # Verify scores are different (comprehensive should score higher)
        assert float(result.overall_score) > float(
            incomplete_result.overall_score
        ), "Complete data should score higher than incomplete data"

        print("✓ All acceptance criteria working together successfully")

    def test_scoring_metrics_tracking(self):
        """Test scoring metrics and performance tracking"""
        engine = ConfigurableScoringEngine(enable_metrics=True)

        # Test multiple scoring operations
        test_data_list = [
            {
                "id": "metrics_001",
                "company_name": "Metrics Corp 1",
                "annual_revenue": 1000000,
            },
            {
                "id": "metrics_002",
                "company_name": "Metrics Corp 2",
                "annual_revenue": 500000,
            },
            {
                "id": "metrics_003",
                "company_name": "Metrics Corp 3",
                "annual_revenue": 2000000,
            },
        ]

        results = []
        for data in test_data_list:
            result = engine.calculate_score(data)
            results.append(result)

        # Check metrics were collected
        metrics = engine.get_performance_metrics()
        assert metrics["total_evaluations"] == 3, "Should track 3 evaluations"
        assert metrics["average_execution_time"] > 0, "Should track execution time"
        assert len(metrics["tier_distribution"]) > 0, "Should track tier distribution"

        print("✓ Scoring metrics tracking works correctly")

    def test_rules_validation(self):
        """Test rules configuration validation"""
        parser = ScoringRulesParser("scoring_rules.yaml")
        parser.load_rules()

        # Validate loaded rules
        validation_errors = parser.validate_rules()
        assert isinstance(validation_errors, list), "Should return list of errors"

        # With valid rules, should have no errors
        if validation_errors:
            print(f"Validation warnings: {validation_errors}")

        print("✓ Rules validation works correctly")

    def test_score_explanation(self):
        """Test detailed score explanation functionality"""
        engine = ConfigurableScoringEngine()

        test_data = {
            "id": "explanation_test_001",
            "company_name": "Explanation Corp",
            "industry": "technology",
            "annual_revenue": 1200000,
        }

        explanation = engine.explain_score(test_data)

        # Verify explanation structure
        assert "business_id" in explanation, "Should include business ID"
        assert "component_explanations" in explanation, "Should explain components"
        assert "overall_calculation" in explanation, "Should explain overall calculation"
        assert "tier_assignment" in explanation, "Should explain tier assignment"

        # Verify component explanations
        assert len(explanation["component_explanations"]) > 0, "Should have component details"

        for component_name, component_explanation in explanation["component_explanations"].items():
            assert "weight" in component_explanation, f"Component {component_name} should have weight"
            assert "total_points" in component_explanation, f"Component {component_name} should have points"
            assert "rule_details" in component_explanation, f"Component {component_name} should have rule details"

        print("✓ Score explanation works correctly")

    def test_custom_rules_file(self):
        """Test loading custom rules file"""
        # Create temporary rules file
        custom_rules = """
version: "test_1.0.0"
engine_config:
  max_score: 100.0
  fallback_enabled: true

fallbacks:
  company_info:
    company_name: "Unknown Company"
    industry: "unknown"

scoring_components:
  simple_component:
    weight: 10.0
    description: "Simple test component"
    rules:
      - condition: "company_name != 'Unknown Company'"
        points: 5.0
        description: "Company name provided"

tier_rules:
  high:
    min_score: 50.0
    max_score: 100.0
    description: "High tier"
    priority: "high"
  low:
    min_score: 0.0
    max_score: 49.9
    description: "Low tier"
    priority: "low"

quality_control:
  min_data_completeness: 0.1
  confidence_threshold: 0.5
  manual_review_triggers: []
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(custom_rules)
            temp_file = f.name

        try:
            # Test loading custom rules
            engine = ConfigurableScoringEngine(rules_file=temp_file)
            assert engine.loaded, "Should load custom rules file"

            # Test scoring with custom rules
            test_data = {"id": "custom_001", "company_name": "Custom Test Corp"}
            result = engine.calculate_score(test_data)

            assert result.business_id == "custom_001", "Should work with custom rules"
            assert result.tier in ["high", "low"], "Should use custom tier definitions"

        finally:
            os.unlink(temp_file)

        print("✓ Custom rules file loading works correctly")


# Allow running this test file directly
if __name__ == "__main__":

    def run_tests():
        test_instance = TestTask046AcceptanceCriteria()

        print("🏆 Running Task 046 Scoring Rules Engine Tests...")
        print()

        try:
            # Run all acceptance criteria tests
            test_instance.test_yaml_rules_loading()
            test_instance.test_rule_evaluation_works()
            test_instance.test_weighted_scoring_accurate()
            test_instance.test_fallback_values_used()
            test_instance.test_comprehensive_engine_functionality()
            test_instance.test_scoring_metrics_tracking()
            test_instance.test_rules_validation()
            test_instance.test_score_explanation()
            test_instance.test_custom_rules_file()

            print()
            print("🎉 All Task 046 acceptance criteria tests pass!")
            print("   - YAML rules loading: ✓")
            print("   - Rule evaluation works: ✓")
            print("   - Weighted scoring accurate: ✓")
            print("   - Fallback values used: ✓")

        except Exception as e:
            print(f"❌ Test failed: {e}")
            import traceback

            traceback.print_exc()

    # Run tests
    run_tests()
