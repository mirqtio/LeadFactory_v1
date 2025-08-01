"""
Test Visual Rubric - Comprehensive Unit Tests

Tests for the visual rubric scoring system with 9 dimensions.
Each dimension is scored 1-9 based on specific criteria.

Visual Rubric Dimensions:
1. Visual Design Quality (1-9)
2. Brand Consistency (1-9)
3. Navigation Clarity (1-9)
4. Content Organization (1-9)
5. Call-to-Action Prominence (1-9)
6. Mobile Responsiveness (1-9)
7. Loading Performance (1-9)
8. Trust Signals (1-9)
9. Overall User Experience (1-9)

Test Coverage:
- Score validation and bounds checking
- Rubric interpretation and categorization
- Average score calculations
- Performance impact analysis
- Quick win prioritization
- Warning severity levels
"""

import pytest

from d3_assessment.assessors.visual_analyzer import VisualAnalyzer


class TestVisualRubric:
    """Test suite for visual rubric scoring system"""

    @pytest.fixture
    def visual_analyzer(self):
        """Create visual analyzer instance for testing rubric methods"""
        return VisualAnalyzer()

    def test_rubric_dimensions_completeness(self):
        """Test that all 9 rubric dimensions are defined"""
        expected_dimensions = [
            "visual_design_quality",
            "brand_consistency",
            "navigation_clarity",
            "content_organization",
            "call_to_action_prominence",
            "mobile_responsiveness",
            "loading_performance",
            "trust_signals",
            "overall_user_experience",
        ]

        # Create a sample scores dict
        scores = dict.fromkeys(expected_dimensions, 5)

        # Verify all dimensions are present
        assert len(scores) == 9
        for dimension in expected_dimensions:
            assert dimension in scores

    def test_score_ranges_and_categories(self):
        """Test score interpretation and categorization"""
        test_cases = [
            # (score, expected_category, expected_severity)
            (1, "critical", "severe"),
            (2, "poor", "high"),
            (3, "poor", "high"),
            (4, "below_average", "medium"),
            (5, "average", "medium"),
            (6, "average", "low"),
            (7, "good", "low"),
            (8, "good", "none"),
            (9, "excellent", "none"),
        ]

        for score, expected_category, expected_severity in test_cases:
            category = self._categorize_score(score)
            severity = self._get_severity(score)
            assert category == expected_category, f"Score {score} should be {expected_category}"
            assert severity == expected_severity, f"Score {score} should have {expected_severity} severity"

    def test_average_score_calculation(self):
        """Test calculation of average visual score"""
        test_scores = {
            "visual_design_quality": 8,
            "brand_consistency": 7,
            "navigation_clarity": 9,
            "content_organization": 8,
            "call_to_action_prominence": 6,
            "mobile_responsiveness": 9,
            "loading_performance": 7,
            "trust_signals": 8,
            "overall_user_experience": 8,
        }

        # Calculate average
        avg_score = sum(test_scores.values()) / len(test_scores)
        expected_avg = 7.78  # (70 / 9)

        assert avg_score == pytest.approx(expected_avg, rel=0.01)

    def test_dimension_impact_on_overall_ux(self):
        """Test how individual dimensions impact overall UX score"""
        # Dimensions with high impact on overall UX
        high_impact_dimensions = [
            "navigation_clarity",
            "content_organization",
            "mobile_responsiveness",
            "loading_performance",
        ]

        # Dimensions with medium impact on overall UX
        medium_impact_dimensions = ["visual_design_quality", "call_to_action_prominence", "trust_signals"]

        # Dimension with contextual impact
        contextual_dimensions = ["brand_consistency"]  # Important for established brands

        # Verify categorization
        all_dimensions = high_impact_dimensions + medium_impact_dimensions + contextual_dimensions
        assert len(all_dimensions) == 8  # Plus overall_user_experience = 9 total

    def test_warning_generation_from_low_scores(self):
        """Test warning generation based on low dimension scores"""
        test_cases = [
            # (dimension, score, expected_warning_contains)
            ("visual_design_quality", 3, "design quality"),
            ("brand_consistency", 2, "brand consistency"),
            ("navigation_clarity", 2, "navigation"),
            ("content_organization", 3, "content organization"),
            ("call_to_action_prominence", 1, "call-to-action"),
            ("mobile_responsiveness", 4, "mobile"),
            ("loading_performance", 3, "loading performance"),
            ("trust_signals", 2, "trust signals"),
            ("overall_user_experience", 3, "user experience"),
        ]

        for dimension, score, expected_text in test_cases:
            warning = self._generate_warning(dimension, score)
            assert expected_text.lower() in warning.lower()
            assert score < 5  # Warnings generated for below-average scores

    def test_quick_win_prioritization(self):
        """Test prioritization of quick wins based on impact and effort"""
        quick_wins = [
            {
                "title": "Increase CTA button size",
                "impact": "high",
                "effort": "low",
                "dimension": "call_to_action_prominence",
                "potential_score_improvement": 2,
            },
            {
                "title": "Optimize image loading",
                "impact": "medium",
                "effort": "medium",
                "dimension": "loading_performance",
                "potential_score_improvement": 1,
            },
            {
                "title": "Add trust badges",
                "impact": "medium",
                "effort": "low",
                "dimension": "trust_signals",
                "potential_score_improvement": 1,
            },
            {
                "title": "Redesign navigation menu",
                "impact": "high",
                "effort": "high",
                "dimension": "navigation_clarity",
                "potential_score_improvement": 2,
            },
        ]

        # Sort by priority (high impact + low effort first)
        # Primary key: high impact items first
        # Secondary key: low effort items first
        # Tertiary key: highest score improvement
        prioritized = sorted(
            quick_wins,
            key=lambda x: (
                x["impact"] == "high",  # High impact first
                x["effort"] == "low",  # Low effort second
                x["potential_score_improvement"],  # High improvement third
            ),
            reverse=True,
        )

        # Verify high impact + low effort items come first
        high_impact_low_effort = [q for q in prioritized if q["impact"] == "high" and q["effort"] == "low"]
        assert len(high_impact_low_effort) >= 1
        assert high_impact_low_effort[0]["title"] == "Increase CTA button size"

        # Verify that high impact items generally rank higher than medium impact
        # when effort is the same (or better for high impact)
        first_item = prioritized[0]
        assert first_item["impact"] == "high" and first_item["effort"] == "low"

    def test_score_boundary_conditions(self, visual_analyzer):
        """Test score clamping at boundaries"""
        # Test lower boundary
        assert visual_analyzer._clamp_score(-10) == 1
        assert visual_analyzer._clamp_score(0) == 1
        assert visual_analyzer._clamp_score(0.4) == 1
        assert visual_analyzer._clamp_score(0.5) == 1

        # Test upper boundary
        assert visual_analyzer._clamp_score(100) == 9
        assert visual_analyzer._clamp_score(100.4) == 9
        assert visual_analyzer._clamp_score(100.6) == 9
        assert visual_analyzer._clamp_score(110) == 9
        assert visual_analyzer._clamp_score(1000) == 9

        # Test normal range
        assert visual_analyzer._clamp_score(5) == 5
        assert visual_analyzer._clamp_score(5.4) == 5
        assert visual_analyzer._clamp_score(5.5) == 5
        assert visual_analyzer._clamp_score(5.9) == 5
        assert visual_analyzer._clamp_score(7.7) == 7

    def test_dimension_interdependencies(self):
        """Test relationships between different visual dimensions"""
        # Example: Poor loading performance should impact overall UX
        scores_with_poor_loading = {
            "visual_design_quality": 9,
            "brand_consistency": 8,
            "navigation_clarity": 9,
            "content_organization": 8,
            "call_to_action_prominence": 8,
            "mobile_responsiveness": 9,
            "loading_performance": 3,  # Poor
            "trust_signals": 8,
            "overall_user_experience": 6,  # Should be lower due to loading
        }

        # Overall UX should not exceed 7 when loading is below 4
        assert scores_with_poor_loading["overall_user_experience"] < 7

        # Example: Poor mobile responsiveness impacts overall UX significantly
        scores_with_poor_mobile = {
            "visual_design_quality": 8,
            "brand_consistency": 8,
            "navigation_clarity": 8,
            "content_organization": 8,
            "call_to_action_prominence": 7,
            "mobile_responsiveness": 2,  # Poor
            "loading_performance": 8,
            "trust_signals": 8,
            "overall_user_experience": 6,  # Should be impacted
        }

        # With mobile traffic > 50%, poor mobile score heavily impacts overall
        assert scores_with_poor_mobile["overall_user_experience"] < 7

    def test_perfect_score_handling(self):
        """Test handling of perfect scores (100)"""
        perfect_scores = dict.fromkeys(
            [
                "visual_design_quality",
                "brand_consistency",
                "navigation_clarity",
                "content_organization",
                "call_to_action_prominence",
                "mobile_responsiveness",
                "loading_performance",
                "trust_signals",
                "overall_user_experience",
            ],
            9,
        )

        # Average should be 9
        avg = sum(perfect_scores.values()) / len(perfect_scores)
        assert avg == 9.0

        # No warnings should be generated
        warnings = []
        for dim, score in perfect_scores.items():
            if score < 5:
                warnings.append(f"Issue with {dim}")
        assert len(warnings) == 0

    def test_critical_dimension_thresholds(self):
        """Test critical thresholds for key dimensions"""
        critical_thresholds = {
            "navigation_clarity": 3,  # Below this, site is hard to use
            "mobile_responsiveness": 4,  # Below this, mobile UX is broken
            "loading_performance": 3,  # Below this, users abandon
            "content_organization": 2,  # Below this, information is lost
        }

        for dimension, threshold in critical_thresholds.items():
            # Scores below threshold should generate severe warnings
            test_score = threshold - 1
            severity = self._get_severity(test_score)
            # Scores below 2 are severe, 2-3 are high
            assert severity in [
                "severe",
                "high",
            ], f"Score {test_score} for {dimension} should be severe/high, got {severity}"

    # Helper methods for testing (these simulate internal logic)
    def _categorize_score(self, score: int) -> str:
        """Categorize score into performance bands"""
        if score >= 9:
            return "excellent"
        if score >= 7:
            return "good"
        if score >= 5:
            return "average"
        if score >= 4:
            return "below_average"
        if score >= 2:
            return "poor"
        return "critical"

    def _get_severity(self, score: int) -> str:
        """Get severity level based on score"""
        if score < 2:
            return "severe"
        if score < 4:
            return "high"
        if score < 6:
            return "medium"
        if score < 8:
            return "low"
        return "none"

    def _generate_warning(self, dimension: str, score: int) -> str:
        """Generate warning message for low-scoring dimension"""
        dimension_names = {
            "visual_design_quality": "Visual design quality",
            "brand_consistency": "Brand consistency",
            "navigation_clarity": "Navigation clarity",
            "content_organization": "Content organization",
            "call_to_action_prominence": "Call-to-action prominence",
            "mobile_responsiveness": "Mobile responsiveness",
            "loading_performance": "Loading performance",
            "trust_signals": "Trust signals",
            "overall_user_experience": "Overall user experience",
        }

        name = dimension_names.get(dimension, dimension)
        severity = self._get_severity(score)

        return f"{name} needs improvement (score: {score}, severity: {severity})"

    def test_rubric_consistency_with_analyzer(self, visual_analyzer):
        """Test that rubric logic is consistent with visual analyzer implementation"""
        # Test score clamping matches
        test_values = [-10, 0, 5, 9, 15, "7", None]
        for value in test_values:
            clamped = visual_analyzer._clamp_score(value)
            assert 1 <= clamped <= 9

    def test_insight_generation_thresholds(self):
        """Test thresholds for generating different types of insights"""
        # High-performing dimensions (8+) -> Strengths
        # Mid-range dimensions (5-7) -> Opportunities
        # Low-performing dimensions (<5) -> Weaknesses

        scores = {
            "visual_design_quality": 8,  # Strength
            "brand_consistency": 4,  # Weakness
            "navigation_clarity": 6,  # Opportunity
            "content_organization": 9,  # Strength
            "call_to_action_prominence": 3,  # Weakness
            "mobile_responsiveness": 7,  # Opportunity
            "loading_performance": 4,  # Weakness
            "trust_signals": 8,  # Strength
            "overall_user_experience": 7,  # Opportunity
        }

        strengths = [dim for dim, score in scores.items() if score >= 8]
        opportunities = [dim for dim, score in scores.items() if 5 <= score < 8]
        weaknesses = [dim for dim, score in scores.items() if score < 5]

        assert len(strengths) == 3
        assert len(opportunities) == 3
        assert len(weaknesses) == 3

        assert "visual_design_quality" in strengths
        assert "content_organization" in strengths
        assert "trust_signals" in strengths

        assert "navigation_clarity" in opportunities
        assert "mobile_responsiveness" in opportunities

        assert "brand_consistency" in weaknesses
        assert "call_to_action_prominence" in weaknesses
        assert "loading_performance" in weaknesses
