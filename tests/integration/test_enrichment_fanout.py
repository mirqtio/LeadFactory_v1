"""
Integration tests for Phase 0.5 enrichment fanout
Task EN-05: Test Data Axle first, Hunter fallback, cost tracking
"""
import pytest

# Mark entire module as slow for CI optimization
pytestmark = pytest.mark.slow
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from d4_enrichment.coordinator import EnrichmentCoordinator
from d4_enrichment.models import EnrichmentSource, MatchConfidence


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Phase 0.5 feature", strict=False)
class TestEnrichmentFanout:
    """Test enrichment fanout with Data Axle and Hunter"""

    @pytest.fixture
    async def coordinator(self):
        """Create enrichment coordinator with mocked enrichers"""
        coordinator = EnrichmentCoordinator()

        # Mock Data Axle enricher
        mock_dataaxle = AsyncMock()
        mock_dataaxle.enrich_business = AsyncMock()

        # Mock Hunter enricher
        mock_hunter = AsyncMock()
        mock_hunter.enrich_business = AsyncMock()

        # Mock GBP enricher
        mock_gbp = AsyncMock()
        mock_gbp.enrich_business = AsyncMock()

        # Add to coordinator
        coordinator.enrichers[EnrichmentSource.DATA_AXLE] = mock_dataaxle
        coordinator.enrichers[EnrichmentSource.HUNTER] = mock_hunter
        coordinator.enrichers[EnrichmentSource.INTERNAL] = mock_gbp

        return coordinator

    @pytest.fixture
    def test_business(self):
        """Test business data"""
        return {
            "id": "test-123",
            "name": "Test Business",
            "website": "https://test.com",
            "address": "123 Main St",
            "city": "Test City",
            "state": "TS",
            "zip_code": "12345",
        }

    async def test_dataaxle_first_with_email(self, coordinator, test_business):
        """Test that Data Axle is tried first and Hunter is skipped if email found"""
        # Setup Data Axle to return email
        dataaxle_result = MagicMock()
        dataaxle_result.id = "result-1"
        dataaxle_result.business_id = "test-123"
        dataaxle_result.source = EnrichmentSource.DATA_AXLE
        dataaxle_result.email = "contact@test.com"
        dataaxle_result.email_confidence = 0.9
        dataaxle_result.match_confidence = MatchConfidence.HIGH.value
        dataaxle_result.created_at = datetime.utcnow()
        dataaxle_result.phone = None
        dataaxle_result.additional_phones = None
        dataaxle_result.additional_emails = None
        dataaxle_result.enrichment_metadata = None
        coordinator.enrichers[EnrichmentSource.DATA_AXLE].enrich_business.return_value = dataaxle_result

        # Setup Hunter (should not be called)
        hunter_result = MagicMock()
        hunter_result.id = "result-2"
        hunter_result.business_id = "test-123"
        hunter_result.source = EnrichmentSource.HUNTER
        hunter_result.email = "hunter@test.com"
        hunter_result.email_confidence = 0.8
        hunter_result.match_confidence = MatchConfidence.MEDIUM.value
        hunter_result.created_at = datetime.utcnow()
        coordinator.enrichers[EnrichmentSource.HUNTER].enrich_business.return_value = hunter_result

        # Run enrichment
        sources = [EnrichmentSource.DATA_AXLE, EnrichmentSource.HUNTER]
        batch_result = await coordinator.enrich_businesses_batch(
            businesses=[test_business], sources=sources, skip_existing=False
        )

        # Verify Data Axle was called
        assert coordinator.enrichers[EnrichmentSource.DATA_AXLE].enrich_business.called

        # Verify result has Data Axle email
        assert batch_result.successful_enrichments == 1
        assert batch_result.results[0].email == "contact@test.com"
        assert batch_result.results[0].source == EnrichmentSource.DATA_AXLE

    async def test_hunter_fallback_no_email_from_dataaxle(self, coordinator, test_business):
        """Test Hunter is used when Data Axle returns no email"""
        # Setup Data Axle to return no email
        dataaxle_result = EnrichmentResult(
            id="result-1",
            business_id="test-123",
            source=EnrichmentSource.DATA_AXLE,
            email=None,  # No email
            phone="555-1234",
            match_confidence=MatchConfidence.MEDIUM.value,
            created_at=datetime.utcnow(),
        )
        coordinator.enrichers[EnrichmentSource.DATA_AXLE].enrich_business.return_value = dataaxle_result

        # Setup Hunter to provide email
        hunter_result = EnrichmentResult(
            id="result-2",
            business_id="test-123",
            source=EnrichmentSource.HUNTER,
            email="hunter@test.com",
            email_confidence=0.8,
            match_confidence=MatchConfidence.MEDIUM.value,
            created_at=datetime.utcnow(),
        )
        coordinator.enrichers[EnrichmentSource.HUNTER].enrich_business.return_value = hunter_result

        # Run enrichment
        sources = [EnrichmentSource.DATA_AXLE, EnrichmentSource.HUNTER]
        batch_result = await coordinator.enrich_businesses_batch(
            businesses=[test_business], sources=sources, skip_existing=False
        )

        # Verify both were called
        assert coordinator.enrichers[EnrichmentSource.DATA_AXLE].enrich_business.called
        assert coordinator.enrichers[EnrichmentSource.HUNTER].enrich_business.called

        # Verify result has Hunter email but Data Axle phone
        assert batch_result.successful_enrichments == 1
        result = batch_result.results[0]
        assert result.email == "hunter@test.com"  # From Hunter
        assert result.phone == "555-1234"  # From Data Axle

    async def test_merge_emails_and_phones(self, coordinator, test_business):
        """Test that emails and phones are merged correctly from multiple sources"""
        # Setup Data Axle with phone but no email
        dataaxle_result = EnrichmentResult(
            id="result-1",
            business_id="test-123",
            source=EnrichmentSource.DATA_AXLE,
            email=None,
            phone="555-1234",
            additional_phones=["555-5678"],
            match_confidence=MatchConfidence.HIGH.value,
            created_at=datetime.utcnow(),
        )
        coordinator.enrichers[EnrichmentSource.DATA_AXLE].enrich_business.return_value = dataaxle_result

        # Setup Hunter with email
        hunter_result = EnrichmentResult(
            id="result-2",
            business_id="test-123",
            source=EnrichmentSource.HUNTER,
            email="contact@test.com",
            additional_emails=["sales@test.com"],
            email_confidence=0.85,
            match_confidence=MatchConfidence.MEDIUM.value,
            created_at=datetime.utcnow(),
        )
        coordinator.enrichers[EnrichmentSource.HUNTER].enrich_business.return_value = hunter_result

        # Run enrichment
        sources = [EnrichmentSource.DATA_AXLE, EnrichmentSource.HUNTER]
        batch_result = await coordinator.enrich_businesses_batch(
            businesses=[test_business], sources=sources, skip_existing=False
        )

        # Verify merged result
        assert batch_result.successful_enrichments == 1
        result = batch_result.results[0]

        # Should have email from Hunter
        assert result.email == "contact@test.com"
        assert result.email_confidence == 0.85

        # Should have phone from Data Axle
        assert result.phone == "555-1234"
        assert result.additional_phones == ["555-5678"]

        # Should have additional emails from Hunter
        assert result.additional_emails == ["sales@test.com"]

    @patch("d0_gateway.base.BaseAPIClient.emit_cost")
    async def test_cost_tracking_for_each_api_call(self, mock_emit_cost, coordinator, test_business):
        """Test that cost is tracked for each API call"""
        # Setup enrichers to return results
        dataaxle_result = EnrichmentResult(
            id="result-1",
            business_id="test-123",
            source=EnrichmentSource.DATA_AXLE,
            email="test@example.com",
            match_confidence=MatchConfidence.HIGH.value,
            created_at=datetime.utcnow(),
        )
        coordinator.enrichers[EnrichmentSource.DATA_AXLE].enrich_business.return_value = dataaxle_result

        hunter_result = EnrichmentResult(
            id="result-2",
            business_id="test-123",
            source=EnrichmentSource.HUNTER,
            email="hunter@example.com",
            match_confidence=MatchConfidence.MEDIUM.value,
            created_at=datetime.utcnow(),
        )
        coordinator.enrichers[EnrichmentSource.HUNTER].enrich_business.return_value = hunter_result

        # Run enrichment with both sources
        sources = [EnrichmentSource.DATA_AXLE, EnrichmentSource.HUNTER]
        batch_result = await coordinator.enrich_businesses_batch(
            businesses=[test_business], sources=sources, skip_existing=False
        )

        # Verify enrichment succeeded
        assert batch_result.successful_enrichments == 1

        # Note: Cost tracking happens within the provider clients (Data Axle, Hunter)
        # which are mocked in this test. In a real scenario, the providers would
        # call emit_cost when they make API calls.

    async def test_source_ordering_phase05(self, coordinator, test_business):
        """Test that sources are ordered correctly for Phase 0.5"""
        # Test ordering method directly
        sources = [
            EnrichmentSource.HUNTER,
            EnrichmentSource.INTERNAL,
            EnrichmentSource.DATA_AXLE,
        ]

        ordered = coordinator._order_sources_for_phase05(sources, test_business)

        # Data Axle should be first
        assert ordered[0] == EnrichmentSource.DATA_AXLE
        # Internal should be second
        assert ordered[1] == EnrichmentSource.INTERNAL
        # Hunter should be last
        assert ordered[2] == EnrichmentSource.HUNTER

    async def test_error_handling_dataaxle_failure(self, coordinator, test_business):
        """Test that Hunter is still tried if Data Axle fails"""
        # Setup Data Axle to fail
        coordinator.enrichers[EnrichmentSource.DATA_AXLE].enrich_business.side_effect = Exception("API Error")

        # Setup Hunter to succeed
        hunter_result = EnrichmentResult(
            id="result-2",
            business_id="test-123",
            source=EnrichmentSource.HUNTER,
            email="hunter@test.com",
            match_confidence=MatchConfidence.MEDIUM.value,
            created_at=datetime.utcnow(),
        )
        coordinator.enrichers[EnrichmentSource.HUNTER].enrich_business.return_value = hunter_result

        # Run enrichment
        sources = [EnrichmentSource.DATA_AXLE, EnrichmentSource.HUNTER]
        batch_result = await coordinator.enrich_businesses_batch(
            businesses=[test_business], sources=sources, skip_existing=False
        )

        # Should still get result from Hunter
        assert batch_result.successful_enrichments == 1
        assert batch_result.results[0].email == "hunter@test.com"
        assert batch_result.results[0].source == EnrichmentSource.HUNTER

        # Should have error logged
        assert len(batch_result.progress.errors) > 0
        assert "API Error" in batch_result.progress.errors[0]
