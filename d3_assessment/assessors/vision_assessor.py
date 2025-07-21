"""
GPT-4o Vision assessor for visual website analysis
PRD v1.2 - Analyze screenshots for visual quality

Timeout: 12s
Cost: $0.003 per analysis
Output: visual_scores_json, visual_warnings, visual_quickwins columns
"""

import json
from typing import Any

from core.config import settings
from core.logging import get_logger
from d0_gateway.factory import create_client
from d0_gateway.providers.humanloop import HumanloopClient
from d3_assessment.assessors.base import AssessmentResult, BaseAssessor
from d3_assessment.exceptions import AssessmentError, AssessmentTimeoutError
from d3_assessment.models import AssessmentType

logger = get_logger(__name__, domain="d3")


# PRD v1.2 GPT-4o Vision prompt - now loaded from prompts/website_screenshot_analysis_v1.md
VISION_PROMPT_SLUG = "website_screenshot_analysis_v1"


class VisionAssessor(BaseAssessor):
    """Analyze website screenshots using GPT-4o Vision"""

    def __init__(self):
        super().__init__()
        self.timeout = 12  # 12 second timeout as per PRD
        self._client = None

    @property
    def assessment_type(self) -> AssessmentType:
        return AssessmentType.AI_INSIGHTS

    def _get_client(self) -> HumanloopClient:
        """Get or create Humanloop client"""
        if not self._client:
            self._client = create_client("humanloop")
        return self._client

    async def assess(self, url: str, business_data: dict[str, Any]) -> AssessmentResult:
        """
        Analyze website screenshot using GPT-4o Vision

        Args:
            url: Website URL (for reference)
            business_data: Business information including screenshot URLs

        Returns:
            AssessmentResult with visual analysis
        """
        try:
            # Get screenshot URL from business data or previous assessment
            screenshot_url = business_data.get("screenshot_url") or business_data.get("assessments", {}).get(
                "screenshot_url"
            )

            if not screenshot_url:
                return AssessmentResult(
                    assessment_type=self.assessment_type,
                    status="failed",
                    error_message="No screenshot URL available for analysis",
                )

            # Get Humanloop client
            client = self._get_client()

            # Prepare vision request
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": screenshot_url,
                                "detail": "high",  # High detail for better analysis
                            },
                        },
                    ],
                }
            ]

            # Call Humanloop with vision prompt
            response = await client.chat_completion(
                prompt_slug=VISION_PROMPT_SLUG,
                inputs={},  # No template variables needed for this prompt
                messages=messages,
                metadata={"lead_id": business_data.get("id")},
            )

            if not response or "choices" not in response:
                raise AssessmentError("Invalid response from GPT-4o Vision")

            # Parse the JSON response
            content = response["choices"][0]["message"]["content"]
            try:
                visual_data = json.loads(content)
            except json.JSONDecodeError:
                # Try to extract JSON from the response
                visual_data = self._extract_json_from_text(content)

            # Validate and clean the response
            scores = visual_data.get("scores", {})
            visual_scores = {
                "visual_appeal": self._clamp_score(scores.get("visual_appeal", 0)),
                "readability": self._clamp_score(scores.get("readability", 0)),
                "modernity": self._clamp_score(scores.get("modernity", 0)),
                "brand_consistency": self._clamp_score(scores.get("brand_consistency", 0)),
                "accessibility": self._clamp_score(scores.get("accessibility", 0)),
            }

            # Extract warnings and quick wins
            visual_warnings = visual_data.get("style_warnings", [])[:3]
            visual_quickwins = visual_data.get("quick_wins", [])[:3]

            # Calculate average score
            avg_score = sum(visual_scores.values()) / len(visual_scores)

            return AssessmentResult(
                assessment_type=self.assessment_type,
                status="completed",
                data={
                    "visual_scores_json": visual_scores,
                    "visual_warnings": visual_warnings,
                    "visual_quickwins": visual_quickwins,
                    "visual_analysis": {
                        "average_score": avg_score,
                        "lowest_score_area": min(visual_scores.items(), key=lambda x: x[1])[0],
                        "highest_score_area": max(visual_scores.items(), key=lambda x: x[1])[0],
                        "issues_count": len(visual_warnings),
                        "opportunities_count": len(visual_quickwins),
                    },
                },
                metrics={
                    "model_used": response.get("model", "gpt-4o-mini"),
                    "average_visual_score": avg_score,
                    "warnings_count": len(visual_warnings),
                    "quickwins_count": len(visual_quickwins),
                    "api_cost_usd": 0.003,
                },
                cost=0.003,  # Estimated for ~1k tokens
            )

        except AssessmentTimeoutError:
            raise
        except Exception as e:
            logger.error(f"Vision assessment failed for {url}: {e}")

            # Return minimal result with error
            return AssessmentResult(
                assessment_type=self.assessment_type,
                status="completed",
                data={
                    "visual_scores_json": {
                        "visual_appeal": 0,
                        "readability": 0,
                        "modernity": 0,
                        "brand_consistency": 0,
                        "accessibility": 0,
                    },
                    "visual_warnings": [],
                    "visual_quickwins": [],
                    "error": str(e),
                },
                error_message=f"Vision API error: {str(e)}",
            )

    def _clamp_score(self, score: Any) -> int:
        """Ensure score is between 0-5"""
        try:
            score_int = int(score)
            return max(0, min(5, score_int))
        except Exception:
            return 0

    def _extract_json_from_text(self, text: str) -> dict[str, Any]:
        """Try to extract JSON from text response"""
        # Look for JSON-like structure
        import re

        json_match = re.search(r"\{[\s\S]*\}", text)
        if json_match:
            try:
                return json.loads(json_match.group())
            except Exception:
                pass

        # Return empty structure if extraction fails
        return {
            "scores": {
                "visual_appeal": 0,
                "readability": 0,
                "modernity": 0,
                "brand_consistency": 0,
                "accessibility": 0,
            },
            "style_warnings": ["Failed to parse response"],
            "quick_wins": [],
        }

    def calculate_cost(self) -> float:
        """Vision analysis costs ~$0.003 for typical response"""
        return 0.003

    def is_available(self) -> bool:
        """Check if Humanloop/Vision is available"""
        return bool(settings.humanloop_api_key) or settings.use_stubs
