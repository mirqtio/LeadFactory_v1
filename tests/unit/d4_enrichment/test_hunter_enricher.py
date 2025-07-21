"""
Tests for Hunter.io enricher (P0-001)
Ensures Hunter enrichment works properly
"""

from unittest.mock import AsyncMock

import pytest

from d4_enrichment.hunter_enricher import EnrichmentResult, HunterEnricher
from d4_enrichment.models import EnrichmentSource


class TestHunterEnricher:
    """Test Hunter enricher functionality"""

    @pytest.fixture
    def mock_client(self):
        """Create mock Hunter client"""
        return AsyncMock()

    @pytest.fixture
    def enricher(self, mock_client):
        """Create Hunter enricher with mock client"""
        return HunterEnricher(client=mock_client)

    @pytest.fixture
    def sample_business(self):
        """Sample business data"""
        return {
            "id": "biz_001",
            "name": "Test Company Inc",
            "website": "testcompany.com",
            "lead_id": "lead_123",
            "address": "123 Test St",
            "city": "Test City",
        }

    @pytest.mark.asyncio
    async def test_enrich_business_success_high_confidence(self, enricher, mock_client, sample_business):
        """Test successful enrichment with high confidence email"""
        # Mock successful API response
        mock_client.find_email.return_value = {
            "emails": [
                {
                    "value": "john.doe@testcompany.com",
                    "confidence": 95,
                    "first_name": "John",
                    "last_name": "Doe",
                    "position": "CEO",
                },
                {"value": "info@testcompany.com", "confidence": 80, "first_name": "", "last_name": "", "position": ""},
            ],
            "pattern": "{first}.{last}",
            "organization": "Test Company Inc",
        }

        result = await enricher.enrich_business(sample_business, "biz_001")

        assert isinstance(result, EnrichmentResult)
        assert result.business_id == "biz_001"
        assert result.source == EnrichmentSource.HUNTER_IO
        assert result.email == "john.doe@testcompany.com"  # Highest confidence email
        assert result.phone is None  # Hunter doesn't provide phone
        assert result.website == "testcompany.com"
        assert result.contact_name == "John Doe"
        assert result.contact_title == "CEO"
        assert result.confidence_score == 0.95  # Converted to 0-1 scale
        assert result.match_confidence == "high"
        assert len(result.raw_data["emails"]) == 2
        assert result.raw_data["pattern"] == "{first}.{last}"

        expected_company_data = {"domain": "testcompany.com", "company_name": "Test Company Inc", "lead_id": "lead_123"}
        mock_client.find_email.assert_called_once_with(expected_company_data)

    @pytest.mark.asyncio
    async def test_enrich_business_exact_confidence(self, enricher, mock_client, sample_business):
        """Test enrichment with exact match (100% confidence)"""
        mock_client.find_email.return_value = {
            "emails": [
                {
                    "value": "exact@match.com",
                    "confidence": 100,
                    "first_name": "Exact",
                    "last_name": "Match",
                    "position": "Owner",
                }
            ]
        }

        result = await enricher.enrich_business(sample_business, "biz_001")

        assert result.confidence_score == 1.0
        assert result.match_confidence == "exact"

    @pytest.mark.asyncio
    async def test_enrich_business_medium_confidence(self, enricher, mock_client, sample_business):
        """Test enrichment with medium confidence email"""
        mock_client.find_email.return_value = {
            "emails": [
                {"value": "medium@match.com", "confidence": 75, "first_name": "", "last_name": "", "position": ""}
            ]
        }

        result = await enricher.enrich_business(sample_business, "biz_001")

        assert result.confidence_score == 0.75
        assert result.match_confidence == "medium"
        assert result.contact_name == " "  # Empty first/last name

    @pytest.mark.asyncio
    async def test_enrich_business_low_confidence(self, enricher, mock_client, sample_business):
        """Test enrichment with low confidence email"""
        mock_client.find_email.return_value = {
            "emails": [
                {
                    "value": "low@match.com",
                    "confidence": 50,
                    "first_name": "Low",
                    "last_name": "Confidence",
                    "position": "Unknown",
                }
            ]
        }

        result = await enricher.enrich_business(sample_business, "biz_001")

        assert result.confidence_score == 0.5
        assert result.match_confidence == "low"
        assert result.email == "low@match.com"  # Still returns low confidence results

    @pytest.mark.asyncio
    async def test_enrich_business_no_website(self, enricher, mock_client):
        """Test when business has no website"""
        business = {
            "id": "biz_002",
            "name": "No Website Company",
            # No website field
        }

        result = await enricher.enrich_business(business, "biz_002")

        assert result is None
        mock_client.find_email.assert_not_called()

    @pytest.mark.asyncio
    async def test_enrich_business_no_emails_found(self, enricher, mock_client, sample_business):
        """Test when Hunter returns no emails"""
        mock_client.find_email.return_value = {"emails": [], "pattern": None, "organization": "Test Company Inc"}

        result = await enricher.enrich_business(sample_business, "biz_001")

        assert result is None

    @pytest.mark.asyncio
    async def test_enrich_business_api_returns_none(self, enricher, mock_client, sample_business):
        """Test when API returns None"""
        mock_client.find_email.return_value = None

        result = await enricher.enrich_business(sample_business, "biz_001")

        assert result is None

    @pytest.mark.asyncio
    async def test_enrich_business_multiple_emails_selection(self, enricher, mock_client, sample_business):
        """Test that highest confidence email is selected from multiple"""
        mock_client.find_email.return_value = {
            "emails": [
                {"value": "low@test.com", "confidence": 60},
                {"value": "best@test.com", "confidence": 90},
                {"value": "medium@test.com", "confidence": 75},
            ]
        }

        result = await enricher.enrich_business(sample_business, "biz_001")

        assert result.email == "best@test.com"
        assert result.confidence_score == 0.9

    @pytest.mark.asyncio
    async def test_enrich_business_missing_email_fields(self, enricher, mock_client, sample_business):
        """Test handling of missing fields in email data"""
        mock_client.find_email.return_value = {
            "emails": [
                {
                    "value": "minimal@test.com",
                    "confidence": 85,
                    # Missing first_name, last_name, position
                }
            ]
        }

        result = await enricher.enrich_business(sample_business, "biz_001")

        assert result.email == "minimal@test.com"
        assert result.contact_name == " "  # Empty string concatenation
        assert result.contact_title is None

    @pytest.mark.asyncio
    async def test_enrich_business_exception_handling(self, enricher, mock_client, sample_business):
        """Test exception handling during enrichment"""
        mock_client.find_email.side_effect = Exception("API error")

        result = await enricher.enrich_business(sample_business, "biz_001")

        assert result is None
        mock_client.find_email.assert_called_once()

    @pytest.mark.xfail(reason="Client initialization differs in test environment")
    def test_enricher_initialization_default_client(self):
        """Test enricher initialization without client"""
        enricher = HunterEnricher()
        assert enricher.client is not None
        assert enricher.source == EnrichmentSource.HUNTER_IO

    def test_enricher_initialization_with_client(self, mock_client):
        """Test enricher initialization with provided client"""
        enricher = HunterEnricher(client=mock_client)
        assert enricher.client is mock_client
        assert enricher.source == EnrichmentSource.HUNTER_IO

    @pytest.mark.asyncio
    async def test_enrich_business_edge_confidence_90(self, enricher, mock_client, sample_business):
        """Test edge case: confidence exactly 90"""
        mock_client.find_email.return_value = {"emails": [{"value": "edge@case.com", "confidence": 90}]}

        result = await enricher.enrich_business(sample_business, "biz_001")

        assert result.confidence_score == 0.9
        assert result.match_confidence == "high"  # >= 0.9 is high

    @pytest.mark.asyncio
    async def test_enrich_business_edge_confidence_70(self, enricher, mock_client, sample_business):
        """Test edge case: confidence exactly 70"""
        mock_client.find_email.return_value = {"emails": [{"value": "edge@case.com", "confidence": 70}]}

        result = await enricher.enrich_business(sample_business, "biz_001")

        assert result.confidence_score == 0.7
        assert result.match_confidence == "medium"  # >= 0.7 is medium

    @pytest.mark.asyncio
    async def test_enrich_business_no_confidence_score(self, enricher, mock_client, sample_business):
        """Test handling of missing confidence score"""
        mock_client.find_email.return_value = {
            "emails": [
                {
                    "value": "no-confidence@test.com"
                    # Missing confidence field
                }
            ]
        }

        result = await enricher.enrich_business(sample_business, "biz_001")

        assert result.email == "no-confidence@test.com"
        assert result.confidence_score == 0.0  # Default value
        assert result.match_confidence == "low"
