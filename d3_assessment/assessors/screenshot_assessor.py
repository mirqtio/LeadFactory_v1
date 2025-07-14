"""
Screenshot assessor using ScreenshotOne API
PRD v1.2 - Full page screenshots with thumbnails

Timeout: 8s
Cost: $0.010 per screenshot
Output: screenshot_url and screenshot_thumb_url columns
"""
from typing import Any, Dict

from core.config import settings
from core.logging import get_logger
from d0_gateway.factory import create_client
from d0_gateway.providers.screenshotone import ScreenshotOneClient
from d3_assessment.assessors.base import AssessmentResult, BaseAssessor
from d3_assessment.exceptions import AssessmentTimeoutError
from d3_assessment.models import AssessmentType

logger = get_logger(__name__, domain="d3")


class ScreenshotAssessor(BaseAssessor):
    """Capture website screenshots using ScreenshotOne API"""

    def __init__(self):
        super().__init__()
        self.timeout = 8  # 8 second timeout as per PRD
        self._client = None

    @property
    def assessment_type(self) -> AssessmentType:
        return AssessmentType.VISUAL_ANALYSIS

    def _get_client(self) -> ScreenshotOneClient:
        """Get or create ScreenshotOne client"""
        if not self._client:
            self._client = create_client("screenshotone")
        return self._client

    async def assess(self, url: str, business_data: Dict[str, Any]) -> AssessmentResult:
        """
        Capture screenshots of the website

        Args:
            url: Website URL to screenshot
            business_data: Business information (includes lead_id for cost tracking)

        Returns:
            AssessmentResult with screenshot URLs
        """
        try:
            # Get ScreenshotOne client
            client = self._get_client()

            # Take full page screenshot
            screenshot_result = await client.take_screenshot(
                url=url,
                full_page=True,
                viewport_width=1920,
                viewport_height=1080,
                device_scale_factor=1,
                format="png",
                lead_id=business_data.get("id"),
            )

            if not screenshot_result or not screenshot_result.get("screenshot_url"):
                return AssessmentResult(
                    assessment_type=self.assessment_type,
                    status="failed",
                    error_message="Failed to generate screenshot",
                )

            # Extract URLs
            screenshot_url = screenshot_result.get("screenshot_url")
            thumbnail_url = screenshot_result.get("screenshot_thumb_url")

            # Also capture mobile screenshot for GPT-4 Vision analysis
            mobile_result = await client.take_screenshot(
                url=url,
                full_page=False,  # Just viewport for mobile
                viewport_width=375,  # iPhone width
                viewport_height=812,  # iPhone height
                device_scale_factor=2,  # Retina
                format="png",
                lead_id=business_data.get("id"),
            )

            mobile_screenshot_url = mobile_result.get("screenshot_url") if mobile_result else None

            return AssessmentResult(
                assessment_type=self.assessment_type,
                status="completed",
                data={
                    "screenshot_url": screenshot_url,
                    "screenshot_thumb_url": thumbnail_url,
                    "mobile_screenshot_url": mobile_screenshot_url,
                    "screenshots": {
                        "desktop_full": screenshot_url,
                        "desktop_thumb": thumbnail_url,
                        "mobile": mobile_screenshot_url,
                    },
                },
                metrics={
                    "url_captured": url,
                    "formats_captured": ["desktop", "mobile"] if mobile_screenshot_url else ["desktop"],
                    "api_cost_usd": 0.020 if mobile_screenshot_url else 0.010,  # 2 screenshots
                },
                cost=0.020 if mobile_screenshot_url else 0.010,
            )

        except AssessmentTimeoutError:
            raise
        except Exception as e:
            logger.error(f"Screenshot assessment failed for {url}: {e}")

            return AssessmentResult(
                assessment_type=self.assessment_type,
                status="failed",
                error_message=f"Screenshot API error: {str(e)}",
            )

    def calculate_cost(self) -> float:
        """Screenshot costs $0.010 per capture (x2 for desktop+mobile)"""
        return 0.020  # Desktop + mobile

    def is_available(self) -> bool:
        """Check if ScreenshotOne is available"""
        return bool(settings.screenshotone_key) or settings.use_stubs
