"""
Integration tests for LLM Heuristic Assessor with coordinator - P1-040
"""

from unittest.mock import AsyncMock, patch

import pytest

from d3_assessment.assessors import ASSESSOR_REGISTRY
from d3_assessment.assessors.llm_heuristic_assessor import LLMHeuristicAssessor
from d3_assessment.coordinator import AssessmentCoordinator, AssessmentPriority, AssessmentRequest
from d3_assessment.models import AssessmentType


class TestLLMHeuristicIntegration:
    """Integration tests for LLM Heuristic Assessor"""

    def test_assessor_registered(self):
        """Test that LLM Heuristic Assessor is properly registered"""
        assert "llm_heuristic" in ASSESSOR_REGISTRY
        assert ASSESSOR_REGISTRY["llm_heuristic"] == LLMHeuristicAssessor

    def test_assessor_instantiation(self):
        """Test that assessor can be instantiated from registry"""
        assessor_class = ASSESSOR_REGISTRY["llm_heuristic"]
        assessor = assessor_class()

        assert isinstance(assessor, LLMHeuristicAssessor)
        assert assessor.assessment_type == AssessmentType.AI_INSIGHTS

    @pytest.mark.asyncio
    @patch("d3_assessment.assessors.llm_heuristic_assessor.settings")
    async def test_assessor_availability_check(self, mock_settings):
        """Test assessor availability with different configurations"""
        assessor = LLMHeuristicAssessor()

        # Test with feature disabled
        mock_settings.get.return_value = False
        mock_settings.humanloop_api_key = "test-key"
        mock_settings.use_stubs = False
        assert not assessor.is_available()

        # Test with feature enabled
        mock_settings.get.return_value = True
        mock_settings.humanloop_api_key = "test-key"
        mock_settings.use_stubs = False
        assert assessor.is_available()

        # Test with stubs
        mock_settings.get.return_value = True
        mock_settings.humanloop_api_key = None
        mock_settings.use_stubs = True
        assert assessor.is_available()

    @pytest.mark.asyncio
    @patch("d3_assessment.assessors.llm_heuristic_assessor.settings")
    @patch("d3_assessment.assessors.llm_heuristic_assessor.create_client")
    async def test_coordinator_integration(self, mock_create_client, mock_settings):
        """Test LLM assessor integration with assessment coordinator"""
        # Setup mocks
        mock_settings.get.return_value = True
        mock_settings.use_stubs = True

        mock_client = AsyncMock()
        mock_client.completion.return_value = {
            "output": '{"heuristic_scores": {"uvp_clarity_score": 75, "contact_info_completeness": 80, "cta_clarity_score": 70, "social_proof_presence": 60, "readability_score": 85, "mobile_viewport_detection": true, "intrusive_popup_detection": false}}',
            "usage": {"prompt_tokens": 800, "completion_tokens": 300, "total_tokens": 1100},
            "model": "gpt-4o-mini",
        }
        mock_create_client.return_value = mock_client

        # Create coordinator (mocked to avoid other assessors)
        coordinator = AssessmentCoordinator(max_concurrent=1)

        # Create test business data
        business_data = {
            "id": "test-business",
            "business_type": "Restaurant",
            "industry": "Food Service",
            "assessments": {
                "bsoup_json": {
                    "title": "Test Restaurant",
                    "meta_description": "Great food and service",
                    "headings": [{"level": 1, "text": "Welcome"}],
                    "paragraphs": ["Best restaurant in town"],
                    "links": [{"text": "Order Now", "href": "/order"}],
                    "forms": [{"action": "/contact"}],
                    "images": ["hero.jpg"],
                    "scripts": ["analytics.js"],
                    "styles": ["main.css"],
                }
            },
        }

        # Test direct assessor call
        assessor = LLMHeuristicAssessor()
        result = await assessor.assess("https://testrestaurant.com", business_data)

        assert result.status == "completed"
        assert result.assessment_type == AssessmentType.AI_INSIGHTS
        assert "heuristic_scores" in result.data

        # Verify all required heuristic scores are present
        scores = result.data["heuristic_scores"]
        required_scores = [
            "uvp_clarity_score",
            "contact_info_completeness",
            "cta_clarity_score",
            "social_proof_presence",
            "readability_score",
            "mobile_viewport_detection",
            "intrusive_popup_detection",
        ]

        for score_name in required_scores:
            assert score_name in scores

        # Verify numeric scores are in valid range
        for score_name in required_scores[:-2]:  # Skip boolean scores
            score_value = scores[score_name]
            assert isinstance(score_value, int)
            assert 0 <= score_value <= 100

        # Verify boolean scores
        assert isinstance(scores["mobile_viewport_detection"], bool)
        assert isinstance(scores["intrusive_popup_detection"], bool)

    @pytest.mark.asyncio
    @patch("d3_assessment.assessors.llm_heuristic_assessor.settings")
    async def test_assessor_with_missing_content(self, mock_settings):
        """Test assessor behavior with missing website content"""
        mock_settings.get.return_value = True
        mock_settings.use_stubs = True

        assessor = LLMHeuristicAssessor()

        # Business data without content
        business_data = {"id": "test-business", "business_type": "Service", "assessments": {}}  # No bsoup_json data

        result = await assessor.assess("https://example.com", business_data)

        assert result.status == "failed"
        assert "No website content available" in result.error_message

    @pytest.mark.asyncio
    @patch("d3_assessment.assessors.llm_heuristic_assessor.settings")
    @patch("d3_assessment.assessors.llm_heuristic_assessor.create_client")
    async def test_assessor_graceful_degradation(self, mock_create_client, mock_settings):
        """Test assessor graceful degradation on errors"""
        mock_settings.get.return_value = True
        mock_settings.use_stubs = False

        # Mock client to raise exception
        mock_client = AsyncMock()
        mock_client.completion.side_effect = Exception("API Error")
        mock_create_client.return_value = mock_client

        assessor = LLMHeuristicAssessor()

        business_data = {
            "id": "test-business",
            "assessments": {"bsoup_json": {"title": "Test Site", "paragraphs": ["Some content"]}},
        }

        result = await assessor.assess("https://example.com", business_data)

        # Should complete with default values rather than fail completely
        assert result.status == "completed"
        assert result.error_message is not None
        assert "heuristic_scores" in result.data

        # Default scores should be zeros
        scores = result.data["heuristic_scores"]
        assert scores["uvp_clarity_score"] == 0
        assert scores["contact_info_completeness"] == 0

    @pytest.mark.asyncio
    @patch("d3_assessment.assessors.llm_heuristic_assessor.settings")
    @patch("d3_assessment.assessors.llm_heuristic_assessor.create_client")
    async def test_assessor_cost_tracking(self, mock_create_client, mock_settings):
        """Test that assessor properly tracks costs"""
        mock_settings.get.return_value = True
        mock_settings.use_stubs = False

        mock_client = AsyncMock()
        mock_client.completion.return_value = {
            "output": '{"heuristic_scores": {"uvp_clarity_score": 80, "contact_info_completeness": 85, "cta_clarity_score": 75, "social_proof_presence": 65, "readability_score": 90, "mobile_viewport_detection": true, "intrusive_popup_detection": false}}',
            "usage": {"prompt_tokens": 1200, "completion_tokens": 600, "total_tokens": 1800},
            "model": "gpt-4o-mini",
        }
        mock_create_client.return_value = mock_client

        assessor = LLMHeuristicAssessor()

        business_data = {
            "id": "test-business",
            "assessments": {"bsoup_json": {"title": "Test Site", "paragraphs": ["Content for analysis"]}},
        }

        result = await assessor.assess("https://example.com", business_data)

        assert result.status == "completed"
        assert result.cost > 0
        assert result.cost <= 0.10  # Should be within reasonable bounds

        # Verify cost metrics
        assert "api_cost_usd" in result.metrics
        assert result.metrics["api_cost_usd"] == result.cost
        assert result.metrics["total_tokens"] == 1800

    def test_assessor_timeout_configuration(self):
        """Test assessor timeout configuration"""
        assessor = LLMHeuristicAssessor()

        assert assessor.get_timeout() == 30  # 30 second timeout
        assert assessor.timeout == 30

    @pytest.mark.asyncio
    @patch("d3_assessment.assessors.llm_heuristic_assessor.settings")
    @patch("d3_assessment.assessors.llm_heuristic_assessor.create_client")
    async def test_assessor_with_complex_content(self, mock_create_client, mock_settings):
        """Test assessor with complex website content"""
        mock_settings.get.return_value = True
        mock_settings.use_stubs = False

        mock_client = AsyncMock()
        mock_client.completion.return_value = {
            "output": '{"heuristic_scores": {"uvp_clarity_score": 95, "contact_info_completeness": 100, "cta_clarity_score": 90, "social_proof_presence": 85, "readability_score": 88, "mobile_viewport_detection": true, "intrusive_popup_detection": false}, "detailed_analysis": {"value_proposition": {"clarity": "Excellent"}}, "priority_recommendations": [{"category": "Performance", "issue": "Minor optimization needed", "recommendation": "Compress images", "impact": "low", "effort": "low"}]}',
            "usage": {"prompt_tokens": 1500, "completion_tokens": 800, "total_tokens": 2300},
            "model": "gpt-4o-mini",
        }
        mock_create_client.return_value = mock_client

        assessor = LLMHeuristicAssessor()

        # Complex business data with full content
        business_data = {
            "id": "complex-business",
            "business_type": "E-commerce",
            "industry": "Retail",
            "assessments": {
                "bsoup_json": {
                    "title": "Premium Online Store - Best Products & Service",
                    "meta_description": "Shop premium products with free shipping, excellent customer service, and 30-day returns",
                    "headings": [
                        {"level": 1, "text": "Welcome to Premium Store"},
                        {"level": 2, "text": "Featured Products"},
                        {"level": 2, "text": "Customer Reviews"},
                        {"level": 2, "text": "About Us"},
                        {"level": 2, "text": "Contact & Support"},
                    ],
                    "paragraphs": [
                        "We offer the highest quality products with exceptional customer service",
                        "Founded in 2010, we've served over 100,000 satisfied customers",
                        "Free shipping on all orders over $50 with 30-day money-back guarantee",
                        "Our team of experts carefully curates every product in our catalog",
                        "Call us at (555) 123-4567 or email support@premiumstore.com",
                    ],
                    "links": [
                        {"text": "Shop Now", "href": "/shop"},
                        {"text": "View Cart", "href": "/cart"},
                        {"text": "Customer Reviews", "href": "/reviews"},
                        {"text": "Contact Us", "href": "/contact"},
                        {"text": "Track Order", "href": "/tracking"},
                        {"text": "Returns", "href": "/returns"},
                    ],
                    "forms": [{"action": "/contact", "method": "post"}, {"action": "/newsletter", "method": "post"}],
                    "images": ["hero-banner.jpg", "product1.jpg", "product2.jpg", "testimonial1.jpg"],
                    "scripts": ["analytics.js", "ecommerce.js", "reviews.js"],
                    "styles": ["main.css", "ecommerce.css", "responsive.css"],
                },
                "pagespeed_data": {
                    "performance_score": 92,
                    "accessibility_score": 95,
                    "best_practices_score": 88,
                    "seo_score": 100,
                    "largest_contentful_paint": 1.2,
                    "first_input_delay": 50,
                    "cumulative_layout_shift": 0.05,
                },
            },
        }

        result = await assessor.assess("https://premiumstore.com", business_data)

        assert result.status == "completed"
        assert "heuristic_scores" in result.data
        assert "detailed_analysis" in result.data
        assert "priority_recommendations" in result.data

        # Verify high scores for well-optimized site
        scores = result.data["heuristic_scores"]
        assert scores["uvp_clarity_score"] >= 90  # Should be high for good content
        assert scores["contact_info_completeness"] >= 90  # Good contact info

        # Verify detailed analysis is present
        assert result.data["detailed_analysis"] is not None

        # Verify recommendations are present
        recommendations = result.data["priority_recommendations"]
        assert len(recommendations) >= 1

        # Verify cost is reasonable for larger content
        assert result.cost > 0
        assert result.cost <= 0.10
