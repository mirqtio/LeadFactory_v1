"""
Test Data Generator Tests - Task 088

Comprehensive tests for business and assessment data generators.
Validates realistic data generation, scenarios, deterministic output, and performance.

Acceptance Criteria:
- Realistic test data ✓
- Various scenarios covered ✓
- Deterministic generation ✓
- Performance data sets ✓
"""

from datetime import datetime
from decimal import Decimal

import pytest

from d3_assessment.models import AssessmentResult
from database.models import Business
from tests.generators.assessment_generator import (AssessmentGenerator,
                                                   AssessmentScenario)
from tests.generators.business_generator import (BusinessGenerator,
                                                 BusinessScenario)


class TestBusinessGenerator:
    """Test business data generator functionality"""

    def test_deterministic_generation(self):
        """Test that generators produce deterministic output"""
        gen1 = BusinessGenerator(seed=42)
        gen2 = BusinessGenerator(seed=42)

        business1 = gen1.generate_business(BusinessScenario.RESTAURANTS)
        business2 = gen2.generate_business(BusinessScenario.RESTAURANTS)

        assert business1.name == business2.name
        assert business1.address == business2.address
        assert business1.phone == business2.phone
        assert business1.rating == business2.rating

    def test_restaurant_scenario(self):
        """Test restaurant business generation"""
        gen = BusinessGenerator(seed=42)
        business = gen.generate_business(BusinessScenario.RESTAURANTS)

        assert isinstance(business, Business)
        assert business.vertical == "restaurants"
        assert business.categories is not None
        assert any(
            cat
            in [
                "restaurant",
                "italian",
                "chinese",
                "mexican",
                "pizza",
                "cafe",
                "bistro",
            ]
            for cat in business.categories
        )
        assert 3.0 <= business.rating <= 5.0
        assert 1 <= business.price_level <= 4

    def test_healthcare_scenario(self):
        """Test healthcare business generation"""
        gen = BusinessGenerator(seed=42)
        business = gen.generate_business(BusinessScenario.HEALTHCARE)

        assert business.vertical == "healthcare"
        assert any(
            cat in ["medical", "dental", "therapy", "clinic", "hospital"]
            for cat in business.categories
        )
        assert 3.8 <= business.rating <= 4.9
        assert 3 <= business.price_level <= 4

    def test_professional_services_scenario(self):
        """Test professional services business generation"""
        gen = BusinessGenerator(seed=42)
        business = gen.generate_business(BusinessScenario.PROFESSIONAL_SERVICES)

        assert business.vertical == "professional_services"
        assert any(
            cat in ["legal", "accounting", "consulting", "financial", "insurance"]
            for cat in business.categories
        )
        assert 4.0 <= business.rating <= 4.8

    def test_multiple_businesses_generation(self):
        """Test generating multiple businesses"""
        gen = BusinessGenerator(seed=42)
        businesses = gen.generate_businesses(10)

        assert len(businesses) == 10
        assert all(isinstance(b, Business) for b in businesses)

        # Should have variety in scenarios
        verticals = [b.vertical for b in businesses]
        assert len(set(verticals)) > 1

    def test_performance_dataset_generation(self):
        """Test performance dataset generation"""
        gen = BusinessGenerator(seed=42)

        # Test different sizes
        small = gen.generate_performance_dataset("small")
        medium = gen.generate_performance_dataset("medium")
        large = gen.generate_performance_dataset("large")

        assert len(small) == 100
        assert len(medium) == 1000
        assert len(large) == 5000

        # All should be valid businesses
        assert all(isinstance(b, Business) for b in small)

    def test_scenario_dataset_generation(self):
        """Test scenario-specific dataset generation"""
        gen = BusinessGenerator(seed=42)
        restaurants = gen.generate_scenario_dataset(BusinessScenario.RESTAURANTS, 20)

        assert len(restaurants) == 20
        assert all(b.vertical == "restaurants" for b in restaurants)

    def test_mixed_dataset_generation(self):
        """Test mixed scenario dataset generation"""
        gen = BusinessGenerator(seed=42)
        counts = {
            BusinessScenario.RESTAURANTS: 10,
            BusinessScenario.HEALTHCARE: 5,
            BusinessScenario.AUTOMOTIVE: 8,
        }

        businesses = gen.generate_mixed_dataset(counts)
        assert len(businesses) == 23

        # Check counts by vertical
        verticals = [b.vertical for b in businesses]
        assert verticals.count("restaurants") == 10
        assert verticals.count("healthcare") == 5
        assert verticals.count("automotive") == 8

    def test_realistic_data_quality(self):
        """Test that generated data is realistic"""
        gen = BusinessGenerator(seed=42)
        business = gen.generate_business(BusinessScenario.RETAIL)

        # Basic field validation
        assert business.name is not None and len(business.name) > 0
        assert business.address is not None and len(business.address) > 0
        assert business.city is not None and len(business.city) > 0
        assert business.state is not None and len(business.state) == 2
        assert business.zip_code is not None and len(business.zip_code) == 5
        assert business.phone is not None and len(business.phone) == 12  # XXX-XXX-XXXX

        # Coordinate validation
        assert 25.0 <= business.latitude <= 49.0
        assert -125.0 <= business.longitude <= -65.0

        # Rating validation
        assert isinstance(business.rating, Decimal)
        assert 0.0 <= business.rating <= 5.0

        # Categories validation
        assert isinstance(business.categories, list)
        assert len(business.categories) >= 1


class TestAssessmentGenerator:
    """Test assessment data generator functionality"""

    def test_deterministic_generation(self):
        """Test that assessment generation is deterministic"""
        gen1 = AssessmentGenerator(seed=42)
        gen2 = AssessmentGenerator(seed=42)

        # Create a test business
        business_gen = BusinessGenerator(seed=42)
        business = business_gen.generate_business(BusinessScenario.RESTAURANTS)

        assessment1 = gen1.generate_assessment(
            business, AssessmentScenario.HIGH_PERFORMANCE
        )
        assessment2 = gen2.generate_assessment(
            business, AssessmentScenario.HIGH_PERFORMANCE
        )

        assert assessment1.performance_score == assessment2.performance_score
        assert assessment1.accessibility_score == assessment2.accessibility_score
        assert assessment1.seo_score == assessment2.seo_score

    def test_high_performance_scenario(self):
        """Test high performance assessment scenario"""
        gen = AssessmentGenerator(seed=42)
        business_gen = BusinessGenerator(seed=42)
        business = business_gen.generate_business(BusinessScenario.RESTAURANTS)

        assessment = gen.generate_assessment(
            business, AssessmentScenario.HIGH_PERFORMANCE
        )

        assert isinstance(assessment, AssessmentResult)
        assert 85 <= assessment.performance_score <= 98
        assert 90 <= assessment.accessibility_score <= 100
        assert 88 <= assessment.best_practices_score <= 96
        assert 85 <= assessment.seo_score <= 95

    def test_poor_performance_scenario(self):
        """Test poor performance assessment scenario"""
        gen = AssessmentGenerator(seed=42)
        business_gen = BusinessGenerator(seed=42)
        business = business_gen.generate_business(BusinessScenario.RESTAURANTS)

        assessment = gen.generate_assessment(
            business, AssessmentScenario.POOR_PERFORMANCE
        )

        assert 15 <= assessment.performance_score <= 45
        assert 30 <= assessment.accessibility_score <= 60
        assert 25 <= assessment.best_practices_score <= 55
        assert 20 <= assessment.seo_score <= 50

    def test_mobile_optimized_scenario(self):
        """Test mobile optimized assessment scenario"""
        gen = AssessmentGenerator(seed=42)
        business_gen = BusinessGenerator(seed=42)
        business = business_gen.generate_business(BusinessScenario.RESTAURANTS)

        assessment = gen.generate_assessment(
            business, AssessmentScenario.MOBILE_OPTIMIZED
        )

        # Mobile score should be higher than desktop for this scenario
        mobile_score = assessment.assessment_metadata["mobile_score"]
        desktop_score = assessment.assessment_metadata["desktop_score"]

        assert mobile_score >= 85
        assert mobile_score > desktop_score

    def test_pagespeed_data_generation(self):
        """Test PageSpeed data generation"""
        gen = AssessmentGenerator(seed=42)
        scores = {
            "performance_score": 85,
            "accessibility_score": 90,
            "best_practices_score": 88,
            "seo_score": 87,
            "mobile_score": 89,
            "desktop_score": 91,
        }

        pagespeed_data = gen.generate_pagespeed_data(
            AssessmentScenario.HIGH_PERFORMANCE, scores
        )

        assert pagespeed_data["performance_score"] == 85
        assert "core_web_vitals" in pagespeed_data
        assert "first_contentful_paint" in pagespeed_data["core_web_vitals"]
        assert "largest_contentful_paint" in pagespeed_data["core_web_vitals"]
        assert "cumulative_layout_shift" in pagespeed_data["core_web_vitals"]
        assert "first_input_delay" in pagespeed_data["core_web_vitals"]

        # Load time should correlate with performance score
        assert 0.8 <= pagespeed_data["load_time"] <= 2.1  # High performance range

    def test_tech_stack_data_generation(self):
        """Test technology stack detection data"""
        gen = AssessmentGenerator(seed=42)
        tech_data = gen.generate_tech_stack_data(AssessmentScenario.HIGH_PERFORMANCE)

        assert "detected_technologies" in tech_data
        assert "cms_detected" in tech_data
        assert "javascript_framework" in tech_data
        assert "css_framework" in tech_data
        assert "analytics_tools" in tech_data
        assert "security_features" in tech_data
        assert "hosting_info" in tech_data

        # Should have some detected technologies
        assert len(tech_data["detected_technologies"]) > 0

        # Each technology should have required fields
        for tech in tech_data["detected_technologies"]:
            assert "name" in tech
            assert "confidence" in tech
            assert "version" in tech
            assert "category" in tech
            assert 0.0 <= tech["confidence"] <= 1.0

    def test_ai_insights_generation(self):
        """Test AI insights data generation"""
        gen = AssessmentGenerator(seed=42)
        scores = {
            "performance_score": 85,
            "accessibility_score": 90,
            "best_practices_score": 88,
            "seo_score": 87,
        }

        insights = gen.generate_ai_insights_data(
            AssessmentScenario.HIGH_PERFORMANCE, scores
        )

        assert "overall_score" in insights
        assert "strengths" in insights
        assert "issues" in insights
        assert "recommendations" in insights
        assert "competitor_analysis" in insights
        assert "industry_benchmarks" in insights
        assert "improvement_potential" in insights
        assert "analysis_confidence" in insights

        # Should have strengths for high performance
        assert len(insights["strengths"]) > 0

        # Recommendations should have proper structure
        assert len(insights["recommendations"]) > 0
        for rec in insights["recommendations"]:
            assert "recommendation" in rec
            assert "priority" in rec
            assert "estimated_impact" in rec
            assert "implementation_effort" in rec
            assert "category" in rec

    def test_multiple_assessments_generation(self):
        """Test generating multiple assessments"""
        gen = AssessmentGenerator(seed=42)
        business_gen = BusinessGenerator(seed=42)
        businesses = business_gen.generate_businesses(5)

        assessments = gen.generate_assessments(businesses)

        assert len(assessments) == 5
        assert all(isinstance(a, AssessmentResult) for a in assessments)

        # Should have variety in scenarios
        scenarios = [a.assessment_metadata["generated_scenario"] for a in assessments]
        assert len(set(scenarios)) > 1

    def test_performance_dataset_generation(self):
        """Test performance dataset generation for assessments"""
        gen = AssessmentGenerator(seed=42)
        business_gen = BusinessGenerator(seed=42)
        businesses = business_gen.generate_businesses(10)

        # Test different sizes
        small = gen.generate_performance_dataset(businesses, "small")
        medium = gen.generate_performance_dataset(businesses, "medium")
        large = gen.generate_performance_dataset(businesses, "large")

        assert len(small) == 10  # Same as input businesses
        assert len(medium) == 20  # 2x businesses
        assert len(large) == 30  # 3x businesses

        assert all(isinstance(a, AssessmentResult) for a in small)

    def test_realistic_assessment_data(self):
        """Test that assessment data is realistic"""
        gen = AssessmentGenerator(seed=42)
        business_gen = BusinessGenerator(seed=42)
        business = business_gen.generate_business(BusinessScenario.RESTAURANTS)

        assessment = gen.generate_assessment(business, AssessmentScenario.MIXED_RESULTS)

        # Basic validation
        assert assessment.business_id == business.id
        assert assessment.url is not None
        assert assessment.domain is not None
        assert assessment.user_agent is not None

        # Score validation
        assert 0 <= assessment.performance_score <= 100
        assert 0 <= assessment.accessibility_score <= 100
        assert 0 <= assessment.best_practices_score <= 100
        assert 0 <= assessment.seo_score <= 100

        # Data structures validation
        assert isinstance(assessment.pagespeed_data, dict)
        assert isinstance(assessment.tech_stack_data, dict)
        assert isinstance(assessment.ai_insights_data, dict)
        assert isinstance(assessment.assessment_metadata, dict)

        # Timestamps validation
        assert isinstance(assessment.created_at, datetime)

    def test_seed_reset_functionality(self):
        """Test that generators can reset their seed"""
        gen = AssessmentGenerator(seed=42)
        business_gen = BusinessGenerator(seed=42)
        business = business_gen.generate_business(BusinessScenario.RESTAURANTS)

        assessment1 = gen.generate_assessment(
            business, AssessmentScenario.HIGH_PERFORMANCE
        )

        # Reset seed and generate again
        gen.reset_seed(42)
        assessment2 = gen.generate_assessment(
            business, AssessmentScenario.HIGH_PERFORMANCE
        )

        assert assessment1.performance_score == assessment2.performance_score
        assert assessment1.accessibility_score == assessment2.accessibility_score


class TestGeneratorIntegration:
    """Test integration between business and assessment generators"""

    def test_full_data_generation_workflow(self):
        """Test complete workflow of generating businesses and assessments"""
        business_gen = BusinessGenerator(seed=42)
        assessment_gen = AssessmentGenerator(seed=42)

        # Generate businesses
        businesses = business_gen.generate_businesses(10)

        # Generate assessments for all businesses
        assessments = assessment_gen.generate_assessments(businesses)

        assert len(businesses) == len(assessments)

        # Verify relationships
        business_ids = [b.id for b in businesses]
        assessment_business_ids = [a.business_id for a in assessments]

        for assessment_bid in assessment_business_ids:
            assert assessment_bid in business_ids

    def test_scenario_specific_workflow(self):
        """Test scenario-specific generation workflow"""
        business_gen = BusinessGenerator(seed=42)
        assessment_gen = AssessmentGenerator(seed=42)

        # Generate restaurant businesses
        restaurants = business_gen.generate_scenario_dataset(
            BusinessScenario.RESTAURANTS, 5
        )

        # Generate high-performance assessments for them
        assessments = []
        for restaurant in restaurants:
            assessment = assessment_gen.generate_assessment(
                restaurant, AssessmentScenario.HIGH_PERFORMANCE
            )
            assessments.append(assessment)

        assert len(assessments) == 5
        assert all(a.performance_score >= 85 for a in assessments)
        assert all(restaurants[i].id == assessments[i].business_id for i in range(5))

    def test_performance_data_generation(self):
        """Test large-scale data generation for performance testing"""
        business_gen = BusinessGenerator(seed=42)
        assessment_gen = AssessmentGenerator(seed=42)

        # Generate large dataset
        businesses = business_gen.generate_performance_dataset(
            "medium"
        )  # 1000 businesses

        # Sample assessments (not all, for performance)
        sample_businesses = businesses[:100]
        assessments = assessment_gen.generate_performance_dataset(
            sample_businesses, "small"
        )

        assert len(businesses) == 1000
        assert len(assessments) == 100

        # Verify data quality on sample
        assert all(isinstance(b, Business) for b in sample_businesses)
        assert all(isinstance(a, AssessmentResult) for a in assessments)
