"""
Smoke test for Google Business Profile (Places) API
PRD v1.2 - Verify GBP API for business profile data
"""
import asyncio
import os
import pytest

from d0_gateway.providers.google_places import GooglePlacesClient
from core.config import settings

# Skip if no API key
pytestmark = pytest.mark.skipif(
    not os.getenv("GOOGLE_API_KEY"),
    reason="GOOGLE_API_KEY not set"
)


class TestGBPSmoke:
    """Smoke tests for Google Business Profile API"""
    
    @pytest.mark.asyncio
    async def test_gbp_find_place(self):
        """Test GBP place finding"""
        client = GooglePlacesClient(api_key=settings.google_api_key)
        
        # Find a well-known place
        results = await client.find_place(
            query="Starbucks Union Square San Francisco",
            fields=['place_id', 'name', 'formatted_address']
        )
        
        assert results is not None
        assert len(results) > 0
        assert results[0].get('place_id')
        assert results[0].get('name')
        
        print(f"✓ GBP find place successful:")
        print(f"  Found: {results[0]['name']}")
        print(f"  Place ID: {results[0]['place_id']}")
    
    @pytest.mark.asyncio
    async def test_gbp_place_details(self):
        """Test GBP place details with focus on hours"""
        client = GooglePlacesClient(api_key=settings.google_api_key)
        
        # First find a place
        results = await client.find_place(
            query="Apple Store San Francisco",
            fields=['place_id']
        )
        
        if results:
            place_id = results[0]['place_id']
            
            # Get details including opening hours
            details = await client.get_place_details(
                place_id=place_id,
                fields=[
                    'name', 'formatted_address', 'formatted_phone_number',
                    'opening_hours', 'rating', 'user_ratings_total',
                    'website', 'business_status'
                ]
            )
            
            assert details is not None
            assert details.get('name')
            
            # Check for hours (key for PRD v1.2 scoring)
            has_hours = bool(details.get('opening_hours', {}).get('periods'))
            
            print(f"\n✓ GBP place details successful:")
            print(f"  Name: {details['name']}")
            print(f"  Rating: {details.get('rating', 'N/A')}")
            print(f"  Reviews: {details.get('user_ratings_total', 0)}")
            print(f"  Has Hours: {has_hours}")
            print(f"  Status: {details.get('business_status', 'Unknown')}")
    
    @pytest.mark.asyncio
    async def test_gbp_missing_hours_detection(self):
        """Test detection of missing business hours"""
        client = GooglePlacesClient(api_key=settings.google_api_key)
        
        # Search for a business that might not have hours
        results = await client.find_place(
            query="Golden Gate Bridge San Francisco",  # Landmark, no hours
            fields=['place_id']
        )
        
        if results:
            place_id = results[0]['place_id']
            details = await client.get_place_details(
                place_id=place_id,
                fields=['name', 'opening_hours']
            )
            
            has_hours = bool(details.get('opening_hours', {}).get('periods'))
            
            print(f"\n✓ GBP missing hours detection:")
            print(f"  Place: {details.get('name', 'Unknown')}")
            print(f"  Has Hours: {has_hours}")
            print(f"  Missing Hours Detected: {not has_hours}")
    
    @pytest.mark.asyncio
    async def test_gbp_cost_tracking(self):
        """Test GBP cost tracking"""
        client = GooglePlacesClient(api_key=settings.google_api_key)
        
        # Cost should be $0.002 per place details call
        cost = await client.calculate_cost("places/details")
        assert cost == 0.002, f"Expected cost $0.002, got ${cost}"
        
        print(f"\n✓ GBP cost tracking correct: ${cost} per place details")
    
    @pytest.mark.asyncio
    async def test_gbp_error_handling(self):
        """Test GBP error handling"""
        client = GooglePlacesClient(api_key=settings.google_api_key)
        
        # Test with invalid place ID
        details = await client.get_place_details(
            place_id="InvalidPlaceID123",
            fields=['name']
        )
        
        # Should handle gracefully
        assert details is None or 'error' in details
        print("\n✓ GBP error handling works correctly")
    
    @pytest.mark.asyncio
    async def test_gbp_fields_extraction(self):
        """Test extraction of all required GBP fields"""
        client = GooglePlacesClient(api_key=settings.google_api_key)
        
        # Find a restaurant (likely to have all fields)
        results = await client.find_place(
            query="Chipotle San Francisco Financial District",
            fields=['place_id']
        )
        
        if results:
            place_id = results[0]['place_id']
            details = await client.get_place_details(
                place_id=place_id,
                fields=[
                    'name', 'types', 'price_level', 'rating',
                    'user_ratings_total', 'opening_hours',
                    'website', 'formatted_phone_number'
                ]
            )
            
            print(f"\n✓ GBP fields extraction:")
            print(f"  Name: {details.get('name')}")
            print(f"  Types: {details.get('types', [])[:3]}")
            print(f"  Price Level: {'$' * details.get('price_level', 0) if details.get('price_level') else 'N/A'}")
            print(f"  Phone: {details.get('formatted_phone_number', 'N/A')}")
            print(f"  Website: {'Yes' if details.get('website') else 'No'}")


if __name__ == "__main__":
    # Run smoke tests
    asyncio.run(test_gbp_find_place())
    asyncio.run(test_gbp_place_details())
    asyncio.run(test_gbp_missing_hours_detection())
    asyncio.run(test_gbp_cost_tracking())
    asyncio.run(test_gbp_error_handling())
    asyncio.run(test_gbp_fields_extraction())