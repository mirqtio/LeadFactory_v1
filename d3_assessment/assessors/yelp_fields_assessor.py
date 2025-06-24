"""
Yelp Search Fields assessor
PRD v1.2 - Extract Yelp data WITHOUT making an API call

Timeout: 0s (instant - no API call)
Cost: Free
Output: yelp_json column with rating, review_count, price, categories
"""
from typing import Dict, Any, Optional, List

from d3_assessment.assessors.base import BaseAssessor, AssessmentResult
from d3_assessment.models import AssessmentType
from core.logging import get_logger

logger = get_logger(__name__, domain="d3")


class YelpSearchFieldsAssessor(BaseAssessor):
    """
    Extract Yelp search fields from existing business data
    NO EXTRA API CALL - uses data already fetched during sourcing
    """

    def __init__(self):
        super().__init__()
        self.timeout = 0  # Instant - no external calls

    @property
    def assessment_type(self) -> AssessmentType:
        return AssessmentType.BUSINESS_INFO

    async def assess(self, url: str, business_data: Dict[str, Any]) -> AssessmentResult:
        """
        Extract Yelp fields from existing business data

        Args:
            url: Website URL (not used for this assessor)
            business_data: Business information containing Yelp data

        Returns:
            AssessmentResult with yelp_json data
        """
        try:
            # Extract Yelp-specific fields from business data
            yelp_data = {
                "yelp_id": business_data.get("yelp_id"),
                "rating": float(business_data.get("rating", 0)),
                "review_count": int(business_data.get("user_ratings_total", 0)),
                "price": self._extract_price(business_data),
                "categories": self._extract_categories(business_data),
                "is_closed": business_data.get("business_status") != "OPERATIONAL",
                "phone": business_data.get("phone"),
                "display_phone": self._format_phone(business_data.get("phone")),
                "location": {
                    "address": business_data.get("address"),
                    "city": business_data.get("city"),
                    "state": business_data.get("state"),
                    "zip_code": business_data.get("zip_code"),
                    "country": "US",
                },
                "coordinates": {
                    "latitude": business_data.get("latitude"),
                    "longitude": business_data.get("longitude"),
                },
            }

            # Add raw data if available
            if "raw_data" in business_data and isinstance(
                business_data["raw_data"], dict
            ):
                raw_yelp = business_data["raw_data"].get("yelp_data", {})

                # Extract additional fields from raw data
                if raw_yelp:
                    yelp_data["transactions"] = raw_yelp.get("transactions", [])
                    yelp_data["hours"] = raw_yelp.get("hours", [])
                    yelp_data["photos"] = raw_yelp.get("photos", [])[
                        :3
                    ]  # Limit to 3 photos
                    yelp_data["url"] = raw_yelp.get("url")
                    yelp_data["is_claimed"] = raw_yelp.get("is_claimed", False)

            return AssessmentResult(
                assessment_type=self.assessment_type,
                status="completed",
                data={
                    "yelp_json": yelp_data,
                    "has_low_reviews": yelp_data["review_count"] < 5,  # For scoring
                    "rating_tier": self._calculate_rating_tier(yelp_data["rating"]),
                },
                metrics={
                    "review_count": yelp_data["review_count"],
                    "rating": yelp_data["rating"],
                    "categories_count": len(yelp_data["categories"]),
                },
            )

        except Exception as e:
            logger.error(f"Yelp fields extraction failed: {e}")

            # Return minimal data on error
            return AssessmentResult(
                assessment_type=self.assessment_type,
                status="completed",
                data={
                    "yelp_json": {
                        "error": str(e),
                        "yelp_id": business_data.get("yelp_id"),
                        "rating": 0,
                        "review_count": 0,
                        "categories": [],
                    }
                },
                error_message=f"Failed to extract Yelp fields: {str(e)}",
            )

    def _extract_price(self, business_data: Dict[str, Any]) -> str:
        """Extract price level as Yelp-style string ($, $$, etc.)"""
        price_level = business_data.get("price_level", 0)

        # Convert numeric price level to Yelp format
        price_map = {0: None, 1: "$", 2: "$$", 3: "$$$", 4: "$$$$"}

        return price_map.get(price_level)

    def _extract_categories(
        self, business_data: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """Extract categories in Yelp format"""
        categories = []

        # Get categories from business data
        raw_categories = business_data.get("categories", [])

        if isinstance(raw_categories, list):
            for cat in raw_categories:
                if isinstance(cat, str):
                    # Simple string category
                    categories.append(
                        {"alias": cat.lower().replace(" ", ""), "title": cat}
                    )
                elif isinstance(cat, dict):
                    # Already in dict format
                    categories.append(cat)

        # Add vertical as a category if not present
        vertical = business_data.get("vertical")
        if vertical and not any(c.get("alias") == vertical for c in categories):
            categories.append(
                {"alias": vertical, "title": vertical.replace("_", " ").title()}
            )

        return categories

    def _format_phone(self, phone: Optional[str]) -> str:
        """Format phone number for display"""
        if not phone:
            return ""

        # Remove non-numeric characters
        digits = "".join(c for c in phone if c.isdigit())

        # Format as US phone number if 10 digits
        if len(digits) == 10:
            return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
        elif len(digits) == 11 and digits[0] == "1":
            return f"+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}"

        return phone

    def _calculate_rating_tier(self, rating: float) -> str:
        """Calculate rating tier for analysis"""
        if rating >= 4.5:
            return "excellent"
        elif rating >= 4.0:
            return "good"
        elif rating >= 3.5:
            return "average"
        elif rating >= 3.0:
            return "below_average"
        else:
            return "poor"

    def calculate_cost(self) -> float:
        """Yelp fields extraction is free - no API call"""
        return 0.0

    def is_available(self) -> bool:
        """Always available - uses existing data"""
        return True
