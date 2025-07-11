"""
Tests for Hunter.io client - Phase 0.5 Task GW-03
"""
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient, Response

from d0_gateway.exceptions import (
    APIProviderError,
    AuthenticationError,
    RateLimitExceededError,
)
from core.exceptions import ValidationError
from d0_gateway.providers.hunter import HunterClient

# Mark entire module as xfail for Phase 0.5
pytestmark = pytest.mark.xfail(reason="Phase 0.5 feature", strict=False)


@pytest.fixture
def mock_settings():
    """Mock settings for testing"""
    settings = MagicMock()
    settings.hunter_rate_limit_per_min = 30
    settings.use_stubs = False  # Disable stub mode in tests
    settings.get_api_key = MagicMock(return_value="test-key")
    return settings


@pytest.fixture
def hunter_client(mock_settings):
    """Create Hunter client for testing"""
    with patch("core.config.settings", mock_settings), patch(
        "core.config.get_settings", return_value=mock_settings
    ), patch("d0_gateway.base.get_settings", return_value=mock_settings), patch(
        "d0_gateway.base.RateLimiter"
    ), patch(
        "d0_gateway.base.CircuitBreaker"
    ), patch(
        "d0_gateway.base.ResponseCache"
    ), patch(
        "d0_gateway.base.GatewayMetrics"
    ):
        return HunterClient(api_key="test-key")


@pytest.fixture
def mock_httpx_client():
    """Mock httpx AsyncClient"""
    return AsyncMock(spec=AsyncClient)


class TestHunterClient:
    """Test Hunter.io client functionality"""

    def test_initialization(self, mock_settings):
        """Test client initialization"""
        with patch("core.config.settings", mock_settings), patch(
            "core.config.get_settings", return_value=mock_settings
        ), patch("d0_gateway.base.get_settings", return_value=mock_settings), patch(
            "d0_gateway.base.RateLimiter"
        ), patch(
            "d0_gateway.base.CircuitBreaker"
        ), patch(
            "d0_gateway.base.ResponseCache"
        ), patch(
            "d0_gateway.base.GatewayMetrics"
        ):
            client = HunterClient(api_key="test-key", base_url="https://test.com")

            assert client.api_key == "test-key"
            assert client.provider == "hunter"
            assert client._rate_limit == 30
            assert client.base_url == "https://test.com"

    def test_initialization_with_defaults(self, mock_settings):
        """Test client initialization with default values"""
        with patch("core.config.settings", mock_settings), patch(
            "core.config.get_settings", return_value=mock_settings
        ), patch("d0_gateway.base.get_settings", return_value=mock_settings), patch(
            "d0_gateway.base.RateLimiter"
        ), patch(
            "d0_gateway.base.CircuitBreaker"
        ), patch(
            "d0_gateway.base.ResponseCache"
        ), patch(
            "d0_gateway.base.GatewayMetrics"
        ):
            client = HunterClient(api_key="test-key")

            assert client.base_url == "https://api.hunter.io/v2"
            assert client.timeout == 30
            assert client.max_retries == 3

    def test_get_headers(self, hunter_client):
        """Test header generation"""
        headers = hunter_client._get_headers()

        assert headers["Accept"] == "application/json"

    def test_get_rate_limit(self, hunter_client):
        """Test rate limit configuration"""
        rate_limits = hunter_client.get_rate_limit()

        assert rate_limits["requests_per_minute"] == 30
        assert rate_limits["requests_per_hour"] == 1800
        assert rate_limits["requests_per_day"] == 25  # Free tier limit

    def test_calculate_cost(self, hunter_client):
        """Test cost calculation"""
        cost = hunter_client.calculate_cost("find_email")
        assert cost == Decimal("0.01")  # $0.01 per email

        cost = hunter_client.calculate_cost("other_operation")
        assert cost == Decimal("0.00")

    @pytest.mark.asyncio
    async def test_find_email_success_with_domain(
        self, hunter_client, mock_httpx_client
    ):
        """Test successful email finding with domain"""
        # Mock response
        mock_response = MagicMock(spec=Response)
        mock_response.json.return_value = {
            "data": {
                "email": "john.doe@example.com",
                "score": 95,
                "domain": "example.com",
                "first_name": "John",
                "last_name": "Doe",
                "position": "CEO",
                "twitter": "https://twitter.com/johndoe",
                "linkedin_url": "https://linkedin.com/in/john-doe",
                "sources": [
                    {
                        "domain": "example.com",
                        "uri": "https://example.com/about",
                        "extracted_on": "2024-01-15",
                        "still_on_page": True,
                    }
                ],
            }
        }
        mock_response.status_code = 200
        mock_httpx_client.get.return_value = mock_response

        # Patch the client's HTTP client
        hunter_client._client = mock_httpx_client

        # Test company data
        company_data = {
            "domain": "example.com",
            "first_name": "John",
            "last_name": "Doe",
            "lead_id": "lead_123",
        }

        result = await hunter_client.find_email(company_data)

        # Verify request
        mock_httpx_client.get.assert_called_once()
        call_args = mock_httpx_client.get.call_args
        assert call_args[0][0] == "/email-finder"

        params = call_args[1]["params"]
        assert params["api_key"] == "test-key"
        assert params["domain"] == "example.com"
        assert params["first_name"] == "John"
        assert params["last_name"] == "Doe"

        # Verify response transformation
        assert result["email"] == "john.doe@example.com"
        assert result["confidence"] == 95
        assert result["first_name"] == "John"
        assert result["last_name"] == "Doe"
        assert result["position"] == "CEO"
        assert result["twitter"] == "https://twitter.com/johndoe"
        assert result["linkedin"] == "https://linkedin.com/in/john-doe"
        assert len(result["sources"]) == 1

    @pytest.mark.asyncio
    async def test_find_email_success_with_company(
        self, hunter_client, mock_httpx_client
    ):
        """Test successful email finding with company name"""
        # Mock response
        mock_response = MagicMock(spec=Response)
        mock_response.json.return_value = {
            "data": {
                "email": "contact@acmecorp.com",
                "score": 85,
                "domain": "acmecorp.com",
            }
        }
        mock_response.status_code = 200
        mock_httpx_client.get.return_value = mock_response

        hunter_client._client = mock_httpx_client

        company_data = {"company": "Acme Corp", "lead_id": "lead_456"}

        result = await hunter_client.find_email(company_data)

        # Verify request
        call_args = mock_httpx_client.get.call_args
        params = call_args[1]["params"]
        assert params["company"] == "Acme Corp"
        assert "domain" not in params

        # Verify response
        assert result["email"] == "contact@acmecorp.com"
        assert result["confidence"] == 85

    @pytest.mark.asyncio
    async def test_find_email_no_result(self, hunter_client, mock_httpx_client):
        """Test email finding with no results"""
        # Mock response with no email
        mock_response = MagicMock(spec=Response)
        mock_response.json.return_value = {
            "data": {
                "email": None,
                "score": 0,
            }
        }
        mock_response.status_code = 200
        mock_httpx_client.get.return_value = mock_response

        hunter_client._client = mock_httpx_client

        company_data = {"domain": "unknown.com"}
        result = await hunter_client.find_email(company_data)

        assert result is None

    @pytest.mark.asyncio
    async def test_find_email_missing_required_fields(self, hunter_client):
        """Test validation error for missing required fields"""
        company_data = {"first_name": "John"}

        with pytest.raises(
            ValidationError, match="Either domain or company name is required"
        ):
            await hunter_client.find_email(company_data)

    @pytest.mark.asyncio
    async def test_find_email_rate_limit(self, hunter_client, mock_httpx_client):
        """Test rate limit error handling"""
        # Mock 429 response
        mock_httpx_client.get.side_effect = Exception("429 Rate limit exceeded")

        hunter_client._client = mock_httpx_client

        with pytest.raises(RateLimitExceededError):
            await hunter_client.find_email({"domain": "test.com"})

    @pytest.mark.asyncio
    async def test_find_email_auth_error(self, hunter_client, mock_httpx_client):
        """Test authentication error handling"""
        # Mock 401 response
        mock_httpx_client.get.side_effect = Exception("401 Unauthorized")

        hunter_client._client = mock_httpx_client

        with pytest.raises(AuthenticationError):
            await hunter_client.find_email({"company": "Test"})

    @pytest.mark.asyncio
    async def test_find_email_api_error(self, hunter_client, mock_httpx_client):
        """Test general API error handling"""
        # Mock generic error
        mock_httpx_client.get.side_effect = Exception("Connection error")

        hunter_client._client = mock_httpx_client

        with pytest.raises(APIProviderError):
            await hunter_client.find_email({"domain": "test.com"})

    def test_transform_response_minimal(self, hunter_client):
        """Test response transformation with minimal data"""
        data = {
            "email": "test@example.com",
            "score": 75,
        }

        result = hunter_client._transform_response(data)

        assert result["email"] == "test@example.com"
        assert result["confidence"] == 75
        assert result["first_name"] is None
        assert result["last_name"] is None
        assert result["position"] is None
        assert result["sources"] == []

    def test_transform_response_full(self, hunter_client):
        """Test response transformation with full data"""
        data = {
            "email": "jane.smith@company.com",
            "score": 98,
            "first_name": "Jane",
            "last_name": "Smith",
            "position": "CTO",
            "twitter": "https://twitter.com/janesmith",
            "linkedin_url": "https://linkedin.com/in/jane-smith",
            "domain": "company.com",
            "sources": [{"uri": "https://company.com/team"}],
        }

        result = hunter_client._transform_response(data)

        assert result["email"] == "jane.smith@company.com"
        assert result["confidence"] == 98
        assert result["first_name"] == "Jane"
        assert result["last_name"] == "Smith"
        assert result["position"] == "CTO"
        assert result["twitter"] == "https://twitter.com/janesmith"
        assert result["linkedin"] == "https://linkedin.com/in/jane-smith"
        assert result["hunter_domain"] == "company.com"
        assert len(result["sources"]) == 1

    @pytest.mark.asyncio
    async def test_verify_api_key_success(self, hunter_client, mock_httpx_client):
        """Test API key verification success"""
        # Mock response
        mock_response = MagicMock(spec=Response)
        mock_response.json.return_value = {
            "data": {
                "email": "user@example.com",
                "plan_name": "Free",
            }
        }
        mock_response.status_code = 200
        mock_httpx_client.get.return_value = mock_response

        hunter_client._client = mock_httpx_client

        result = await hunter_client.verify_api_key()

        assert result is True
        mock_httpx_client.get.assert_called_with(
            "/account",
            headers=hunter_client._get_headers(),
            params={"api_key": "test-key"},
        )

    @pytest.mark.asyncio
    async def test_verify_api_key_invalid(self, hunter_client, mock_httpx_client):
        """Test API key verification with invalid key"""
        # Mock 401 response
        mock_httpx_client.get.side_effect = Exception("401 Unauthorized")

        hunter_client._client = mock_httpx_client

        with pytest.raises(AuthenticationError):
            await hunter_client.verify_api_key()

    @pytest.mark.asyncio
    async def test_cost_emission(self, hunter_client, mock_httpx_client):
        """Test cost emission for successful email find"""
        # Mock emit_cost method
        hunter_client.emit_cost = MagicMock()

        # Mock successful response
        mock_response = MagicMock(spec=Response)
        mock_response.json.return_value = {
            "data": {
                "email": "test@example.com",
                "score": 90,
            }
        }
        mock_response.status_code = 200
        mock_httpx_client.get.return_value = mock_response

        hunter_client._client = mock_httpx_client

        # Make request
        await hunter_client.find_email({"domain": "example.com", "lead_id": "lead_789"})

        # Verify cost emission
        hunter_client.emit_cost.assert_called_once_with(
            lead_id="lead_789",
            cost_usd=0.01,
            operation="find_email",
            metadata={"confidence": 90, "email": "test@example.com", "domain": None},
        )
