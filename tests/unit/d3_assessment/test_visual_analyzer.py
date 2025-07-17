"""
Test Visual Analyzer - Comprehensive Unit Tests

Tests for the visual analyzer that combines screenshot capture and AI vision analysis
with 9 visual rubric dimensions scored 1-9.

Coverage includes:
- Screenshot capture functionality (desktop and mobile)
- Vision API analysis with GPT-4o
- 9 rubric dimensions scoring (1-9)
- Stub mode behavior for deterministic testing
- Error handling and edge cases
- Cost calculation ($0.023 total)
- Integration with assessment models
- Mock Humanloop and ScreenshotOne clients
"""
import json
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from d3_assessment.assessors.base import AssessmentResult
from d3_assessment.assessors.visual_analyzer import VisualAnalyzer
from d3_assessment.exceptions import AssessmentError, AssessmentTimeoutError
from d3_assessment.models import AssessmentType


class TestVisualAnalyzer:
    """Test suite for Visual Analyzer functionality"""

    @pytest.fixture
    def visual_analyzer(self):
        """Create visual analyzer instance"""
        return VisualAnalyzer()

    @pytest.fixture
    def mock_screenshot_client(self):
        """Mock ScreenshotOne client"""
        client = MagicMock()
        client.take_screenshot = AsyncMock()
        return client

    @pytest.fixture
    def mock_vision_client(self):
        """Mock Humanloop vision client"""
        client = MagicMock()
        client.chat_completion = AsyncMock()
        return client

    @pytest.fixture
    def mock_screenshot_response(self):
        """Mock screenshot API response"""
        return {
            "screenshot_url": "https://screenshots.test/desktop-123.png",
            "screenshot_thumb_url": "https://screenshots.test/desktop-123-thumb.png",
            "status": "success",
            "cached": False,
        }

    @pytest.fixture
    def mock_mobile_screenshot_response(self):
        """Mock mobile screenshot API response"""
        return {
            "screenshot_url": "https://screenshots.test/mobile-123.png",
            "screenshot_thumb_url": "https://screenshots.test/mobile-123-thumb.png",
            "status": "success",
            "cached": False,
        }

    @pytest.fixture
    def mock_vision_response(self):
        """Mock vision API response with all 9 rubric dimensions"""
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "scores": {
                                    "visual_design_quality": 8,
                                    "brand_consistency": 7,
                                    "navigation_clarity": 9,
                                    "content_organization": 8,
                                    "call_to_action_prominence": 6,
                                    "mobile_responsiveness": 9,
                                    "loading_performance": 7,
                                    "trust_signals": 8,
                                    "overall_user_experience": 8,
                                },
                                "warnings": [
                                    "Low contrast text in footer section",
                                    "CTA buttons could be more prominent",
                                    "Some images lack alt text",
                                    "Navigation menu items too close together",
                                    "Missing trust badges near checkout",
                                ],
                                "quick_wins": [
                                    "Increase CTA button size and contrast",
                                    "Add more whitespace between sections",
                                    "Implement lazy loading for images",
                                    "Add trust badges near conversion points",
                                    "Improve mobile touch target sizes",
                                ],
                                "insights": {
                                    "strengths": [
                                        "Clean, modern design aesthetic",
                                        "Good mobile responsiveness",
                                        "Clear navigation structure",
                                    ],
                                    "weaknesses": [
                                        "CTA buttons lack visual prominence",
                                        "Some performance optimization needed",
                                    ],
                                    "opportunities": [
                                        "Implement A/B testing for CTA colors",
                                        "Add customer testimonials section",
                                    ],
                                },
                            }
                        )
                    }
                }
            ],
            "model": "gpt-4o-mini",
            "usage": {"prompt_tokens": 150, "completion_tokens": 250, "total_tokens": 400},
        }

    @pytest.fixture
    def business_data(self):
        """Standard business data for testing"""
        return {
            "id": "test-lead-123",
            "name": "Test Business Inc",
            "industry": "E-commerce",
            "website": "https://testbusiness.com",
        }

    @pytest.mark.asyncio
    @patch("d3_assessment.assessors.visual_analyzer.create_client")
    @patch("d3_assessment.assessors.visual_analyzer.settings")
    async def test_successful_visual_analysis(
        self,
        mock_settings,
        mock_create_client,
        visual_analyzer,
        mock_screenshot_client,
        mock_vision_client,
        mock_screenshot_response,
        mock_mobile_screenshot_response,
        mock_vision_response,
        business_data,
    ):
        """Test successful visual analysis with screenshots and vision API"""
        # Setup
        mock_settings.use_stubs = False
        mock_settings.screenshotone_key = "test-key"
        mock_settings.humanloop_api_key = "test-key"

        # Configure mock clients
        mock_create_client.side_effect = [mock_screenshot_client, mock_vision_client]
        mock_screenshot_client.take_screenshot.side_effect = [mock_screenshot_response, mock_mobile_screenshot_response]
        mock_vision_client.chat_completion.return_value = mock_vision_response

        # Execute
        result = await visual_analyzer.assess("https://testbusiness.com", business_data)

        # Verify result structure
        assert isinstance(result, AssessmentResult)
        assert result.assessment_type == AssessmentType.VISUAL
        assert result.status == "completed"
        assert result.cost == 0.023  # $0.020 screenshots + $0.003 vision

        # Verify screenshot URLs
        assert result.data["screenshot_url"] == "https://screenshots.test/desktop-123.png"
        assert result.data["screenshot_thumb_url"] == "https://screenshots.test/desktop-123-thumb.png"
        assert result.data["mobile_screenshot_url"] == "https://screenshots.test/mobile-123.png"

        # Verify visual scores (all 9 dimensions)
        # Scores are returned as-is from the 1-9 scale
        scores = result.data["visual_scores_json"]
        assert scores["visual_design_quality"] == 8
        assert scores["brand_consistency"] == 7
        assert scores["navigation_clarity"] == 9
        assert scores["content_organization"] == 8
        assert scores["call_to_action_prominence"] == 6
        assert scores["mobile_responsiveness"] == 9
        assert scores["loading_performance"] == 7
        assert scores["trust_signals"] == 8
        assert scores["overall_user_experience"] == 8

        # Verify warnings and quick wins
        assert len(result.data["visual_warnings"]) == 5
        assert len(result.data["visual_quickwins"]) == 5
        assert "Low contrast text in footer section" in result.data["visual_warnings"]
        assert "Increase CTA button size and contrast" in result.data["visual_quickwins"]

        # Verify visual analysis summary
        analysis = result.data["visual_analysis"]
        # Average of scores on 1-9 scale: (8+7+9+8+6+9+7+8+8)/9 ≈ 7.78
        assert analysis["average_score"] == pytest.approx(7.78, rel=0.1)
        assert analysis["lowest_score_area"] == "call_to_action_prominence"
        assert analysis["highest_score_area"] in ["navigation_clarity", "mobile_responsiveness"]  # Both have score 9
        assert analysis["issues_count"] == 5
        assert analysis["opportunities_count"] == 5

        # Verify insights
        insights = analysis["insights"]
        assert len(insights["strengths"]) == 3
        assert len(insights["weaknesses"]) == 2
        assert len(insights["opportunities"]) == 2

        # Verify metrics
        assert result.metrics["model_used"] == "gpt-4o-mini"
        assert result.metrics["average_visual_score"] == pytest.approx(7.78, rel=0.1)
        assert result.metrics["warnings_count"] == 5
        assert result.metrics["quickwins_count"] == 5
        assert result.metrics["screenshots_captured"] == 2
        assert result.metrics["api_cost_usd"] == 0.023

        # Verify API calls
        assert mock_screenshot_client.take_screenshot.call_count == 2

        # Desktop screenshot call
        desktop_call = mock_screenshot_client.take_screenshot.call_args_list[0]
        assert desktop_call.kwargs["url"] == "https://testbusiness.com"
        assert desktop_call.kwargs["viewport_width"] == 1920
        assert desktop_call.kwargs["viewport_height"] == 1080
        assert desktop_call.kwargs["full_page"] is True
        assert desktop_call.kwargs["lead_id"] == "test-lead-123"

        # Mobile screenshot call
        mobile_call = mock_screenshot_client.take_screenshot.call_args_list[1]
        assert mobile_call.kwargs["viewport_width"] == 375
        assert mobile_call.kwargs["viewport_height"] == 812
        assert mobile_call.kwargs["device_scale_factor"] == 2
        assert mobile_call.kwargs["full_page"] is False

        # Vision API call
        assert mock_vision_client.chat_completion.call_count == 1
        vision_call = mock_vision_client.chat_completion.call_args
        assert vision_call.kwargs["prompt_slug"] == "website_visual_analysis_v2"
        assert vision_call.kwargs["inputs"]["url"] == "https://testbusiness.com"
        assert vision_call.kwargs["inputs"]["business_name"] == "Test Business Inc"
        assert vision_call.kwargs["metadata"]["lead_id"] == "test-lead-123"

    @pytest.mark.asyncio
    @patch("d3_assessment.assessors.visual_analyzer.settings")
    async def test_stub_mode_behavior(self, mock_settings, visual_analyzer, business_data):
        """Test stub mode returns deterministic data based on URL hash"""
        # Enable stub mode
        mock_settings.use_stubs = True

        # Test with specific URL
        url = "https://example.com"
        result = await visual_analyzer.assess(url, business_data)

        # Verify stub response
        assert result.status == "completed"
        assert result.cost == 0.0  # No cost for stub data

        # Verify deterministic screenshot URLs
        url_hash = hash(url) % 9
        assert result.data["screenshot_url"] == f"https://stub-screenshots.com/{url_hash}/desktop.png"
        assert result.data["screenshot_thumb_url"] == f"https://stub-screenshots.com/{url_hash}/thumb.png"
        assert result.data["mobile_screenshot_url"] == f"https://stub-screenshots.com/{url_hash}/mobile.png"

        # Verify scores are deterministic (5-9 range)
        scores = result.data["visual_scores_json"]
        base_score = 5 + (url_hash % 4)
        assert scores["visual_design_quality"] == min(9, base_score + 1)
        assert scores["brand_consistency"] == max(1, base_score - 1)
        assert scores["navigation_clarity"] == min(9, base_score + 2)
        assert scores["content_organization"] == base_score
        assert scores["call_to_action_prominence"] == max(1, base_score - 2)
        assert scores["mobile_responsiveness"] == min(9, base_score + 1)
        assert scores["loading_performance"] == max(1, base_score - 1)
        assert scores["trust_signals"] == min(9, base_score + 1)
        assert scores["overall_user_experience"] == base_score

        # Verify stub warnings and quick wins
        assert len(result.data["visual_warnings"]) == 2
        assert len(result.data["visual_quickwins"]) == 3
        assert "Low contrast text detected in header" in result.data["visual_warnings"]

        # Verify metrics indicate stub mode
        assert result.metrics["is_stub"] is True
        assert result.metrics["analysis_model"] == "gpt-4o-mini"

    @pytest.mark.asyncio
    @patch("d3_assessment.assessors.visual_analyzer.create_client")
    @patch("d3_assessment.assessors.visual_analyzer.settings")
    async def test_screenshot_failure(
        self, mock_settings, mock_create_client, visual_analyzer, mock_screenshot_client, business_data
    ):
        """Test handling of screenshot capture failure"""
        # Setup
        mock_settings.use_stubs = False
        mock_create_client.return_value = mock_screenshot_client

        # Screenshot fails
        mock_screenshot_client.take_screenshot.return_value = None

        # Execute
        result = await visual_analyzer.assess("https://testbusiness.com", business_data)

        # Verify failure handling
        assert result.status == "failed"
        assert result.error_message == "Failed to capture desktop screenshot"
        assert result.cost == 0.0

    @pytest.mark.asyncio
    @patch("d3_assessment.assessors.visual_analyzer.create_client")
    @patch("d3_assessment.assessors.visual_analyzer.settings")
    async def test_vision_api_failure(
        self,
        mock_settings,
        mock_create_client,
        visual_analyzer,
        mock_screenshot_client,
        mock_vision_client,
        mock_screenshot_response,
        mock_mobile_screenshot_response,
        business_data,
    ):
        """Test handling of vision API failure"""
        # Setup
        mock_settings.use_stubs = False
        mock_create_client.side_effect = [mock_screenshot_client, mock_vision_client]
        mock_screenshot_client.take_screenshot.side_effect = [mock_screenshot_response, mock_mobile_screenshot_response]

        # Vision API returns invalid response
        mock_vision_client.chat_completion.return_value = {"error": "API Error"}

        # Execute
        result = await visual_analyzer.assess("https://testbusiness.com", business_data)

        # Verify error handling
        assert result.status == "failed"
        assert "Visual analysis error" in result.error_message

        # Should have default minimum scores
        scores = result.data["visual_scores_json"]
        for dimension in scores:
            assert scores[dimension] == 1

        assert result.data["visual_warnings"] == []
        assert result.data["visual_quickwins"] == []

    @pytest.mark.asyncio
    @patch("d3_assessment.assessors.visual_analyzer.create_client")
    @patch("d3_assessment.assessors.visual_analyzer.settings")
    async def test_malformed_json_response(
        self,
        mock_settings,
        mock_create_client,
        visual_analyzer,
        mock_screenshot_client,
        mock_vision_client,
        mock_screenshot_response,
        mock_mobile_screenshot_response,
        business_data,
    ):
        """Test handling of malformed JSON in vision response"""
        # Setup
        mock_settings.use_stubs = False
        mock_create_client.side_effect = [mock_screenshot_client, mock_vision_client]
        mock_screenshot_client.take_screenshot.side_effect = [mock_screenshot_response, mock_mobile_screenshot_response]

        # Vision API returns text with embedded JSON
        mock_vision_client.chat_completion.return_value = {
            "choices": [
                {
                    "message": {
                        "content": """Here is the analysis:
                    {"scores": {"visual_design_quality": 75, "brand_consistency": 80}}
                    That's all!"""
                    }
                }
            ],
            "model": "gpt-4o-mini",
        }

        # Execute
        result = await visual_analyzer.assess("https://testbusiness.com", business_data)

        # Should extract JSON and use defaults for missing scores
        assert result.status == "completed"
        scores = result.data["visual_scores_json"]
        assert scores["visual_design_quality"] == 7
        assert scores["brand_consistency"] == 8
        # Missing scores should default to 5
        assert scores["navigation_clarity"] == 5
        assert scores["mobile_responsiveness"] == 5

    @pytest.mark.asyncio
    @patch("d3_assessment.assessors.visual_analyzer.create_client")
    @patch("d3_assessment.assessors.visual_analyzer.settings")
    async def test_mobile_screenshot_failure_continues(
        self,
        mock_settings,
        mock_create_client,
        visual_analyzer,
        mock_screenshot_client,
        mock_vision_client,
        mock_screenshot_response,
        mock_vision_response,
        business_data,
    ):
        """Test that mobile screenshot failure doesn't stop the analysis"""
        # Setup
        mock_settings.use_stubs = False
        mock_create_client.side_effect = [mock_screenshot_client, mock_vision_client]

        # Desktop succeeds, mobile fails
        mock_screenshot_client.take_screenshot.side_effect = [mock_screenshot_response, None]  # Mobile fails
        mock_vision_client.chat_completion.return_value = mock_vision_response

        # Execute
        result = await visual_analyzer.assess("https://testbusiness.com", business_data)

        # Should continue with desktop screenshot only
        assert result.status == "completed"
        assert result.data["screenshot_url"] == "https://screenshots.test/desktop-123.png"
        assert result.data["mobile_screenshot_url"] is None
        assert result.metrics["screenshots_captured"] == 1

    def test_score_clamping(self, visual_analyzer):
        """Test score clamping to 0-100 range"""
        # Test various inputs
        assert visual_analyzer._clamp_score(85) == 85
        assert visual_analyzer._clamp_score(85.7) == 85
        assert visual_analyzer._clamp_score(-10) == 0
        assert visual_analyzer._clamp_score(150) == 100
        assert visual_analyzer._clamp_score("75") == 75
        assert visual_analyzer._clamp_score("invalid") == 50  # Default
        assert visual_analyzer._clamp_score(None) == 50  # Default
        assert visual_analyzer._clamp_score([]) == 50  # Default

    def test_json_extraction_from_text(self, visual_analyzer):
        """Test JSON extraction from mixed text response"""
        # Valid JSON embedded in text
        text = 'Here\'s the analysis: {"scores": {"visual_design_quality": 90}, "warnings": ["Issue 1"]}'
        result = visual_analyzer._extract_json_from_text(text)
        assert result["scores"]["visual_design_quality"] == 90
        assert result["warnings"] == ["Issue 1"]

        # No JSON found
        text = "This is just plain text with no JSON"
        result = visual_analyzer._extract_json_from_text(text)
        # Should return default structure
        assert "scores" in result
        assert len(result["scores"]) == 9  # All dimensions
        assert result["warnings"][0] == "Failed to parse visual analysis response"

        # Invalid JSON
        text = '{"broken": json'
        result = visual_analyzer._extract_json_from_text(text)
        assert result["warnings"][0] == "Failed to parse visual analysis response"

    def test_cost_calculation(self, visual_analyzer):
        """Test cost calculation method"""
        cost = visual_analyzer.calculate_cost()
        assert cost == 0.023  # $0.010 x 2 screenshots + $0.003 vision

    @patch("d3_assessment.assessors.visual_analyzer.settings")
    def test_availability_check(self, mock_settings, visual_analyzer):
        """Test availability check for required API keys"""
        # Both keys available
        mock_settings.screenshotone_key = "key1"
        mock_settings.humanloop_api_key = "key2"
        mock_settings.use_stubs = False
        assert visual_analyzer.is_available() is True

        # Missing screenshot key
        mock_settings.screenshotone_key = None
        assert visual_analyzer.is_available() is False

        # Missing vision key
        mock_settings.screenshotone_key = "key1"
        mock_settings.humanloop_api_key = None
        assert visual_analyzer.is_available() is False

        # Stubs enabled (always available)
        mock_settings.use_stubs = True
        mock_settings.screenshotone_key = None
        mock_settings.humanloop_api_key = None
        assert visual_analyzer.is_available() is True

    def test_assessment_type(self, visual_analyzer):
        """Test correct assessment type is returned"""
        assert visual_analyzer.assessment_type == AssessmentType.VISUAL

    def test_timeout_configuration(self, visual_analyzer):
        """Test timeout is properly configured"""
        assert visual_analyzer.timeout == 20  # Combined timeout for both operations
        assert visual_analyzer.get_timeout() == 20

    @pytest.mark.asyncio
    @patch("d3_assessment.assessors.visual_analyzer.create_client")
    @patch("d3_assessment.assessors.visual_analyzer.settings")
    async def test_edge_case_empty_response(
        self,
        mock_settings,
        mock_create_client,
        visual_analyzer,
        mock_screenshot_client,
        mock_vision_client,
        mock_screenshot_response,
        mock_mobile_screenshot_response,
        business_data,
    ):
        """Test handling of empty vision API response"""
        # Setup
        mock_settings.use_stubs = False
        mock_create_client.side_effect = [mock_screenshot_client, mock_vision_client]
        mock_screenshot_client.take_screenshot.side_effect = [mock_screenshot_response, mock_mobile_screenshot_response]

        # Empty response
        mock_vision_client.chat_completion.return_value = {
            "choices": [{"message": {"content": "{}"}}],
            "model": "gpt-4o-mini",
        }

        # Execute
        result = await visual_analyzer.assess("https://testbusiness.com", business_data)

        # Should use defaults
        assert result.status == "completed"
        scores = result.data["visual_scores_json"]
        # All scores should be default 5
        for dimension in scores:
            assert scores[dimension] == 5

    @pytest.mark.asyncio
    @patch("d3_assessment.assessors.visual_analyzer.create_client")
    @patch("d3_assessment.assessors.visual_analyzer.settings")
    async def test_high_scores_and_perfect_scores(
        self,
        mock_settings,
        mock_create_client,
        visual_analyzer,
        mock_screenshot_client,
        mock_vision_client,
        mock_screenshot_response,
        mock_mobile_screenshot_response,
        business_data,
    ):
        """Test handling of very high and perfect scores"""
        # Setup
        mock_settings.use_stubs = False
        mock_create_client.side_effect = [mock_screenshot_client, mock_vision_client]
        mock_screenshot_client.take_screenshot.side_effect = [mock_screenshot_response, mock_mobile_screenshot_response]

        # Return very high/perfect scores
        mock_vision_client.chat_completion.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "scores": {
                                    "visual_design_quality": 9,
                                    "brand_consistency": 9,
                                    "navigation_clarity": 9,
                                    "content_organization": 9,
                                    "call_to_action_prominence": 9,
                                    "mobile_responsiveness": 9,
                                    "loading_performance": 9,
                                    "trust_signals": 9,
                                    "overall_user_experience": 9,
                                },
                                "warnings": [],  # No warnings for perfect site
                                "quick_wins": ["Consider A/B testing minor variations"],
                                "insights": {
                                    "strengths": [
                                        "Exceptional visual design",
                                        "Perfect navigation clarity",
                                        "Outstanding mobile experience",
                                    ],
                                    "weaknesses": [],
                                    "opportunities": ["Maintain current high standards"],
                                },
                            }
                        )
                    }
                }
            ],
            "model": "gpt-4o-mini",
        }

        # Execute
        result = await visual_analyzer.assess("https://testbusiness.com", business_data)

        # Verify high scores
        scores = result.data["visual_scores_json"]
        assert scores["visual_design_quality"] == 9
        assert scores["navigation_clarity"] == 9
        assert scores["call_to_action_prominence"] == 9
        assert scores["trust_signals"] == 9

        # Average should be very high
        analysis = result.data["visual_analysis"]
        assert analysis["average_score"] >= 9
        assert analysis["highest_score_area"] in [
            "visual_design_quality",
            "navigation_clarity",
            "call_to_action_prominence",
            "trust_signals",
        ]
        assert len(result.data["visual_warnings"]) == 0
