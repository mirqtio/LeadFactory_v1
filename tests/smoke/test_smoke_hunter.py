"""
Smoke test for Hunter.io API
PRD v1.2 - Verify Hunter.io domain search with confidence threshold
"""
import asyncio
import os
import pytest
from decimal import Decimal

from d0_gateway.providers.hunter import HunterClient
from core.config import settings

# Skip if no API key
pytestmark = pytest.mark.skipif(
    not os.getenv("HUNTER_API_KEY"), reason="HUNTER_API_KEY not set"
)


class TestHunterSmoke:
    """Smoke tests for Hunter.io API"""

    @pytest.mark.asyncio
    async def test_hunter_domain_search(self):
        """Test Hunter domain search functionality"""
        client = HunterClient(api_key=settings.hunter_api_key)

        # Search for emails at a known domain
        email, confidence = await client.domain_search("stripe.com")

        print(f"Hunter.io results for stripe.com:")
        print(f"  Email: {email}")
        print(f"  Confidence: {confidence}")

        # We may or may not find an email, but API should work
        assert confidence >= 0
        assert confidence <= 1

        if email:
            assert "@" in email
            assert "stripe.com" in email
            print(f"✓ Hunter.io domain search successful")
        else:
            print(f"✓ Hunter.io API working but no email found for stripe.com")

    @pytest.mark.asyncio
    async def test_hunter_confidence_threshold(self):
        """Test Hunter confidence threshold logic"""
        client = HunterClient(api_key=settings.hunter_api_key)

        # Test with a few domains
        test_domains = ["google.com", "facebook.com", "amazon.com"]

        for domain in test_domains:
            email, confidence = await client.domain_search(domain)

            print(f"\nDomain: {domain}")
            print(f"  Email: {email}")
            print(f"  Confidence: {confidence}")
            print(
                f"  Meets PRD threshold (0.75): {'Yes' if confidence >= 0.75 else 'No'}"
            )

        print("✓ Hunter.io confidence threshold test complete")

    @pytest.mark.asyncio
    async def test_hunter_cost_tracking(self):
        """Test Hunter cost tracking"""
        client = HunterClient(api_key=settings.hunter_api_key)

        # Cost should be $0.003 per search
        cost = client.calculate_cost("GET:/v2/domain-search")
        assert cost == Decimal("0.003"), f"Expected cost $0.003, got ${cost}"

        print(f"✓ Hunter.io cost tracking correct: ${cost} per search")

    @pytest.mark.asyncio
    async def test_hunter_error_handling(self):
        """Test Hunter error handling with invalid domain"""
        client = HunterClient(api_key=settings.hunter_api_key)

        # Test with invalid domain
        email, confidence = await client.domain_search("not-a-real-domain-xyz123.fake")

        # Should return None or empty instead of crashing
        assert confidence == 0
        print("✓ Hunter.io error handling works correctly")


if __name__ == "__main__":
    # Run smoke tests
    asyncio.run(test_hunter_domain_search())
    asyncio.run(test_hunter_confidence_threshold())
    asyncio.run(test_hunter_cost_tracking())
    asyncio.run(test_hunter_error_handling())
