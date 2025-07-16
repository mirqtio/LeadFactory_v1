"""
Data Axle API client for business enrichment
PRD v1.2 - Trial mode email enrichment (fallback)

Endpoint: GET /v1/companies/enrich?domain=
Cost: Free (trial credits)
Used only when Hunter.io doesn't return email
"""
import logging
from decimal import Decimal
from typing import Any, Dict, Optional

from core.exceptions import ValidationError
from d0_gateway.base import BaseAPIClient
from d0_gateway.exceptions import APIProviderError, AuthenticationError, RateLimitExceededError

logger = logging.getLogger(__name__)


class DataAxleClient(BaseAPIClient):
    """
    Data Axle Business Match API client

    Implements POST /v2/business/match endpoint for enriching business data
    with emails, phones, and firmographics.
    """

    def __init__(self, api_key: str, **kwargs):
        """
        Initialize Data Axle client

        Args:
            api_key: Data Axle API key
            **kwargs: Additional configuration
        """
        # Store base_url before calling parent init
        self.base_url = kwargs.get("base_url", "https://api.data-axle.com/v2")
        self.timeout = kwargs.get("timeout", 30)
        self.max_retries = kwargs.get("max_retries", 3)

        # Call parent constructor with required args only
        super().__init__(
            provider="dataaxle",
            api_key=api_key,
            base_url=self.base_url,
        )

        # Set rate limit from config
        from core.config import settings

        self._rate_limit = settings.data_axle_rate_limit_per_min

        # Create HTTP client if needed (for compatibility with tests)
        self._client = None

    def _get_base_url(self) -> str:
        """Get the base URL for Data Axle API"""
        return self.base_url

    def get_rate_limit(self) -> Dict[str, int]:
        """Get rate limit configuration for Data Axle"""
        return {
            "requests_per_minute": self._rate_limit,
            "requests_per_hour": self._rate_limit * 60,
        }

    def calculate_cost(self, operation: str, **kwargs) -> Decimal:
        """Calculate cost for Data Axle operations"""
        if operation == "match_business":
            # $0.05 per successful match
            return Decimal("0.05")
        return Decimal("0.00")

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for Data Axle API requests"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def match_business(self, business_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Match business and return enriched data

        Args:
            business_data: Business information for matching
                - name: Business name (required)
                - address: Street address
                - city: City name
                - state: State code
                - zip_code: ZIP code
                - lead_id: Lead ID for cost tracking

        Returns:
            Enriched business data if match found, None otherwise

        Raises:
            APIProviderError: For API communication errors
            RateLimitExceededError: If rate limit exceeded
            ValidationError: For invalid input data
        """
        # Validate required fields
        if not business_data.get("name"):
            raise ValidationError("Business name is required for matching")

        # Prepare request payload
        payload = {
            "business_name": business_data.get("name"),
            "address": business_data.get("address", ""),
            "city": business_data.get("city", ""),
            "state": business_data.get("state", ""),
            "zip": business_data.get("zip_code", ""),
            "match_threshold": 0.8,  # 80% match confidence
            "return_fields": [
                "emails",
                "phones",
                "website",
                "employee_count",
                "annual_revenue",
                "years_in_business",
                "business_type",
                "sic_codes",
                "naics_codes",
            ],
        }

        try:
            # Make API call
            response = await self._post("/business/match", json=payload)

            if not response:
                logger.warning(
                    f"No match found for business: {business_data.get('name')} in {business_data.get('city')}"
                )
                return None

            # Check if match was found
            if not response.get("match_found", False):
                return None

            # Extract business data
            matched_data = response.get("business_data", {})

            # Log successful match
            logger.info(
                f"Business match found for {business_data.get('name')} - "
                f"confidence: {response.get('match_confidence', 0):.2f}, "
                f"has_email: {bool(matched_data.get('emails'))}, "
                f"has_phone: {bool(matched_data.get('phones'))}"
            )

            # Emit cost for successful match (Phase 0.5 requirement)
            self.emit_cost(
                lead_id=business_data.get("lead_id"),
                cost_usd=0.05,  # $0.05 per successful match
                operation="match_business",
                metadata={
                    "match_confidence": response.get("match_confidence", 0),
                    "has_email": bool(matched_data.get("emails")),
                    "has_phone": bool(matched_data.get("phones")),
                },
            )

            # Transform to standard format
            return self._transform_response(matched_data)

        except Exception as e:
            if "429" in str(e) or "rate_limit" in str(e).lower():
                raise RateLimitExceededError("dataaxle", "api_calls")
            elif "401" in str(e) or "403" in str(e):
                raise AuthenticationError("dataaxle", str(e))
            else:
                raise APIProviderError("dataaxle", str(e))

    def _transform_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform Data Axle response to standard format

        Args:
            data: Raw Data Axle response

        Returns:
            Standardized business data
        """
        # Extract emails
        emails = data.get("emails", [])
        primary_email = None
        if emails and isinstance(emails, list):
            primary_email = emails[0].get("email") if isinstance(emails[0], dict) else emails[0]

        # Extract phones
        phones = data.get("phones", [])
        primary_phone = None
        if phones and isinstance(phones, list):
            primary_phone = phones[0].get("number") if isinstance(phones[0], dict) else phones[0]

        # Build standardized response
        return {
            "emails": emails if isinstance(emails, list) else [],
            "primary_email": primary_email,
            "phones": phones if isinstance(phones, list) else [],
            "primary_phone": primary_phone,
            "website": data.get("website"),
            "employee_count": data.get("employee_count"),
            "annual_revenue": data.get("annual_revenue"),
            "years_in_business": data.get("years_in_business"),
            "business_type": data.get("business_type"),
            "sic_codes": data.get("sic_codes", []),
            "naics_codes": data.get("naics_codes", []),
            "data_axle_id": data.get("business_id"),
            "match_confidence": data.get("match_confidence", 0),
        }

    async def enrich(self, domain: str) -> Optional[Dict[str, Any]]:
        """
        Enrich company data by domain (PRD v1.2 requirement)

        Args:
            domain: Company domain (e.g. example.com)

        Returns:
            Enrichment data with email if available
        """
        if not domain:
            return None

        params = {"domain": domain, "fields": "email,phone,employees,revenue"}

        try:
            # Use GET /v1/companies/enrich endpoint
            response = await self._get("/companies/enrich", params=params)

            if not response or "data" not in response:
                return None

            data = response.get("data", {})

            # Transform to match expected format
            return {
                "email": data.get("primary_email") or data.get("email"),
                "phone": data.get("primary_phone") or data.get("phone"),
                "employee_count": data.get("employees"),
                "annual_revenue": data.get("revenue"),
                "data_axle_id": data.get("id"),
            }

        except Exception as e:
            logger.error(f"Data Axle enrichment failed for {domain}: {e}")
            return None

    async def verify_api_key(self) -> bool:
        """
        Verify API key is valid

        Returns:
            True if API key is valid

        Raises:
            AuthenticationError: If API key is invalid
        """
        try:
            # Make a lightweight test request
            response = await self._get("/account/status")
            return response.get("status") == "active"
        except Exception as e:
            if "401" in str(e) or "403" in str(e):
                raise AuthenticationError("dataaxle", "Invalid API key")
            raise

    async def _get(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make GET request using base client or test client"""
        if self._client:
            # Test mode - use injected client
            response = await self._client.get(endpoint, headers=self._get_headers(), **kwargs)
            return response.json()
        else:
            # Production mode - use base client's make_request
            return await self.make_request("GET", endpoint, **kwargs)

    async def _post(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make POST request using base client or test client"""
        if self._client:
            # Test mode - use injected client
            response = await self._client.post(endpoint, headers=self._get_headers(), **kwargs)
            return response.json()
        else:
            # Production mode - use base client's make_request
            return await self.make_request("POST", endpoint, **kwargs)
