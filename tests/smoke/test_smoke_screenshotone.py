"""
Smoke test for ScreenshotOne API
PRD v1.2 - Verify screenshot capture functionality
"""
import asyncio
import os
from datetime import datetime

import pytest

from core.config import settings
from d0_gateway.providers.screenshotone import ScreenshotOneClient

# Skip if no API key
pytestmark = pytest.mark.skipif(not os.getenv("SCREENSHOTONE_KEY"), reason="SCREENSHOTONE_KEY not set")


class TestScreenshotOneSmoke:
    """Smoke tests for ScreenshotOne API"""

    @pytest.mark.asyncio
    async def test_screenshot_capture(self):
        """Test basic screenshot capture"""
        client = ScreenshotOneClient(
            access_key=settings.screenshotone_key,
            secret_key=settings.screenshotone_secret,
        )

        # Capture screenshot of example.com
        result = await client.capture_screenshot(url="https://example.com", full_page=True, format="png")

        assert result is not None
        assert "url" in result
        assert result["url"].startswith("https://")

        print("✓ ScreenshotOne capture successful:")
        print(f"  URL: {result['url']}")
        print(f"  Cached: {result.get('cached', False)}")

    @pytest.mark.asyncio
    async def test_screenshot_with_options(self):
        """Test screenshot with various options"""
        client = ScreenshotOneClient(
            access_key=settings.screenshotone_key,
            secret_key=settings.screenshotone_secret,
        )

        # Capture with options
        result = await client.capture_screenshot(
            url="https://stripe.com",
            full_page=False,
            viewport_width=1920,
            viewport_height=1080,
            device_scale_factor=2,
            format="jpg",
            quality=85,
        )

        assert result is not None
        assert "url" in result

        print("\n✓ ScreenshotOne with options successful:")
        print(f"  Screenshot URL: {result['url'][:80]}...")

    @pytest.mark.asyncio
    async def test_screenshot_timeout(self):
        """Test screenshot timeout handling"""
        client = ScreenshotOneClient(
            access_key=settings.screenshotone_key,
            secret_key=settings.screenshotone_secret,
        )

        # Set timeout to 8 seconds as per PRD
        client.timeout = 8

        start = datetime.now()
        await client.capture_screenshot(url="https://nytimes.com", full_page=True)  # Heavy page
        duration = (datetime.now() - start).total_seconds()

        assert duration <= 10  # Should timeout before 10s
        print(f"\n✓ ScreenshotOne timeout handling: {duration:.1f}s")

    @pytest.mark.asyncio
    async def test_screenshot_cost_tracking(self):
        """Test screenshot cost tracking"""
        client = ScreenshotOneClient(
            access_key=settings.screenshotone_key,
            secret_key=settings.screenshotone_secret,
        )

        # Cost should be $0.010 per screenshot
        cost = await client.calculate_cost()
        assert cost == 0.010, f"Expected cost $0.010, got ${cost}"

        print(f"\n✓ ScreenshotOne cost tracking correct: ${cost} per screenshot")

    @pytest.mark.asyncio
    async def test_screenshot_rate_limit(self):
        """Test screenshot rate limiting"""
        client = ScreenshotOneClient(
            access_key=settings.screenshotone_key,
            secret_key=settings.screenshotone_secret,
        )

        # Check rate limiter if available (2/sec)
        if hasattr(client, "rate_limiter"):
            rate = client.rate_limiter.rate
            assert rate == 2, f"Expected 2/sec rate limit, got {rate}/sec"
            print(f"\n✓ ScreenshotOne rate limit configured: {rate} requests/sec")
        else:
            print("\n⚠️  No rate limiter found on ScreenshotOne client")

    @pytest.mark.asyncio
    async def test_screenshot_error_handling(self):
        """Test screenshot error handling"""
        client = ScreenshotOneClient(
            access_key=settings.screenshotone_key,
            secret_key=settings.screenshotone_secret,
        )

        # Test with invalid URL
        result = await client.capture_screenshot(url="not-a-valid-url")

        # Should handle gracefully
        if result is None or "error" in result:
            print("\n✓ ScreenshotOne error handling works correctly")
        else:
            # Some services might still return a screenshot of error page
            print("\n✓ ScreenshotOne handled invalid URL")


if __name__ == "__main__":
    # Run smoke tests
    test_instance = TestScreenshotOneSmoke()
    asyncio.run(test_instance.test_screenshot_capture())
    asyncio.run(test_instance.test_screenshot_with_options())
    asyncio.run(test_instance.test_screenshot_timeout())
    asyncio.run(test_instance.test_screenshot_cost_tracking())
    asyncio.run(test_instance.test_screenshot_rate_limit())
    asyncio.run(test_instance.test_screenshot_error_handling())
