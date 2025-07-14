"""
Tests for Data Axle enricher (P0-001)
Ensures Data Axle enrichment works properly
"""
from unittest.mock import AsyncMock

import pytest

from d4_enrichment.dataaxle_enricher import DataAxleEnricher, EnrichmentResult
from d4_enrichment.models import EnrichmentSource


class TestDataAxleEnricher:
    """Test Data Axle enricher functionality"""

    @pytest.fixture
    def mock_client(self):
        """Create mock Data Axle client"""
        return AsyncMock()

    @pytest.fixture
    def enricher(self, mock_client):
        """Create Data Axle enricher with mock client"""
        return DataAxleEnricher(client=mock_client)

    @pytest.fixture
    def sample_business(self):
        """Sample business data"""
        return {
            "id": "biz_001",
            "name": "Test Company Inc",
            "address": "123 Test St",
            "city": "Test City",
            "state": "TS",
            "zip": "12345",
            "phone": "555-1234",
        }

    @pytest.mark.asyncio
    async def test_enrich_business_success_high_confidence(self, enricher, mock_client, sample_business):
        """Test successful enrichment with high confidence match"""
        # Mock successful API response
        mock_client.match_business.return_value = {
            "confidence": 0.95,
            "match_id": "DA123456",
            "data": {
                "email": "info@testcompany.com",
                "phone": "555-1234",
                "website": "https://testcompany.com",
                "employee_count": 50,
                "annual_revenue": 5000000.0,
                "years_in_business": 10,
                "contact_name": "John Doe",
                "contact_title": "CEO",
            },
        }

        result = await enricher.enrich_business(sample_business, "biz_001")

        assert isinstance(result, EnrichmentResult)
        assert result.business_id == "biz_001"
        assert result.source == EnrichmentSource.DATA_AXLE
        assert result.email == "info@testcompany.com"
        assert result.phone == "555-1234"
        assert result.website == "https://testcompany.com"
        assert result.employee_count == 50
        assert result.annual_revenue == 5000000.0
        assert result.years_in_business == 10
        assert result.contact_name == "John Doe"
        assert result.contact_title == "CEO"
        assert result.confidence_score == 0.95
        assert result.match_confidence == "high"
        assert result.raw_data["match_id"] == "DA123456"

        mock_client.match_business.assert_called_once_with(sample_business)

    @pytest.mark.asyncio
    async def test_enrich_business_exact_match(self, enricher, mock_client, sample_business):
        """Test enrichment with exact match (confidence >= 1.0)"""
        mock_client.match_business.return_value = {"confidence": 1.0, "data": {"email": "exact@match.com"}}

        result = await enricher.enrich_business(sample_business, "biz_001")

        assert result.confidence_score == 1.0
        assert result.match_confidence == "exact"

    @pytest.mark.asyncio
    async def test_enrich_business_medium_confidence(self, enricher, mock_client, sample_business):
        """Test enrichment with medium confidence match"""
        mock_client.match_business.return_value = {"confidence": 0.75, "data": {"email": "medium@match.com"}}

        result = await enricher.enrich_business(sample_business, "biz_001")

        assert result.confidence_score == 0.75
        assert result.match_confidence == "medium"

    @pytest.mark.asyncio
    async def test_enrich_business_low_confidence_rejected(self, enricher, mock_client, sample_business):
        """Test that low confidence matches are rejected"""
        mock_client.match_business.return_value = {
            "confidence": 0.65,  # Below 0.7 threshold
            "data": {"email": "low@confidence.com"},
        }

        result = await enricher.enrich_business(sample_business, "biz_001")

        assert result is None
        mock_client.match_business.assert_called_once()

    @pytest.mark.asyncio
    async def test_enrich_business_no_match(self, enricher, mock_client, sample_business):
        """Test when no match is found"""
        mock_client.match_business.return_value = None

        result = await enricher.enrich_business(sample_business, "biz_001")

        assert result is None
        mock_client.match_business.assert_called_once()

    @pytest.mark.asyncio
    async def test_enrich_business_empty_result(self, enricher, mock_client, sample_business):
        """Test when API returns empty result"""
        mock_client.match_business.return_value = {}

        result = await enricher.enrich_business(sample_business, "biz_001")

        assert result is None

    @pytest.mark.asyncio
    async def test_enrich_business_partial_data(self, enricher, mock_client, sample_business):
        """Test enrichment with partial data available"""
        mock_client.match_business.return_value = {
            "confidence": 0.85,
            "data": {
                "email": "partial@testcompany.com",
                "employee_count": 25
                # Missing other fields
            },
        }

        result = await enricher.enrich_business(sample_business, "biz_001")

        assert result.email == "partial@testcompany.com"
        assert result.employee_count == 25
        assert result.phone is None
        assert result.website is None
        assert result.annual_revenue is None
        assert result.years_in_business is None
        assert result.contact_name is None
        assert result.contact_title is None

    @pytest.mark.asyncio
    async def test_enrich_business_exception_handling(self, enricher, mock_client, sample_business):
        """Test exception handling during enrichment"""
        mock_client.match_business.side_effect = Exception("API error")

        result = await enricher.enrich_business(sample_business, "biz_001")

        assert result is None
        mock_client.match_business.assert_called_once()

    @pytest.mark.asyncio
    async def test_enrich_business_missing_confidence(self, enricher, mock_client, sample_business):
        """Test handling of missing confidence score"""
        mock_client.match_business.return_value = {
            # No confidence field
            "data": {"email": "test@example.com"}
        }

        result = await enricher.enrich_business(sample_business, "biz_001")

        # Should use default confidence of 0.0 and reject
        assert result is None

    def test_enricher_initialization_default_client(self):
        """Test enricher initialization without client"""
        enricher = DataAxleEnricher()
        assert enricher.client is not None
        assert enricher.source == EnrichmentSource.DATA_AXLE

    def test_enricher_initialization_with_client(self, mock_client):
        """Test enricher initialization with provided client"""
        enricher = DataAxleEnricher(client=mock_client)
        assert enricher.client is mock_client
        assert enricher.source == EnrichmentSource.DATA_AXLE

    @pytest.mark.asyncio
    async def test_enrich_business_edge_confidence_0_9(self, enricher, mock_client, sample_business):
        """Test edge case: confidence exactly 0.9"""
        mock_client.match_business.return_value = {"confidence": 0.9, "data": {"email": "edge@case.com"}}

        result = await enricher.enrich_business(sample_business, "biz_001")

        assert result.confidence_score == 0.9
        assert result.match_confidence == "high"  # >= 0.9 is high

    @pytest.mark.asyncio
    async def test_enrich_business_edge_confidence_0_7(self, enricher, mock_client, sample_business):
        """Test edge case: confidence exactly 0.7"""
        mock_client.match_business.return_value = {"confidence": 0.7, "data": {"email": "edge@case.com"}}

        result = await enricher.enrich_business(sample_business, "biz_001")

        assert result.confidence_score == 0.7
        assert result.match_confidence == "medium"  # >= 0.7 is medium
