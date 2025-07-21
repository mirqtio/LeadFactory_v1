"""
Data Axle enricher for business data
Phase 0.5 - Task EN-05
"""

import logging
from dataclasses import dataclass
from typing import Any

from d0_gateway.providers.dataaxle import DataAxleClient

from .models import EnrichmentSource


@dataclass
class EnrichmentResult:
    """Simple result class for enrichment data"""

    business_id: str
    source: EnrichmentSource
    email: str | None = None
    phone: str | None = None
    website: str | None = None
    employee_count: int | None = None
    annual_revenue: float | None = None
    years_in_business: int | None = None
    contact_name: str | None = None
    contact_title: str | None = None
    confidence_score: float = 0.0
    raw_data: dict[str, Any] | None = None
    match_confidence: str = "high"  # For coordinator compatibility


logger = logging.getLogger(__name__)


class DataAxleEnricher:
    """Enricher that uses Data Axle API for business matching and enrichment"""

    def __init__(self, client: DataAxleClient | None = None):
        self.client = client or DataAxleClient()
        self.source = EnrichmentSource.DATA_AXLE

    async def enrich_business(self, business_data: dict[str, Any], business_id: str) -> EnrichmentResult | None:
        """
        Enrich business data using Data Axle API

        Args:
            business_data: Original business data from sourcing
            business_id: Business ID for tracking

        Returns:
            EnrichmentResult if match found, None otherwise
        """
        try:
            # Call Data Axle to match business
            result = await self.client.match_business(business_data)

            if not result:
                logger.info(f"No Data Axle match found for business {business_id}")
                return None

            # Extract matched data
            match_data = result.get("data", {})
            confidence = result.get("confidence", 0.0)

            # Only accept high confidence matches
            if confidence < 0.7:
                logger.info(f"Low confidence match ({confidence}) for business {business_id}")
                return None

            # Determine match confidence level
            if confidence >= 0.9:
                match_confidence = "exact" if confidence >= 1.0 else "high"
            elif confidence >= 0.7:
                match_confidence = "medium"
            else:
                match_confidence = "low"

            # Build enrichment result
            enrichment = EnrichmentResult(
                business_id=business_id,
                source=self.source,
                email=match_data.get("email"),
                phone=match_data.get("phone"),
                website=match_data.get("website"),
                employee_count=match_data.get("employee_count"),
                annual_revenue=match_data.get("annual_revenue"),
                years_in_business=match_data.get("years_in_business"),
                contact_name=match_data.get("contact_name"),
                contact_title=match_data.get("contact_title"),
                confidence_score=confidence,
                match_confidence=match_confidence,
                # Store full match data for reference
                raw_data={
                    "match_data": match_data,
                    "confidence": confidence,
                    "match_id": result.get("match_id"),
                },
            )

            logger.info(f"Successfully enriched business {business_id} via Data Axle (confidence: {confidence})")

            return enrichment

        except Exception as e:
            logger.error(f"Data Axle enrichment failed for {business_id}: {e}")
            return None
