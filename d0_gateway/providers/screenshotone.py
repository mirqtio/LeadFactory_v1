"""
ScreenshotOne API client for website screenshots
PRD v1.2 - Full page screenshots with thumbnails

Endpoint: POST /take
Cost: $0.010 per screenshot
Rate limit: 2/sec
"""
import asyncio
import base64
from typing import Dict, Any, Optional
from urllib.parse import urlencode
import hashlib
import hmac

from d0_gateway.base import BaseAPIClient
from d0_gateway.exceptions import APIProviderError, RateLimitExceededError
from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__, domain="d0")


class ScreenshotOneClient(BaseAPIClient):
    """ScreenshotOne API client for website screenshots"""

    def __init__(self, api_key: str, **kwargs):
        """
        Initialize ScreenshotOne client

        Args:
            api_key: ScreenshotOne API key (access key)
            **kwargs: Additional configuration including secret_key
        """
        self.base_url = kwargs.get("base_url", "https://api.screenshotone.com")
        self.access_key = api_key
        self.secret_key = kwargs.get("secret_key", "")  # For signed URLs

        super().__init__(
            provider="screenshotone",
            api_key=api_key,
            base_url=self.base_url,
        )

        # Rate limit: 2 requests per second
        self._last_request_time = 0
        self._rate_limit_delay = 0.5  # 500ms between requests

    def _get_base_url(self) -> str:
        """Get the base URL for ScreenshotOne API"""
        return self.base_url

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for ScreenshotOne API"""
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def get_rate_limit(self) -> Dict[str, int]:
        """Get rate limit configuration"""
        return {
            "requests_per_second": 2,
            "requests_per_minute": 120,
            "requests_per_hour": 7200,
        }

    def calculate_cost(self, operation: str, **kwargs) -> float:
        """Calculate cost for screenshot operations"""
        if operation == "take_screenshot":
            return 0.010  # $0.010 per screenshot
        return 0.0

    async def take_screenshot(
        self,
        url: str,
        full_page: bool = True,
        viewport_width: int = 1920,
        viewport_height: int = 1080,
        device_scale_factor: int = 1,
        format: str = "png",
        lead_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Take a screenshot of a website

        Args:
            url: Website URL to screenshot
            full_page: Capture full page (True) or viewport only
            viewport_width: Viewport width in pixels
            viewport_height: Viewport height in pixels
            device_scale_factor: Device scale factor (1 for normal, 2 for retina)
            format: Image format (png or jpg)
            lead_id: Lead ID for cost tracking

        Returns:
            Dict with screenshot_url and screenshot_thumb_url
        """
        # Enforce rate limit
        await self._enforce_rate_limit()

        # Build parameters
        params = {
            "url": url,
            "full_page": str(full_page).lower(),
            "viewport_width": viewport_width,
            "viewport_height": viewport_height,
            "device_scale_factor": device_scale_factor,
            "format": format,
            "block_ads": "true",
            "block_cookie_banners": "true",
            "block_chats": "true",
            "time_zone": "America/New_York",
            "cache": "true",  # Use cache if available
            "cache_ttl": 86400,  # 24 hours
        }

        try:
            # Generate screenshot URL
            screenshot_url = self._generate_screenshot_url(params)

            # Generate thumbnail URL (smaller viewport)
            thumb_params = params.copy()
            thumb_params.update(
                {"viewport_width": 400, "viewport_height": 300, "full_page": "false"}
            )
            thumbnail_url = self._generate_screenshot_url(thumb_params)

            # Track cost
            self.emit_cost(
                lead_id=lead_id,
                cost_usd=0.010,
                operation="take_screenshot",
                metadata={"url": url, "full_page": full_page, "format": format},
            )

            # Log success
            logger.info(f"Screenshot generated for {url}")

            return {
                "screenshot_url": screenshot_url,
                "screenshot_thumb_url": thumbnail_url,
                "success": True,
                "cached": False,  # Would be set by actual API response
                "format": format,
            }

        except Exception as e:
            logger.error(f"Screenshot generation failed for {url}: {e}")
            raise APIProviderError("screenshotone", str(e))

    def _generate_screenshot_url(self, params: Dict[str, Any]) -> str:
        """
        Generate a signed screenshot URL

        Args:
            params: Screenshot parameters

        Returns:
            Signed screenshot URL
        """
        # Add access key
        params["access_key"] = self.access_key

        # Sort parameters for consistent signing
        sorted_params = sorted(params.items())
        query_string = urlencode(sorted_params)

        if self.secret_key:
            # Generate signature
            signature = self._sign_request(query_string)
            return f"{self.base_url}/take?{query_string}&signature={signature}"
        else:
            # Unsigned URL (less secure)
            return f"{self.base_url}/take?{query_string}"

    def _sign_request(self, query_string: str) -> str:
        """
        Sign request with HMAC-SHA256

        Args:
            query_string: URL query string to sign

        Returns:
            Base64-encoded signature
        """
        signature = hmac.new(
            self.secret_key.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).digest()

        return base64.urlsafe_b64encode(signature).decode("utf-8").rstrip("=")

    async def _enforce_rate_limit(self):
        """Enforce rate limit of 2 requests per second"""
        current_time = asyncio.get_event_loop().time()
        time_since_last = current_time - self._last_request_time

        if time_since_last < self._rate_limit_delay:
            await asyncio.sleep(self._rate_limit_delay - time_since_last)

        self._last_request_time = asyncio.get_event_loop().time()

    async def verify_api_key(self) -> bool:
        """
        Verify API key is valid

        Returns:
            True if API key is valid
        """
        try:
            # Try to generate a screenshot URL for a test page
            result = await self.take_screenshot(
                url="https://example.com",
                full_page=False,
                viewport_width=100,
                viewport_height=100,
            )
            return bool(result.get("screenshot_url"))
        except Exception as e:
            logger.error(f"API key verification failed: {e}")
            return False
