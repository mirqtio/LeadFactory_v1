"""
Google Places API client for business data
"""
import logging
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from d0_gateway.base import BaseAPIClient
from d0_gateway.exceptions import APIProviderError

logger = logging.getLogger(__name__)


class GooglePlacesClient(BaseAPIClient):
    """
    Google Places API client for business search and details
    
    Uses Places API (New) for better search capabilities
    """
    
    def __init__(self, api_key: str, **kwargs):
        """
        Initialize Google Places client
        
        Args:
            api_key: Google API key with Places API enabled
            **kwargs: Additional configuration
        """
        base_url = kwargs.get("base_url", "https://maps.googleapis.com/maps/api/place")
        
        super().__init__(
            provider="google_places",
            api_key=api_key,
            base_url=base_url,
        )
        
        self.timeout = kwargs.get("timeout", 30)
        
    def _get_base_url(self) -> str:
        """Get base URL"""
        return self.base_url
        
    def _get_headers(self) -> Dict[str, str]:
        """Get headers"""
        return {
            "Content-Type": "application/json",
            "User-Agent": "LeadFactory/1.0"
        }
        
    def get_rate_limit(self) -> Dict[str, int]:
        """Get rate limit configuration"""
        return {
            "daily_limit": 10000,
            "daily_used": 0,
            "burst_limit": 50,
            "window_seconds": 1,
        }
        
    def calculate_cost(self, operation: str, **kwargs) -> float:
        """Calculate cost for Google Places operations"""
        # Pricing as of 2024
        if "textsearch" in operation:
            return 0.032  # $32 per 1000 requests
        elif "details" in operation:
            return 0.017  # $17 per 1000 requests
        elif "findplace" in operation:
            return 0.017
        elif "nearbysearch" in operation:
            return 0.032
        else:
            return 0.02  # Default
        
    async def search_businesses(
        self,
        query: str,
        location: Optional[str] = None,
        radius: int = 50000,  # 50km default
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Search for businesses using text search
        
        Args:
            query: Search query (business name)
            location: Location bias (lat,lng or address)
            radius: Search radius in meters
            **kwargs: Additional parameters
            
        Returns:
            List of place results
        """
        params = {
            "query": query,
            "key": self.api_key,
            "type": kwargs.get("type", "establishment"),
            "language": kwargs.get("language", "en"),
        }
        
        if location:
            params["location"] = location
            params["radius"] = radius
            
        try:
            response = await self.make_request(
                method="GET",
                endpoint="/textsearch/json",
                params=params
            )
            
            if response.get("status") != "OK":
                logger.warning(f"Places search failed: {response.get('status')}")
                return []
                
            results = response.get("results", [])
            logger.info(f"Found {len(results)} places for query: {query}")
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to search places: {str(e)}")
            raise
            
    async def get_place_details(
        self,
        place_id: str,
        fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Get detailed information about a place
        
        Args:
            place_id: Google Place ID
            fields: Specific fields to retrieve (billing optimization)
            
        Returns:
            Place details
        """
        if not fields:
            # Default fields for business enrichment
            fields = [
                "name",
                "formatted_address",
                "formatted_phone_number",
                "website",
                "rating",
                "user_ratings_total",
                "business_status",
                "opening_hours",
                "types",
                "url",  # Google Maps URL
                "vicinity",
                "price_level"
            ]
            
        params = {
            "place_id": place_id,
            "fields": ",".join(fields),
            "key": self.api_key
        }
        
        try:
            response = await self.make_request(
                method="GET",
                endpoint="/details/json",
                params=params
            )
            
            if response.get("status") != "OK":
                logger.warning(f"Place details failed: {response.get('status')}")
                return {}
                
            result = response.get("result", {})
            logger.info(f"Retrieved details for place: {result.get('name', place_id)}")
            
            # Emit cost for successful place details
            self.emit_cost(
                lead_id=kwargs.get("lead_id"),
                campaign_id=kwargs.get("campaign_id"),
                cost_usd=0.002,  # $0.002 per place details call as per PRD
                operation="place_details",
                metadata={
                    "place_id": place_id,
                    "place_name": result.get("name"),
                    "fields": fields
                }
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get place details: {str(e)}")
            raise
            
    async def find_place(
        self,
        input_text: str,
        input_type: str = "textquery",
        fields: Optional[List[str]] = None,
        location_bias: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Find a single place from text query (best match)
        
        Args:
            input_text: Query text (name, address, or phone)
            input_type: Type of input (textquery or phonenumber)
            fields: Fields to return
            location_bias: Location to bias results
            
        Returns:
            Best matching place or None
        """
        if not fields:
            fields = ["place_id", "name", "formatted_address", "types"]
            
        params = {
            "input": input_text,
            "inputtype": input_type,
            "fields": ",".join(fields),
            "key": self.api_key
        }
        
        if location_bias:
            params["locationbias"] = location_bias
            
        try:
            response = await self.make_request(
                method="GET",
                endpoint="/findplacefromtext/json",
                params=params
            )
            
            if response.get("status") != "OK":
                logger.warning(f"Find place failed: {response.get('status')}")
                return None
                
            candidates = response.get("candidates", [])
            if candidates:
                logger.info(f"Found place: {candidates[0].get('name', 'Unknown')}")
                
                # Emit cost for successful find place
                self.emit_cost(
                    lead_id=kwargs.get("lead_id"),
                    campaign_id=kwargs.get("campaign_id"),
                    cost_usd=0.002,  # $0.002 per find place call
                    operation="find_place",
                    metadata={
                        "input_text": input_text,
                        "place_name": candidates[0].get("name"),
                        "place_id": candidates[0].get("place_id")
                    }
                )
                
                return candidates[0]
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to find place: {str(e)}")
            raise
            
    async def search_nearby(
        self,
        location: str,
        radius: int = 1000,
        keyword: Optional[str] = None,
        type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for places near a location
        
        Args:
            location: Center point as "lat,lng"
            radius: Search radius in meters
            keyword: Keyword to filter results
            type: Place type to filter
            
        Returns:
            List of nearby places
        """
        params = {
            "location": location,
            "radius": radius,
            "key": self.api_key
        }
        
        if keyword:
            params["keyword"] = keyword
        if type:
            params["type"] = type
            
        try:
            response = await self.make_request(
                method="GET",
                endpoint="/nearbysearch/json",
                params=params
            )
            
            if response.get("status") != "OK":
                logger.warning(f"Nearby search failed: {response.get('status')}")
                return []
                
            results = response.get("results", [])
            logger.info(f"Found {len(results)} nearby places")
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to search nearby: {str(e)}")
            raise