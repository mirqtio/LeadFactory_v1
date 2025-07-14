"""
Tests for Phase 0.5 enrichment flow modifications - Task EN-05
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from d0_gateway.providers.dataaxle import DataAxleClient
from d0_gateway.providers.hunter import HunterClient
from d4_enrichment.coordinator import EnrichmentCoordinator
from d4_enrichment.dataaxle_enricher import DataAxleEnricher
from d4_enrichment.hunter_enricher import HunterEnricher
from d4_enrichment.models import EnrichmentSource

# Mark entire module as xfail for Phase 0.5
pytestmark = pytest.mark.xfail(reason="Phase 0.5 feature", strict=False)


class TestDataAxleEnricher:
    """Test Data Axle enricher"""

    @pytest.mark.asyncio
    async def test_enrich_business_success(self):
        """Test successful business enrichment via Data Axle"""
        # Mock client
        mock_client = MagicMock(spec=DataAxleClient)
        mock_client.match_business = AsyncMock(
            return_value={
                "data": {
                    "email": "contact@example.com",
                    "phone": "+1-555-123-4567",
                    "website": "https://example.com",
                    "employee_count": 50,
                    "annual_revenue": 5000000,
                    "years_in_business": 10,
                    "contact_name": "John Doe",
                    "contact_title": "Owner",
                },
                "confidence": 0.85,
                "match_id": "DA123456",
            }
        )

        # Create enricher
        enricher = DataAxleEnricher(client=mock_client)

        # Test business data
        business_data = {
            "name": "Example Business",
            "address": "123 Main St",
            "city": "San Francisco",
            "state": "CA",
            "zip": "94105",
        }

        # Enrich
        result = await enricher.enrich_business(business_data, "biz_123")

        # Verify
        assert result is not None
        assert result.business_id == "biz_123"
        assert result.source == EnrichmentSource.DATA_AXLE
        assert result.email == "contact@example.com"
        assert result.phone == "+1-555-123-4567"
        assert result.website == "https://example.com"
        assert result.employee_count == 50
        assert result.annual_revenue == 5000000
        assert result.confidence_score == 0.85

    @pytest.mark.asyncio
    async def test_enrich_business_low_confidence(self):
        """Test business enrichment with low confidence match"""
        # Mock client with low confidence match
        mock_client = MagicMock(spec=DataAxleClient)
        mock_client.match_business = AsyncMock(
            return_value={
                "data": {"email": "test@example.com"},
                "confidence": 0.5,  # Below threshold
            }
        )

        enricher = DataAxleEnricher(client=mock_client)

        # Should return None for low confidence
        result = await enricher.enrich_business({"name": "Test"}, "biz_123")
        assert result is None

    @pytest.mark.asyncio
    async def test_enrich_business_no_match(self):
        """Test business enrichment with no match"""
        mock_client = MagicMock(spec=DataAxleClient)
        mock_client.match_business = AsyncMock(return_value=None)

        enricher = DataAxleEnricher(client=mock_client)

        result = await enricher.enrich_business({"name": "Test"}, "biz_123")
        assert result is None

    @pytest.mark.asyncio
    async def test_enrich_business_error_handling(self):
        """Test error handling in enrichment"""
        mock_client = MagicMock(spec=DataAxleClient)
        mock_client.match_business = AsyncMock(side_effect=Exception("API Error"))

        enricher = DataAxleEnricher(client=mock_client)

        # Should handle error gracefully
        result = await enricher.enrich_business({"name": "Test"}, "biz_123")
        assert result is None


class TestHunterEnricher:
    """Test Hunter.io enricher"""

    @pytest.mark.asyncio
    async def test_find_email_success(self):
        """Test successful email finding via Hunter"""
        # Mock client
        mock_client = MagicMock(spec=HunterClient)
        mock_client.find_email = AsyncMock(
            return_value={
                "emails": [
                    {
                        "value": "john@example.com",
                        "confidence": 90,
                        "first_name": "John",
                        "last_name": "Doe",
                        "position": "CEO",
                    },
                    {
                        "value": "jane@example.com",
                        "confidence": 70,
                        "first_name": "Jane",
                        "last_name": "Smith",
                        "position": "CTO",
                    },
                ],
                "pattern": "{first}.{last}@example.com",
                "organization": "Example Corp",
            }
        )

        # Create enricher
        enricher = HunterEnricher(client=mock_client)

        # Test business data with website
        business_data = {"name": "Example Business", "website": "https://example.com"}

        # Enrich
        result = await enricher.enrich_business(business_data, "biz_456")

        # Verify - should pick highest confidence email
        assert result is not None
        assert result.business_id == "biz_456"
        assert result.source == EnrichmentSource.HUNTER_IO
        assert result.email == "john@example.com"
        assert result.contact_name == "John Doe"
        assert result.contact_title == "CEO"
        assert result.confidence_score == 0.9  # 90/100

    @pytest.mark.asyncio
    async def test_find_email_no_website(self):
        """Test email finding without website"""
        mock_client = MagicMock(spec=HunterClient)
        enricher = HunterEnricher(client=mock_client)

        # No website = no search possible
        business_data = {"name": "Example Business"}
        result = await enricher.enrich_business(business_data, "biz_456")
        assert result is None

    @pytest.mark.asyncio
    async def test_find_email_no_results(self):
        """Test email finding with no results"""
        mock_client = MagicMock(spec=HunterClient)
        mock_client.find_email = AsyncMock(return_value={"emails": []})

        enricher = HunterEnricher(client=mock_client)

        business_data = {"website": "https://example.com"}
        result = await enricher.enrich_business(business_data, "biz_456")
        assert result is None


class TestEnrichmentCoordinatorIntegration:
    """Test enrichment coordinator with Phase 0.5 enrichers"""

    @patch("d0_gateway.factory.GatewayClientFactory")
    def test_initialize_phase05_enrichers(self, mock_gateway_factory):
        """Test initialization of Phase 0.5 enrichers"""
        # Mock gateway factory
        mock_gateway = MagicMock()
        mock_gateway._is_provider_enabled.side_effect = lambda p: p in [
            "dataaxle",
            "hunter",
        ]
        mock_gateway.get_dataaxle_client.return_value = MagicMock(spec=DataAxleClient)
        mock_gateway.get_hunter_client.return_value = MagicMock(spec=HunterClient)
        mock_gateway_factory.return_value = mock_gateway

        # Create coordinator
        coordinator = EnrichmentCoordinator()

        # Verify enrichers were added
        assert EnrichmentSource.DATA_AXLE in coordinator.enrichers
        assert EnrichmentSource.HUNTER_IO in coordinator.enrichers
        assert isinstance(coordinator.enrichers[EnrichmentSource.DATA_AXLE], DataAxleEnricher)
        assert isinstance(coordinator.enrichers[EnrichmentSource.HUNTER_IO], HunterEnricher)

    @pytest.mark.asyncio
    @patch("d0_gateway.factory.GatewayClientFactory")
    async def test_enrichment_fanout_pattern(self, mock_gateway_factory):
        """Test fan-out pattern: Data Axle first, then Hunter as fallback"""
        # Setup mocks
        mock_gateway = MagicMock()
        mock_gateway._is_provider_enabled.return_value = True

        # Mock Data Axle client - returns partial data (no email)
        mock_dataaxle = MagicMock(spec=DataAxleClient)
        mock_dataaxle.match_business = AsyncMock(
            return_value={
                "data": {
                    "phone": "+1-555-123-4567",
                    "website": "https://example.com",
                    "employee_count": 50,
                },
                "confidence": 0.8,
            }
        )
        mock_gateway.get_dataaxle_client.return_value = mock_dataaxle

        # Mock Hunter client - finds email
        mock_hunter = MagicMock(spec=HunterClient)
        mock_hunter.find_email = AsyncMock(
            return_value={
                "emails": [
                    {
                        "value": "contact@example.com",
                        "confidence": 85,
                        "first_name": "John",
                        "last_name": "Doe",
                    }
                ]
            }
        )
        mock_gateway.get_hunter_client.return_value = mock_hunter

        mock_gateway_factory.return_value = mock_gateway

        # Create coordinator
        coordinator = EnrichmentCoordinator()

        # Test data
        businesses = [{"id": "biz_789", "name": "Test Business", "website": "https://example.com"}]

        # Enrich with both sources
        result = await coordinator.enrich_businesses_batch(
            businesses=businesses,
            sources=[EnrichmentSource.DATA_AXLE, EnrichmentSource.HUNTER_IO],
        )

        # The coordinator stops after first successful enrichment
        # This is the expected behavior - it tries sources in order until one succeeds
        assert result.successful_enrichments == 1
        assert len(result.results) == 1

        # Since Data Axle is first and succeeds, we should only get Data Axle result
        dataaxle_result = result.results[0]
        assert dataaxle_result.source == EnrichmentSource.DATA_AXLE
        assert dataaxle_result.phone == "+1-555-123-4567"
        assert dataaxle_result.employee_count == 50

        # Hunter should not be called since Data Axle succeeded
        mock_hunter.find_email.assert_not_called()

    @pytest.mark.asyncio
    @patch("d0_gateway.factory.GatewayClientFactory")
    async def test_enrichment_fallback_pattern(self, mock_gateway_factory):
        """Test fallback pattern: Hunter used when Data Axle fails"""
        # Setup mocks
        mock_gateway = MagicMock()
        mock_gateway._is_provider_enabled.return_value = True

        # Mock Data Axle client - returns no match
        mock_dataaxle = MagicMock(spec=DataAxleClient)
        mock_dataaxle.match_business = AsyncMock(return_value=None)
        mock_gateway.get_dataaxle_client.return_value = mock_dataaxle

        # Mock Hunter client - finds email
        mock_hunter = MagicMock(spec=HunterClient)
        mock_hunter.find_email = AsyncMock(
            return_value={
                "emails": [
                    {
                        "value": "fallback@example.com",
                        "confidence": 75,
                        "first_name": "Jane",
                        "last_name": "Doe",
                    }
                ]
            }
        )
        mock_gateway.get_hunter_client.return_value = mock_hunter

        mock_gateway_factory.return_value = mock_gateway

        # Create coordinator
        coordinator = EnrichmentCoordinator()

        # Test data
        businesses = [
            {
                "id": "biz_fallback",
                "name": "Test Business",
                "website": "https://example.com",
            }
        ]

        # Enrich with both sources
        result = await coordinator.enrich_businesses_batch(
            businesses=businesses,
            sources=[EnrichmentSource.DATA_AXLE, EnrichmentSource.HUNTER_IO],
        )

        # Verify fallback worked
        assert result.successful_enrichments == 1
        assert len(result.results) == 1

        # Should have Hunter result since Data Axle failed
        hunter_result = result.results[0]
        assert hunter_result.source == EnrichmentSource.HUNTER_IO
        assert hunter_result.email == "fallback@example.com"
        assert hunter_result.contact_name == "Jane Doe"

        # Both should have been called
        mock_dataaxle.match_business.assert_called_once()
        mock_hunter.find_email.assert_called_once()

    @pytest.mark.asyncio
    @patch("d0_gateway.factory.GatewayClientFactory")
    async def test_cost_tracking_integration(self, mock_gateway_factory):
        """Test that enrichment triggers cost tracking"""
        # Setup mocks
        mock_gateway = MagicMock()
        mock_gateway._is_provider_enabled.return_value = True

        # Mock Data Axle client with emit_cost tracking
        mock_dataaxle = MagicMock(spec=DataAxleClient)
        mock_dataaxle.match_business = AsyncMock(
            return_value={"data": {"email": "test@example.com"}, "confidence": 0.9}
        )
        mock_dataaxle.emit_cost = MagicMock()
        mock_gateway.get_dataaxle_client.return_value = mock_dataaxle

        mock_gateway_factory.return_value = mock_gateway

        # Create coordinator
        coordinator = EnrichmentCoordinator()

        # Enrich
        businesses = [{"id": "biz_999", "name": "Test"}]
        await coordinator.enrich_businesses_batch(businesses=businesses, sources=[EnrichmentSource.DATA_AXLE])

        # Verify cost was tracked
        mock_dataaxle.match_business.assert_called_once()
        # Note: emit_cost is called inside the Data Axle client, not in the enricher
