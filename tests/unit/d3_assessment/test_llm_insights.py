"""
Test LLM Insight Generator - Task 033

Comprehensive tests for LLM insight generation functionality.
Tests all acceptance criteria:
- 3 recommendations generated
- Industry-specific insights
- Cost tracking works
- Structured output parsing
"""
import json
import sys
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, "/app")  # noqa: E402

from d3_assessment.llm_insights import LLMInsightBatchGenerator  # noqa: E402
from d3_assessment.llm_insights import LLMInsightGenerator, LLMInsightResult
from d3_assessment.models import AssessmentResult  # noqa: E402
from d3_assessment.prompts import InsightPrompts  # noqa: E402
from d3_assessment.types import AssessmentStatus  # noqa: E402
from d3_assessment.types import AssessmentType, InsightType


class TestTask033AcceptanceCriteria:
    """Test that Task 033 meets all acceptance criteria"""

    @pytest.fixture
    def mock_llm_client(self):
        """Mock LLM client with realistic responses"""
        client = AsyncMock()

        # Mock recommendation response
        client.generate_completion.return_value = MagicMock(
            content=json.dumps(
                {
                    "recommendations": [
                        {
                            "title": "Optimize Image Loading",
                            "description": "Implement lazy loading and WebP format for faster page loads",
                            "priority": "High",
                            "effort": "Medium",
                            "impact": "Reduce LCP by 30-40%",
                            "implementation_steps": [
                                "Convert images to WebP format",
                                "Implement lazy loading for below-fold images",
                            ],
                            "industry_context": "E-commerce sites benefit greatly from fast image loading",
                        },
                        {
                            "title": "Improve Mobile Navigation",
                            "description": "Enhance mobile menu design and touch targets",
                            "priority": "Medium",
                            "effort": "Low",
                            "impact": "Better mobile user experience",
                            "implementation_steps": [
                                "Increase touch target sizes to 44px minimum",
                                "Simplify navigation hierarchy",
                            ],
                            "industry_context": "Mobile optimization is crucial for e-commerce conversion",
                        },
                        {
                            "title": "Enable Compression",
                            "description": "Configure Gzip/Brotli compression for text resources",
                            "priority": "Medium",
                            "effort": "Low",
                            "impact": "Reduce file sizes by 60-80%",
                            "implementation_steps": [
                                "Enable Gzip compression on server",
                                "Configure Brotli for modern browsers",
                            ],
                            "industry_context": "Essential for all industries to reduce bandwidth costs",
                        },
                    ],
                    "industry_insights": {
                        "industry": "ecommerce",
                        "benchmarks": {
                            "performance_percentile": "Your site is in the bottom 40% for e-commerce",
                            "key_metrics": "Focus on conversion-critical metrics",
                        },
                        "competitive_advantage": "Fast loading drives higher conversion rates",
                        "compliance_notes": "Consider accessibility guidelines for inclusive shopping",
                    },
                    "summary": {
                        "overall_health": "Moderate with clear improvement opportunities",
                        "quick_wins": "Image optimization and compression",
                        "long_term_strategy": "Comprehensive performance and UX overhaul",
                    },
                }
            ),
            usage={
                "prompt_tokens": 1500,
                "completion_tokens": 800,
                "total_tokens": 2300,
            },
        )

        client.get_model_version.return_value = "gpt-4-0125-preview"
        return client

    @pytest.fixture
    def sample_assessment(self):
        """Create sample assessment result for testing"""
        return AssessmentResult(
            id="test-assessment-123",
            business_id="test-business",
            assessment_type=AssessmentType.PAGESPEED,
            status=AssessmentStatus.COMPLETED,
            url="https://example-store.com",
            domain="example-store.com",
            performance_score=65,
            accessibility_score=78,
            seo_score=82,
            best_practices_score=71,
            largest_contentful_paint=3500,
            first_input_delay=180,
            cumulative_layout_shift=0.15,
            speed_index=4200,
            time_to_interactive=5100,
            total_blocking_time=320,
            pagespeed_data={
                "mobile": {
                    "lighthouseResult": {
                        "categories": {"performance": {"score": 0.65}},
                        "audits": {
                            "unused-css-rules": {
                                "score": 0.3,
                                "title": "Remove unused CSS",
                                "description": "Remove dead rules from stylesheets",
                                "details": {"overallSavingsMs": 1200},
                            },
                            "render-blocking-resources": {
                                "score": 0.4,
                                "title": "Eliminate render-blocking resources",
                                "description": "Resources are blocking the first paint",
                                "details": {"overallSavingsMs": 800},
                            },
                        },
                    }
                }
            },
            tech_stack_data={
                "technologies": [
                    {
                        "technology_name": "WordPress",
                        "category": "cms",
                        "confidence": 0.95,
                    },
                    {
                        "technology_name": "WooCommerce",
                        "category": "ecommerce",
                        "confidence": 0.90,
                    },
                ]
            },
        )

    @pytest.fixture
    def insight_generator(self, mock_llm_client):
        """Create insight generator with mocked LLM client"""
        return LLMInsightGenerator(llm_client=mock_llm_client)

    @pytest.mark.asyncio
    async def test_three_recommendations_generated(
        self, insight_generator, sample_assessment
    ):
        """
        Test that exactly 3 recommendations are generated

        Acceptance Criteria: 3 recommendations generated
        """
        result = await insight_generator.generate_comprehensive_insights(
            assessment=sample_assessment, industry="ecommerce"
        )

        # Verify result structure
        assert isinstance(result, LLMInsightResult)
        assert result.assessment_id == sample_assessment.id
        assert result.business_id == sample_assessment.business_id

        # Verify 3 recommendations
        recommendations = result.insights["recommendations"]["recommendations"]
        assert len(recommendations) == 3

        # Verify recommendation structure
        for i, rec in enumerate(recommendations):
            assert "title" in rec, f"Recommendation {i+1} missing title"
            assert "description" in rec, f"Recommendation {i+1} missing description"
            assert "priority" in rec, f"Recommendation {i+1} missing priority"
            assert "effort" in rec, f"Recommendation {i+1} missing effort"
            assert "impact" in rec, f"Recommendation {i+1} missing impact"
            assert (
                "implementation_steps" in rec
            ), f"Recommendation {i+1} missing implementation_steps"
            assert (
                "industry_context" in rec
            ), f"Recommendation {i+1} missing industry_context"

        # Verify recommendation quality
        titles = [rec["title"] for rec in recommendations]
        assert len(set(titles)) == 3, "Recommendations should be unique"

        # Check for actionable content
        for rec in recommendations:
            assert len(rec["title"]) > 5, "Title should be descriptive"
            assert len(rec["description"]) > 20, "Description should be detailed"
            assert (
                len(rec["implementation_steps"]) > 0
            ), "Should have implementation steps"

        print("✓ 3 recommendations generated correctly")

    @pytest.mark.asyncio
    async def test_industry_specific_insights(
        self, insight_generator, sample_assessment
    ):
        """
        Test that industry-specific insights are provided

        Acceptance Criteria: Industry-specific insights
        """
        # Test e-commerce specific insights
        result = await insight_generator.generate_comprehensive_insights(
            assessment=sample_assessment, industry="ecommerce"
        )

        # Verify industry context in recommendations
        recommendations = result.insights["recommendations"]["recommendations"]
        industry_contexts = [rec["industry_context"] for rec in recommendations]

        # Should mention e-commerce or related terms
        ecommerce_mentions = sum(
            1
            for context in industry_contexts
            if any(
                term in context.lower()
                for term in [
                    "ecommerce",
                    "e-commerce",
                    "conversion",
                    "shopping",
                    "commerce",
                ]
            )
        )
        assert ecommerce_mentions > 0, "Should have e-commerce specific context"

        # Verify industry insights section
        industry_insights = result.insights["recommendations"]["industry_insights"]
        assert industry_insights["industry"] == "ecommerce"
        assert "benchmarks" in industry_insights
        assert "competitive_advantage" in industry_insights

        # Test different industry
        healthcare_result = await insight_generator.generate_comprehensive_insights(
            assessment=sample_assessment, industry="healthcare"
        )

        assert healthcare_result.industry == "healthcare"

        # Verify industry-specific prompting works
        industry_context = InsightPrompts.get_industry_context("healthcare")
        assert "accessibility" in industry_context["key_metrics"]
        assert "HIPAA" in industry_context["compliance"]

        print("✓ Industry-specific insights provided correctly")

    @pytest.mark.asyncio
    async def test_cost_tracking_works(self, insight_generator, sample_assessment):
        """
        Test that cost tracking works properly

        Acceptance Criteria: Cost tracking works
        """
        with patch("d3_assessment.llm_insights.AssessmentCost") as mock_cost:
            result = await insight_generator.generate_comprehensive_insights(
                assessment=sample_assessment, industry="ecommerce"
            )

            # Verify cost tracking was called
            assert mock_cost.called, "AssessmentCost should be called for cost tracking"

            # Verify cost in result
            assert result.total_cost_usd > Decimal("0"), "Should track non-zero cost"
            assert isinstance(
                result.total_cost_usd, Decimal
            ), "Cost should be Decimal type"

            # Verify cost calculation based on token usage
            expected_cost = (1500 * Decimal("0.00003")) + (800 * Decimal("0.00006"))
            assert abs(result.total_cost_usd - expected_cost) < Decimal(
                "0.001"
            ), f"Cost calculation should be accurate: expected {expected_cost}, got {result.total_cost_usd}"

            # Verify cost tracking call structure
            cost_calls = mock_cost.call_args_list
            assert len(cost_calls) > 0, "Should have cost tracking calls"

            first_call = cost_calls[0][1]  # kwargs
            assert first_call["cost_type"].value == "api_call"
            assert first_call["provider"] == "OpenAI"
            assert first_call["amount"] > Decimal("0")

        print("✓ Cost tracking works correctly")

    @pytest.mark.asyncio
    async def test_structured_output_parsing(
        self, insight_generator, sample_assessment
    ):
        """
        Test that structured output parsing works correctly

        Acceptance Criteria: Structured output parsing
        """
        # Test successful JSON parsing
        result = await insight_generator.generate_comprehensive_insights(
            assessment=sample_assessment, industry="ecommerce"
        )

        # Verify structured output
        assert isinstance(result.insights, dict), "Insights should be dictionary"
        assert (
            "recommendations" in result.insights
        ), "Should have recommendations section"

        recommendations_data = result.insights["recommendations"]
        assert isinstance(
            recommendations_data, dict
        ), "Recommendations should be structured dict"
        assert (
            "recommendations" in recommendations_data
        ), "Should have recommendations array"
        assert (
            "industry_insights" in recommendations_data
        ), "Should have industry insights"
        assert "summary" in recommendations_data, "Should have summary"

        # Test fallback parsing with invalid JSON
        with patch.object(
            insight_generator.llm_client, "generate_completion"
        ) as mock_llm:
            mock_llm.return_value = MagicMock(
                content="This is not valid JSON but contains some recommendations to improve performance",
                usage={
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "total_tokens": 150,
                },
            )

            fallback_result = await insight_generator.generate_comprehensive_insights(
                assessment=sample_assessment, industry="ecommerce"
            )

            # Should still produce structured output via fallback
            assert fallback_result.insights is not None, "Should have fallback insights"
            fallback_recs = fallback_result.insights["recommendations"][
                "recommendations"
            ]
            assert (
                len(fallback_recs) == 3
            ), "Fallback should still produce 3 recommendations"

        # Test validation of structured output
        valid_result = result
        try:
            insight_generator._validate_insights(valid_result)
            print("✓ Validation passed for valid insights")
        except ValueError as e:
            pytest.fail(f"Valid insights failed validation: {e}")

        print("✓ Structured output parsing works correctly")

    @pytest.mark.asyncio
    async def test_multiple_insight_types(self, insight_generator, sample_assessment):
        """Test generation of different insight types"""
        result = await insight_generator.generate_comprehensive_insights(
            assessment=sample_assessment,
            industry="technology",
            insight_types=[
                InsightType.RECOMMENDATIONS,
                InsightType.TECHNICAL_ANALYSIS,
                InsightType.INDUSTRY_BENCHMARK,
            ],
        )

        # Should have multiple insight types
        assert len(result.insight_types) == 3
        assert InsightType.RECOMMENDATIONS in result.insight_types
        assert InsightType.TECHNICAL_ANALYSIS in result.insight_types
        assert InsightType.INDUSTRY_BENCHMARK in result.insight_types

        # Each type should be represented in insights
        assert "recommendations" in result.insights
        assert "technical_analysis" in result.insights
        assert "industry_benchmark" in result.insights

        print("✓ Multiple insight types generated correctly")

    def test_prompt_variable_extraction(self, sample_assessment):
        """Test extraction of prompt variables from assessment data"""
        generator = LLMInsightGenerator()
        assessment_data = generator._prepare_assessment_data(sample_assessment)

        # Verify key data extracted
        assert assessment_data["url"] == "https://example-store.com"
        assert assessment_data["performance_score"] == 65
        assert assessment_data["largest_contentful_paint"] == 3500
        assert assessment_data["tech_stack"] is not None

        # Test prompt variable formatting
        prompt_vars = InsightPrompts.get_prompt_variables(assessment_data, "ecommerce")
        assert prompt_vars["industry"] == "ecommerce"
        assert "WordPress" in prompt_vars["technologies"]
        assert "Remove unused CSS" in prompt_vars["top_issues"]

        print("✓ Prompt variable extraction works correctly")

    def test_industry_context_mapping(self):
        """Test industry context mapping functionality"""
        # Test specific industries
        ecommerce_context = InsightPrompts.get_industry_context("ecommerce")
        assert "conversion_rate" in ecommerce_context["key_metrics"]
        assert "PCI DSS" in ecommerce_context["compliance"]

        healthcare_context = InsightPrompts.get_industry_context("healthcare")
        assert "accessibility" in healthcare_context["key_metrics"]
        assert "HIPAA" in healthcare_context["compliance"]

        # Test default fallback
        unknown_context = InsightPrompts.get_industry_context("unknown_industry")
        assert "performance" in unknown_context["key_metrics"]

        print("✓ Industry context mapping works correctly")

    def test_technology_formatting(self):
        """Test technology stack formatting for prompts"""
        tech_stack = [
            {"technology_name": "WordPress", "category": "CMS", "confidence": 0.95},
            {
                "technology_name": "WooCommerce",
                "category": "E-commerce",
                "confidence": 0.90,
            },
            {
                "technology_name": "Google Analytics",
                "category": "Analytics",
                "confidence": 0.85,
            },
        ]

        formatted = InsightPrompts.format_technologies(tech_stack)
        assert "CMS: WordPress" in formatted
        assert "E-commerce: WooCommerce" in formatted
        assert "Analytics: Google Analytics" in formatted

        # Test empty tech stack
        empty_formatted = InsightPrompts.format_technologies([])
        assert empty_formatted == "None detected"

        print("✓ Technology formatting works correctly")

    def test_performance_issue_formatting(self):
        """Test performance issue formatting for prompts"""
        issues = [
            {"title": "Remove unused CSS", "impact": "high", "savings_ms": 1200},
            {
                "title": "Eliminate render-blocking resources",
                "impact": "medium",
                "savings_ms": 800,
            },
        ]

        formatted = InsightPrompts.format_issues(issues)
        assert "Remove unused CSS (Impact: high, Saves: 1200ms)" in formatted
        assert (
            "Eliminate render-blocking resources (Impact: medium, Saves: 800ms)"
            in formatted
        )

        print("✓ Performance issue formatting works correctly")

    @pytest.mark.asyncio
    async def test_batch_insight_generation(self, mock_llm_client):
        """Test batch processing of multiple assessments"""
        # Create multiple assessments
        assessments = []
        for i in range(3):
            assessment = AssessmentResult(
                id=f"test-assessment-{i}",
                business_id=f"test-business-{i}",
                assessment_type=AssessmentType.PAGESPEED,
                status=AssessmentStatus.COMPLETED,
                url=f"https://example{i}.com",
                domain=f"example{i}.com",
                performance_score=70 + i * 5,
            )
            assessments.append(assessment)

        # Test batch generation
        batch_generator = LLMInsightBatchGenerator(
            LLMInsightGenerator(llm_client=mock_llm_client)
        )

        industry_mapping = {
            "test-assessment-0": "ecommerce",
            "test-assessment-1": "healthcare",
            "test-assessment-2": "technology",
        }

        results = await batch_generator.generate_batch_insights(
            assessments=assessments, industry_mapping=industry_mapping, max_concurrent=2
        )

        # Verify batch results
        assert len(results) == 3
        for i, result in enumerate(results):
            assert result.assessment_id == f"test-assessment-{i}"
            expected_industry = list(industry_mapping.values())[i]
            assert result.industry == expected_industry

        # Test cost calculation
        estimated_cost = await batch_generator.calculate_batch_cost(assessments)
        assert estimated_cost > Decimal("0")
        assert estimated_cost == len(assessments) * Decimal("0.50")

        print("✓ Batch insight generation works correctly")

    @pytest.mark.asyncio
    async def test_error_handling(self, sample_assessment):
        """Test error handling in insight generation"""
        # Create generator with failing LLM client
        failing_client = AsyncMock()
        failing_client.generate_completion.side_effect = Exception("LLM API Error")
        failing_client.get_model_version.return_value = "gpt-4-test"

        generator = LLMInsightGenerator(llm_client=failing_client)

        result = await generator.generate_comprehensive_insights(
            assessment=sample_assessment, industry="ecommerce"
        )

        # Should return failed result, not raise exception
        assert result.error_message == "LLM API Error"
        assert result.insights == {}
        assert result.assessment_id == sample_assessment.id

        print("✓ Error handling works correctly")

    @pytest.mark.asyncio
    async def test_comprehensive_insight_flow(
        self, insight_generator, sample_assessment
    ):
        """Test complete insight generation flow with all components"""
        result = await insight_generator.generate_comprehensive_insights(
            assessment=sample_assessment,
            industry="ecommerce",
            insight_types=[
                InsightType.RECOMMENDATIONS,
                InsightType.TECHNICAL_ANALYSIS,
                InsightType.INDUSTRY_BENCHMARK,
                InsightType.QUICK_WINS,
            ],
        )

        # Verify comprehensive result structure
        assert result.id is not None
        assert result.assessment_id == sample_assessment.id
        assert result.business_id == sample_assessment.business_id
        assert result.industry == "ecommerce"
        assert len(result.insight_types) == 4

        # Verify timing
        assert result.generated_at is not None
        assert result.completed_at is not None
        assert result.processing_time_ms > 0

        # Verify cost tracking
        assert result.total_cost_usd > Decimal("0")
        assert result.model_version is not None

        # Verify all insight types present
        assert "recommendations" in result.insights
        assert "technical_analysis" in result.insights
        assert "industry_benchmark" in result.insights
        assert "quick_wins" in result.insights

        # Verify validation passes
        insight_generator._validate_insights(result)

        print("✓ Comprehensive insight flow works correctly")


# Allow running this test file directly
if __name__ == "__main__":
    import asyncio

    async def run_tests():
        test_instance = TestTask033AcceptanceCriteria()

        print("🧠 Running Task 033 LLM Insight Generator Tests...")
        print()

        try:
            # Create fixtures
            mock_client = test_instance.mock_llm_client()
            sample_assessment = test_instance.sample_assessment()
            generator = test_instance.insight_generator(mock_client)

            # Run all tests
            await test_instance.test_three_recommendations_generated(
                generator, sample_assessment
            )
            await test_instance.test_industry_specific_insights(
                generator, sample_assessment
            )
            await test_instance.test_cost_tracking_works(generator, sample_assessment)
            await test_instance.test_structured_output_parsing(
                generator, sample_assessment
            )
            await test_instance.test_multiple_insight_types(
                generator, sample_assessment
            )
            test_instance.test_prompt_variable_extraction(sample_assessment)
            test_instance.test_industry_context_mapping()
            test_instance.test_technology_formatting()
            test_instance.test_performance_issue_formatting()
            await test_instance.test_batch_insight_generation(mock_client)
            await test_instance.test_error_handling(sample_assessment)
            await test_instance.test_comprehensive_insight_flow(
                generator, sample_assessment
            )

            print()
            print("🎉 All Task 033 acceptance criteria tests pass!")
            print("   - 3 recommendations generated: ✓")
            print("   - Industry-specific insights: ✓")
            print("   - Cost tracking works: ✓")
            print("   - Structured output parsing: ✓")

        except Exception as e:
            print(f"❌ Test failed: {e}")
            import traceback

            traceback.print_exc()

    # Run async tests
    asyncio.run(run_tests())
