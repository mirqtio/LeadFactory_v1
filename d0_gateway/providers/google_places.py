"""
Google Places API client for business profile data
PRD v1.2 - Get business hours and additional metadata

Cost: $0.002 per place details call
"""
from decimal import Decimal
from typing import Any, Dict, Optional

from ..base import BaseAPIClient


class GooglePlacesClient(BaseAPIClient):
    """Google Places API client for business data"""

    def __init__(self, api_key: Optional[str] = None, allow_test_mode: bool = False):
        from core.config import get_settings

        settings = get_settings()

        # Check if GBP is enabled (bypass for testing or when using stubs in test environment)
        if (
            not settings.enable_gbp
            and not (settings.environment == "test" and settings.use_stubs)
            and not allow_test_mode
        ):
            raise RuntimeError("GBP client initialized but ENABLE_GBP=false")

        # Set base URL based on stub configuration
        if settings.use_stubs:
            self.base_url = f"{settings.stub_base_url}/maps/api/place"
        else:
            self.base_url = "https://maps.googleapis.com/maps/api/place"

        super().__init__(provider="google_places", api_key=api_key)

    def _get_base_url(self) -> str:
        """Get Google Places API base URL"""
        return self.base_url

    def _get_headers(self) -> Dict[str, str]:
        """Google Places uses API key in URL params, not headers"""
        return {
            "Accept": "application/json",
        }

    def get_rate_limit(self) -> Dict[str, int]:
        """Get Google Places rate limit configuration"""
        return {
            "daily_limit": 25000,  # Standard quota
            "daily_used": 0,
            "burst_limit": 50,
            "window_seconds": 1,
        }

    def calculate_cost(self, operation: str, **kwargs) -> Decimal:
        """
        Calculate cost for Google Places operations

        Place Details: $0.017 per call (we'll use $0.002 for PRD v1.2)
        Find Place: $0.017 per call
        """
        if "details" in operation or "details/json" in operation:
            return Decimal("0.002")
        elif "findplacefromtext" in operation:
            return Decimal("0.017")
        else:
            return Decimal("0.000")

    async def find_place(self, query: str, fields: Optional[list] = None) -> Optional[Dict[str, Any]]:
        """
        Find a place by text query

        Args:
            query: Business name and/or address
            fields: Fields to return (default: place_id, name, formatted_address)

        Returns:
            Place data or None
        """
        if not fields:
            fields = ["place_id", "name", "formatted_address"]

        params = {
            "input": query,
            "inputtype": "textquery",
            "fields": ",".join(fields),
            "key": self.api_key,
        }

        response = await self.make_request("GET", "/findplacefromtext/json", params=params)

        if response and response.get("candidates"):
            return response["candidates"][0]
        return None

    async def get_place_details(self, place_id: str, fields: Optional[list] = None) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a place

        Args:
            place_id: Google Place ID
            fields: Fields to return

        Returns:
            Place details or None
        """
        if not fields:
            fields = [
                "name",
                "formatted_address",
                "formatted_phone_number",
                "website",
                "opening_hours",
                "business_status",
                "rating",
                "user_ratings_total",
                "types",
            ]

        params = {"place_id": place_id, "fields": ",".join(fields), "key": self.api_key}

        response = await self.make_request("GET", "/details/json", params=params)

        # Handle error responses
        if response and response.get("status") != "OK":
            return {"error": response.get("error_message", "Unknown error"), "status": response.get("status")}

        if response and response.get("result"):
            result = response["result"]

            # Check for missing hours as per PRD
            missing_hours = not result.get("opening_hours") or not result["opening_hours"].get("weekday_text")

            return {**result, "missing_hours": missing_hours}

        return None

    async def search_business(
        self, name: str, address: Optional[str] = None, phone: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Search for a business and get its details

        Args:
            name: Business name
            address: Optional address
            phone: Optional phone number

        Returns:
            Business details with missing_hours flag
        """
        # Build search query
        query_parts = [name]
        if address:
            query_parts.append(address)

        query = " ".join(query_parts)

        # Find the place
        place = await self.find_place(query)
        if not place or not place.get("place_id"):
            return None

        # Get detailed information
        details = await self.get_place_details(place["place_id"])

        return details
