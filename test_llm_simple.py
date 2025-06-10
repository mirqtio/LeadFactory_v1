#!/usr/bin/env python3
"""
Simple test for LLM Insight Generator - Task 033 validation

Tests all acceptance criteria:
- 3 recommendations generated
- Industry-specific insights
- Cost tracking works
- Structured output parsing
"""
import asyncio
import json
# Import the modules
import sys
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, "/Users/charlieirwin/Documents/GitHub/Anthrasite_LeadFactory_v1")

from d3_assessment.llm_insights import LLMInsightGenerator
from d3_assessment.models import AssessmentResult
from d3_assessment.types import AssessmentStatus, AssessmentType, InsightType


async def test_task_033_acceptance_criteria():
    """Test all Task 033 acceptance criteria"""
    print("🧠 Testing Task 033: LLM Insight Generator")
    print("=" * 50)

    # Create mock LLM client
    mock_client = AsyncMock()
    mock_client.generate_completion.return_value = MagicMock(
        content=json.dumps(
            {
                "recommendations": [
                    {
                        "title": "Optimize Image Loading Performance",
                        "description": "Implement lazy loading and WebP format for e-commerce product images",
                        "priority": "High",
                        "effort": "Medium",
                        "impact": "Reduce LCP by 30-40%, improve conversion rates",
                        "implementation_steps": [
                            "Convert product images to WebP format",
                            "Implement lazy loading for below-fold images",
                            "Add image size optimization",
                        ],
                        "industry_context": "E-commerce sites benefit greatly from fast image loading to improve product discovery and reduce cart abandonment",
                    },
                    {
                        "title": "Enhance Mobile Navigation Experience",
                        "description": "Improve mobile menu design and touch targets for better e-commerce UX",
                        "priority": "Medium",
                        "effort": "Low",
                        "impact": "Better mobile conversion rates and user satisfaction",
                        "implementation_steps": [
                            "Increase touch target sizes to 44px minimum",
                            "Simplify navigation hierarchy",
                            "Add swipe gestures for product browsing",
                        ],
                        "industry_context": "Mobile optimization is crucial for e-commerce conversion as 60%+ of traffic is mobile",
                    },
                    {
                        "title": "Enable Advanced Compression",
                        "description": "Configure Gzip/Brotli compression to reduce bandwidth costs",
                        "priority": "Medium",
                        "effort": "Low",
                        "impact": "Reduce file sizes by 60-80%, faster page loads",
                        "implementation_steps": [
                            "Enable Gzip compression on web server",
                            "Configure Brotli for modern browsers",
                            "Optimize CSS and JavaScript minification",
                        ],
                        "industry_context": "Essential for all e-commerce to reduce bandwidth costs and improve global performance",
                    },
                ],
                "industry_insights": {
                    "industry": "ecommerce",
                    "benchmarks": {
                        "performance_percentile": "Your site is in the bottom 40% for e-commerce performance",
                        "key_metrics": "Focus on conversion-critical metrics like LCP and FID",
                    },
                    "competitive_advantage": "Fast loading drives 20%+ higher conversion rates in e-commerce",
                    "compliance_notes": "Consider accessibility guidelines for inclusive shopping experience",
                },
                "summary": {
                    "overall_health": "Moderate performance with clear improvement opportunities",
                    "quick_wins": "Image optimization and compression setup",
                    "long_term_strategy": "Comprehensive performance and mobile UX overhaul",
                },
            }
        ),
        usage={"prompt_tokens": 1500, "completion_tokens": 800, "total_tokens": 2300},
    )
    mock_client.get_model_version.return_value = "gpt-4-0125-preview"

    # Create sample assessment
    sample_assessment = AssessmentResult(
        id="test-assessment-123",
        business_id="test-business",
        assessment_type=AssessmentType.PAGESPEED,
        status=AssessmentStatus.COMPLETED,
        url="https://example-store.com",
        domain="example-store.com",
        performance_score=65,
        accessibility_score=78,
        seo_score=82,
        largest_contentful_paint=3500,
        first_input_delay=180,
        cumulative_layout_shift=0.15,
    )

    # Test the generator
    generator = LLMInsightGenerator(llm_client=mock_client)

    print("🔍 Generating comprehensive insights...")
    result = await generator.generate_comprehensive_insights(
        assessment=sample_assessment, industry="ecommerce"
    )

    # Test Acceptance Criteria
    print("\n📋 Testing Acceptance Criteria:")

    # 1. Test: 3 recommendations generated
    print("\n1. Testing: 3 recommendations generated")
    try:
        assert result.insights is not None, "Should have insights"
        assert (
            "recommendations" in result.insights
        ), "Should have recommendations section"
        recommendations = result.insights["recommendations"]["recommendations"]
        assert (
            len(recommendations) == 3
        ), f"Expected 3 recommendations, got {len(recommendations)}"

        # Verify each recommendation has required fields
        for i, rec in enumerate(recommendations):
            required_fields = [
                "title",
                "description",
                "priority",
                "effort",
                "impact",
                "implementation_steps",
                "industry_context",
            ]
            for field in required_fields:
                assert field in rec, f"Recommendation {i+1} missing field: {field}"

        print("   ✅ PASS: Exactly 3 recommendations generated with all required fields")
    except Exception as e:
        print(f"   ❌ FAIL: {e}")
        return False

    # 2. Test: Industry-specific insights
    print("\n2. Testing: Industry-specific insights")
    try:
        assert result.industry == "ecommerce", "Should track industry"

        # Check for industry-specific content
        industry_contexts = [rec["industry_context"] for rec in recommendations]
        ecommerce_mentions = sum(
            1
            for context in industry_contexts
            if any(
                term in context.lower()
                for term in ["ecommerce", "e-commerce", "conversion", "commerce"]
            )
        )
        assert (
            ecommerce_mentions >= 2
        ), "Should have industry-specific context in recommendations"

        # Check industry insights section
        industry_insights = result.insights["recommendations"]["industry_insights"]
        assert (
            industry_insights["industry"] == "ecommerce"
        ), "Should identify correct industry"
        assert "benchmarks" in industry_insights, "Should have industry benchmarks"

        print("   ✅ PASS: Industry-specific insights provided for e-commerce")
    except Exception as e:
        print(f"   ❌ FAIL: {e}")
        return False

    # 3. Test: Cost tracking works
    print("\n3. Testing: Cost tracking works")
    try:
        assert result.total_cost_usd > Decimal("0"), "Should track non-zero cost"
        assert isinstance(result.total_cost_usd, Decimal), "Cost should be Decimal type"

        # Verify cost calculation (1500 input + 800 output tokens)
        expected_cost = (1500 * Decimal("0.00003")) + (800 * Decimal("0.00006"))
        cost_diff = abs(result.total_cost_usd - expected_cost)
        assert cost_diff < Decimal(
            "0.001"
        ), f"Cost calculation incorrect: expected ~{expected_cost}, got {result.total_cost_usd}"

        print(f"   ✅ PASS: Cost tracking works (${result.total_cost_usd})")
    except Exception as e:
        print(f"   ❌ FAIL: {e}")
        return False

    # 4. Test: Structured output parsing
    print("\n4. Testing: Structured output parsing")
    try:
        # Verify structure
        assert isinstance(result.insights, dict), "Insights should be dictionary"
        recommendations_data = result.insights["recommendations"]
        assert isinstance(
            recommendations_data, dict
        ), "Recommendations should be structured dict"

        required_sections = ["recommendations", "industry_insights", "summary"]
        for section in required_sections:
            assert section in recommendations_data, f"Missing section: {section}"

        # Verify recommendations structure
        recs = recommendations_data["recommendations"]
        assert isinstance(recs, list), "Recommendations should be list"
        assert all(
            isinstance(rec, dict) for rec in recs
        ), "Each recommendation should be dict"

        print("   ✅ PASS: Structured output parsing works correctly")
    except Exception as e:
        print(f"   ❌ FAIL: {e}")
        return False

    # Additional verification
    print("\n🔧 Additional Verification:")
    print(f"   - Assessment ID: {result.assessment_id}")
    print(f"   - Business ID: {result.business_id}")
    print(f"   - Industry: {result.industry}")
    print(f"   - Model Version: {result.model_version}")
    print(f"   - Processing Time: {result.processing_time_ms}ms")
    print(f"   - Generated At: {result.generated_at}")
    print(f"   - Insight Types: {[t.value for t in result.insight_types]}")

    print("\n🎉 All Task 033 acceptance criteria PASSED!")
    print("   ✅ 3 recommendations generated")
    print("   ✅ Industry-specific insights")
    print("   ✅ Cost tracking works")
    print("   ✅ Structured output parsing")

    return True


if __name__ == "__main__":
    success = asyncio.run(test_task_033_acceptance_criteria())
    if success:
        print("\n✨ Task 033 implementation is ready!")
        exit(0)
    else:
        print("\n💥 Task 033 needs fixes")
        exit(1)
