"""
Tests for Data Axle client - Phase 0.5 Task GW-02
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient, Response

from d0_gateway.exceptions import (
    APIProviderError,
    AuthenticationError,
    RateLimitExceededError,
)
from core.exceptions import ValidationError
from d0_gateway.providers.dataaxle import DataAxleClient


@pytest.fixture
def mock_settings():
    """Mock settings for testing"""
    settings = MagicMock()
    settings.data_axle_rate_limit_per_min = 200
    settings.use_stubs = False  # Disable stub mode in tests
    settings.get_api_key = MagicMock(return_value="test-key")
    return settings


@pytest.fixture
def dataaxle_client(mock_settings):
    """Create Data Axle client for testing"""
    with patch("core.config.settings", mock_settings), \
         patch("core.config.get_settings", return_value=mock_settings), \
         patch("d0_gateway.base.get_settings", return_value=mock_settings), \
         patch("d0_gateway.base.RateLimiter"), \
         patch("d0_gateway.base.CircuitBreaker"), \
         patch("d0_gateway.base.ResponseCache"), \
         patch("d0_gateway.base.GatewayMetrics"):
        return DataAxleClient(api_key="test-key")


@pytest.fixture
def mock_httpx_client():
    """Mock httpx AsyncClient"""
    return AsyncMock(spec=AsyncClient)


class TestDataAxleClient:
    """Test Data Axle client functionality"""
    
    def test_initialization(self, mock_settings):
        """Test client initialization"""
        with patch("core.config.settings", mock_settings), \
             patch("core.config.get_settings", return_value=mock_settings), \
             patch("d0_gateway.base.get_settings", return_value=mock_settings), \
             patch("d0_gateway.base.RateLimiter"), \
             patch("d0_gateway.base.CircuitBreaker"), \
             patch("d0_gateway.base.ResponseCache"), \
             patch("d0_gateway.base.GatewayMetrics"):
            client = DataAxleClient(api_key="test-key", base_url="https://test.com")
            
            assert client.api_key == "test-key"
            assert client.provider == "dataaxle"
            assert client._rate_limit == 200
            assert client.base_url == "https://test.com"
            
    def test_initialization_with_defaults(self, mock_settings):
        """Test client initialization with default values"""
        with patch("core.config.settings", mock_settings), \
             patch("core.config.get_settings", return_value=mock_settings), \
             patch("d0_gateway.base.get_settings", return_value=mock_settings), \
             patch("d0_gateway.base.RateLimiter"), \
             patch("d0_gateway.base.CircuitBreaker"), \
             patch("d0_gateway.base.ResponseCache"), \
             patch("d0_gateway.base.GatewayMetrics"):
            client = DataAxleClient(api_key="test-key")
            
            assert client.base_url == "https://api.data-axle.com/v2"
            assert client.timeout == 30
            assert client.max_retries == 3
            
    def test_get_headers(self, dataaxle_client):
        """Test header generation"""
        headers = dataaxle_client._get_headers()
        
        assert headers["Authorization"] == "Bearer test-key"
        assert headers["Content-Type"] == "application/json"
        assert headers["Accept"] == "application/json"
        
    @pytest.mark.asyncio
    async def test_match_business_success(self, dataaxle_client, mock_httpx_client):
        """Test successful business match"""
        # Mock response
        mock_response = MagicMock(spec=Response)
        mock_response.json.return_value = {
            "match_found": True,
            "match_confidence": 0.95,
            "business_data": {
                "business_id": "DA_123456",
                "emails": [
                    {"email": "contact@business.com", "type": "primary"},
                    {"email": "info@business.com", "type": "general"}
                ],
                "phones": [
                    {"number": "+12125551234", "type": "main"}
                ],
                "website": "https://www.business.com",
                "employee_count": 50,
                "annual_revenue": 5000000,
                "years_in_business": 10,
                "business_type": "LLC",
                "sic_codes": ["5812"],
                "naics_codes": ["722511"],
            }
        }
        mock_response.status_code = 200
        mock_httpx_client.post.return_value = mock_response
        
        # Patch the client's HTTP client
        dataaxle_client._client = mock_httpx_client
        
        # Test business data
        business_data = {
            "name": "Test Business",
            "address": "123 Main St",
            "city": "New York",
            "state": "NY",
            "zip_code": "10001",
            "lead_id": "lead_123"
        }
        
        result = await dataaxle_client.match_business(business_data)
        
        # Verify request
        mock_httpx_client.post.assert_called_once()
        call_args = mock_httpx_client.post.call_args
        assert call_args[0][0] == "/business/match"
        
        request_json = call_args[1]["json"]
        assert request_json["business_name"] == "Test Business"
        assert request_json["address"] == "123 Main St"
        assert request_json["city"] == "New York"
        assert request_json["state"] == "NY"
        assert request_json["zip"] == "10001"
        assert request_json["match_threshold"] == 0.8
        
        # Verify response transformation
        assert result["primary_email"] == "contact@business.com"
        assert result["emails"] == [
            {"email": "contact@business.com", "type": "primary"},
            {"email": "info@business.com", "type": "general"}
        ]
        assert result["primary_phone"] == "+12125551234"
        assert result["website"] == "https://www.business.com"
        assert result["employee_count"] == 50
        assert result["data_axle_id"] == "DA_123456"
        
    @pytest.mark.asyncio
    async def test_match_business_no_match(self, dataaxle_client, mock_httpx_client):
        """Test business match with no results"""
        # Mock response with no match
        mock_response = MagicMock(spec=Response)
        mock_response.json.return_value = {
            "match_found": False,
            "match_confidence": 0.0,
            "business_data": {}
        }
        mock_response.status_code = 200
        mock_httpx_client.post.return_value = mock_response
        
        dataaxle_client._client = mock_httpx_client
        
        business_data = {"name": "Nonexistent Business"}
        result = await dataaxle_client.match_business(business_data)
        
        assert result is None
        
    @pytest.mark.asyncio
    async def test_match_business_missing_name(self, dataaxle_client):
        """Test validation error for missing business name"""
        business_data = {"city": "New York"}
        
        with pytest.raises(ValidationError, match="Business name is required"):
            await dataaxle_client.match_business(business_data)
            
    @pytest.mark.asyncio
    async def test_match_business_rate_limit(self, dataaxle_client, mock_httpx_client):
        """Test rate limit error handling"""
        # Mock 429 response
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 429
        mock_response.json.return_value = {"error": "Rate limit exceeded"}
        mock_httpx_client.post.side_effect = Exception("429 Rate limit exceeded")
        
        dataaxle_client._client = mock_httpx_client
        
        with pytest.raises(RateLimitExceededError):
            await dataaxle_client.match_business({"name": "Test"})
            
    @pytest.mark.asyncio
    async def test_match_business_auth_error(self, dataaxle_client, mock_httpx_client):
        """Test authentication error handling"""
        # Mock 401 response
        mock_httpx_client.post.side_effect = Exception("401 Unauthorized")
        
        dataaxle_client._client = mock_httpx_client
        
        with pytest.raises(AuthenticationError):
            await dataaxle_client.match_business({"name": "Test"})
            
    @pytest.mark.asyncio
    async def test_match_business_api_error(self, dataaxle_client, mock_httpx_client):
        """Test general API error handling"""
        # Mock generic error
        mock_httpx_client.post.side_effect = Exception("Connection error")
        
        dataaxle_client._client = mock_httpx_client
        
        with pytest.raises(APIProviderError):
            await dataaxle_client.match_business({"name": "Test"})
            
    def test_transform_response_minimal(self, dataaxle_client):
        """Test response transformation with minimal data"""
        data = {
            "business_id": "DA_123",
            "match_confidence": 0.85
        }
        
        result = dataaxle_client._transform_response(data)
        
        assert result["data_axle_id"] == "DA_123"
        assert result["match_confidence"] == 0.85
        assert result["emails"] == []
        assert result["primary_email"] is None
        assert result["phones"] == []
        assert result["primary_phone"] is None
        
    def test_transform_response_string_lists(self, dataaxle_client):
        """Test response transformation with string lists"""
        data = {
            "emails": ["test@example.com", "info@example.com"],
            "phones": ["+12125551234", "+12125555678"]
        }
        
        result = dataaxle_client._transform_response(data)
        
        assert result["primary_email"] == "test@example.com"
        assert result["emails"] == ["test@example.com", "info@example.com"]
        assert result["primary_phone"] == "+12125551234"
        assert result["phones"] == ["+12125551234", "+12125555678"]
        
    @pytest.mark.asyncio
    async def test_verify_api_key_success(self, dataaxle_client, mock_httpx_client):
        """Test API key verification success"""
        # Mock response
        mock_response = MagicMock(spec=Response)
        mock_response.json.return_value = {"status": "active"}
        mock_response.status_code = 200
        mock_httpx_client.get.return_value = mock_response
        
        dataaxle_client._client = mock_httpx_client
        
        result = await dataaxle_client.verify_api_key()
        
        assert result is True
        mock_httpx_client.get.assert_called_with("/account/status", headers=dataaxle_client._get_headers())
        
    @pytest.mark.asyncio
    async def test_verify_api_key_invalid(self, dataaxle_client, mock_httpx_client):
        """Test API key verification with invalid key"""
        # Mock 401 response
        mock_httpx_client.get.side_effect = Exception("401 Unauthorized")
        
        dataaxle_client._client = mock_httpx_client
        
        with pytest.raises(AuthenticationError):
            await dataaxle_client.verify_api_key()
            
    @pytest.mark.asyncio
    async def test_cost_emission(self, dataaxle_client, mock_httpx_client):
        """Test cost emission for successful match"""
        # Mock emit_cost method
        dataaxle_client.emit_cost = MagicMock()
        
        # Mock successful response
        mock_response = MagicMock(spec=Response)
        mock_response.json.return_value = {
            "match_found": True,
            "match_confidence": 0.9,
            "business_data": {"emails": ["test@example.com"]}
        }
        mock_response.status_code = 200
        mock_httpx_client.post.return_value = mock_response
        
        dataaxle_client._client = mock_httpx_client
        
        # Make request
        await dataaxle_client.match_business({
            "name": "Test",
            "lead_id": "lead_456"
        })
        
        # Verify cost emission
        dataaxle_client.emit_cost.assert_called_once_with(
            lead_id="lead_456",
            cost_usd=0.05
        )