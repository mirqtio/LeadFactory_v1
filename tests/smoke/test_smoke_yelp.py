"""
Smoke test for Yelp API
PRD v1.2 - Verify Yelp API is accessible and respects 300/day limit
"""
import asyncio
import os
import pytest
from datetime import datetime

from d0_gateway.providers.yelp import YelpClient
from core.config import settings

# Skip if no API key
pytestmark = pytest.mark.skipif(
    not os.getenv("YELP_API_KEY"),
    reason="YELP_API_KEY not set"
)


class TestYelpSmoke:
    """Smoke tests for Yelp API"""
    
    @pytest.mark.asyncio
    async def test_yelp_search(self):
        """Test basic Yelp search functionality"""
        client = YelpClient(api_key=settings.yelp_api_key)
        
        # Search for restaurants in San Francisco
        results = await client.search_businesses(
            term="pizza",
            location="San Francisco, CA",
            limit=1
        )
        
        assert results is not None
        assert len(results) > 0
        assert results[0].get('name')
        assert results[0].get('id')
        print(f"✓ Yelp search successful: Found {results[0]['name']}")
    
    @pytest.mark.asyncio
    async def test_yelp_business_details(self):
        """Test Yelp business details retrieval"""
        client = YelpClient(api_key=settings.yelp_api_key)
        
        # First search for a business
        results = await client.search_businesses(
            term="pizza",
            location="San Francisco, CA",
            limit=1
        )
        
        if results:
            business_id = results[0]['id']
            
            # Get details
            details = await client.get_business_details(business_id)
            
            assert details is not None
            assert details.get('id') == business_id
            assert details.get('name')
            assert 'rating' in details
            assert 'review_count' in details
            print(f"✓ Yelp details successful: {details['name']} - {details['rating']} stars")
    
    @pytest.mark.asyncio
    async def test_yelp_rate_limit(self):
        """Test Yelp respects 300/day rate limit"""
        client = YelpClient(api_key=settings.yelp_api_key)
        
        # Check rate limiter status
        if hasattr(client, 'rate_limiter'):
            available = client.rate_limiter.tokens_available()
            max_daily = client.rate_limiter.max_tokens
            
            assert max_daily == 300, f"Expected 300 daily limit, got {max_daily}"
            assert available <= 300, f"Available tokens {available} exceeds daily limit"
            print(f"✓ Yelp rate limit configured: {available}/{max_daily} calls available")
        else:
            print("⚠️  No rate limiter found on Yelp client")
    
    def test_yelp_quota_config(self):
        """Test Yelp quota is configured correctly"""
        assert settings.max_daily_yelp_calls == 300, "Yelp daily quota should be 300"
        print("✓ Yelp quota configuration correct: 300 calls/day")


if __name__ == "__main__":
    # Run smoke tests
    asyncio.run(test_yelp_search())
    asyncio.run(test_yelp_business_details())
    asyncio.run(test_yelp_rate_limit())
    test_yelp_quota_config()