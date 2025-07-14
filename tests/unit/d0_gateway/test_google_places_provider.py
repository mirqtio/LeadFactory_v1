"""
Unit tests for Google Places provider using mock factory pattern.
Part of P0-015 coverage enhancement - targeting golden paths.
"""
import pytest
import responses
from decimal import Decimal
from unittest.mock import patch, Mock
from requests.exceptions import Timeout, ConnectionError as RequestsConnectionError

from d0_gateway.providers.google_places import GooglePlacesClient
from tests.fixtures import GooglePlacesMockFactory


class TestGooglePlacesClient:
    """Test Google Places API client with mock factory patterns."""
    
    @pytest.fixture
    def client(self):
        """Create a Google Places client with test API key."""
        with patch.dict('os.environ', {'GOOGLE_PLACES_API_KEY': 'test-api-key'}):
            return GooglePlacesClient()
    
    def test_initialization_with_api_key(self):
        """Test client initialization with API key."""
        client = GooglePlacesClient(api_key="test-key-123")
        assert client._api_key == "test-key-123"
        assert client._base_url == "https://maps.googleapis.com/maps/api/place"
    
    def test_initialization_from_env(self):
        """Test client initialization from environment variable."""
        with patch.dict('os.environ', {'GOOGLE_PLACES_API_KEY': 'env-test-key'}):
            client = GooglePlacesClient()
            assert client._api_key == "env-test-key"
    
    def test_get_headers(self, client):
        """Test header configuration."""
        headers = client._get_headers()
        assert headers["Accept"] == "application/json"
        # Google Places uses API key in URL params, not headers
        assert "Authorization" not in headers
    
    def test_get_rate_limit(self, client):
        """Test rate limit configuration."""
        limits = client.get_rate_limit()
        assert limits["daily_limit"] == 25000
        assert limits["burst_limit"] == 50
        assert limits["window_seconds"] == 1
    
    def test_calculate_cost_place_details(self, client):
        """Test cost calculation for place details."""
        cost = client.calculate_cost("details/json")
        assert cost == Decimal("0.002")
    
    def test_calculate_cost_find_place(self, client):
        """Test cost calculation for find place."""
        cost = client.calculate_cost("findplacefromtext/json")
        assert cost == Decimal("0.017")
    
    @responses.activate
    def test_search_places_success(self, client):
        """Test successful place search - golden path."""
        # Setup mock response
        mock_response = GooglePlacesMockFactory.create_success_response()
        responses.add(
            responses.GET,
            "https://maps.googleapis.com/maps/api/place/textsearch/json",
            json=mock_response,
            status=200
        )
        
        # Make request
        result = client.search_places("italian restaurant", "San Francisco, CA")
        
        # Verify response
        assert result["status"] == "OK"
        assert len(result["results"]) == 1
        assert result["results"][0]["name"] == "Test Business"
        assert result["results"][0]["rating"] == 4.5
    
    @responses.activate
    def test_search_places_zero_results(self, client):
        """Test search with no results."""
        # Setup mock response
        mock_response = GooglePlacesMockFactory.create_error_response("ZERO_RESULTS")
        responses.add(
            responses.GET,
            "https://maps.googleapis.com/maps/api/place/textsearch/json",
            json=mock_response,
            status=200
        )
        
        # Make request
        result = client.search_places("nonexistent business", "Nowhere, XX")
        
        # Verify response
        assert result["status"] == "ZERO_RESULTS"
        assert result["results"] == []
    
    @responses.activate
    def test_get_place_details_success(self, client):
        """Test successful place details retrieval - golden path."""
        # Setup mock response
        place_id = "test_place_123"
        mock_response = GooglePlacesMockFactory.create_place_details_response(place_id)
        responses.add(
            responses.GET,
            "https://maps.googleapis.com/maps/api/place/details/json",
            json=mock_response,
            status=200
        )
        
        # Make request
        result = client.get_place_details(place_id)
        
        # Verify response
        assert result["status"] == "OK"
        assert result["result"]["place_id"] == place_id
        assert result["result"]["name"] == "Detailed Test Business"
        assert result["result"]["website"] == "https://testbusiness.com"
        assert len(result["result"]["reviews"]) > 0
    
    @responses.activate
    def test_nearby_search_success(self, client):
        """Test successful nearby search."""
        # Setup mock response
        lat, lng = 37.7749, -122.4194
        mock_response = GooglePlacesMockFactory.create_nearby_search_response(lat, lng)
        responses.add(
            responses.GET,
            "https://maps.googleapis.com/maps/api/place/nearbysearch/json",
            json=mock_response,
            status=200
        )
        
        # Make request
        result = client.nearby_search(lat, lng, radius=1000, type="restaurant")
        
        # Verify response
        assert result["status"] == "OK"
        assert len(result["results"]) == 3
        assert all("nearby_place_" in r["place_id"] for r in result["results"])
    
    @responses.activate
    def test_handle_rate_limit(self, client):
        """Test rate limit handling."""
        # Setup mock response
        mock_response = GooglePlacesMockFactory.create_error_response("OVER_QUERY_LIMIT")
        responses.add(
            responses.GET,
            "https://maps.googleapis.com/maps/api/place/textsearch/json",
            json=mock_response,
            status=200
        )
        
        # Make request
        result = client.search_places("test", "test")
        
        # Verify rate limit is detected
        assert result["status"] == "OVER_QUERY_LIMIT"
    
    def test_timeout_handling(self, client):
        """Test timeout scenario handling."""
        timeout_mock = GooglePlacesMockFactory.create_timeout_scenario()
        
        with patch.object(client.session, 'get', side_effect=timeout_mock.side_effect):
            with pytest.raises(Timeout):
                client.search_places("test", "test")
    
    def test_connection_error_handling(self, client):
        """Test connection error handling."""
        error_mock = GooglePlacesMockFactory.create_connection_error_scenario()
        
        with patch.object(client.session, 'get', side_effect=error_mock.side_effect):
            with pytest.raises(RequestsConnectionError):
                client.search_places("test", "test")
    
    @responses.activate
    def test_extract_business_hours(self, client):
        """Test extraction of business hours from place details."""
        # Setup mock response with opening hours
        mock_response = GooglePlacesMockFactory.create_place_details_response("test_place")
        mock_response["result"]["opening_hours"] = {
            "open_now": True,
            "periods": [
                {
                    "open": {"day": 1, "time": "0900"},
                    "close": {"day": 1, "time": "2100"}
                }
            ],
            "weekday_text": [
                "Monday: 9:00 AM – 9:00 PM",
                "Tuesday: 9:00 AM – 9:00 PM",
                "Wednesday: 9:00 AM – 9:00 PM",
                "Thursday: 9:00 AM – 9:00 PM",
                "Friday: 9:00 AM – 10:00 PM",
                "Saturday: 10:00 AM – 10:00 PM",
                "Sunday: 10:00 AM – 8:00 PM"
            ]
        }
        
        responses.add(
            responses.GET,
            "https://maps.googleapis.com/maps/api/place/details/json",
            json=mock_response,
            status=200
        )
        
        # Make request
        result = client.get_place_details("test_place", fields=["opening_hours"])
        
        # Verify opening hours
        assert result["result"]["opening_hours"]["open_now"] is True
        assert len(result["result"]["opening_hours"]["weekday_text"]) == 7
    
    @responses.activate
    def test_search_with_pagination(self, client):
        """Test search with next page token."""
        # First page
        first_response = GooglePlacesMockFactory.create_multiple_results(20)
        first_response["next_page_token"] = "next_page_123"
        
        responses.add(
            responses.GET,
            "https://maps.googleapis.com/maps/api/place/textsearch/json",
            json=first_response,
            status=200
        )
        
        # Make request
        result = client.search_places("restaurant", "San Francisco")
        
        # Verify pagination token
        assert "next_page_token" in result
        assert result["next_page_token"] == "next_page_123"
        assert len(result["results"]) == 20
    
    def test_validate_place_id(self, client):
        """Test place ID validation."""
        # Valid place IDs
        assert client._validate_place_id("ChIJN1t_tDeuEmsRUsoyG83frY4") is True
        
        # Invalid place IDs
        assert client._validate_place_id("") is False
        assert client._validate_place_id("invalid-id") is False
        assert client._validate_place_id(None) is False
    
    @responses.activate
    def test_get_photo_success(self, client):
        """Test successful photo retrieval."""
        photo_ref = "mock_photo_ref_123"
        photo_data = GooglePlacesMockFactory.create_photo_response(photo_ref)
        
        responses.add(
            responses.GET,
            "https://maps.googleapis.com/maps/api/place/photo",
            body=photo_data,
            status=200,
            content_type="image/jpeg"
        )
        
        # Make request
        result = client.get_photo(photo_ref, max_width=400)
        
        # Verify we got image data
        assert isinstance(result, bytes)
        assert len(result) > 0
        # JPEG magic number
        assert result[:2] == b'\xff\xd8'