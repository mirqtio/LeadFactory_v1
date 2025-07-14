"""
Smoke test for SEMrush API
PRD v1.2 - Verify SEMrush domain overview API
"""
import asyncio
import os

import pytest

from core.config import settings
from d0_gateway.providers.semrush import SEMrushClient

# Skip if no API key
pytestmark = pytest.mark.skipif(not os.getenv("SEMRUSH_API_KEY"), reason="SEMRUSH_API_KEY not set")


class TestSEMrushSmoke:
    """Smoke tests for SEMrush API"""

    @pytest.mark.asyncio
    async def test_semrush_domain_overview(self):
        """Test SEMrush domain overview functionality"""
        client = SEMrushClient(api_key=settings.semrush_api_key)

        # Test with a known domain
        result = await client.get_domain_overview("example.com")

        assert result is not None
        assert "domain" in result
        assert result["domain"] == "example.com"

        # Check for expected fields
        if "organic_keywords" in result:
            print("✓ SEMrush domain overview successful:")
            print(f"  Domain: {result['domain']}")
            print(f"  Organic Keywords: {result.get('organic_keywords', 0)}")
            print(f"  Organic Traffic: {result.get('organic_traffic', 0)}")
            print(f"  Domain Authority: {result.get('domain_authority', 0)}")
        else:
            print("✓ SEMrush API working but limited data for example.com")

    @pytest.mark.asyncio
    async def test_semrush_popular_domain(self):
        """Test SEMrush with a popular domain for better data"""
        client = SEMrushClient(api_key=settings.semrush_api_key)

        # Test with a popular domain
        result = await client.get_domain_overview("nytimes.com")

        assert result is not None
        assert result.get("organic_keywords", 0) > 0

        print("\n✓ SEMrush data for nytimes.com:")
        print(f"  Organic Keywords: {result.get('organic_keywords', 0):,}")
        print(f"  Domain Authority: {result.get('domain_authority', 0)}")

    @pytest.mark.asyncio
    async def test_semrush_cost_tracking(self):
        """Test SEMrush cost tracking"""
        client = SEMrushClient(api_key=settings.semrush_api_key)

        # Cost should be $0.010 per call
        cost = await client.calculate_cost()
        assert cost == 0.010, f"Expected cost $0.010, got ${cost}"

        print(f"\n✓ SEMrush cost tracking correct: ${cost} per call")

    @pytest.mark.asyncio
    async def test_semrush_rate_limit(self):
        """Test SEMrush rate limiting"""
        client = SEMrushClient(api_key=settings.semrush_api_key)

        # Check rate limiter if available
        if hasattr(client, "rate_limiter"):
            available = client.rate_limiter.tokens_available()
            max_daily = client.rate_limiter.max_tokens

            assert max_daily == 1000, f"Expected 1000 daily limit, got {max_daily}"
            print(f"\n✓ SEMrush rate limit configured: {available}/{max_daily} calls available")
        else:
            print("\n⚠️  No rate limiter found on SEMrush client")

    @pytest.mark.asyncio
    async def test_semrush_error_handling(self):
        """Test SEMrush error handling with invalid domain"""
        client = SEMrushClient(api_key=settings.semrush_api_key)

        # Test with invalid domain
        result = await client.domain_overview("not-a-real-domain-xyz123.fake")

        # Should return empty result instead of crashing
        assert result is not None
        assert result.get("organic_keywords", 0) == 0
        print("\n✓ SEMrush error handling works correctly")


if __name__ == "__main__":
    # Run smoke tests
    asyncio.run(test_semrush_domain_overview())
    asyncio.run(test_semrush_popular_domain())
    asyncio.run(test_semrush_cost_tracking())
    asyncio.run(test_semrush_rate_limit())
    asyncio.run(test_semrush_error_handling())
