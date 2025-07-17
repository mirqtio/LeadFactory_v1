"""
Visual analyzer that combines screenshot capture and AI vision analysis
Implements 9 visual rubric dimensions with 0-100 scoring
"""
import json
from typing import Any, Dict, List, Optional

from core.config import settings
from core.logging import get_logger
from d0_gateway.factory import create_client
from d0_gateway.providers.humanloop import HumanloopClient
from d0_gateway.providers.screenshotone import ScreenshotOneClient
from d3_assessment.assessors.base import AssessmentResult, BaseAssessor
from d3_assessment.exceptions import AssessmentError, AssessmentTimeoutError
from d3_assessment.models import AssessmentType

logger = get_logger(__name__, domain="d3")


# Vision analysis prompt slug
VISION_PROMPT_SLUG = "website_visual_analysis_v2"


class VisualAnalyzer(BaseAssessor):
    """
    Combined visual analyzer that captures screenshots and performs AI vision analysis
    with 9 visual rubric dimensions scored 0-100
    """

    def __init__(self):
        super().__init__()
        self.timeout = 20  # Combined timeout for both operations
        self._screenshot_client = None
        self._vision_client = None

    @property
    def assessment_type(self) -> AssessmentType:
        return AssessmentType.VISUAL

    def _get_screenshot_client(self) -> ScreenshotOneClient:
        """Get or create ScreenshotOne client"""
        if not self._screenshot_client:
            self._screenshot_client = create_client("screenshotone")
        return self._screenshot_client

    def _get_vision_client(self) -> HumanloopClient:
        """Get or create Humanloop client for vision analysis"""
        if not self._vision_client:
            self._vision_client = create_client("humanloop")
        return self._vision_client

    def _get_stub_data(self, url: str) -> Dict[str, Any]:
        """Return deterministic stub data when USE_STUBS=true"""
        # Generate deterministic scores based on URL hash
        url_hash = hash(url) % 9
        base_score = 5 + (url_hash % 4)  # 5-8 range

        visual_scores = {
            "visual_design_quality": min(9, base_score + 1),
            "brand_consistency": max(1, base_score - 1),
            "navigation_clarity": min(9, base_score + 2),
            "content_organization": base_score,
            "call_to_action_prominence": max(1, base_score - 2),
            "mobile_responsiveness": min(9, base_score + 1),
            "loading_performance": max(1, base_score - 1),
            "trust_signals": min(9, base_score + 1),
            "overall_user_experience": base_score,
        }

        # Calculate average
        avg_score = sum(visual_scores.values()) / len(visual_scores)

        return {
            "screenshot_url": f"https://stub-screenshots.com/{url_hash}/desktop.png",
            "screenshot_thumb_url": f"https://stub-screenshots.com/{url_hash}/thumb.png",
            "mobile_screenshot_url": f"https://stub-screenshots.com/{url_hash}/mobile.png",
            "visual_scores": visual_scores,
            "visual_warnings": [
                "Low contrast text detected in header",
                "Images missing alt text for accessibility",
                "Mobile menu button too small for touch targets",
            ][
                :2
            ],  # Return 2 warnings
            "visual_quickwins": [
                "Add more whitespace between sections for better readability",
                "Increase font size on mobile devices",
                "Make CTA buttons more prominent with contrasting colors",
            ][
                :3
            ],  # Return 3 quick wins
            "visual_insights": {
                "strengths": [
                    "Clean and modern design aesthetic",
                    "Good use of brand colors throughout",
                ],
                "weaknesses": [
                    "Navigation could be more intuitive",
                    "Call-to-action buttons lack prominence",
                ],
                "opportunities": [
                    "Implement lazy loading for images",
                    "Add trust badges near conversion points",
                ],
            },
            "metrics": {
                "average_score": avg_score,
                "lowest_dimension": min(visual_scores.items(), key=lambda x: x[1])[0],
                "highest_dimension": max(visual_scores.items(), key=lambda x: x[1])[0],
                "screenshots_captured": 3,
                "analysis_model": "gpt-4o-mini",
                "is_stub": True,
            },
        }

    async def assess(self, url: str, business_data: Dict[str, Any]) -> AssessmentResult:
        """
        Capture screenshots and analyze them with AI vision

        Args:
            url: Website URL to analyze
            business_data: Business information including lead_id

        Returns:
            AssessmentResult with visual analysis data
        """
        try:
            # Use stub data if configured
            if settings.use_stubs:
                logger.info("Using stub data for visual analysis")
                stub_data = self._get_stub_data(url)

                return AssessmentResult(
                    assessment_type=self.assessment_type,
                    status="completed",
                    data={
                        "screenshot_url": stub_data["screenshot_url"],
                        "screenshot_thumb_url": stub_data["screenshot_thumb_url"],
                        "mobile_screenshot_url": stub_data["mobile_screenshot_url"],
                        "visual_scores_json": stub_data["visual_scores"],
                        "visual_warnings": stub_data["visual_warnings"],
                        "visual_quickwins": stub_data["visual_quickwins"],
                        "visual_analysis": {
                            "average_score": stub_data["metrics"]["average_score"],
                            "lowest_score_area": stub_data["metrics"]["lowest_dimension"],
                            "highest_score_area": stub_data["metrics"]["highest_dimension"],
                            "insights": stub_data["visual_insights"],
                        },
                    },
                    metrics=stub_data["metrics"],
                    cost=0.0,  # No cost for stub data
                )

            # Step 1: Capture screenshots
            screenshot_client = self._get_screenshot_client()

            # Capture desktop screenshot
            desktop_result = await screenshot_client.take_screenshot(
                url=url,
                full_page=True,
                viewport_width=1920,
                viewport_height=1080,
                device_scale_factor=1,
                format="png",
                lead_id=business_data.get("id"),
            )

            if not desktop_result or not desktop_result.get("screenshot_url"):
                return AssessmentResult(
                    assessment_type=self.assessment_type,
                    status="failed",
                    error_message="Failed to capture desktop screenshot",
                )

            screenshot_url = desktop_result["screenshot_url"]
            thumbnail_url = desktop_result.get("screenshot_thumb_url", screenshot_url)

            # Capture mobile screenshot
            mobile_result = await screenshot_client.take_screenshot(
                url=url,
                full_page=False,
                viewport_width=375,
                viewport_height=812,
                device_scale_factor=2,
                format="png",
                lead_id=business_data.get("id"),
            )

            mobile_screenshot_url = mobile_result.get("screenshot_url") if mobile_result else None

            # Step 2: Analyze with Vision API
            vision_client = self._get_vision_client()

            # Prepare messages for vision analysis
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": screenshot_url,
                                "detail": "high",
                            },
                        },
                    ],
                }
            ]

            # Call vision API with our custom prompt
            response = await vision_client.chat_completion(
                prompt_slug=VISION_PROMPT_SLUG,
                inputs={
                    "url": url,
                    "business_name": business_data.get("name", "Unknown Business"),
                },
                messages=messages,
                metadata={"lead_id": business_data.get("id")},
            )

            if not response or "choices" not in response:
                raise AssessmentError("Invalid response from Vision API")

            # Parse the JSON response
            content = response["choices"][0]["message"]["content"]
            try:
                visual_data = json.loads(content)
            except json.JSONDecodeError:
                visual_data = self._extract_json_from_text(content)

            # Extract and validate scores (1-9 scale)
            scores = visual_data.get("scores", {})
            visual_scores = {
                "visual_design_quality": self._clamp_score(scores.get("visual_design_quality", 5)),
                "brand_consistency": self._clamp_score(scores.get("brand_consistency", 5)),
                "navigation_clarity": self._clamp_score(scores.get("navigation_clarity", 5)),
                "content_organization": self._clamp_score(scores.get("content_organization", 5)),
                "call_to_action_prominence": self._clamp_score(scores.get("call_to_action_prominence", 5)),
                "mobile_responsiveness": self._clamp_score(scores.get("mobile_responsiveness", 5)),
                "loading_performance": self._clamp_score(scores.get("loading_performance", 5)),
                "trust_signals": self._clamp_score(scores.get("trust_signals", 5)),
                "overall_user_experience": self._clamp_score(scores.get("overall_user_experience", 5)),
            }

            # Extract warnings and quick wins
            visual_warnings = visual_data.get("warnings", [])[:5]
            visual_quickwins = visual_data.get("quick_wins", [])[:5]

            # Calculate metrics
            avg_score = sum(visual_scores.values()) / len(visual_scores)
            lowest_dimension = min(visual_scores.items(), key=lambda x: x[1])
            highest_dimension = max(visual_scores.items(), key=lambda x: x[1])

            # Extract insights if available
            insights = visual_data.get(
                "insights",
                {
                    "strengths": [],
                    "weaknesses": [],
                    "opportunities": [],
                },
            )

            return AssessmentResult(
                assessment_type=self.assessment_type,
                status="completed",
                data={
                    # Screenshot URLs
                    "screenshot_url": screenshot_url,
                    "screenshot_thumb_url": thumbnail_url,
                    "mobile_screenshot_url": mobile_screenshot_url,
                    # Vision analysis
                    "visual_scores_json": visual_scores,
                    "visual_warnings": visual_warnings,
                    "visual_quickwins": visual_quickwins,
                    # Combined analysis
                    "visual_analysis": {
                        "average_score": avg_score,
                        "lowest_score_area": lowest_dimension[0],
                        "highest_score_area": highest_dimension[0],
                        "insights": insights,
                        "issues_count": len(visual_warnings),
                        "opportunities_count": len(visual_quickwins),
                    },
                },
                metrics={
                    "model_used": response.get("model", "gpt-4o-mini"),
                    "average_visual_score": avg_score,
                    "warnings_count": len(visual_warnings),
                    "quickwins_count": len(visual_quickwins),
                    "screenshots_captured": 2 if mobile_screenshot_url else 1,
                    "api_cost_usd": 0.023,  # $0.020 screenshots + $0.003 vision
                },
                cost=0.023,  # Combined cost
            )

        except AssessmentTimeoutError:
            raise
        except Exception as e:
            logger.error(f"Visual analysis failed for {url}: {e}")

            # Return minimal result with error
            return AssessmentResult(
                assessment_type=self.assessment_type,
                status="failed",
                data={
                    "visual_scores_json": {
                        "visual_design_quality": 1,
                        "brand_consistency": 1,
                        "navigation_clarity": 1,
                        "content_organization": 1,
                        "call_to_action_prominence": 1,
                        "mobile_responsiveness": 1,
                        "loading_performance": 1,
                        "trust_signals": 1,
                        "overall_user_experience": 1,
                    },
                    "visual_warnings": [],
                    "visual_quickwins": [],
                },
                error_message=f"Visual analysis error: {str(e)}",
            )

    def _clamp_score(self, score: Any) -> int:
        """Ensure score is between 1-9"""
        try:
            score_num = float(score)
            return max(1, min(9, int(score_num)))
        except (ValueError, TypeError):
            return 5  # Default middle score

    def _extract_json_from_text(self, text: str) -> Dict[str, Any]:
        """Try to extract JSON from text response"""
        import re

        json_match = re.search(r"\{[\s\S]*\}", text)
        if json_match:
            try:
                return json.loads(json_match.group())
            except Exception:
                pass

        # Return default structure if extraction fails
        return {
            "scores": {
                "visual_design_quality": 5,
                "brand_consistency": 5,
                "navigation_clarity": 5,
                "content_organization": 5,
                "call_to_action_prominence": 5,
                "mobile_responsiveness": 5,
                "loading_performance": 5,
                "trust_signals": 5,
                "overall_user_experience": 5,
            },
            "warnings": ["Failed to parse visual analysis response"],
            "quick_wins": [],
            "insights": {
                "strengths": [],
                "weaknesses": ["Analysis parsing failed"],
                "opportunities": [],
            },
        }

    def calculate_cost(self) -> float:
        """Combined cost for screenshots and vision analysis"""
        # $0.010 per screenshot (x2) + $0.003 for vision analysis
        return 0.023

    def is_available(self) -> bool:
        """Check if both ScreenshotOne and Vision API are available"""
        return bool(settings.screenshotone_key and settings.humanloop_api_key) or settings.use_stubs
