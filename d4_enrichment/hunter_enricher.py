"""
Hunter.io enricher for email finding
Phase 0.5 - Task EN-05
"""
import logging
from typing import Dict, Optional, Any

from d0_gateway.providers.hunter import HunterClient
from .models import EnrichmentSource
from dataclasses import dataclass


@dataclass
class EnrichmentResult:
    """Simple result class for enrichment data"""

    business_id: str
    source: EnrichmentSource
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    employee_count: Optional[int] = None
    annual_revenue: Optional[float] = None
    years_in_business: Optional[int] = None
    contact_name: Optional[str] = None
    contact_title: Optional[str] = None
    confidence_score: float = 0.0
    raw_data: Optional[Dict[str, Any]] = None
    match_confidence: str = "high"  # For coordinator compatibility


logger = logging.getLogger(__name__)


class HunterEnricher:
    """Enricher that uses Hunter.io API for email finding as fallback"""

    def __init__(self, client: Optional[HunterClient] = None):
        self.client = client or HunterClient()
        self.source = EnrichmentSource.HUNTER_IO

    async def enrich_business(
        self, business_data: Dict[str, Any], business_id: str
    ) -> Optional[EnrichmentResult]:
        """
        Find emails using Hunter.io API (fallback enrichment)

        Args:
            business_data: Original business data with website
            business_id: Business ID for tracking

        Returns:
            EnrichmentResult if email found, None otherwise
        """
        try:
            # Hunter requires a domain to search
            website = business_data.get("website")
            if not website:
                logger.debug(f"No website available for Hunter search on {business_id}")
                return None

            # Extract company info for Hunter
            company_data = {
                "domain": website,
                "company_name": business_data.get("name"),
                "lead_id": business_data.get("lead_id"),
            }

            # Call Hunter to find emails
            result = await self.client.find_email(company_data)

            if not result:
                logger.info(f"No Hunter emails found for business {business_id}")
                return None

            # Extract email data
            emails = result.get("emails", [])
            if not emails:
                return None

            # Use the highest confidence email
            best_email = max(emails, key=lambda e: e.get("confidence", 0))
            confidence = best_email.get("confidence", 0) / 100.0  # Convert to 0-1 scale

            # Determine match confidence level
            if confidence >= 0.9:
                match_confidence = "exact" if confidence >= 1.0 else "high"
            elif confidence >= 0.7:
                match_confidence = "medium"
            else:
                match_confidence = "low"

            # Build enrichment result (Hunter only provides emails)
            enrichment = EnrichmentResult(
                business_id=business_id,
                source=self.source,
                email=best_email.get("value"),
                # Hunter provides limited data compared to Data Axle
                phone=None,  # Hunter doesn't provide phone
                website=website,  # We already had this
                employee_count=None,
                annual_revenue=None,
                years_in_business=None,
                contact_name=best_email.get("first_name", "")
                + " "
                + best_email.get("last_name", ""),
                contact_title=best_email.get("position"),
                confidence_score=confidence,
                match_confidence=match_confidence,
                # Store all found emails for reference
                raw_data={
                    "emails": emails,
                    "domain": website,
                    "pattern": result.get("pattern"),
                    "organization": result.get("organization"),
                },
            )

            logger.info(
                f"Successfully found email for business {business_id} via Hunter "
                f"(confidence: {enrichment.confidence_score})"
            )

            return enrichment

        except Exception as e:
            logger.error(f"Hunter enrichment failed for {business_id}: {e}")
            return None
