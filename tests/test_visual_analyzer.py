"""
Tests for the visual analyzer implementation
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from d3_assessment.assessors.base import AssessmentResult
from d3_assessment.assessors.visual_analyzer import VisualAnalyzer
from d3_assessment.models import AssessmentType


@pytest.fixture
def visual_analyzer():
    """Create visual analyzer instance"""
    return VisualAnalyzer()


@pytest.fixture
def mock_screenshot_client():
    """Mock ScreenshotOne client"""
    client = MagicMock()
    client.take_screenshot = AsyncMock()
    return client


@pytest.fixture
def mock_vision_client():
    """Mock Humanloop vision client"""
    client = MagicMock()
    client.chat_completion = AsyncMock()
    return client


class TestVisualAnalyzer:
    """Test visual analyzer functionality"""

    async def test_assessment_type(self, visual_analyzer):
        """Test correct assessment type"""
        assert visual_analyzer.assessment_type == AssessmentType.AI_INSIGHTS

    async def test_calculate_cost(self, visual_analyzer):
        """Test cost calculation"""
        assert visual_analyzer.calculate_cost() == 0.023  # $0.020 screenshots + $0.003 vision

    async def test_timeout(self, visual_analyzer):
        """Test timeout configuration"""
        assert visual_analyzer.get_timeout() == 20

    @patch("d3_assessment.assessors.visual_analyzer.settings")
    async def test_is_available_with_keys(self, mock_settings, visual_analyzer):
        """Test availability check with API keys"""
        mock_settings.screenshotone_key = "test-key"
        mock_settings.humanloop_api_key = "test-key"
        mock_settings.use_stubs = False

        assert visual_analyzer.is_available() is True

    @patch("d3_assessment.assessors.visual_analyzer.settings")
    async def test_is_available_with_stubs(self, mock_settings, visual_analyzer):
        """Test availability check with stubs"""
        mock_settings.screenshotone_key = None
        mock_settings.humanloop_api_key = None
        mock_settings.use_stubs = True

        assert visual_analyzer.is_available() is True

    @patch("d3_assessment.assessors.visual_analyzer.settings")
    async def test_stub_data(self, mock_settings, visual_analyzer):
        """Test stub data generation"""
        mock_settings.use_stubs = True

        result = await visual_analyzer.assess(
            url="https://example.com", business_data={"id": "test-123", "name": "Test Business"}
        )

        assert result.status == "completed"
        assert result.assessment_type == AssessmentType.AI_INSIGHTS
        assert result.cost == 0.0  # No cost for stubs

        # Check screenshot URLs
        assert "screenshot_url" in result.data
        assert "screenshot_thumb_url" in result.data
        assert "mobile_screenshot_url" in result.data

        # Check visual scores (9 dimensions)
        scores = result.data["visual_scores_json"]
        assert len(scores) == 9
        assert all(0 <= score <= 100 for score in scores.values())

        # Check required dimensions
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
        for dimension in expected_dimensions:
            assert dimension in scores

        # Check warnings and quickwins
        assert isinstance(result.data["visual_warnings"], list)
        assert isinstance(result.data["visual_quickwins"], list)
        assert len(result.data["visual_warnings"]) <= 5
        assert len(result.data["visual_quickwins"]) <= 5

    @patch("d3_assessment.assessors.visual_analyzer.settings")
    @patch("d3_assessment.assessors.visual_analyzer.create_client")
    async def test_successful_analysis(
        self, mock_create_client, mock_settings, visual_analyzer, mock_screenshot_client, mock_vision_client
    ):
        """Test successful visual analysis flow"""
        mock_settings.use_stubs = False
        mock_create_client.side_effect = [mock_screenshot_client, mock_vision_client]

        # Mock screenshot responses
        mock_screenshot_client.take_screenshot.side_effect = [
            {
                "screenshot_url": "https://screenshots.com/desktop.png",
                "screenshot_thumb_url": "https://screenshots.com/thumb.png",
                "success": True,
            },
            {
                "screenshot_url": "https://screenshots.com/mobile.png",
                "success": True,
            },
        ]

        # Mock vision response
        vision_response = {
            "scores": {
                "visual_design_quality": 85,
                "brand_consistency": 78,
                "navigation_clarity": 90,
                "content_organization": 82,
                "call_to_action_prominence": 65,
                "mobile_responsiveness": 88,
                "loading_performance": 75,
                "trust_signals": 70,
                "overall_user_experience": 80,
            },
            "warnings": ["Low contrast text in header", "CTA buttons need more prominence"],
            "quick_wins": ["Increase button size", "Add more whitespace", "Optimize images"],
            "insights": {
                "strengths": ["Clean design", "Good navigation"],
                "weaknesses": ["Weak CTAs"],
                "opportunities": ["Add testimonials"],
            },
        }

        mock_vision_client.chat_completion.return_value = {
            "choices": [{"message": {"content": json.dumps(vision_response)}}],
            "model": "gpt-4o-mini",
            "usage": {"prompt_tokens": 800, "completion_tokens": 300, "total_tokens": 1100},
        }

        # Run analysis
        result = await visual_analyzer.assess(
            url="https://example.com", business_data={"id": "test-123", "name": "Test Business"}
        )

        # Verify result
        assert result.status == "completed"
        assert result.cost == 0.023

        # Verify screenshot calls
        assert mock_screenshot_client.take_screenshot.call_count == 2

        # Verify vision call
        mock_vision_client.chat_completion.assert_called_once()
        call_args = mock_vision_client.chat_completion.call_args
        assert call_args[1]["prompt_slug"] == "website_visual_analysis_v2"
        assert call_args[1]["inputs"]["url"] == "https://example.com"
        assert call_args[1]["inputs"]["business_name"] == "Test Business"

        # Verify data structure
        assert result.data["screenshot_url"] == "https://screenshots.com/desktop.png"
        assert result.data["mobile_screenshot_url"] == "https://screenshots.com/mobile.png"
        assert result.data["visual_scores_json"] == vision_response["scores"]
        assert len(result.data["visual_warnings"]) == 2
        assert len(result.data["visual_quickwins"]) == 3

    @patch("d3_assessment.assessors.visual_analyzer.settings")
    @patch("d3_assessment.assessors.visual_analyzer.create_client")
    async def test_screenshot_failure(self, mock_create_client, mock_settings, visual_analyzer, mock_screenshot_client):
        """Test handling of screenshot capture failure"""
        mock_settings.use_stubs = False
        mock_create_client.return_value = mock_screenshot_client

        # Mock screenshot failure
        mock_screenshot_client.take_screenshot.return_value = {"success": False, "error": "Screenshot failed"}

        result = await visual_analyzer.assess(url="https://example.com", business_data={"id": "test-123"})

        assert result.status == "failed"
        assert "Failed to capture desktop screenshot" in result.error_message

    @patch("d3_assessment.assessors.visual_analyzer.settings")
    @patch("d3_assessment.assessors.visual_analyzer.create_client")
    async def test_vision_failure(
        self, mock_create_client, mock_settings, visual_analyzer, mock_screenshot_client, mock_vision_client
    ):
        """Test handling of vision API failure"""
        mock_settings.use_stubs = False
        mock_create_client.side_effect = [mock_screenshot_client, mock_vision_client]

        # Mock successful screenshots
        mock_screenshot_client.take_screenshot.return_value = {
            "screenshot_url": "https://screenshots.com/desktop.png",
            "screenshot_thumb_url": "https://screenshots.com/thumb.png",
            "success": True,
        }

        # Mock vision failure
        mock_vision_client.chat_completion.side_effect = Exception("Vision API error")

        result = await visual_analyzer.assess(url="https://example.com", business_data={"id": "test-123"})

        assert result.status == "failed"
        assert "Vision API error" in result.error_message
        # Should still have default scores
        assert all(score == 0 for score in result.data["visual_scores_json"].values())

    def test_clamp_score(self, visual_analyzer):
        """Test score clamping to 0-100 range"""
        assert visual_analyzer._clamp_score(50) == 50
        assert visual_analyzer._clamp_score(150) == 100
        assert visual_analyzer._clamp_score(-10) == 0
        assert visual_analyzer._clamp_score("75") == 75
        assert visual_analyzer._clamp_score("invalid") == 50  # Default
        assert visual_analyzer._clamp_score(None) == 50  # Default

    def test_extract_json_from_text(self, visual_analyzer):
        """Test JSON extraction from text"""
        # Valid JSON
        text = 'Some text {"scores": {"visual_design_quality": 80}} more text'
        result = visual_analyzer._extract_json_from_text(text)
        assert result["scores"]["visual_design_quality"] == 80

        # Invalid JSON - should return default
        text = "No JSON here"
        result = visual_analyzer._extract_json_from_text(text)
        assert len(result["scores"]) == 9
        assert all(score == 50 for score in result["scores"].values())
