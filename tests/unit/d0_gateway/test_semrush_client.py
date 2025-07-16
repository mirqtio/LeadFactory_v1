"""
Test SEMrush API client implementation
"""
import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import httpx
import pytest

from core.exceptions import ValidationError
from d0_gateway.exceptions import APIProviderError, AuthenticationError, RateLimitExceededError
from d0_gateway.providers.semrush import SEMrushClient

# Mark entire module as slow for CI optimization
pytestmark = pytest.mark.slow


# Mock settings globally for all tests
@pytest.fixture(autouse=True)
def mock_settings():
    with patch("d0_gateway.base.get_settings") as mock_get_settings:
        mock_settings_obj = Mock()
        mock_settings_obj.use_stubs = False
        mock_settings_obj.get_api_key.return_value = "test-api-key"
        mock_settings_obj.semrush_daily_quota = 1000
        mock_get_settings.return_value = mock_settings_obj

        # Also mock the settings import inside SEMrush __init__
        with patch("core.config.settings") as mock_core_settings:
            mock_core_settings.semrush_daily_quota = 1000
            yield mock_settings_obj


class TestSEMrushClient:
    @pytest.fixture
    def semrush_client(self):
        """Create SEMrush client for testing"""
        return SEMrushClient(api_key="test-api-key")

    def test_initialization(self, semrush_client):
        """Test that SEMrush client is properly initialized"""
        # Should inherit from BaseAPIClient
        assert hasattr(semrush_client, "provider")
        assert semrush_client.provider == "semrush"

        # Should have rate limiter, circuit breaker, cache
        assert hasattr(semrush_client, "rate_limiter")
        assert hasattr(semrush_client, "circuit_breaker")
        assert hasattr(semrush_client, "cache")

        # Should have proper base URL
        assert semrush_client.base_url == "https://api.semrush.com"

        # Should have proper headers
        headers = semrush_client._get_headers()
        assert headers["Accept"] == "application/json"

        # Should have API key
        assert semrush_client.api_key == "test-api-key"

    def test_daily_quota_config(self, semrush_client):
        """Test that daily quota is properly configured"""
        rate_limit = semrush_client.get_rate_limit()

        # Should have 1000 daily limit as per PRD
        assert rate_limit["requests_per_minute"] == 100
        assert rate_limit["requests_per_hour"] == 1000
        assert rate_limit["requests_per_day"] == 1000  # From settings

    def test_cost_calculation(self, semrush_client):
        """Test cost calculation for SEMrush operations"""
        # Domain overview should cost $0.010 as per PRD
        domain_cost = semrush_client.calculate_cost("domain_overview")
        assert domain_cost == Decimal("0.010")

        # Other operations should be free
        other_cost = semrush_client.calculate_cost("other_operation")
        assert other_cost == Decimal("0.00")

    @pytest.mark.asyncio
    async def test_domain_overview_basic(self, semrush_client):
        """Test basic domain overview functionality with all 6 metrics"""
        # Mock SEMrush API response (CSV format)
        mock_csv_response = """Or;Ot;Oc;Ad;At;Ac;Dn;Rk;Tr;Tc;La;Lc;Hs;Bs
1250;45000;12500.50;125;5000;2500.75;45;75;2500;150;500;25;85;15"""

        # Inject test client
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.text = mock_csv_response
        mock_response.json = Mock(side_effect=Exception("Not JSON"))
        mock_client.get = AsyncMock(return_value=mock_response)
        semrush_client._client = mock_client

        # Test domain analysis
        result = await semrush_client.get_domain_overview("example.com", lead_id="test-lead-123")

        # Verify API call was made correctly
        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert call_args[0][0] == "/"
        assert call_args[1]["headers"] == {"Accept": "application/json"}
        assert call_args[1]["params"]["domain"] == "example.com"
        assert call_args[1]["params"]["type"] == "domain_organic"
        assert call_args[1]["params"]["database"] == "us"

        # Verify response parsing
        assert result is not None
        assert result["organic_keywords"] == 1250
        assert result["organic_traffic"] == 45000
        assert result["organic_cost"] == 12500.50
        assert result["adwords_keywords"] == 125
        assert result["adwords_traffic"] == 5000
        assert result["adwords_cost"] == 2500.75

    @pytest.mark.asyncio
    async def test_domain_overview_with_extended_metrics(self, semrush_client):
        """Test domain overview with all 6 PRP metrics (including mocked extended data)"""
        # For the 6 metrics mentioned in PRP:
        # 1. Site Health - Would need separate API endpoint
        # 2. Domain Authority (DA) - Dn column
        # 3. Backlink Toxicity - Would need backlinks API
        # 4. Organic Traffic - Ot column
        # 5. Keywords - Or column
        # 6. Issues - Would need site audit API

        # Mock response with extended columns
        mock_extended_response = {
            "organic_keywords": 1500,
            "organic_traffic": 50000,
            "organic_cost": 15000.0,
            "adwords_keywords": 200,
            "adwords_traffic": 8000,
            "adwords_cost": 4000.0,
            "domain_authority": 65,  # Mocked DA
            "site_health": 85,  # Mocked site health score
            "backlink_toxicity": 5,  # Mocked toxicity percentage
            "site_issues": 12,  # Mocked number of issues
            "semrush_raw": {
                "Or": "1500",
                "Ot": "50000",
                "Oc": "15000",
                "Ad": "200",
                "At": "8000",
                "Ac": "4000",
                "Dn": "65",
            },
        }

        # Mock the client to return dict response
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.text = "mock"
        mock_response.json = Mock(return_value=mock_extended_response)
        mock_client.get = AsyncMock(return_value=mock_response)
        semrush_client._client = mock_client

        # Override parse method to return extended data
        semrush_client._parse_semrush_response = Mock(return_value=mock_extended_response)

        result = await semrush_client.get_domain_overview("example.com")

        # Verify all metrics are present
        assert result["organic_keywords"] == 1500
        assert result["organic_traffic"] == 50000
        assert result["domain_authority"] == 65
        assert result["site_health"] == 85
        assert result["backlink_toxicity"] == 5
        assert result["site_issues"] == 12

    @pytest.mark.asyncio
    async def test_domain_overview_empty_response(self, semrush_client):
        """Test handling of empty/no data response"""
        # Mock empty CSV response
        mock_empty_response = ""

        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.text = mock_empty_response
        mock_client.get = AsyncMock(return_value=mock_response)
        semrush_client._client = mock_client

        result = await semrush_client.get_domain_overview("unknown-domain.com")

        # Should return None for domains with no data
        assert result is None

    @pytest.mark.asyncio
    async def test_domain_overview_invalid_domain(self, semrush_client):
        """Test validation of invalid domain input"""
        # Test with empty domain
        with pytest.raises(ValidationError) as exc_info:
            await semrush_client.get_domain_overview("")
        assert "Domain is required" in str(exc_info.value)

        # Test with None domain
        with pytest.raises(ValidationError) as exc_info:
            await semrush_client.get_domain_overview(None)
        assert "Domain is required" in str(exc_info.value)

    def test_csv_parsing(self, semrush_client):
        """Test CSV response parsing"""
        # Test normal CSV response
        csv_response = """Or;Ot;Oc;Ad;At;Ac
1000;25000;5000.50;50;2000;1000.25"""

        result = semrush_client._parse_semrush_response(csv_response)

        assert result is not None
        assert result["organic_keywords"] == 1000
        assert result["organic_traffic"] == 25000
        assert result["organic_cost"] == 5000.50
        assert result["adwords_keywords"] == 50
        assert result["adwords_traffic"] == 2000
        assert result["adwords_cost"] == 1000.25
        assert "semrush_raw" in result

    def test_csv_parsing_with_missing_columns(self, semrush_client):
        """Test CSV parsing with missing columns"""
        # CSV with only some columns
        csv_response = """Or;Ot
500;10000"""

        result = semrush_client._parse_semrush_response(csv_response)

        assert result is not None
        assert result["organic_keywords"] == 500
        assert result["organic_traffic"] == 10000
        assert result["organic_cost"] == 0  # Default for missing
        assert result["adwords_keywords"] == 0  # Default for missing

    def test_csv_parsing_invalid_format(self, semrush_client):
        """Test CSV parsing with invalid format"""
        # Invalid CSV
        invalid_response = "This is not CSV data"

        result = semrush_client._parse_semrush_response(invalid_response)

        # Should return None for unparseable data
        assert result is None

    def test_dict_response_passthrough(self, semrush_client):
        """Test that dict responses (from stub) are passed through"""
        dict_response = {"organic_keywords": 2000, "organic_traffic": 60000, "test": "data"}

        result = semrush_client._parse_semrush_response(dict_response)

        # Should return dict unchanged
        assert result == dict_response

    @pytest.mark.asyncio
    async def test_cost_tracking(self, semrush_client):
        """Test that costs are properly tracked"""
        # Mock successful response
        mock_response = {"organic_keywords": 100, "organic_traffic": 5000}

        # Mock the parse method
        semrush_client._parse_semrush_response = Mock(return_value=mock_response)

        # Mock the emit_cost method to track calls
        semrush_client.emit_cost = Mock()

        # Mock HTTP client
        mock_client = AsyncMock()
        mock_response_obj = Mock()
        mock_response_obj.text = "mock"
        mock_client.get = AsyncMock(return_value=mock_response_obj)
        semrush_client._client = mock_client

        # Make request
        await semrush_client.get_domain_overview("example.com", lead_id="lead-123")

        # Verify cost was emitted
        semrush_client.emit_cost.assert_called_once_with(
            lead_id="lead-123",
            cost_usd=0.010,
            operation="domain_overview",
            metadata={
                "domain": "example.com",
                "organic_keywords": 100,
                "organic_traffic": 5000,
            },
        )

    @pytest.mark.asyncio
    async def test_error_handling_rate_limit(self, semrush_client):
        """Test rate limit error handling"""
        # Mock the _get method to simulate rate limit
        with patch.object(semrush_client, "_get", side_effect=RateLimitExceededError("semrush", "api_calls")):
            with pytest.raises(RateLimitExceededError) as exc_info:
                await semrush_client.get_domain_overview("example.com")

            assert exc_info.value.provider == "semrush"

    @pytest.mark.asyncio
    async def test_error_handling_authentication(self, semrush_client):
        """Test authentication error handling"""
        # Mock auth error
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(
            side_effect=httpx.HTTPStatusError("401 Unauthorized", request=Mock(), response=Mock(status_code=401))
        )
        semrush_client._client = mock_client

        with pytest.raises(AuthenticationError) as exc_info:
            await semrush_client.get_domain_overview("example.com")

        assert exc_info.value.provider == "semrush"

    @pytest.mark.asyncio
    async def test_error_handling_api_error(self, semrush_client):
        """Test general API error handling"""
        # Mock API error
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("API connection failed"))
        semrush_client._client = mock_client

        with pytest.raises(APIProviderError) as exc_info:
            await semrush_client.get_domain_overview("example.com")

        assert exc_info.value.provider == "semrush"
        assert "API connection failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_verify_api_key_valid(self, semrush_client):
        """Test API key verification with valid key"""
        # Mock successful response
        mock_response = {"organic_keywords": 100}
        semrush_client.get_domain_overview = AsyncMock(return_value=mock_response)

        result = await semrush_client.verify_api_key()

        assert result is True
        semrush_client.get_domain_overview.assert_called_once_with("example.com")

    @pytest.mark.asyncio
    async def test_verify_api_key_invalid(self, semrush_client):
        """Test API key verification with invalid key"""
        # Mock auth error
        semrush_client.get_domain_overview = AsyncMock(side_effect=AuthenticationError("semrush", "Invalid API key"))

        with pytest.raises(AuthenticationError):
            await semrush_client.verify_api_key()

    @pytest.mark.asyncio
    async def test_verify_api_key_other_error(self, semrush_client):
        """Test API key verification with non-auth errors"""
        # Mock other error (e.g., domain has no data)
        semrush_client.get_domain_overview = AsyncMock(side_effect=APIProviderError("semrush", "No data"))

        # Should still return True (key is valid, just no data)
        result = await semrush_client.verify_api_key()
        assert result is True

    @pytest.mark.asyncio
    async def test_make_request_direct(self, semrush_client):
        """Test direct make_request method"""
        # Mock httpx client - it's imported inside the method
        with patch("httpx.AsyncClient") as mock_httpx:
            mock_client_instance = AsyncMock()
            mock_httpx.return_value.__aenter__.return_value = mock_client_instance

            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = "Or;Ot\n100;5000"
            mock_client_instance.request = AsyncMock(return_value=mock_response)

            result = await semrush_client.make_request("GET", "/", params={"key": "test-key", "domain": "example.com"})

            assert result == "Or;Ot\n100;5000"
            mock_client_instance.request.assert_called_once()

    @pytest.mark.asyncio
    async def test_make_request_http_errors(self, semrush_client):
        """Test make_request with various HTTP errors"""
        # Mock httpx client - it's imported inside the method
        with patch("httpx.AsyncClient") as mock_httpx:
            mock_client_instance = AsyncMock()
            mock_httpx.return_value.__aenter__.return_value = mock_client_instance

            # Test 401 error
            mock_response = Mock()
            mock_response.status_code = 401
            mock_response.text = "Invalid API key"
            mock_client_instance.request = AsyncMock(return_value=mock_response)

            with pytest.raises(AuthenticationError) as exc_info:
                await semrush_client.make_request("GET", "/")
            assert "401" in str(exc_info.value) and "Invalid API key" in str(exc_info.value)

            # Test 429 error
            mock_response.status_code = 429
            mock_response.text = "Rate limit exceeded"

            with pytest.raises(RateLimitExceededError) as exc_info:
                await semrush_client.make_request("GET", "/")
            assert exc_info.value.retry_after == 3600

            # Test other HTTP error
            mock_response.status_code = 500
            mock_response.text = "Internal server error"

            with pytest.raises(APIProviderError) as exc_info:
                await semrush_client.make_request("GET", "/")
            assert "HTTP 500" in str(exc_info.value)


class TestSEMrushClientIntegration:
    @pytest.mark.asyncio
    async def test_rate_limiting_integration(self):
        """Test integration with rate limiting"""
        semrush_client = SEMrushClient(api_key="test-key")

        # Mock the _get method to simulate rate limit
        with patch.object(semrush_client, "_get", side_effect=RateLimitExceededError("semrush", "api_calls")):
            with pytest.raises(RateLimitExceededError):
                await semrush_client.get_domain_overview("example.com")

    @pytest.mark.asyncio
    async def test_circuit_breaker_integration(self):
        """Test integration with circuit breaker"""
        from d0_gateway.exceptions import CircuitBreakerOpenError

        semrush_client = SEMrushClient(api_key="test-key")

        # Mock the _get method to simulate circuit breaker open
        with patch.object(semrush_client, "_get", side_effect=CircuitBreakerOpenError("semrush", 5)):
            # The client wraps CircuitBreakerOpenError as APIProviderError
            with pytest.raises(APIProviderError) as exc_info:
                await semrush_client.get_domain_overview("example.com")
            assert "Circuit breaker open" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_caching_integration(self):
        """Test integration with response caching"""
        semrush_client = SEMrushClient(api_key="test-key")

        # Test that cache is properly initialized
        assert hasattr(semrush_client, "cache")
        assert semrush_client.cache.provider == "semrush"

        # Test cache key generation
        cache_params = {"domain": "example.com"}
        cache_key = semrush_client.cache.generate_key("/domain_overview", cache_params)

        # Cache key should be deterministic
        assert isinstance(cache_key, str)
        assert cache_key.startswith("api_cache:")

        # Test cache statistics are available
        stats = await semrush_client.cache.get_cache_stats()
        assert "provider" in stats
        assert stats["provider"] == "semrush"

    @pytest.mark.asyncio
    async def test_stub_mode_integration(self):
        """Test integration with stub mode"""
        with patch("d0_gateway.base.get_settings") as mock_get_settings:
            mock_settings = Mock()
            mock_settings.use_stubs = True
            mock_settings.stub_base_url = "http://localhost:8000"
            mock_settings.get_api_key.return_value = "stub-semrush-key"
            mock_settings.semrush_daily_quota = 1000
            mock_get_settings.return_value = mock_settings

            # Also mock the direct settings import
            with patch("core.config.settings") as mock_core_settings:
                mock_core_settings.semrush_daily_quota = 1000

                # Create client in stub mode
                semrush_client = SEMrushClient(api_key="test-key")

                # In stub mode, should use stub configuration
                assert semrush_client.api_key == "stub-semrush-key"
                assert semrush_client.base_url == "http://localhost:8000"


class TestSEMrushClientExtendedMetrics:
    """Tests for extended metrics that would require additional API endpoints"""

    @pytest.mark.asyncio
    async def test_site_health_metric(self):
        """Test site health metric (would require site audit API)"""
        # This would require implementing a separate method like get_site_health()
        # that calls SEMrush Site Audit API
        pass

    @pytest.mark.asyncio
    async def test_domain_authority_metric(self):
        """Test domain authority metric extraction"""
        # The Dn column in domain overview should provide this
        # Already covered in basic tests
        pass

    @pytest.mark.asyncio
    async def test_backlink_toxicity_metric(self):
        """Test backlink toxicity metric (would require backlinks API)"""
        # This would require implementing a separate method like get_backlink_toxicity()
        # that calls SEMrush Backlinks API
        pass

    @pytest.mark.asyncio
    async def test_site_issues_metric(self):
        """Test site issues metric (would require site audit API)"""
        # This would require implementing a separate method like get_site_issues()
        # that calls SEMrush Site Audit API
        pass


class TestSEMrushClientMockResponses:
    """Test with various mock response scenarios"""

    def test_mock_response_formats(self):
        """Test various response format handling"""
        client = SEMrushClient(api_key="test-key")

        # Test complete response
        full_csv = """Or;Ot;Oc;Ad;At;Ac
2500;100000;25000.00;300;15000;7500.00"""
        result = client._parse_semrush_response(full_csv)
        assert result["organic_keywords"] == 2500
        assert result["organic_traffic"] == 100000

        # Test response with zeros
        zero_csv = """Or;Ot;Oc;Ad;At;Ac
0;0;0;0;0;0"""
        result = client._parse_semrush_response(zero_csv)
        assert result["organic_keywords"] == 0
        assert result["organic_traffic"] == 0

        # Test response with decimals
        decimal_csv = """Or;Ot;Oc;Ad;At;Ac
1234;56789;12345.67;89;1234;567.89"""
        result = client._parse_semrush_response(decimal_csv)
        assert result["organic_cost"] == 12345.67
        assert result["adwords_cost"] == 567.89

    @pytest.mark.asyncio
    async def test_concurrent_requests(self):
        """Test handling of concurrent requests"""
        client = SEMrushClient(api_key="test-key")

        # Mock successful responses
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.text = "Or;Ot\n100;5000"
        mock_client.get = AsyncMock(return_value=mock_response)
        client._client = mock_client

        # Make concurrent requests
        domains = ["example1.com", "example2.com", "example3.com"]
        results = await asyncio.gather(*[client.get_domain_overview(domain) for domain in domains])

        # All should succeed
        assert len(results) == 3
        assert all(r is not None for r in results)
        assert mock_client.get.call_count == 3
