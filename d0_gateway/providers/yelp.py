"""
Yelp Fusion API v3 client implementation
"""
from decimal import Decimal
from typing import Any, Dict, List, Optional

from ..base import BaseAPIClient


class YelpClient(BaseAPIClient):
    """Yelp Fusion API v3 client"""

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(provider="yelp", api_key=api_key)

    def _get_base_url(self) -> str:
        """Get Yelp API base URL"""
        return "https://api.yelp.com"

    def _get_headers(self) -> Dict[str, str]:
        """Get Yelp API headers"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def get_rate_limit(self) -> Dict[str, int]:
        """Get Yelp rate limit configuration"""
        return {
            "daily_limit": 5000,
            "daily_used": 0,  # Would be fetched from Redis in real implementation
            "burst_limit": 10,
            "window_seconds": 1,
        }

    def calculate_cost(self, operation: str, **kwargs) -> Decimal:
        """
        Calculate cost for Yelp API operations

        Yelp API is free up to 5,000 calls/day
        Beyond that, estimated at $0.001 per call
        """
        if operation.startswith("GET:/v3/businesses/search"):
            # Free tier - no cost
            return Decimal("0.000")
        elif operation.startswith("GET:/v3/businesses/"):
            # Business details - free tier
            return Decimal("0.000")
        else:
            # Other operations - minimal cost
            return Decimal("0.001")

    async def search_businesses(
        self,
        location: str,
        categories: Optional[str] = None,
        term: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        radius: Optional[int] = None,
        price: Optional[str] = None,
        open_now: Optional[bool] = None,
        sort_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Search for businesses on Yelp

        Args:
            location: Location to search (required)
            categories: Business categories to filter by
            term: Search term (e.g. "food", "restaurants")
            limit: Number of results to return (max 50)
            offset: Offset for pagination
            radius: Search radius in meters (max 40000)
            price: Price levels (1, 2, 3, 4 or combinations like "1,2")
            open_now: Filter for businesses open now
            sort_by: Sort order (best_match, rating, review_count, distance)

        Returns:
            Dict containing businesses list and metadata
        """
        params = {
            "location": location,
            "limit": min(limit, 50),  # Yelp max is 50
            "offset": offset,
        }

        # Add optional parameters
        if categories:
            params["categories"] = categories
        if term:
            params["term"] = term
        if radius:
            params["radius"] = min(radius, 40000)  # Yelp max is 40km
        if price:
            params["price"] = price
        if open_now is not None:
            params["open_now"] = open_now
        if sort_by:
            params["sort_by"] = sort_by

        return await self.make_request("GET", "/v3/businesses/search", params=params)

    async def get_business_details(self, business_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific business

        Args:
            business_id: Yelp business ID

        Returns:
            Dict containing detailed business information
        """
        return await self.make_request("GET", f"/v3/businesses/{business_id}")

    async def get_business_reviews(
        self, business_id: str, locale: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get reviews for a specific business

        Args:
            business_id: Yelp business ID
            locale: Locale for reviews (e.g. 'en_US')

        Returns:
            Dict containing business reviews
        """
        params = {}
        if locale:
            params["locale"] = locale

        return await self.make_request(
            "GET", f"/v3/businesses/{business_id}/reviews", params=params
        )

    async def search_businesses_by_phone(self, phone: str) -> Dict[str, Any]:
        """
        Search for businesses by phone number

        Args:
            phone: Phone number to search for

        Returns:
            Dict containing business matches
        """
        return await self.make_request(
            "GET", "/v3/businesses/search/phone", params={"phone": phone}
        )

    async def get_autocomplete(
        self,
        text: str,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Get autocomplete suggestions

        Args:
            text: Text to autocomplete
            latitude: Latitude for location-based suggestions
            longitude: Longitude for location-based suggestions

        Returns:
            Dict containing autocomplete suggestions
        """
        params = {"text": text}

        if latitude is not None and longitude is not None:
            params["latitude"] = latitude
            params["longitude"] = longitude

        return await self.make_request("GET", "/v3/autocomplete", params=params)

    async def batch_search_locations(
        self,
        locations: List[str],
        categories: Optional[str] = None,
        limit_per_location: int = 50,
    ) -> Dict[str, Any]:
        """
        Search multiple locations efficiently

        Args:
            locations: List of locations to search
            categories: Business categories to filter by
            limit_per_location: Results per location

        Returns:
            Dict containing results for all locations
        """
        results = {}

        for location in locations:
            try:
                result = await self.search_businesses(
                    location=location, categories=categories, limit=limit_per_location
                )
                results[location] = result
            except Exception as e:
                self.logger.error(f"Failed to search location {location}: {e}")
                results[location] = {"error": str(e), "businesses": []}

        return {
            "locations": results,
            "total_locations": len(locations),
            "successful_locations": len(
                [r for r in results.values() if "error" not in r]
            ),
        }
