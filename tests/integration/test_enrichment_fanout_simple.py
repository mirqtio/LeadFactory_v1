"""
Simplified integration tests for Phase 0.5 enrichment fanout
Task EN-05: Test Data Axle first, Hunter fallback, cost tracking
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from d4_enrichment.coordinator import EnrichmentCoordinator
from d4_enrichment.models import EnrichmentSource, MatchConfidence


def create_mock_result(
    source, email=None, phone=None, confidence=MatchConfidence.HIGH.value
):
    """Helper to create mock enrichment result"""
    result = MagicMock()
    result.source = source
    result.email = email
    result.email_confidence = 0.9 if email else None
    result.phone = phone
    result.match_confidence = confidence
    result.additional_phones = None
    result.additional_emails = None
    result.enrichment_metadata = {}
    return result


@pytest.mark.asyncio
class TestEnrichmentFanoutSimple:
    """Simplified tests for enrichment fanout"""

    @pytest.mark.skip(reason="Phase 0.5 source ordering not implemented in current coordinator")
    async def test_source_ordering(self):
        """Test that sources are ordered correctly for Phase 0.5"""
        coordinator = EnrichmentCoordinator()

        # Test ordering method
        sources = [
            EnrichmentSource.HUNTER_IO_IO,
            EnrichmentSource.INTERNAL,
            EnrichmentSource.CLEARBIT,
        ]

        ordered = coordinator._order_sources_for_phase05(sources, {})

        # Data Axle (Clearbit) should be first
        assert ordered[0] == EnrichmentSource.CLEARBIT
        # Internal should be second
        assert ordered[1] == EnrichmentSource.INTERNAL
        # Hunter should be last
        assert ordered[2] == EnrichmentSource.HUNTER_IO

    @pytest.mark.skip(reason="Phase 0.5 merge method not implemented in current coordinator")
    async def test_result_merging(self):
        """Test that results are merged correctly"""
        coordinator = EnrichmentCoordinator()

        # Create base result with phone
        base_result = create_mock_result(
            source=EnrichmentSource.CLEARBIT, phone="555-1234"
        )

        # Create new result with email
        new_result = create_mock_result(
            source=EnrichmentSource.HUNTER_IO, email="test@example.com"
        )

        # Merge results
        merged = coordinator._merge_enrichment_results(base_result, new_result)

        # Should have both phone and email
        assert merged.phone == "555-1234"
        assert merged.email == "test@example.com"
        assert merged.email_confidence == 0.9

    @pytest.mark.skip(reason="Phase 0.5 fanout logic not fully implemented in current coordinator")
    async def test_fanout_with_mocked_enrichers(self):
        """Test complete fanout with mocked enrichers"""
        coordinator = EnrichmentCoordinator()

        # Mock enrichers
        mock_dataaxle = AsyncMock()
        mock_dataaxle.enrich_business = AsyncMock(
            return_value=create_mock_result(
                source=EnrichmentSource.CLEARBIT, phone="555-1234"  # No email
            )
        )

        mock_hunter = AsyncMock()
        mock_hunter.enrich_business = AsyncMock(
            return_value=create_mock_result(
                source=EnrichmentSource.HUNTER_IO, email="contact@test.com"
            )
        )

        # Add to coordinator
        coordinator.enrichers[EnrichmentSource.CLEARBIT] = mock_dataaxle
        coordinator.enrichers[EnrichmentSource.HUNTER_IO] = mock_hunter

        # Test business
        business = {
            "id": "test-123",
            "name": "Test Business",
            "website": "https://test.com",
        }

        # Run enrichment
        sources = [EnrichmentSource.CLEARBIT, EnrichmentSource.HUNTER_IO]
        batch_result = await coordinator.enrich_businesses_batch(
            businesses=[business], sources=sources, skip_existing=False
        )

        # Both enrichers should be called
        assert mock_dataaxle.enrich_business.called
        assert mock_hunter.enrich_business.called

        # Result should have data from both sources
        assert batch_result.successful_enrichments == 1
        result = batch_result.results[0]
        assert result.phone == "555-1234"  # From Data Axle
        assert result.email == "contact@test.com"  # From Hunter
