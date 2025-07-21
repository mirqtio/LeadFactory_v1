"""Google Business Profile adapter for trust signal assessment."""

import logging
import os

from d0_gateway.factory import create_client
from d0_gateway.providers.google_places import GooglePlacesClient
from d3_assessment.audit_schema import AuditFinding, Evidence, FindingCategory, FindingSeverity
from d3_assessment.rubric import map_severity

logger = logging.getLogger(__name__)


class GBPAdapter:
    """
    Google Business Profile adapter for fetching business trust signals.

    Performs Place ID lookup then details call to get rating and review count.
    """

    def __init__(self, api_key: str | None = None):
        """Initialize GBP adapter."""
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("Google API key not configured")

        # Use factory to create client
        self._client = None

    def _get_client(self) -> GooglePlacesClient:
        """Get or create Google Places client."""
        if not self._client:
            self._client = create_client("google_places", api_key=self.api_key)
        return self._client

    async def fetch_business_profile(
        self,
        business_name: str,
        address: str | None = None,
        website: str | None = None,
    ) -> dict | None:
        """
        Fetch Google Business Profile data.

        Args:
            business_name: Name of the business
            address: Business address (optional)
            website: Business website (optional)

        Returns:
            Dict with place_id, rating, review_count, or None if not found
        """
        try:
            client = self._get_client()

            # First, find the place
            search_query = business_name
            if address:
                search_query += f" {address}"

            place_result = await client.find_place(query=search_query, fields=["place_id", "name", "formatted_address"])

            if not place_result or not place_result.get("place_id"):
                logger.warning(f"No GBP found for {business_name}")
                return None

            place_id = place_result["place_id"]

            # Get detailed info
            details = await client.get_place_details(
                place_id=place_id,
                fields=["rating", "user_ratings_total", "reviews", "opening_hours"],
            )

            if not details:
                return None

            return {
                "place_id": place_id,
                "rating": details.get("rating", 0),
                "review_count": details.get("user_ratings_total", 0),
                "has_hours": bool(details.get("opening_hours")),
                "name": details.get("name", business_name),
            }

        except Exception as e:
            logger.error(f"GBP fetch failed for {business_name}: {e}")
            return None

    def create_trust_finding(self, gbp_data: dict | None) -> AuditFinding | None:
        """
        Create an AuditFinding for trust signals based on GBP data.

        Args:
            gbp_data: Google Business Profile data or None

        Returns:
            AuditFinding with severity based on rating/reviews
        """
        if not gbp_data:
            # No GBP is itself a trust issue
            return AuditFinding(
                issue_id="no_gbp_profile",
                title="No Google Business Profile Found",
                description="Business lacks a Google Business Profile, missing out on local search visibility and trust signals.",
                severity=FindingSeverity.HIGH,
                category=FindingCategory.TRUST,
                evidence=[
                    Evidence(
                        type="Google Business Profile status",
                        value="Not found",
                    )
                ],
                effort_estimate="easy",
                conversion_impact=0.035,  # 3.5% impact
            )

        # Determine severity based on rating and review count
        rating = gbp_data.get("rating", 0)
        review_count = gbp_data.get("review_count", 0)

        # Use rubric to map severity
        raw_metric = {"name": "rating", "value": rating, "review_count": review_count}
        severity_level = map_severity("trust", raw_metric)

        # Convert numeric severity to enum
        severity_map = {
            1: FindingSeverity.LOW,
            2: FindingSeverity.MEDIUM,
            3: FindingSeverity.HIGH,
            4: FindingSeverity.CRITICAL,
        }
        severity = severity_map.get(severity_level, FindingSeverity.MEDIUM)

        # Create appropriate finding based on issues
        if review_count < 20 or rating < 4.0:
            title = "Weak Google Business Profile Presence"
            if review_count < 20 and rating < 4.0:
                description = f"Business has only {review_count} reviews with a {rating:.1f} star rating. Both metrics need improvement for better trust signals."
            elif review_count < 20:
                description = (
                    f"Business has only {review_count} reviews. More reviews needed to build trust and social proof."
                )
            else:
                description = f"Business rating of {rating:.1f} stars is below the 4.0 threshold. Higher ratings correlate with increased conversions."

            return AuditFinding(
                issue_id="weak_gbp_presence",
                title=title,
                description=description,
                severity=severity,
                category=FindingCategory.TRUST,
                evidence=[
                    Evidence(
                        type="Current rating",
                        value=f"{rating:.1f} stars",
                    ),
                    Evidence(
                        type="Review count",
                        value=str(review_count),
                    ),
                    Evidence(
                        type="Target rating",
                        value="4.0+ stars",
                    ),
                    Evidence(
                        type="Target reviews",
                        value="20+ reviews",
                    ),
                ],
                effort_estimate="moderate",
                conversion_impact=0.03,  # 3% impact
            )

        # Good GBP presence - still return as informational
        return AuditFinding(
            issue_id="strong_gbp_presence",
            title="Strong Google Business Profile",
            description=f"Business has {review_count} reviews with {rating:.1f} star rating. This provides good trust signals.",
            severity=FindingSeverity.LOW,
            category=FindingCategory.TRUST,
            evidence=[
                Evidence(
                    type="Current rating",
                    value=f"{rating:.1f} stars",
                ),
                Evidence(
                    type="Review count",
                    value=str(review_count),
                ),
            ],
            effort_estimate="easy",
            conversion_impact=0.005,  # 0.5% further improvement possible
        )
