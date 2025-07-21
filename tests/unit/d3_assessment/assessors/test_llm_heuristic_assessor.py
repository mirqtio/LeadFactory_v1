"""
Unit tests for LLM Heuristic Assessor - P1-040
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from d3_assessment.assessors.llm_heuristic_assessor import LLMHeuristicAssessor
from d3_assessment.models import AssessmentType


class TestLLMHeuristicAssessor:
    """Test suite for LLM Heuristic Assessor"""

    @pytest.fixture
    def assessor(self):
        """Create LLM Heuristic Assessor instance"""
        return LLMHeuristicAssessor()

    @pytest.fixture
    def mock_business_data(self):
        """Mock business data with website content"""
        return {
            "id": "test-business-id",
            "business_type": "Restaurant",
            "industry": "Food & Dining",
            "assessments": {
                "bsoup_json": {
                    "title": "Best Pizza in Town - Mario's Restaurant",
                    "meta_description": "Authentic Italian pizza and pasta since 1985",
                    "headings": [
                        {"level": 1, "text": "Welcome to Mario's"},
                        {"level": 2, "text": "Our Menu"},
                        {"level": 2, "text": "Contact Us"},
                    ],
                    "paragraphs": [
                        "We serve the best pizza in town with fresh ingredients",
                        "Family owned and operated for over 35 years",
                        "Call us at (555) 123-4567 for reservations",
                    ],
                    "links": [
                        {"text": "Order Online", "href": "/order"},
                        {"text": "View Menu", "href": "/menu"},
                        {"text": "Contact", "href": "/contact"},
                    ],
                    "forms": [{"action": "/contact", "method": "post"}],
                    "images": ["hero.jpg", "pizza1.jpg", "interior.jpg"],
                    "scripts": ["analytics.js", "booking.js"],
                    "styles": ["main.css", "responsive.css"],
                },
                "pagespeed_data": {
                    "performance_score": 75,
                    "accessibility_score": 85,
                    "best_practices_score": 80,
                    "seo_score": 90,
                    "largest_contentful_paint": 2.5,
                    "first_input_delay": 100,
                    "cumulative_layout_shift": 0.1,
                },
            },
        }

    @pytest.fixture
    def mock_llm_response(self):
        """Mock successful LLM response"""
        return {
            "id": "hl_test_123",
            "model": "gpt-4o-mini",
            "output": json.dumps(
                {
                    "heuristic_scores": {
                        "uvp_clarity_score": 85,
                        "contact_info_completeness": 90,
                        "cta_clarity_score": 75,
                        "social_proof_presence": 60,
                        "readability_score": 80,
                        "mobile_viewport_detection": True,
                        "intrusive_popup_detection": False,
                    },
                    "detailed_analysis": {
                        "value_proposition": {
                            "clarity": "Clear",
                            "positioning": "Well positioned as authentic Italian restaurant",
                            "improvements": ["Add unique selling points", "Highlight awards"],
                        },
                        "contact_information": {
                            "phone_visible": True,
                            "email_visible": False,
                            "address_visible": True,
                            "contact_form_present": True,
                            "social_links_present": False,
                            "missing_elements": ["Email address", "Social media links"],
                        },
                        "call_to_action": {
                            "primary_cta_clear": True,
                            "cta_placement": "Order Online button prominently placed",
                            "cta_language": "Clear and action-oriented",
                            "improvements": ["Add phone ordering CTA", "Make reservation CTA more prominent"],
                        },
                    },
                    "priority_recommendations": [
                        {
                            "category": "Contact",
                            "issue": "Missing email address visibility",
                            "recommendation": "Add email address to contact section",
                            "impact": "medium",
                            "effort": "low",
                        },
                        {
                            "category": "Social Proof",
                            "issue": "No customer testimonials visible",
                            "recommendation": "Add customer reviews section",
                            "impact": "high",
                            "effort": "medium",
                        },
                    ],
                    "overall_assessment": {
                        "conversion_readiness": "medium",
                        "user_experience_quality": "good",
                        "key_strengths": ["Clear menu", "Easy ordering", "Contact information"],
                        "critical_issues": ["Missing social proof", "No email visible"],
                        "next_steps": ["Add testimonials", "Improve contact info", "Add social links"],
                    },
                }
            ),
            "usage": {"prompt_tokens": 800, "completion_tokens": 500, "total_tokens": 1300},
        }

    def test_assessment_type(self, assessor):
        """Test that assessor returns correct assessment type"""
        assert assessor.assessment_type == AssessmentType.AI_INSIGHTS

    def test_calculate_cost(self, assessor):
        """Test cost calculation"""
        cost = assessor.calculate_cost()
        assert cost == 0.03  # PRP requirement: ~$0.03 per audit

    def test_get_timeout(self, assessor):
        """Test timeout configuration"""
        assert assessor.get_timeout() == 30  # 30 second timeout

    @patch("d3_assessment.assessors.llm_heuristic_assessor.settings")
    def test_is_available_with_feature_flag_disabled(self, mock_settings, assessor):
        """Test availability when feature flag is disabled"""
        mock_settings.get.return_value = False  # ENABLE_LLM_AUDIT = False
        mock_settings.humanloop_api_key = "test-key"
        mock_settings.use_stubs = False

        assert not assessor.is_available()

    @patch("d3_assessment.assessors.llm_heuristic_assessor.settings")
    def test_is_available_with_feature_flag_enabled(self, mock_settings, assessor):
        """Test availability when feature flag is enabled"""
        mock_settings.get.return_value = True  # ENABLE_LLM_AUDIT = True
        mock_settings.humanloop_api_key = "test-key"
        mock_settings.use_stubs = False

        assert assessor.is_available()

    @patch("d3_assessment.assessors.llm_heuristic_assessor.settings")
    def test_is_available_with_stubs(self, mock_settings, assessor):
        """Test availability when using stubs"""
        mock_settings.get.return_value = True  # ENABLE_LLM_AUDIT = True
        mock_settings.humanloop_api_key = None
        mock_settings.use_stubs = True

        assert assessor.is_available()

    @patch("d3_assessment.assessors.llm_heuristic_assessor.settings")
    @patch("d3_assessment.assessors.llm_heuristic_assessor.create_client")
    async def test_assess_success(
        self, mock_create_client, mock_settings, assessor, mock_business_data, mock_llm_response
    ):
        """Test successful assessment"""
        # Setup
        mock_settings.get.return_value = True  # ENABLE_LLM_AUDIT = True
        mock_settings.use_stubs = False

        mock_client = AsyncMock()
        mock_client.completion.return_value = mock_llm_response
        mock_create_client.return_value = mock_client

        # Execute
        result = await assessor.assess("https://marios-pizza.com", mock_business_data)

        # Verify
        assert result.status == "completed"
        assert result.assessment_type == AssessmentType.AI_INSIGHTS
        assert result.cost > 0

        # Check heuristic scores
        scores = result.data["heuristic_scores"]
        assert scores["uvp_clarity_score"] == 85
        assert scores["contact_info_completeness"] == 90
        assert scores["cta_clarity_score"] == 75
        assert scores["social_proof_presence"] == 60
        assert scores["readability_score"] == 80
        assert scores["mobile_viewport_detection"] is True
        assert scores["intrusive_popup_detection"] is False

        # Check metrics
        assert result.metrics["uvp_clarity_score"] == 85
        assert result.metrics["total_tokens"] == 1300
        assert result.metrics["recommendations_count"] == 2

        # Verify client was called correctly
        mock_client.completion.assert_called_once()
        call_args = mock_client.completion.call_args
        assert call_args[1]["prompt_slug"] == "website_heuristic_audit_v1"
        assert "website_url" in call_args[1]["inputs"]
        assert "business_type" in call_args[1]["inputs"]

    @patch("d3_assessment.assessors.llm_heuristic_assessor.settings")
    async def test_assess_feature_disabled(self, mock_settings, assessor, mock_business_data):
        """Test assessment when feature flag is disabled"""
        mock_settings.get.return_value = False  # ENABLE_LLM_AUDIT = False
        mock_settings.use_stubs = False

        result = await assessor.assess("https://example.com", mock_business_data)

        assert result.status == "skipped"
        assert "disabled via feature flag" in result.error_message

    @patch("d3_assessment.assessors.llm_heuristic_assessor.settings")
    async def test_assess_no_content(self, mock_settings, assessor):
        """Test assessment with no website content"""
        mock_settings.get.return_value = True
        mock_settings.use_stubs = False

        # Business data with truly empty content
        business_data = {
            "id": "test",
            "assessments": {
                "bsoup_json": {"title": "", "meta_description": "", "headings": [], "paragraphs": [], "links": []}
            },
        }

        result = await assessor.assess("https://example.com", business_data)

        assert result.status == "failed"
        assert "No website content available" in result.error_message

    @patch("d3_assessment.assessors.llm_heuristic_assessor.settings")
    @patch("d3_assessment.assessors.llm_heuristic_assessor.create_client")
    async def test_assess_llm_error(self, mock_create_client, mock_settings, assessor, mock_business_data):
        """Test assessment when LLM call fails"""
        mock_settings.get.return_value = True

        mock_client = AsyncMock()
        mock_client.completion.side_effect = Exception("LLM API error")
        mock_create_client.return_value = mock_client

        result = await assessor.assess("https://example.com", mock_business_data)

        assert result.status == "completed"  # Graceful degradation
        assert result.error_message is not None
        assert "LLM heuristic audit error" in result.error_message

        # Should return default scores
        scores = result.data["heuristic_scores"]
        assert scores["uvp_clarity_score"] == 0
        assert scores["contact_info_completeness"] == 0

    @patch("d3_assessment.assessors.llm_heuristic_assessor.settings")
    @patch("d3_assessment.assessors.llm_heuristic_assessor.create_client")
    async def test_assess_invalid_json_response(self, mock_create_client, mock_settings, assessor, mock_business_data):
        """Test assessment with invalid JSON response"""
        mock_settings.get.return_value = True

        mock_client = AsyncMock()
        mock_client.completion.return_value = {
            "output": "This is not valid JSON",
            "usage": {"prompt_tokens": 800, "completion_tokens": 200},
        }
        mock_create_client.return_value = mock_client

        result = await assessor.assess("https://example.com", mock_business_data)

        assert result.status == "completed"
        # Should fallback to default structure
        assert "heuristic_scores" in result.data
        assert "priority_recommendations" in result.data

    def test_validate_heuristic_scores(self, assessor):
        """Test score validation and clamping"""
        # Test normal scores
        scores = {
            "uvp_clarity_score": 85,
            "contact_info_completeness": 90,
            "cta_clarity_score": 75,
            "social_proof_presence": 60,
            "readability_score": 80,
            "mobile_viewport_detection": True,
            "intrusive_popup_detection": False,
        }

        validated = assessor._validate_heuristic_scores(scores)

        assert validated["uvp_clarity_score"] == 85
        assert validated["mobile_viewport_detection"] is True
        assert validated["intrusive_popup_detection"] is False

    def test_validate_heuristic_scores_out_of_range(self, assessor):
        """Test score validation with out-of-range values"""
        scores = {
            "uvp_clarity_score": 150,  # Too high
            "contact_info_completeness": -10,  # Too low
            "cta_clarity_score": "invalid",  # Invalid type
            "social_proof_presence": 50.5,  # Float (should convert to int)
            "readability_score": None,  # None value
            "mobile_viewport_detection": "true",  # String boolean
            "intrusive_popup_detection": 1,  # Integer boolean
        }

        validated = assessor._validate_heuristic_scores(scores)

        assert validated["uvp_clarity_score"] == 100  # Clamped to max
        assert validated["contact_info_completeness"] == 0  # Clamped to min
        assert validated["cta_clarity_score"] == 0  # Invalid type becomes 0
        assert validated["social_proof_presence"] == 50  # Float converted to int
        assert validated["readability_score"] == 0  # None becomes 0
        assert validated["mobile_viewport_detection"] is True  # String boolean converted
        assert validated["intrusive_popup_detection"] is True  # Integer boolean converted

    def test_extract_website_content(self, assessor, mock_business_data):
        """Test website content extraction"""
        content = assessor._extract_website_content(mock_business_data)

        assert content["title"] == "Best Pizza in Town - Mario's Restaurant"
        assert content["meta_description"] == "Authentic Italian pizza and pasta since 1985"
        assert len(content["headings"]) == 3
        assert len(content["paragraphs"]) == 3
        assert len(content["links"]) == 3
        assert content["images"] == 3
        assert content["scripts"] == 2

    def test_extract_performance_data(self, assessor, mock_business_data):
        """Test performance data extraction"""
        performance = assessor._extract_performance_data(mock_business_data)

        assert performance["performance_score"] == 75
        assert performance["accessibility_score"] == 85
        assert performance["largest_contentful_paint"] == 2.5
        assert performance["first_input_delay"] == 100

    def test_calculate_actual_cost(self, assessor):
        """Test actual cost calculation from token usage"""
        usage = {"prompt_tokens": 800, "completion_tokens": 500, "total_tokens": 1300}

        cost = assessor._calculate_actual_cost(usage)

        # Should be reasonable cost based on GPT-4o-mini pricing
        # 800 * 0.15/1M + 500 * 0.60/1M = 0.00012 + 0.0003 = 0.00042
        assert cost > 0  # Should be positive
        assert cost <= 0.10  # Should be under cap
        assert isinstance(cost, float)

    def test_calculate_actual_cost_high_usage(self, assessor):
        """Test cost calculation with high token usage gets capped"""
        usage = {"prompt_tokens": 500000, "completion_tokens": 500000, "total_tokens": 1000000}  # Very high usage

        cost = assessor._calculate_actual_cost(usage)

        # Should be capped at $0.10 for safety
        assert cost == 0.10

    def test_get_default_scores(self, assessor):
        """Test default scores structure"""
        defaults = assessor._get_default_scores()

        assert defaults["uvp_clarity_score"] == 0
        assert defaults["contact_info_completeness"] == 0
        assert defaults["cta_clarity_score"] == 0
        assert defaults["social_proof_presence"] == 0
        assert defaults["readability_score"] == 0
        assert defaults["mobile_viewport_detection"] is False
        assert defaults["intrusive_popup_detection"] is False

    def test_extract_json_from_text_valid_json(self, assessor):
        """Test JSON extraction from text with valid JSON"""
        text = """
        Here is the analysis:
        {"heuristic_scores": {"uvp_clarity_score": 85}, "test": true}
        Some additional text after.
        """

        result = assessor._extract_json_from_text(text)

        assert result["heuristic_scores"]["uvp_clarity_score"] == 85
        assert result["test"] is True

    def test_extract_json_from_text_no_json(self, assessor):
        """Test JSON extraction with no valid JSON"""
        text = "This is just plain text with no JSON structure."

        result = assessor._extract_json_from_text(text)

        # Should return fallback structure
        assert "heuristic_scores" in result
        assert "priority_recommendations" in result
        assert result["heuristic_scores"]["uvp_clarity_score"] == 0


@pytest.mark.integration
class TestLLMHeuristicAssessorIntegration:
    """Integration tests for LLM Heuristic Assessor"""

    @pytest.fixture
    def assessor(self):
        return LLMHeuristicAssessor()

    @patch("d3_assessment.assessors.llm_heuristic_assessor.settings")
    async def test_end_to_end_with_stubs(self, mock_settings, assessor):
        """Test end-to-end assessment using stubs"""
        mock_settings.get.return_value = True
        mock_settings.use_stubs = True
        mock_settings.humanloop_api_key = "test-key"

        business_data = {
            "id": "integration-test",
            "business_type": "Retail",
            "industry": "E-commerce",
            "assessments": {
                "bsoup_json": {
                    "title": "Test Store",
                    "meta_description": "Online store for testing",
                    "headings": [{"level": 1, "text": "Welcome"}],
                    "paragraphs": ["We sell great products online"],
                    "links": [{"text": "Shop Now", "href": "/shop"}],
                    "forms": [],
                    "images": ["product1.jpg"],
                    "scripts": ["analytics.js"],
                    "styles": ["main.css"],
                }
            },
        }

        result = await assessor.assess("https://teststore.com", business_data)

        # Should succeed with stubs
        assert result.status in ["completed", "failed"]  # Either is acceptable for stubs
        assert result.assessment_type == AssessmentType.AI_INSIGHTS

        if result.status == "completed":
            assert "heuristic_scores" in result.data
            assert "uvp_clarity_score" in result.data["heuristic_scores"]
