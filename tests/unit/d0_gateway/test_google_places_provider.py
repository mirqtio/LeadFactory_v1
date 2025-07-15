"""
Unit tests for Google Places provider using mock factory pattern.
Part of P0-015 coverage enhancement - targeting golden paths.
"""
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from requests.exceptions import Timeout

from d0_gateway.providers.google_places import GooglePlacesClient
from tests.fixtures import GooglePlacesMockFactory


class TestGooglePlacesClient:
    """Test Google Places API client with mock factory patterns."""

    @pytest.fixture
    def client(self):
        """Create a Google Places client with test API key."""
        with patch.dict("os.environ", {"GOOGLE_PLACES_API_KEY": "test-api-key"}):
            return GooglePlacesClient()

    def test_initialization_with_api_key(self):
        """Test client initialization with API key."""
        client = GooglePlacesClient(api_key="test-key-123")
        # In test mode with stubs, the API key is overridden to a stub key
        assert client.api_key.startswith("stub-")
        # In test mode with stubs, should use stub base URL
        assert "localhost:5010" in client._base_url or "stub-server:5010" in client._base_url

    def test_initialization_from_env(self):
        """Test client initialization from environment variable."""
        with patch.dict("os.environ", {"GOOGLE_PLACES_API_KEY": "env-test-key"}):
            client = GooglePlacesClient()
            # In test mode with stubs, the API key is overridden to a stub key
            assert client.api_key.startswith("stub-")

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

    def test_calculate_cost_other_operation(self, client):
        """Test cost calculation for other operations."""
        cost = client.calculate_cost("nearbysearch/json")
        assert cost == Decimal("0.000")

    @pytest.mark.asyncio
    async def test_find_place_success(self, client):
        """Test successful place search - golden path."""
        # Setup mock response
        mock_response = {
            "candidates": [
                {
                    "place_id": "test_place_123",
                    "name": "Test Business",
                    "formatted_address": "123 Test St, San Francisco, CA",
                }
            ],
            "status": "OK",
        }

        with patch.object(client, "make_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            # Make request
            result = await client.find_place("Test Business San Francisco")

            # Verify response
            assert result is not None
            assert result["place_id"] == "test_place_123"
            assert result["name"] == "Test Business"

            # Verify request was made correctly
            # In test environment with stubs, expect stub API key
            mock_request.assert_called_once_with(
                "GET",
                "/findplacefromtext/json",
                params={
                    "input": "Test Business San Francisco",
                    "inputtype": "textquery",
                    "fields": "place_id,name,formatted_address",
                    "key": "stub-google_places-key",
                },
            )

    @pytest.mark.asyncio
    async def test_find_place_no_results(self, client):
        """Test search with no results."""
        mock_response = {"candidates": [], "status": "ZERO_RESULTS"}

        with patch.object(client, "make_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            result = await client.find_place("Nonexistent Business")
            assert result is None

    @pytest.mark.asyncio
    async def test_get_place_details_success(self, client):
        """Test successful place details retrieval - golden path."""
        # Setup mock response
        place_id = "test_place_123"
        mock_response = GooglePlacesMockFactory.create_place_details_response(place_id)

        with patch.object(client, "make_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            # Make request
            result = await client.get_place_details(place_id)

            # Verify response
            assert result is not None
            assert result["place_id"] == place_id
            assert result["name"] == "Detailed Test Business"
            assert result["website"] == "https://testbusiness.com"
            assert "missing_hours" in result  # PRD requirement

    @pytest.mark.asyncio
    async def test_get_place_details_missing_hours(self, client):
        """Test place details with missing hours - PRD requirement."""
        place_id = "test_place_123"
        mock_response = {
            "result": {
                "place_id": place_id,
                "name": "Test Business",
                "formatted_address": "123 Test St",
                # No opening_hours field
            },
            "status": "OK",
        }

        with patch.object(client, "make_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            result = await client.get_place_details(place_id)

            assert result is not None
            assert result["missing_hours"] is True

    @pytest.mark.asyncio
    async def test_get_place_details_with_hours(self, client):
        """Test place details with complete hours."""
        place_id = "test_place_123"
        mock_response = {
            "result": {
                "place_id": place_id,
                "name": "Test Business",
                "opening_hours": {
                    "weekday_text": [
                        "Monday: 9:00 AM – 9:00 PM",
                        "Tuesday: 9:00 AM – 9:00 PM",
                        "Wednesday: 9:00 AM – 9:00 PM",
                        "Thursday: 9:00 AM – 9:00 PM",
                        "Friday: 9:00 AM – 10:00 PM",
                        "Saturday: 10:00 AM – 10:00 PM",
                        "Sunday: 10:00 AM – 8:00 PM",
                    ]
                },
            },
            "status": "OK",
        }

        with patch.object(client, "make_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            result = await client.get_place_details(place_id)

            assert result is not None
            assert result["missing_hours"] is False

    @pytest.mark.asyncio
    async def test_search_business_success(self, client):
        """Test successful business search - golden path."""
        # Mock find_place
        find_place_result = {
            "place_id": "test_place_123",
            "name": "Test Restaurant",
            "formatted_address": "123 Test St, San Francisco, CA",
        }

        # Mock get_place_details
        place_details = GooglePlacesMockFactory.create_place_details_response("test_place_123")
        place_details["result"]["missing_hours"] = False

        with patch.object(client, "find_place", new_callable=AsyncMock) as mock_find:
            with patch.object(client, "get_place_details", new_callable=AsyncMock) as mock_details:
                mock_find.return_value = find_place_result
                mock_details.return_value = place_details["result"]

                result = await client.search_business("Test Restaurant", "123 Test St")

                assert result is not None
                assert result["place_id"] == "test_place_123"
                assert result["name"] == "Detailed Test Business"

                # Verify the search query was built correctly
                mock_find.assert_called_once_with("Test Restaurant 123 Test St")

    @pytest.mark.asyncio
    async def test_search_business_not_found(self, client):
        """Test business search with no results."""
        with patch.object(client, "find_place", new_callable=AsyncMock) as mock_find:
            mock_find.return_value = None

            result = await client.search_business("Nonexistent Business")
            assert result is None

    @pytest.mark.asyncio
    async def test_handle_rate_limit(self, client):
        """Test rate limit handling in make_request."""
        mock_response = GooglePlacesMockFactory.create_error_response("OVER_QUERY_LIMIT")

        with patch.object(client, "make_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            # The find_place method should handle the error response
            result = await client.find_place("test")

            # With OVER_QUERY_LIMIT, candidates will be empty
            assert result is None

    @pytest.mark.asyncio
    async def test_timeout_handling(self, client):
        """Test timeout scenario handling."""
        with patch.object(client, "make_request", new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = Timeout("Connection timed out")

            with pytest.raises(Timeout):
                await client.find_place("test")

    @pytest.mark.asyncio
    async def test_custom_fields_in_find_place(self, client):
        """Test find_place with custom fields."""
        mock_response = {
            "candidates": [{"place_id": "test_123", "name": "Test", "rating": 4.5, "user_ratings_total": 100}],
            "status": "OK",
        }

        with patch.object(client, "make_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            result = await client.find_place(
                "Test Business", fields=["place_id", "name", "rating", "user_ratings_total"]
            )

            assert result is not None
            assert result["rating"] == 4.5
            assert result["user_ratings_total"] == 100

            # Verify custom fields were passed
            call_args = mock_request.call_args[1]["params"]
            assert call_args["fields"] == "place_id,name,rating,user_ratings_total"

    def test_base_url_configuration(self, client):
        """Test base URL is set correctly."""
        # In test environment with stubs, should use stub URL
        assert "localhost:5010" in client._get_base_url() or "stub-server:5010" in client._get_base_url()

    def test_provider_name(self, client):
        """Test provider name is set correctly."""
        assert client.provider == "google_places"
