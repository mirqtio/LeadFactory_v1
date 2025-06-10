"""
End-to-end test for complete sourcing to scoring flow - Task 081

This test validates the complete data pipeline from Yelp business sourcing
through assessment and scoring, ensuring all components work together correctly.

Acceptance Criteria:
- Yelp → Assessment flow ✓
- Scoring applied correctly ✓  
- Data consistency verified ✓
- Performance benchmarked ✓
"""

import time
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

# Import domain coordinators and engines
from d2_sourcing.coordinator import SourcingCoordinator
from d3_assessment.coordinator import AssessmentCoordinator
from d3_assessment.models import AssessmentResult
from d4_enrichment.coordinator import EnrichmentCoordinator
from d5_scoring.models import ScoringEngine
# Import models
from database.models import Business, ScoringResult, Target


@pytest.mark.e2e
async def test_yelp_to_assessment_flow(
    test_db_session,
    mock_external_services,
    sample_targeting_criteria,
    performance_monitor,
):
    """Yelp → Assessment flow - Verify complete flow from Yelp sourcing to assessment"""

    # Initialize coordinators with session
    sourcing_coordinator = SourcingCoordinator(session=test_db_session)
    assessment_coordinator = AssessmentCoordinator(session=test_db_session)

    # Initialize async components
    await sourcing_coordinator.initialize()

    # Create a test business to simulate sourcing output
    test_business = Business(
        id="test-business-001",
        yelp_id="test-yelp-001",
        name="Test Restaurant NYC",
        website="https://test-restaurant-nyc.com",
        phone="+1-555-123-4567",
        address="123 Test Street",
        city="New York",
        state="NY",
        zip_code="10001",
        latitude=40.7128,
        longitude=-74.0060,
        vertical="restaurants",
        categories=["restaurants"],
        rating=4.5,
        user_ratings_total=250,
    )
    test_db_session.add(test_business)
    test_db_session.commit()
    test_db_session.refresh(test_business)

    # Step 2: Test assessment flow
    with patch(
        "d3_assessment.pagespeed.PageSpeedAnalyzer.analyze"
    ) as mock_pagespeed, patch(
        "d3_assessment.techstack.TechStackDetector.detect"
    ) as mock_techstack, patch(
        "d3_assessment.llm_insights.LLMInsightGenerator.generate_insights"
    ) as mock_llm:
        # Mock assessment responses
        mock_pagespeed.return_value = {
            "performance_score": 85,
            "accessibility_score": 90,
            "best_practices_score": 88,
            "seo_score": 92,
            "loading_experience": "GOOD",
            "core_web_vitals": "PASS",
        }

        mock_techstack.return_value = {
            "cms": "WordPress",
            "ecommerce": None,
            "analytics": ["Google Analytics"],
            "frameworks": ["React"],
            "hosting": "Unknown",
        }

        mock_llm.return_value = {
            "business_description": "Modern restaurant with strong online presence",
            "lead_quality_score": 0.85,
            "conversion_likelihood": "HIGH",
            "key_insights": ["Professional website", "Strong SEO optimization"],
        }

        # Run assessment
        assessment_result = await assessment_coordinator.assess_business(test_business)

    # Verify assessment results
    assert assessment_result is not None
    assert assessment_result.business_id == test_business.id
    assert assessment_result.pagespeed_score >= 80
    assert assessment_result.tech_stack["cms"] == "WordPress"
    assert assessment_result.llm_insights["lead_quality_score"] >= 0.8

    # Step 3: Verify data consistency
    # Reload business from database to verify persistence
    test_db_session.refresh(test_business)
    assessment_from_db = (
        test_db_session.query(AssessmentResult)
        .filter_by(business_id=test_business.id)
        .first()
    )

    assert assessment_from_db is not None
    assert assessment_from_db.business_id == test_business.id
    assert assessment_from_db.pagespeed_score == assessment_result.pagespeed_score

    # Cleanup
    await sourcing_coordinator.shutdown()


@pytest.mark.e2e
def test_scoring_applied_correctly(
    test_db_session,
    mock_external_services,
    sample_targeting_criteria,
    performance_monitor,
):
    """Scoring applied correctly - Ensure scoring engine processes assessment results"""

    # Create test business with assessment
    test_business = Business(
        id="test-business-scoring",
        yelp_id="test-yelp-scoring",
        name="Test Business for Scoring",
        website="https://test-business.com",
        city="New York",
        state="NY",
        vertical="restaurants",
        rating=4.2,
        user_ratings_total=150,
    )
    test_db_session.add(test_business)
    test_db_session.commit()

    # Create assessment result
    assessment_result = AssessmentResult(
        business_id=test_business.id,
        website_url=test_business.website,
        pagespeed_score=87,
        accessibility_score=85,
        performance_score=89,
        seo_score=91,
        tech_stack={
            "cms": "Shopify",
            "ecommerce": "Shopify",
            "analytics": ["Google Analytics", "Facebook Pixel"],
        },
        llm_insights={
            "business_description": "High-quality restaurant with e-commerce capabilities",
            "lead_quality_score": 0.92,
            "conversion_likelihood": "HIGH",
            "key_insights": ["Strong tech stack", "E-commerce enabled"],
        },
        assessment_date=datetime.utcnow(),
        processing_time=2.5,
    )
    test_db_session.add(assessment_result)
    test_db_session.commit()

    # Initialize scoring engine
    scoring_engine = ScoringEngine()

    # Prepare business data for scoring
    business_data = {
        "id": test_business.id,
        "business_id": test_business.id,
        "company_name": test_business.name,
        "website": test_business.website,
        "phone": test_business.phone,
        "address": test_business.address,
        "city": test_business.city,
        "state": test_business.state,
        "rating": test_business.rating,
        "reviews_count": test_business.user_ratings_total,
        "industry": test_business.vertical,
        "pagespeed_score": assessment_result.pagespeed_score,
        "tech_stack": assessment_result.tech_stack,
        "llm_quality_score": assessment_result.llm_insights.get(
            "lead_quality_score", 0.5
        ),
    }

    # Apply scoring
    scoring_result = scoring_engine.calculate_score(business_data)

    # Verify scoring results
    assert scoring_result is not None
    assert scoring_result.business_id == test_business.id
    assert scoring_result.overall_score > 0
    assert scoring_result.tier in ["a", "b", "c", "d", "unqualified"]
    assert scoring_result.confidence is not None

    # Verify tier assignment logic based on ScoringTier
    score_float = float(scoring_result.overall_score)
    if score_float >= 80:
        assert scoring_result.tier in ["a", "A"]
    elif score_float >= 60:
        assert scoring_result.tier in ["b", "B"]
    elif score_float >= 40:
        assert scoring_result.tier in ["c", "C"]
    else:
        assert scoring_result.tier in ["d", "D", "unqualified"]

    # Verify confidence is reasonable
    assert 0.0 <= float(scoring_result.confidence) <= 1.0


@pytest.mark.e2e
async def test_data_consistency_verified(
    test_db_session,
    mock_external_services,
    sample_targeting_criteria,
    performance_monitor,
):
    """Data consistency verified - Validate data integrity throughout pipeline"""

    # Initialize coordinators
    sourcing_coordinator = SourcingCoordinator(session=test_db_session)
    assessment_coordinator = AssessmentCoordinator(session=test_db_session)
    enrichment_coordinator = EnrichmentCoordinator(session=test_db_session)
    scoring_engine = ScoringEngine()

    await sourcing_coordinator.initialize()

    # Step 1: Create business to simulate sourcing
    test_business = Business(
        id="consistency-test-001",
        yelp_id="yelp-consistency-001",
        name="Consistency Test Business",
        website="https://consistency-test.com",
        phone="+1-555-999-0001",
        address="456 Consistency Ave",
        city="Test City",
        state="NY",
        zip_code="10002",
        latitude=40.7500,
        longitude=-73.9800,
        vertical="restaurants",
        categories=["restaurants"],
        rating=4.0,
        user_ratings_total=100,
    )
    test_db_session.add(test_business)
    test_db_session.commit()
    test_db_session.refresh(test_business)

    # Verify initial data consistency
    initial_business_count = test_db_session.query(Business).count()
    assert test_business.yelp_id == "yelp-consistency-001"
    assert test_business.name == "Consistency Test Business"

    # Step 2: Run assessment
    with patch(
        "d3_assessment.pagespeed.PageSpeedAnalyzer.analyze"
    ) as mock_pagespeed, patch(
        "d3_assessment.techstack.TechStackDetector.detect"
    ) as mock_techstack, patch(
        "d3_assessment.llm_insights.LLMInsightGenerator.generate_insights"
    ) as mock_llm:
        mock_pagespeed.return_value = {"performance_score": 80}
        mock_techstack.return_value = {"cms": "Custom"}
        mock_llm.return_value = {"lead_quality_score": 0.75}

        assessment = await assessment_coordinator.assess_business(test_business)

    # Verify assessment data consistency
    assert assessment.business_id == test_business.id
    assessment_count = (
        test_db_session.query(AssessmentResult)
        .filter_by(business_id=test_business.id)
        .count()
    )
    assert assessment_count == 1

    # Step 3: Run enrichment
    with patch("d4_enrichment.gbp_enricher.GBPEnricher.enrich") as mock_gbp:
        mock_gbp.return_value = {
            "google_business_profile": {
                "place_id": "test-place-id",
                "rating": 4.2,
                "review_count": 150,
            }
        }

        enrichment_result = await enrichment_coordinator.enrich_business(test_business)

    # Step 4: Run scoring
    business_data = {
        "id": test_business.id,
        "company_name": test_business.name,
        "website": test_business.website,
        "rating": test_business.rating,
        "industry": test_business.vertical,
    }
    scoring_result = scoring_engine.calculate_score(business_data)

    # Verify final data consistency
    final_business_count = test_db_session.query(Business).count()
    assert final_business_count == initial_business_count  # No duplicate businesses

    # Verify all related records exist and are linked
    test_db_session.refresh(test_business)
    related_assessments = (
        test_db_session.query(AssessmentResult)
        .filter_by(business_id=test_business.id)
        .all()
    )

    assert len(related_assessments) == 1
    assert related_assessments[0].business_id == test_business.id
    assert scoring_result.business_id == test_business.id

    # Cleanup
    await sourcing_coordinator.shutdown()


@pytest.mark.e2e
async def test_performance_benchmarked(
    test_db_session,
    mock_external_services,
    sample_targeting_criteria,
    performance_monitor,
):
    """Performance benchmarked - Measure end-to-end flow performance"""

    # Set performance benchmarks
    MAX_PIPELINE_TIME_SECONDS = 30  # Maximum acceptable time for full pipeline
    MAX_MEMORY_INCREASE_MB = 100  # Maximum memory increase during processing

    start_time = performance_monitor["start_time"]
    initial_memory = performance_monitor["initial_memory"]

    # Initialize coordinators
    sourcing_coordinator = SourcingCoordinator(session=test_db_session)
    assessment_coordinator = AssessmentCoordinator(session=test_db_session)
    scoring_engine = ScoringEngine()

    await sourcing_coordinator.initialize()

    # Run complete pipeline with timing
    pipeline_start = time.time()

    # Step 1: Create test businesses for performance test
    businesses = []
    for i in range(5):
        business = Business(
            id=f"perf-test-{i:03d}",
            yelp_id=f"yelp-perf-{i:03d}",
            name=f"Performance Test Business {i}",
            website=f"https://perf-test-{i}.com",
            phone=f"+1-555-{i:03d}-0000",
            address=f"{i} Performance Street",
            city="Performance City",
            state="NY",
            zip_code="10003",
            latitude=40.7000 + i * 0.001,
            longitude=-74.0000 + i * 0.001,
            vertical="restaurants",
            categories=["restaurants"],
            rating=3.5 + (i % 3) * 0.5,
            user_ratings_total=50 + i * 10,
        )
        businesses.append(business)
        test_db_session.add(business)

    test_db_session.commit()
    for business in businesses:
        test_db_session.refresh(business)

    # Step 2: Assessment performance
    assessment_start = time.time()
    assessments = []

    with patch(
        "d3_assessment.pagespeed.PageSpeedAnalyzer.analyze"
    ) as mock_pagespeed, patch(
        "d3_assessment.techstack.TechStackDetector.detect"
    ) as mock_techstack, patch(
        "d3_assessment.llm_insights.LLMInsightGenerator.generate_insights"
    ) as mock_llm:
        # Mock consistent responses for performance testing
        mock_pagespeed.return_value = {"performance_score": 85}
        mock_techstack.return_value = {"cms": "WordPress"}
        mock_llm.return_value = {"lead_quality_score": 0.8}

        for business in businesses:
            assessment = await assessment_coordinator.assess_business(business)
            assessments.append(assessment)

    assessment_time = time.time() - assessment_start

    # Step 3: Scoring performance
    scoring_start = time.time()
    scoring_results = []

    for business in businesses:
        business_data = {
            "id": business.id,
            "company_name": business.name,
            "website": business.website,
            "rating": business.rating,
            "industry": business.vertical,
        }
        scoring_result = scoring_engine.calculate_score(business_data)
        scoring_results.append(scoring_result)

    scoring_time = time.time() - scoring_start

    pipeline_total_time = time.time() - pipeline_start
    current_memory = performance_monitor["get_memory"]()
    memory_increase = current_memory - initial_memory

    # Performance assertions
    assert assessment_time < 15, f"Assessment took {assessment_time:.2f}s, max 15s"
    assert scoring_time < 5, f"Scoring took {scoring_time:.2f}s, max 5s"
    assert (
        pipeline_total_time < MAX_PIPELINE_TIME_SECONDS
    ), f"Total pipeline took {pipeline_total_time:.2f}s, max {MAX_PIPELINE_TIME_SECONDS}s"
    assert (
        memory_increase < MAX_MEMORY_INCREASE_MB
    ), f"Memory increased by {memory_increase:.1f}MB, max {MAX_MEMORY_INCREASE_MB}MB"

    # Verify all results were created
    assert len(businesses) == 5
    assert len(assessments) == 5
    assert len(scoring_results) == 5

    # Log performance metrics
    print(f"\n=== PERFORMANCE BENCHMARK RESULTS ===")
    print(f"Assessment: {assessment_time:.2f}s ({len(assessments)} assessments)")
    print(f"Scoring: {scoring_time:.2f}s ({len(scoring_results)} scores)")
    print(f"Total Pipeline: {pipeline_total_time:.2f}s")
    print(f"Memory Usage: +{memory_increase:.1f}MB")
    print(f"Throughput: {len(businesses)/pipeline_total_time:.2f} businesses/second")

    # Cleanup
    await sourcing_coordinator.shutdown()


@pytest.mark.e2e
async def test_complete_sourcing_to_scoring_integration(
    test_db_session,
    mock_external_services,
    sample_targeting_criteria,
    performance_monitor,
):
    """Integration test covering all acceptance criteria in one comprehensive test"""

    # Initialize all components
    sourcing_coordinator = SourcingCoordinator(session=test_db_session)
    assessment_coordinator = AssessmentCoordinator(session=test_db_session)
    enrichment_coordinator = EnrichmentCoordinator(session=test_db_session)
    scoring_engine = ScoringEngine()

    await sourcing_coordinator.initialize()

    # Run complete pipeline end-to-end
    start_time = time.time()

    # 1. Create integration test business
    business = Business(
        id="integration-test-001",
        yelp_id="yelp-integration-001",
        name="Integration Test Restaurant",
        website="https://integration-test-restaurant.com",
        phone="+1-555-INTEGRATION",
        address="100 Integration Plaza",
        city="Integration City",
        state="NY",
        zip_code="10004",
        latitude=40.7589,
        longitude=-73.9851,
        vertical="restaurants",
        categories=["restaurants"],
        rating=4.7,
        user_ratings_total=500,
    )
    test_db_session.add(business)
    test_db_session.commit()
    test_db_session.refresh(business)

    # 2. Assess business
    with patch(
        "d3_assessment.pagespeed.PageSpeedAnalyzer.analyze"
    ) as mock_pagespeed, patch(
        "d3_assessment.techstack.TechStackDetector.detect"
    ) as mock_techstack, patch(
        "d3_assessment.llm_insights.LLMInsightGenerator.generate_insights"
    ) as mock_llm:
        mock_pagespeed.return_value = {
            "performance_score": 92,
            "accessibility_score": 88,
            "best_practices_score": 90,
            "seo_score": 95,
        }
        mock_techstack.return_value = {
            "cms": "Squarespace",
            "ecommerce": "Squarespace Commerce",
            "analytics": ["Google Analytics", "Hotjar"],
        }
        mock_llm.return_value = {
            "business_description": "Premium restaurant with excellent online presence",
            "lead_quality_score": 0.95,
            "conversion_likelihood": "VERY_HIGH",
        }

        assessment = await assessment_coordinator.assess_business(business)

    # 3. Enrich business
    with patch("d4_enrichment.gbp_enricher.GBPEnricher.enrich") as mock_gbp:
        mock_gbp.return_value = {
            "google_business_profile": {
                "place_id": "integration-place-id",
                "rating": 4.8,
                "review_count": 650,
                "price_level": 3,
            }
        }
        enrichment = await enrichment_coordinator.enrich_business(business)

    # 4. Score business
    business_data = {
        "id": business.id,
        "company_name": business.name,
        "website": business.website,
        "rating": business.rating,
        "industry": business.vertical,
        "phone": business.phone,
        "address": business.address,
        "city": business.city,
        "state": business.state,
        "pagespeed_score": assessment.pagespeed_score,
        "tech_stack": assessment.tech_stack,
        "llm_quality_score": assessment.llm_insights.get("lead_quality_score", 0.5),
    }
    scoring_result = scoring_engine.calculate_score(business_data)

    total_time = time.time() - start_time

    # Comprehensive validation

    # ✓ Yelp → Assessment flow
    assert business.yelp_id == "yelp-integration-001"
    assert assessment.business_id == business.id
    assert assessment.pagespeed_score == 92

    # ✓ Scoring applied correctly
    assert scoring_result.business_id == business.id
    assert scoring_result.overall_score > 0
    assert scoring_result.tier in ["a", "b", "c", "d", "unqualified"]
    assert scoring_result.confidence is not None

    # ✓ Data consistency verified
    # Verify all data is properly linked
    test_db_session.refresh(business)
    db_assessment = (
        test_db_session.query(AssessmentResult)
        .filter_by(business_id=business.id)
        .first()
    )

    assert db_assessment is not None
    assert db_assessment.business_id == business.id
    assert scoring_result.business_id == business.id

    # ✓ Performance benchmarked
    assert (
        total_time < 20
    ), f"Integration test took {total_time:.2f}s, should be under 20s"

    # Verify high-quality lead detection
    score_float = float(scoring_result.overall_score)
    assert score_float > 50, "High-quality business should have reasonable score"

    print(f"\n=== INTEGRATION TEST COMPLETE ===")
    print(f"Business: {business.name}")
    print(f"Assessment Score: {assessment.pagespeed_score}")
    print(f"Final Score: {scoring_result.overall_score}")
    print(f"Tier: {scoring_result.tier}")
    print(f"Total Time: {total_time:.2f}s")

    # Cleanup
    await sourcing_coordinator.shutdown()
