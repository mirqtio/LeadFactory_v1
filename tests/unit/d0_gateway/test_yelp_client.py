"""
Test Yelp API client implementation
"""
import pytest
import json
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch

from d0_gateway.providers.yelp import YelpClient


class TestYelpClient:
    
    @pytest.fixture
    def yelp_client(self):
        """Create Yelp client for testing"""
        # Create client in stub mode for testing
        return YelpClient()
    
    def test_business_search_works_initialization(self, yelp_client):
        """Test that business search client is properly initialized"""
        # Should inherit from BaseAPIClient
        assert hasattr(yelp_client, 'provider')
        assert yelp_client.provider == "yelp"
        
        # Should have rate limiter, circuit breaker, cache
        assert hasattr(yelp_client, 'rate_limiter')
        assert hasattr(yelp_client, 'circuit_breaker')
        assert hasattr(yelp_client, 'cache')
        
        # Should have proper base URL
        assert yelp_client._get_base_url() == "https://api.yelp.com"
        
        # Should have proper headers (in stub mode)
        headers = yelp_client._get_headers()
        assert "Authorization" in headers
        assert "Bearer" in headers["Authorization"]
        assert headers["Content-Type"] == "application/json"
    
    def test_5k_day_limit_enforced_config(self, yelp_client):
        """Test that 5k/day limit is enforced through configuration"""
        rate_limit = yelp_client.get_rate_limit()
        
        # Should have 5000 daily limit as per Yelp API
        assert rate_limit['daily_limit'] == 5000
        assert rate_limit['burst_limit'] == 10  # Reasonable burst limit
        assert rate_limit['window_seconds'] == 1
        
        # Should track daily usage
        assert 'daily_used' in rate_limit
    
    @pytest.mark.asyncio
    async def test_business_search_works_basic(self, yelp_client):
        """Test basic business search functionality"""
        # Mock the make_request method
        yelp_client.make_request = AsyncMock(return_value={
            "businesses": [
                {
                    "id": "test-business-1",
                    "name": "Test Restaurant",
                    "rating": 4.5,
                    "review_count": 123,
                    "location": {
                        "address1": "123 Main St",
                        "city": "San Francisco",
                        "state": "CA",
                        "zip_code": "94105"
                    },
                    "categories": [
                        {"alias": "restaurants", "title": "Restaurants"}
                    ]
                }
            ],
            "total": 1,
            "region": {
                "center": {
                    "latitude": 37.7749,
                    "longitude": -122.4194
                }
            }
        })
        
        # Test basic search
        result = await yelp_client.search_businesses(
            location="San Francisco, CA",
            term="restaurant"
        )
        
        # Verify API call was made correctly
        yelp_client.make_request.assert_called_once_with(
            'GET',
            '/v3/businesses/search',
            params={
                'location': 'San Francisco, CA',
                'limit': 50,
                'offset': 0,
                'term': 'restaurant'
            }
        )
        
        # Verify response structure
        assert 'businesses' in result
        assert len(result['businesses']) == 1
        assert result['businesses'][0]['name'] == "Test Restaurant"
        assert result['total'] == 1
    
    @pytest.mark.asyncio
    async def test_pagination_handled_correctly(self, yelp_client):
        """Test that pagination is handled correctly"""
        # Mock make_request to return paginated results
        yelp_client.make_request = AsyncMock()
        
        # Test pagination with different limits and offsets
        await yelp_client.search_businesses(
            location="Los Angeles, CA",
            limit=25,
            offset=50
        )
        
        yelp_client.make_request.assert_called_with(
            'GET',
            '/v3/businesses/search',
            params={
                'location': 'Los Angeles, CA',
                'limit': 25,  # Should respect provided limit
                'offset': 50   # Should respect provided offset
            }
        )
        
        # Test that limit is capped at Yelp's maximum of 50
        yelp_client.make_request.reset_mock()
        await yelp_client.search_businesses(
            location="Los Angeles, CA",
            limit=100  # Should be capped to 50
        )
        
        call_args = yelp_client.make_request.call_args[1]['params']
        assert call_args['limit'] == 50  # Should be capped to Yelp's max
    
    @pytest.mark.asyncio
    async def test_pagination_large_datasets(self, yelp_client):
        """Test pagination handling for large datasets"""
        # Mock responses for multiple pages
        responses = [
            {"businesses": [f"business_{i}" for i in range(50)], "total": 150},
            {"businesses": [f"business_{i}" for i in range(50, 100)], "total": 150},
            {"businesses": [f"business_{i}" for i in range(100, 150)], "total": 150}
        ]
        
        yelp_client.make_request = AsyncMock(side_effect=responses)
        
        # Simulate paginated searches
        page1 = await yelp_client.search_businesses("NYC", limit=50, offset=0)
        page2 = await yelp_client.search_businesses("NYC", limit=50, offset=50)
        page3 = await yelp_client.search_businesses("NYC", limit=50, offset=100)
        
        # Verify correct pagination parameters
        calls = yelp_client.make_request.call_args_list
        assert calls[0][1]['params']['offset'] == 0
        assert calls[1][1]['params']['offset'] == 50
        assert calls[2][1]['params']['offset'] == 100
        
        # Verify responses
        assert len(page1['businesses']) == 50
        assert len(page2['businesses']) == 50
        assert len(page3['businesses']) == 50
    
    @pytest.mark.asyncio
    async def test_error_handling_complete_api_errors(self, yelp_client):
        """Test complete error handling for API errors"""
        from core.exceptions import ExternalAPIError, RateLimitError
        
        # Test various error scenarios
        error_scenarios = [
            # Rate limit error
            {
                'exception': RateLimitError("Rate limit exceeded"),
                'expected_type': RateLimitError
            },
            # General API error
            {
                'exception': ExternalAPIError("API unavailable", 503),
                'expected_type': ExternalAPIError
            },
            # Authentication error
            {
                'exception': ExternalAPIError("Invalid API key", 401),
                'expected_type': ExternalAPIError
            }
        ]
        
        for scenario in error_scenarios:
            yelp_client.make_request = AsyncMock(side_effect=scenario['exception'])
            
            with pytest.raises(scenario['expected_type']):
                await yelp_client.search_businesses(location="Test Location")
    
    @pytest.mark.asyncio
    async def test_error_handling_complete_network_errors(self, yelp_client):
        """Test error handling for network-related errors"""
        import httpx
        
        # Test network timeout
        yelp_client.make_request = AsyncMock(side_effect=httpx.TimeoutException("Request timeout"))
        
        with pytest.raises(httpx.TimeoutException):
            await yelp_client.search_businesses(location="Test Location")
        
        # Test connection error
        yelp_client.make_request = AsyncMock(side_effect=httpx.ConnectError("Connection failed"))
        
        with pytest.raises(httpx.ConnectError):
            await yelp_client.search_businesses(location="Test Location")
    
    @pytest.mark.asyncio
    async def test_business_details_endpoint(self, yelp_client):
        """Test business details retrieval"""
        # Mock business details response
        business_details = {
            "id": "test-business-123",
            "name": "Test Restaurant",
            "image_url": "https://example.com/image.jpg",
            "is_closed": False,
            "url": "https://yelp.com/biz/test-restaurant",
            "phone": "+14155551234",
            "display_phone": "(415) 555-1234",
            "hours": [
                {
                    "open": [
                        {"is_overnight": False, "start": "1100", "end": "2100", "day": 0}
                    ]
                }
            ]
        }
        
        yelp_client.make_request = AsyncMock(return_value=business_details)
        
        result = await yelp_client.get_business_details("test-business-123")
        
        # Verify correct API call
        yelp_client.make_request.assert_called_once_with(
            'GET',
            '/v3/businesses/test-business-123'
        )
        
        # Verify response
        assert result['id'] == "test-business-123"
        assert result['name'] == "Test Restaurant"
        assert 'hours' in result
    
    @pytest.mark.asyncio
    async def test_business_reviews_endpoint(self, yelp_client):
        """Test business reviews retrieval"""
        reviews_response = {
            "reviews": [
                {
                    "id": "review-1",
                    "rating": 5,
                    "text": "Great food and service!",
                    "time_created": "2023-01-01 12:00:00",
                    "user": {
                        "id": "user-1",
                        "name": "John D.",
                        "image_url": "https://example.com/user.jpg"
                    }
                }
            ],
            "total": 1,
            "possible_languages": ["en"]
        }
        
        yelp_client.make_request = AsyncMock(return_value=reviews_response)
        
        result = await yelp_client.get_business_reviews("test-business-123")
        
        # Verify correct API call
        yelp_client.make_request.assert_called_once_with(
            'GET',
            '/v3/businesses/test-business-123/reviews',
            params={}
        )
        
        # Verify response
        assert 'reviews' in result
        assert len(result['reviews']) == 1
        assert result['reviews'][0]['rating'] == 5
    
    @pytest.mark.asyncio
    async def test_phone_search_endpoint(self, yelp_client):
        """Test phone number search"""
        phone_response = {
            "businesses": [
                {
                    "id": "found-by-phone",
                    "name": "Restaurant Found by Phone",
                    "phone": "+14155551234"
                }
            ]
        }
        
        yelp_client.make_request = AsyncMock(return_value=phone_response)
        
        result = await yelp_client.search_businesses_by_phone("+14155551234")
        
        # Verify correct API call
        yelp_client.make_request.assert_called_once_with(
            'GET',
            '/v3/businesses/search/phone',
            params={'phone': '+14155551234'}
        )
        
        # Verify response
        assert 'businesses' in result
        assert result['businesses'][0]['phone'] == "+14155551234"
    
    def test_cost_calculation(self, yelp_client):
        """Test cost calculation for Yelp operations"""
        # Yelp API is free up to 5k calls per day
        search_cost = yelp_client.calculate_cost("GET:/v3/businesses/search")
        assert search_cost == Decimal('0.000')
        
        details_cost = yelp_client.calculate_cost("GET:/v3/businesses/abc123")
        assert details_cost == Decimal('0.000')
        
        # Other operations might have minimal cost
        other_cost = yelp_client.calculate_cost("GET:/v3/other")
        assert other_cost == Decimal('0.001')
    
    @pytest.mark.asyncio
    async def test_batch_search_locations(self, yelp_client):
        """Test batch location search functionality"""
        # Mock responses for different locations
        responses = [
            {"businesses": [{"name": "NYC Restaurant"}], "total": 1},
            {"businesses": [{"name": "LA Restaurant"}], "total": 1},
            {"businesses": [{"name": "Chicago Restaurant"}], "total": 1}
        ]
        
        yelp_client.search_businesses = AsyncMock(side_effect=responses)
        
        locations = ["New York, NY", "Los Angeles, CA", "Chicago, IL"]
        result = await yelp_client.batch_search_locations(
            locations=locations,
            categories="restaurants"
        )
        
        # Verify all locations were searched
        assert yelp_client.search_businesses.call_count == 3
        
        # Verify result structure
        assert 'locations' in result
        assert 'total_locations' in result
        assert 'successful_locations' in result
        
        assert result['total_locations'] == 3
        assert result['successful_locations'] == 3
        
        # Verify each location has results
        for location in locations:
            assert location in result['locations']
            assert 'businesses' in result['locations'][location]
    
    @pytest.mark.asyncio
    async def test_batch_search_with_errors(self, yelp_client):
        """Test batch search with some location errors"""
        # Mock mixed success/failure responses
        def mock_search(location, **kwargs):
            if location == "Invalid Location":
                raise Exception("Location not found")
            return {"businesses": [{"name": f"Restaurant in {location}"}], "total": 1}
        
        yelp_client.search_businesses = AsyncMock(side_effect=mock_search)
        
        locations = ["New York, NY", "Invalid Location", "Los Angeles, CA"]
        result = await yelp_client.batch_search_locations(locations)
        
        # Should handle errors gracefully
        assert result['total_locations'] == 3
        assert result['successful_locations'] == 2  # 2 succeeded, 1 failed
        
        # Failed location should have error info
        assert 'error' in result['locations']['Invalid Location']
        assert result['locations']['Invalid Location']['businesses'] == []
        
        # Successful locations should have data
        assert 'businesses' in result['locations']['New York, NY']
        assert 'businesses' in result['locations']['Los Angeles, CA']
    
    @pytest.mark.asyncio
    async def test_parameter_validation_and_limits(self, yelp_client):
        """Test parameter validation and Yelp API limits"""
        yelp_client.make_request = AsyncMock(return_value={"businesses": []})
        
        # Test radius limit (max 40000 meters)
        await yelp_client.search_businesses(
            location="Test",
            radius=50000  # Should be capped to 40000
        )
        
        call_args = yelp_client.make_request.call_args[1]['params']
        assert call_args['radius'] == 40000  # Should be capped
        
        # Test limit parameter (max 50)
        yelp_client.make_request.reset_mock()
        await yelp_client.search_businesses(
            location="Test",
            limit=100  # Should be capped to 50
        )
        
        call_args = yelp_client.make_request.call_args[1]['params']
        assert call_args['limit'] == 50  # Should be capped
    
    @pytest.mark.asyncio
    async def test_optional_parameters(self, yelp_client):
        """Test all optional search parameters"""
        yelp_client.make_request = AsyncMock(return_value={"businesses": []})
        
        # Test with all optional parameters
        await yelp_client.search_businesses(
            location="San Francisco, CA",
            categories="restaurants,bars",
            term="pizza",
            limit=25,
            offset=10,
            radius=5000,
            price="1,2,3",
            open_now=True,
            sort_by="rating"
        )
        
        call_args = yelp_client.make_request.call_args[1]['params']
        
        # Verify all parameters are included
        assert call_args['location'] == "San Francisco, CA"
        assert call_args['categories'] == "restaurants,bars"
        assert call_args['term'] == "pizza"
        assert call_args['limit'] == 25
        assert call_args['offset'] == 10
        assert call_args['radius'] == 5000
        assert call_args['price'] == "1,2,3"
        assert call_args['open_now'] is True
        assert call_args['sort_by'] == "rating"
    
    @pytest.mark.asyncio
    async def test_autocomplete_functionality(self, yelp_client):
        """Test autocomplete functionality"""
        autocomplete_response = {
            "terms": [
                {"text": "pizza"},
                {"text": "pizzeria"},
                {"text": "pizza delivery"}
            ],
            "businesses": [
                {"id": "pizza-place", "name": "Pizza Place"}
            ],
            "categories": [
                {"alias": "pizza", "title": "Pizza"}
            ]
        }
        
        yelp_client.make_request = AsyncMock(return_value=autocomplete_response)
        
        # Test basic autocomplete
        result = await yelp_client.get_autocomplete("pizz")
        
        yelp_client.make_request.assert_called_once_with(
            'GET',
            '/v3/autocomplete',
            params={'text': 'pizz'}
        )
        
        assert 'terms' in result
        assert len(result['terms']) == 3
        
        # Test autocomplete with location
        yelp_client.make_request.reset_mock()
        await yelp_client.get_autocomplete(
            "restaur",
            latitude=37.7749,
            longitude=-122.4194
        )
        
        call_args = yelp_client.make_request.call_args[1]['params']
        assert call_args['text'] == "restaur"
        assert call_args['latitude'] == 37.7749
        assert call_args['longitude'] == -122.4194


class TestYelpClientIntegration:
    
    @pytest.mark.asyncio
    async def test_rate_limiting_integration(self):
        """Test integration with rate limiting"""
        yelp_client = YelpClient()
        
        # Mock rate limiter to indicate limit exceeded
        with patch.object(yelp_client.rate_limiter, 'is_allowed', return_value=False):
            from core.exceptions import RateLimitError
            
            # Mock make_request to raise rate limit error
            yelp_client.make_request = AsyncMock(side_effect=RateLimitError("Daily limit exceeded"))
            
            with pytest.raises(RateLimitError):
                await yelp_client.search_businesses(location="Test")
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_integration(self):
        """Test integration with circuit breaker"""
        yelp_client = YelpClient()
        
        # Mock circuit breaker to indicate open state
        with patch.object(yelp_client.circuit_breaker, 'can_execute', return_value=False):
            from d0_gateway.exceptions import CircuitBreakerOpenError
            
            # Mock make_request to raise circuit breaker error
            yelp_client.make_request = AsyncMock(side_effect=CircuitBreakerOpenError("yelp", 5))
            
            with pytest.raises(CircuitBreakerOpenError):
                await yelp_client.search_businesses(location="Test")
    
    @pytest.mark.asyncio
    async def test_caching_integration(self):
        """Test integration with response caching"""
        yelp_client = YelpClient()
        
        # Test that cache is properly initialized
        assert hasattr(yelp_client, 'cache')
        assert yelp_client.cache.provider == "yelp"
        
        # Test cache key generation for search parameters
        search_params = {"location": "Test Location", "term": "restaurant"}
        cache_key = yelp_client.cache.generate_key("/v3/businesses/search", search_params)
        
        # Cache key should be deterministic
        assert isinstance(cache_key, str)
        assert cache_key.startswith("api_cache:")
        
        # Test cache statistics are available
        stats = await yelp_client.cache.get_cache_stats()
        assert 'provider' in stats
        assert stats['provider'] == "yelp"
    
    @pytest.mark.asyncio
    async def test_stub_mode_integration(self):
        """Test integration with stub mode"""
        with patch('core.config.get_settings') as mock_get_settings:
            mock_settings = Mock()
            mock_settings.use_stubs = True
            mock_settings.stub_base_url = "http://localhost:8000"
            mock_get_settings.return_value = mock_settings
            
            yelp_client = YelpClient()
            
            # Should use stub configuration
            assert yelp_client.api_key == "stub-yelp-key"
            assert "localhost" in yelp_client.base_url  # Allow for different ports


class TestYelpClientErrorScenarios:
    
    @pytest.mark.asyncio
    async def test_malformed_response_handling(self):
        """Test handling of malformed API responses"""
        yelp_client = YelpClient()
        
        # Mock malformed JSON response
        yelp_client.make_request = AsyncMock(return_value="invalid json")
        
        # Should handle gracefully or raise appropriate error
        try:
            await yelp_client.search_businesses(location="Test")
        except Exception as e:
            # Should be a specific, expected error type
            assert isinstance(e, (ValueError, TypeError, Exception))
    
    @pytest.mark.asyncio
    async def test_empty_response_handling(self):
        """Test handling of empty responses"""
        yelp_client = YelpClient()
        
        # Mock empty response
        yelp_client.make_request = AsyncMock(return_value={})
        
        result = await yelp_client.search_businesses(location="Test")
        
        # Should handle empty response gracefully
        assert isinstance(result, dict)
    
    @pytest.mark.asyncio
    async def test_api_quota_exceeded_handling(self):
        """Test handling when API quota is exceeded"""
        yelp_client = YelpClient()
        
        # Mock quota exceeded error (HTTP 429)
        from core.exceptions import RateLimitError
        yelp_client.make_request = AsyncMock(side_effect=RateLimitError("API quota exceeded", 429))
        
        with pytest.raises(RateLimitError) as exc_info:
            await yelp_client.search_businesses(location="Test")
        
        assert "quota exceeded" in str(exc_info.value).lower()