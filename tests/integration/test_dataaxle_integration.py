"""
Integration tests for DataAxle provider
Tests the full integration with stub server and cost tracking
"""
import pytest
from httpx import AsyncClient

from d0_gateway.providers.dataaxle import DataAxleClient
from database.models import APICost
from database.session import SessionLocal


@pytest.mark.integration
class TestDataAxleIntegration:
    """Integration tests for DataAxle provider"""

    @pytest.fixture
    async def dataaxle_client(self, settings_override):
        """Create DataAxle client for testing"""
        settings_override(
            use_stubs=True,
            stub_base_url="http://localhost:5010",
            data_axle_api_key="test-key",
            data_axle_rate_limit_per_min=200,
        )
        
        # Import after settings override
        from d0_gateway.providers.dataaxle import DataAxleClient
        
        client = DataAxleClient(api_key="test-key")
        yield client
        # Cleanup
        if hasattr(client, 'client'):
            await client.client.aclose()

    @pytest.fixture
    def test_business_data(self):
        """Sample business data for testing"""
        return {
            "name": "Test Restaurant LLC",
            "address": "123 Main St",
            "city": "San Francisco",
            "state": "CA",
            "zip_code": "94105",
            "lead_id": "test-lead-123",
        }

    @pytest.mark.asyncio
    async def test_match_business_success(self, dataaxle_client, test_business_data, stub_server):
        """Test successful business match with stub server"""
        # Make the request
        result = await dataaxle_client.match_business(test_business_data)
        
        # Verify response
        assert result is not None
        assert result["primary_email"] == "contact@restaurant.com"
        assert result["primary_phone"] == "+14155551234"
        assert result["employee_count"] == 25
        assert result["annual_revenue"] == 2500000
        assert result["years_in_business"] == 10
        assert result["data_axle_id"] == "DA123456"
        assert len(result["sic_codes"]) > 0
        assert len(result["naics_codes"]) > 0

    @pytest.mark.asyncio
    async def test_match_business_no_match(self, dataaxle_client, stub_server):
        """Test business match with no results"""
        business_data = {
            "name": "Nonexistent Business XYZ",
            "city": "Nowhere",
            "state": "XX",
        }
        
        result = await dataaxle_client.match_business(business_data)
        
        # Should return None for no match
        assert result is None

    @pytest.mark.asyncio 
    async def test_cost_tracking(self, dataaxle_client, test_business_data, stub_server, db_session):
        """Test that costs are properly tracked"""
        # Clear any existing costs
        db_session.query(APICost).delete()
        db_session.commit()
        
        # Make the request
        await dataaxle_client.match_business(test_business_data)
        
        # Check cost was recorded
        costs = db_session.query(APICost).filter_by(
            provider="dataaxle",
            lead_id=test_business_data["lead_id"]
        ).all()
        
        assert len(costs) == 1
        assert costs[0].cost_usd == 0.05
        assert costs[0].operation == "match_business"
        assert costs[0].metadata["has_email"] is True
        assert costs[0].metadata["has_phone"] is True

    @pytest.mark.asyncio
    async def test_enrich_by_domain(self, dataaxle_client, stub_server):
        """Test domain enrichment functionality"""
        result = await dataaxle_client.enrich("testcompany.com")
        
        assert result is not None
        assert result["email"] == "info@testcompany.com"
        assert result["phone"] == "+15555551234"
        assert result["employee_count"] == 50
        assert result["annual_revenue"] == 5000000

    @pytest.mark.asyncio
    async def test_rate_limiting(self, dataaxle_client):
        """Test rate limiting configuration"""
        rate_limits = dataaxle_client.get_rate_limit()
        
        assert rate_limits["requests_per_minute"] == 200
        assert rate_limits["requests_per_hour"] == 12000

    @pytest.mark.asyncio
    async def test_error_handling(self, dataaxle_client, test_business_data, stub_server):
        """Test error handling for various scenarios"""
        from d0_gateway.exceptions import APIProviderError, ValidationError
        
        # Test missing business name
        invalid_data = test_business_data.copy()
        del invalid_data["name"]
        
        with pytest.raises(ValidationError, match="Business name is required"):
            await dataaxle_client.match_business(invalid_data)
        
        # Test API error by using special trigger name
        error_data = test_business_data.copy()
        error_data["name"] = "TRIGGER_ERROR"
        
        with pytest.raises(APIProviderError):
            await dataaxle_client.match_business(error_data)

    @pytest.mark.asyncio
    async def test_response_transformation(self, dataaxle_client, stub_server):
        """Test various response formats are handled correctly"""
        # Test with minimal data
        minimal_data = {
            "name": "Minimal Business",
            "city": "San Francisco",
            "state": "CA",
        }
        
        result = await dataaxle_client.match_business(minimal_data)
        
        # Should handle missing fields gracefully
        assert result is not None
        assert isinstance(result["emails"], list)
        assert isinstance(result["phones"], list)
        assert isinstance(result["sic_codes"], list)
        assert isinstance(result["naics_codes"], list)

    @pytest.mark.asyncio
    async def test_api_key_verification(self, dataaxle_client, stub_server):
        """Test API key verification"""
        # Valid key should return True
        is_valid = await dataaxle_client.verify_api_key()
        assert is_valid is True
        
        # Test with invalid key
        from d0_gateway.exceptions import AuthenticationError
        
        dataaxle_client.api_key = "invalid-key"
        with pytest.raises(AuthenticationError):
            await dataaxle_client.verify_api_key()

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, dataaxle_client, test_business_data, stub_server):
        """Test handling of concurrent requests"""
        import asyncio
        
        # Create multiple concurrent requests
        tasks = []
        for i in range(5):
            data = test_business_data.copy()
            data["name"] = f"Test Business {i}"
            data["lead_id"] = f"lead-{i}"
            tasks.append(dataaxle_client.match_business(data))
        
        # Execute concurrently
        results = await asyncio.gather(*tasks)
        
        # All should succeed
        assert len(results) == 5
        assert all(r is not None for r in results)
        assert all(r["primary_email"] is not None for r in results)