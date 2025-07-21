"""
Email enrichment logic for PRD v1.2
Implements Hunter-first, Data Axle fallback pattern
"""

from typing import Any
from urllib.parse import urlparse

from core.config import settings
from core.logging import get_logger
from d0_gateway.factory import get_gateway_factory
from d0_gateway.providers.dataaxle import DataAxleClient
from d0_gateway.providers.hunter import HunterClient

logger = get_logger(__name__, domain="d4")


class EmailEnricher:
    """
    Email enrichment following PRD v1.2 logic:
    1. Try Hunter first
    2. If confidence >= 0.75, use it
    3. Otherwise try Data Axle if API key available
    """

    def __init__(self):
        self._hunter_client = None
        self._dataaxle_client = None

    async def _get_hunter_client(self) -> HunterClient | None:
        """Get Hunter client if available"""
        if not self._hunter_client and settings.hunter_api_key:
            try:
                self._hunter_client = get_gateway_factory().create_client("hunter")
            except Exception as e:
                logger.error(f"Failed to initialize Hunter client: {e}")
        return self._hunter_client

    async def _get_dataaxle_client(self) -> DataAxleClient | None:
        """Get Data Axle client if available"""
        if not self._dataaxle_client and settings.data_axle_api_key:
            try:
                self._dataaxle_client = get_gateway_factory().create_client("dataaxle")
            except Exception as e:
                logger.error(f"Failed to initialize Data Axle client: {e}")
        return self._dataaxle_client

    async def enrich_email(self, business: dict[str, Any]) -> tuple[str | None, str]:
        """
        Enrich business with email following PRD v1.2 logic

        Args:
            business: Business data with domain/website

        Returns:
            Tuple of (email, source) where source is 'hunter', 'dataaxle', or None
        """
        # Check if business already has email
        if business.get("email"):
            return business["email"], "existing"

        # Extract domain from website
        domain = self._extract_domain(business)
        if not domain:
            logger.warning(f"No domain found for business {business.get('name', 'unknown')}")
            return None, None

        # Try Hunter first
        hunter_client = await self._get_hunter_client()
        if hunter_client:
            try:
                email, confidence = await hunter_client.domain_search(domain)

                # PRD v1.2: Use if confidence >= 0.75
                if email and confidence >= 0.75:
                    logger.info(f"Found email via Hunter for {domain}: {email} (confidence: {confidence:.2f})")
                    return email, "hunter"
                if email:
                    logger.info(f"Hunter email confidence too low for {domain}: {confidence:.2f} < 0.75")

            except Exception as e:
                logger.error(f"Hunter search failed for {domain}: {e}")

        # Try Data Axle as fallback
        dataaxle_client = await self._get_dataaxle_client()
        if dataaxle_client and settings.data_axle_api_key:
            try:
                data = await dataaxle_client.enrich(domain)

                if data and data.get("email"):
                    email = data["email"]
                    logger.info(f"Found email via Data Axle for {domain}: {email}")
                    return email, "dataaxle"

            except Exception as e:
                logger.error(f"Data Axle enrichment failed for {domain}: {e}")

        # No email found
        logger.info(f"No email found for {domain}")
        return None, None

    def _extract_domain(self, business: dict[str, Any]) -> str | None:
        """Extract domain from business data"""
        # Try website field first
        website = business.get("website")
        if website:
            try:
                parsed = urlparse(website)
                domain = parsed.netloc
                # Remove www prefix
                if domain.startswith("www."):
                    domain = domain[4:]
                return domain
            except Exception:
                pass

        # Try domain field
        domain = business.get("domain")
        if domain:
            # Clean up domain
            if domain.startswith("www."):
                domain = domain[4:]
            return domain

        # Try to construct from business name and location
        # This is a last resort and may not be accurate
        name = business.get("name", "").lower()
        if name:
            # Remove common business suffixes
            for suffix in [" inc", " llc", " corp", " ltd", " co"]:
                name = name.replace(suffix, "")
            # Remove special characters
            name = "".join(c for c in name if c.isalnum() or c == " ")
            # Convert spaces to hyphens
            name = name.strip().replace(" ", "-")
            if name:
                return f"{name}.com"  # Guess .com domain

        return None

    async def enrich_batch(self, businesses: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        """
        Enrich multiple businesses with emails

        Args:
            businesses: List of business dictionaries

        Returns:
            Dict mapping business ID to enrichment result
        """
        results = {}

        for business in businesses:
            business_id = business.get("id")
            if not business_id:
                continue

            email, source = await self.enrich_email(business)

            results[business_id] = {
                "email": email,
                "source": source,
                "success": email is not None,
            }

        return results


# Singleton instance
_email_enricher = None


def get_email_enricher() -> EmailEnricher:
    """Get singleton email enricher instance"""
    global _email_enricher
    if not _email_enricher:
        _email_enricher = EmailEnricher()
    return _email_enricher
