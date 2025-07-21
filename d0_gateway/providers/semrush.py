"""
SEMrush API client for domain analytics
PRD v1.2 - SEO and domain metrics provider

Endpoint: /domain/overview
Cost: $0.010 per call
Daily quota: 1,000
"""

import logging
from decimal import Decimal
from typing import Any

from core.exceptions import ValidationError
from d0_gateway.base import BaseAPIClient
from d0_gateway.exceptions import APIProviderError, AuthenticationError, RateLimitExceededError

logger = logging.getLogger(__name__)


class SEMrushClient(BaseAPIClient):
    """
    SEMrush API client for domain analytics

    Provides domain overview with organic keywords count and other SEO metrics
    """

    def __init__(self, api_key: str, **kwargs):
        """
        Initialize SEMrush client

        Args:
            api_key: SEMrush API key
            **kwargs: Additional configuration
        """
        self.timeout = kwargs.get("timeout", 30)
        self.max_retries = kwargs.get("max_retries", 3)

        # Call parent constructor (will handle stub base_url automatically)
        super().__init__(
            provider="semrush",
            api_key=api_key,
            base_url=kwargs.get("base_url", "https://api.semrush.com"),
        )

        # Set daily quota from config
        from core.config import settings

        self._daily_quota = settings.semrush_daily_quota

        # Create HTTP client if needed (for compatibility with tests)
        self._client = None

    def _get_base_url(self) -> str:
        """Get the base URL for SEMrush API"""
        return self.base_url

    def get_rate_limit(self) -> dict[str, int]:
        """Get rate limit configuration for SEMrush"""
        return {
            "requests_per_minute": 100,  # SEMrush allows burst
            "requests_per_hour": 1000,
            "requests_per_day": self._daily_quota,
        }

    def calculate_cost(self, operation: str, **kwargs) -> Decimal:
        """Calculate cost for SEMrush operations"""
        if operation == "domain_overview":
            # $0.010 per domain overview as per PRD v1.2
            return Decimal("0.010")
        return Decimal("0.00")

    def _get_headers(self) -> dict[str, str]:
        """Get headers for SEMrush API requests"""
        return {
            "Accept": "application/json",
        }

    async def get_domain_overview(self, domain: str, lead_id: str | None = None) -> dict[str, Any] | None:
        """
        Get domain overview including organic keywords count

        Args:
            domain: Domain to analyze (e.g. example.com)
            lead_id: Lead ID for cost tracking

        Returns:
            Domain overview data or None if error

        Raises:
            APIProviderError: For API communication errors
            RateLimitExceededError: If rate limit exceeded
            ValidationError: For invalid input data
        """
        # Validate domain
        if not domain:
            raise ValidationError("Domain is required for SEMrush analysis")

        # Prepare request parameters
        params = {
            "key": self.api_key,
            "type": "domain_organic",
            "domain": domain,
            "database": "us",  # US database
            "display_limit": 1,  # We just need the summary
            "export_columns": "Or,Ot,Oc,Ad,At,Ac",  # Organic/Ads traffic and keywords
        }

        try:
            # Make API call - SEMrush uses a different endpoint structure
            response = await self._get("/", params=params)

            if not response:
                logger.warning(f"No data returned for domain: {domain}")
                return None

            # Parse SEMrush CSV-style response
            data = self._parse_semrush_response(response)

            if not data:
                return None

            # Add domain to the data
            data["domain"] = domain

            # Log successful analysis
            logger.info(
                f"Domain overview for {domain} - "
                f"organic_keywords: {data.get('organic_keywords', 0)}, "
                f"organic_traffic: {data.get('organic_traffic', 0)}"
            )

            # Emit cost for successful analysis
            self.emit_cost(
                lead_id=lead_id,
                cost_usd=0.010,  # $0.010 per overview
                operation="domain_overview",
                metadata={
                    "domain": domain,
                    "organic_keywords": data.get("organic_keywords", 0),
                    "organic_traffic": data.get("organic_traffic", 0),
                },
            )

            return data

        except Exception as e:
            if "429" in str(e) or "rate" in str(e).lower():
                raise RateLimitExceededError("semrush", "api_calls")
            if "401" in str(e) or "403" in str(e):
                raise AuthenticationError("semrush", str(e))
            raise APIProviderError("semrush", str(e))

    def _parse_semrush_response(self, response: Any) -> dict[str, Any]:
        """
        Parse SEMrush response (usually CSV format)

        Args:
            response: Raw SEMrush response

        Returns:
            Parsed domain data
        """
        # If response is already a dict (from stub), return it
        if isinstance(response, dict):
            return response

        # Parse CSV response
        try:
            lines = response.strip().split("\n")
            if len(lines) < 2:
                return None

            # Headers and data
            headers = lines[0].split(";")
            values = lines[1].split(";")

            # Map to dict
            data = dict(zip(headers, values, strict=False))

            # Transform to standard format
            return {
                "organic_keywords": int(data.get("Or", 0)),
                "organic_traffic": int(data.get("Ot", 0)),
                "organic_cost": float(data.get("Oc", 0)),
                "adwords_keywords": int(data.get("Ad", 0)),
                "adwords_traffic": int(data.get("At", 0)),
                "adwords_cost": float(data.get("Ac", 0)),
                "semrush_raw": data,
            }

        except Exception as e:
            logger.error(f"Failed to parse SEMrush response: {e}")
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
            response = await self.get_domain_overview("example.com")
            return response is not None
        except AuthenticationError:
            raise
        except Exception:
            # Other errors might just mean the domain has no data
            return True

    async def make_request(self, method: str, endpoint: str, **kwargs) -> Any:
        """
        Override to handle SEMrush CSV response format
        """
        # For SEMrush we need the raw text response, not JSON
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"

        # Use httpx directly to get text response
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.request(method, url, **kwargs)

            if response.status_code >= 400:
                error_msg = f"HTTP {response.status_code}: {response.text}"
                if response.status_code == 401:
                    raise AuthenticationError("semrush", error_msg)
                if response.status_code == 429:
                    raise RateLimitExceededError(
                        provider="semrush",
                        limit_type="daily",
                        retry_after=3600,
                    )
                raise APIProviderError("semrush", error_msg)

            # Return text for CSV parsing
            return response.text

    async def _get(self, endpoint: str, **kwargs) -> Any:
        """Make GET request using base client or test client"""
        if self._client:
            # Test mode - use injected client
            response = await self._client.get(endpoint, headers=self._get_headers(), **kwargs)
            return response.text if hasattr(response, "text") else response.json()
        # Production mode - use our custom make_request
        return await self.make_request("GET", endpoint, **kwargs)
