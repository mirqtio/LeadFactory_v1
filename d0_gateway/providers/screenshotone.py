"""
ScreenshotOne API client for website screenshots
"""
import logging
from typing import Any, Dict, Optional
from urllib.parse import urlencode

from d0_gateway.base import BaseAPIClient
from d0_gateway.exceptions import APIProviderError

logger = logging.getLogger(__name__)


class ScreenshotOneClient(BaseAPIClient):
    """
    ScreenshotOne API client for capturing website screenshots
    
    API Documentation: https://screenshotone.com/docs
    """
    
    def __init__(self, api_key: str, **kwargs):
        """
        Initialize ScreenshotOne client
        
        Args:
            api_key: ScreenshotOne API access key
            **kwargs: Additional configuration
        """
        base_url = kwargs.get("base_url", "https://api.screenshotone.com")
        
        super().__init__(
            provider="screenshotone",
            api_key=api_key,
            base_url=base_url,
        )
        
        self.timeout = kwargs.get("timeout", 60)  # Screenshots can take time
        
    def _get_base_url(self) -> str:
        """Get base URL"""
        return self.base_url
        
    def _get_headers(self) -> Dict[str, str]:
        """Get headers - ScreenshotOne uses query params for auth"""
        return {
            "User-Agent": "LeadFactory/1.0"
        }
        
    def get_rate_limit(self) -> Dict[str, int]:
        """Get rate limit configuration"""
        return {
            "daily_limit": 1000,
            "daily_used": 0,
            "burst_limit": 10,
            "window_seconds": 1,
        }
        
    def calculate_cost(self, operation: str, **kwargs) -> float:
        """Calculate cost - ScreenshotOne pricing varies by plan"""
        # Assuming pay-as-you-go pricing
        return 0.01  # $0.01 per screenshot
        
    async def capture_screenshot(
        self,
        url: str,
        full_page: bool = True,
        viewport_width: int = 1920,
        viewport_height: int = 1080,
        format: str = "png",
        **kwargs
    ) -> bytes:
        """
        Capture a screenshot of a website
        
        Args:
            url: Website URL to capture
            full_page: Capture full page (True) or viewport only (False)
            viewport_width: Viewport width in pixels
            viewport_height: Viewport height in pixels
            format: Image format (png, jpg, webp)
            **kwargs: Additional ScreenshotOne parameters
            
        Returns:
            Screenshot image data as bytes
        """
        params = {
            "access_key": self.api_key,
            "url": url,
            "full_page": str(full_page).lower(),
            "viewport_width": viewport_width,
            "viewport_height": viewport_height,
            "format": format,
            "cache": kwargs.get("cache", "false"),
            "device_scale_factor": kwargs.get("device_scale_factor", 1),
            "delay": kwargs.get("delay", 0),  # Wait before screenshot
            "block_ads": kwargs.get("block_ads", "true"),
            "block_cookie_banners": kwargs.get("block_cookie_banners", "true"),
        }
        
        # Add any additional parameters
        for key, value in kwargs.items():
            if key not in params:
                params[key] = value
        
        try:
            # ScreenshotOne uses GET with query parameters
            response = await self.make_request(
                method="GET",
                endpoint="/take",
                params=params,
                timeout=self.timeout
            )
            
            # For ScreenshotOne, the response is the image data directly
            if isinstance(response, bytes):
                logger.info(f"Screenshot captured for {url}, size: {len(response)} bytes")
                
                # Emit cost for successful screenshot
                self.emit_cost(
                    lead_id=kwargs.get("lead_id"),
                    campaign_id=kwargs.get("campaign_id"),
                    cost_usd=0.01,  # $0.01 per screenshot as per PRD
                    operation="capture_screenshot",
                    metadata={
                        "url": url,
                        "full_page": full_page,
                        "format": format,
                        "size_bytes": len(response)
                    }
                )
                
                return response
            else:
                raise APIProviderError(
                    provider="screenshotone",
                    message="Invalid response format",
                    error_code="INVALID_RESPONSE"
                )
                
        except Exception as e:
            logger.error(f"Failed to capture screenshot for {url}: {str(e)}")
            raise
            
    async def get_screenshot_info(self, url: str) -> Dict[str, Any]:
        """
        Get information about a screenshot without capturing it
        
        Args:
            url: Website URL to check
            
        Returns:
            Screenshot metadata
        """
        params = {
            "access_key": self.api_key,
            "url": url,
            "info": "true"  # Get info only
        }
        
        try:
            response = await self.make_request(
                method="GET",
                endpoint="/take",
                params=params
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Failed to get screenshot info for {url}: {str(e)}")
            raise
            
    def get_screenshot_url(
        self,
        url: str,
        full_page: bool = True,
        **kwargs
    ) -> str:
        """
        Get the direct URL for a screenshot (useful for embedding)
        
        Args:
            url: Website URL to capture
            full_page: Capture full page or viewport only
            **kwargs: Additional parameters
            
        Returns:
            Direct screenshot URL
        """
        params = {
            "access_key": self.api_key,
            "url": url,
            "full_page": str(full_page).lower(),
            **kwargs
        }
        
        # Build URL with parameters
        query_string = urlencode(params)
        return f"{self.base_url}/take?{query_string}"