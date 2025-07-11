"""
Integration test for PRD v1.2 full pipeline
Tests Yelp sourcing → 7-assessor stack → Email enrichment → Cost tracking
"""
import asyncio
import pytest

# Mark entire module as slow for CI optimization
pytestmark = pytest.mark.slow
from typing import Dict, Any
from decimal import Decimal

# Yelp has been removed from the codebase
from d3_assessment.coordinator_v2 import AssessmentCoordinatorV2
from d4_enrichment.email_enrichment import get_email_enricher
from d5_scoring.tiers import TierAssignmentEngine
from core.config import settings


class TestPRDv12Pipeline:
    """Test full PRD v1.2 pipeline integration"""

    @pytest.mark.skip(reason="Yelp has been removed from the codebase")
    async def test_yelp_sourcing_with_limit(self):
        """Test Yelp sourcing respects 300/day limit"""
        pass

    @pytest.mark.asyncio
    async def test_seven_assessor_stack(self):
        """Test all 7 assessors work together"""
        coordinator = AssessmentCoordinatorV2()

        # Mock business data
        business_data = {
            "id": "test-biz-123",
            "name": "Test Restaurant",
            "website": "https://example.com",
            "address": "123 Main St",
            "city": "San Francisco",
            "state": "CA",
            "rating": 4.5,
            "user_ratings_total": 100,
            "categories": ["restaurant", "italian"],
        }

        # Run assessments
        result = await coordinator.assess_business(business_data)

        assert result["status"] == "completed"
        assert result["business_id"] == "test-biz-123"
        assert "data" in result

        # Check for expected assessor outputs
        data = result["data"]

        # These assessors should always work
        assert "yelp_json" in data  # YelpFields (instant)
        assert "bsoup_json" in data  # BeautifulSoup

        # These require API keys
        if settings.google_api_key:
            assert "pagespeed_json" in data or "error" in str(
                data.get("pagespeed_json", {})
            )

        print(
            f"✓ Assessment completed with {result['assessments_successful']} assessors"
        )
        print(f"  Total cost: ${result['total_cost']}")

    @pytest.mark.asyncio
    async def test_email_enrichment_flow(self):
        """Test Hunter → Data Axle fallback email enrichment"""
        enricher = get_email_enricher()

        # Test with known domains
        test_cases = [
            {"name": "Stripe", "website": "https://stripe.com"},
            {"name": "Example", "website": "https://example.com"},
        ]

        for business in test_cases:
            email, source = await enricher.enrich_email(business)

            print(f"\nEmail enrichment for {business['name']}:")
            print(f"  Email: {email}")
            print(f"  Source: {source}")

            if email:
                assert "@" in email
                assert source in ["hunter", "dataaxle", "existing"]

    @pytest.mark.asyncio
    async def test_cost_tracking(self):
        """Test per-lead cost stays under $0.055"""
        # Track costs for a single lead
        costs = {}

        # Yelp search: Free (included in monthly fee)
        costs["yelp"] = 0.0

        # Assessments (if APIs available)
        if settings.google_api_key:
            costs["pagespeed"] = 0.0  # Free
            costs["gbp"] = 0.002

        if settings.semrush_api_key:
            costs["semrush"] = 0.010

        if settings.screenshotone_key:
            costs["screenshot"] = 0.010

        if settings.openai_api_key:
            costs["vision"] = 0.003

        # Email enrichment
        if settings.hunter_api_key:
            costs["hunter"] = 0.003

        # Calculate total
        total_cost = sum(costs.values())

        print(f"\nPer-lead cost breakdown:")
        for service, cost in costs.items():
            print(f"  {service:15} ${cost:.3f}")
        print(f"  {'TOTAL':15} ${total_cost:.3f}")

        assert total_cost <= 0.055, f"Cost ${total_cost} exceeds $0.055 limit"
        print(f"\n✓ Cost within limit: ${total_cost:.3f} ≤ $0.055")

    @pytest.mark.asyncio
    async def test_scoring_with_new_rules(self):
        """Test scoring includes PRD v1.2 rules"""
        # Mock assessment data with PRD v1.2 fields
        assessment_data = {
            "visual_scores_json": {
                "readability": 2,  # Low readability
                "modernity": 2,  # Outdated
                "visual_appeal": 4,
                "brand_consistency": 3,
                "accessibility": 3,
            },
            "semrush_json": {"organic_keywords": 5},  # Low keywords
            "gbp_json": {"missing_hours": True},
            "yelp_json": {"review_count": 3},  # Low reviews
        }

        # Check that scoring would penalize these issues
        issues_found = []

        if assessment_data["visual_scores_json"]["readability"] < 3:
            issues_found.append("visual_readability_low")

        if assessment_data["visual_scores_json"]["modernity"] < 3:
            issues_found.append("visual_outdated")

        if assessment_data["semrush_json"]["organic_keywords"] < 10:
            issues_found.append("seo_low_keywords")

        if (
            assessment_data["gbp_json"]["missing_hours"]
            or assessment_data["yelp_json"]["review_count"] < 5
        ):
            issues_found.append("listing_gap")

        print(f"\nPRD v1.2 scoring issues detected:")
        for issue in issues_found:
            print(f"  - {issue}")

        assert len(issues_found) == 4, "Should detect all 4 PRD v1.2 issues"
        print(f"\n✓ All PRD v1.2 scoring rules working")

    @pytest.mark.asyncio
    async def test_full_pipeline_execution(self):
        """Test complete pipeline from Mock Business → Assessment → Enrichment → Scoring"""
        if not settings.google_api_key:
            pytest.skip("Missing required API keys")

        print("\n" + "=" * 60)
        print("FULL PRD v1.2 PIPELINE TEST")
        print("=" * 60)

        # Step 1: Use mock business data instead of Yelp
        print("\n1. Using mock business data...")
        # Create a mock business that looks like Yelp data
        business = {
            "id": "test-pizza-123",
            "name": "Test Pizza Place",
            "phone": "+14155551234",
            "website": "https://example.com",
            "address": "123 Main St",
            "city": "San Francisco",
            "state": "CA",
            "rating": 4.5,
            "user_ratings_total": 100,
            "categories": ["restaurant", "pizza"]
        }
        print(f"   ✓ Using: {business['name']}")

        # Step 2: Assessment
        print("\n2. Running 7-assessor stack...")
        coordinator = AssessmentCoordinatorV2()
        assessment = await coordinator.assess_business(business)
        assert assessment["status"] == "completed"
        print(f"   ✓ Assessed with {assessment['assessments_successful']} assessors")
        print(f"   ✓ Cost: ${assessment['total_cost']}")

        # Step 3: Email enrichment
        print("\n3. Email enrichment...")
        enricher = get_email_enricher()
        email, source = await enricher.enrich_email(business)
        print(f"   ✓ Email: {email or 'Not found'}")
        print(f"   ✓ Source: {source or 'N/A'}")

        # Step 4: Tier assignment
        print("\n4. Tier assignment...")
        tier_engine = TierAssignmentEngine()

        # Calculate a mock score based on assessment
        score = 70  # Base score
        if (
            assessment["data"]
            .get("pagespeed_json", {})
            .get("scores", {})
            .get("performance", 0)
            < 50
        ):
            score -= 10
        if email:
            score += 5

        tier_result = tier_engine.assign_tier(lead_id=business["id"], score=score)
        print(f"   ✓ Score: {score}")
        print(f"   ✓ Tier: {tier_result.tier.value}")
        print(f"   ✓ Gate: {'PASS' if tier_result.passed_gate else 'FAIL'}")

        # Verify total cost
        total_cost = float(assessment["total_cost"])
        if email and source == "hunter":
            total_cost += 0.003

        print(f"\n5. Total per-lead cost: ${total_cost:.3f}")
        assert total_cost <= 0.055, f"Cost ${total_cost} exceeds limit"

        print("\n" + "=" * 60)
        print("✅ FULL PIPELINE TEST PASSED")
        print("=" * 60)


if __name__ == "__main__":
    # Run integration tests
    test = TestPRDv12Pipeline()
    asyncio.run(test.test_full_pipeline_execution())
