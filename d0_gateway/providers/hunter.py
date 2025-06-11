"""
Hunter.io Email Finder API client
Phase 0.5 - Task GW-03

Provides email finding as a fallback when Data Axle returns no email addresses
"""
import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

from d0_gateway.base import BaseAPIClient
from d0_gateway.exceptions import (
    APIProviderError,
    AuthenticationError,
    RateLimitExceededError,
)
from core.exceptions import ValidationError

logger = logging.getLogger(__name__)


class HunterClient(BaseAPIClient):
    """
    Hunter.io Email Finder API client
    
    Implements GET /v2/email-finder endpoint for finding email addresses
    when Data Axle doesn't provide any.
    """
    
    def __init__(self, api_key: str, **kwargs):
        """
        Initialize Hunter client
        
        Args:
            api_key: Hunter.io API key
            **kwargs: Additional configuration
        """
        # Store base_url before calling parent init
        self.base_url = kwargs.get("base_url", "https://api.hunter.io/v2")
        self.timeout = kwargs.get("timeout", 30)
        self.max_retries = kwargs.get("max_retries", 3)
        
        # Call parent constructor with required args only
        super().__init__(
            provider="hunter",
            api_key=api_key,
            base_url=self.base_url,
        )
        
        # Set rate limit from config (30/min as per PRD)
        from core.config import settings
        self._rate_limit = settings.hunter_rate_limit_per_min
        
        # Create HTTP client if needed (for compatibility with tests)
        self._client = None
        
    def _get_base_url(self) -> str:
        """Get the base URL for Hunter API"""
        return self.base_url
        
    def get_rate_limit(self) -> Dict[str, int]:
        """Get rate limit configuration for Hunter"""
        return {
            "requests_per_minute": self._rate_limit,
            "requests_per_hour": self._rate_limit * 60,
            "requests_per_day": 25,  # Hunter.io has a 25/day limit on free tier
        }
        
    def calculate_cost(self, operation: str, **kwargs) -> Decimal:
        """Calculate cost for Hunter operations"""
        if operation == "find_email":
            # $0.01 per email found
            return Decimal("0.01")
        return Decimal("0.00")
        
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for Hunter API requests"""
        return {
            "Accept": "application/json",
        }
        
    async def find_email(self, company_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Find email addresses for a company
        
        Args:
            company_data: Company information for email finding
                - domain: Company domain (required if no company name)
                - company: Company name (required if no domain)
                - first_name: First name for pattern matching
                - last_name: Last name for pattern matching
                - lead_id: Lead ID for cost tracking
                
        Returns:
            Email data if found, None otherwise
            
        Raises:
            APIProviderError: For API communication errors
            RateLimitExceededError: If rate limit exceeded
            ValidationError: For invalid input data
        """
        # Validate required fields
        if not company_data.get("domain") and not company_data.get("company"):
            raise ValidationError("Either domain or company name is required for email finding")
            
        # Prepare request parameters
        params = {
            "api_key": self.api_key,
        }
        
        if company_data.get("domain"):
            params["domain"] = company_data["domain"]
        else:
            params["company"] = company_data["company"]
            
        if company_data.get("first_name"):
            params["first_name"] = company_data["first_name"]
            
        if company_data.get("last_name"):
            params["last_name"] = company_data["last_name"]
        
        try:
            # Make API call
            response = await self._get("/email-finder", params=params)
            
            if not response:
                logger.warning(
                    f"No email found for company: {company_data.get('company')} / {company_data.get('domain')}"
                )
                return None
                
            # Extract data
            data = response.get("data", {})
            
            if not data.get("email"):
                return None
                
            # Log successful find
            logger.info(
                f"Email found for {company_data.get('company', company_data.get('domain'))} - "
                f"email: {data.get('email')}, "
                f"confidence: {data.get('score', 0)}"
            )
            
            # Emit cost for successful email find (Phase 0.5 requirement)
            self.emit_cost(
                lead_id=company_data.get("lead_id"),
                cost_usd=0.01,  # $0.01 per email found
                operation="find_email",
                metadata={
                    "confidence": data.get("score", 0),
                    "email": data.get("email"),
                    "domain": data.get("domain"),
                }
            )
            
            # Transform to standard format
            return self._transform_response(data)
            
        except Exception as e:
            if "429" in str(e) or "rate_limit" in str(e).lower():
                raise RateLimitExceededError("hunter", "api_calls")
            elif "401" in str(e) or "403" in str(e):
                raise AuthenticationError("hunter", str(e))
            else:
                raise APIProviderError("hunter", str(e))
                
    def _transform_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform Hunter response to standard format
        
        Args:
            data: Raw Hunter response
            
        Returns:
            Standardized email data
        """
        # Build standardized response
        return {
            "email": data.get("email"),
            "confidence": data.get("score", 0),
            "first_name": data.get("first_name"),
            "last_name": data.get("last_name"),
            "position": data.get("position"),
            "twitter": data.get("twitter"),
            "linkedin": data.get("linkedin_url"),
            "sources": data.get("sources", []),
            "hunter_domain": data.get("domain"),
        }
        
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
            response = await self._get("/account", params={"api_key": self.api_key})
            return response.get("data", {}).get("email") is not None
        except Exception as e:
            if "401" in str(e) or "403" in str(e):
                raise AuthenticationError("hunter", "Invalid API key")
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