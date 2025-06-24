"""
SEMrush assessor for domain SEO metrics
PRD v1.2 - Extract domain overview with organic keywords

Timeout: 5s
Cost: $0.010 per assessment
Output: semrush_json column
"""
from typing import Dict, Any, Optional
from urllib.parse import urlparse

from d3_assessment.assessors.base import BaseAssessor, AssessmentResult
from d3_assessment.models import AssessmentType
from d3_assessment.exceptions import AssessmentError, AssessmentTimeoutError
from d0_gateway.providers.semrush import SEMrushClient
from d0_gateway.factory import create_client
from core.logging import get_logger
from core.config import settings

logger = get_logger(__name__, domain="d3")


class SEMrushAssessor(BaseAssessor):
    """Extract SEO metrics using SEMrush API"""

    def __init__(self):
        super().__init__()
        self.timeout = 5  # 5 second timeout as per PRD
        self._client = None

    @property
    def assessment_type(self) -> AssessmentType:
        return AssessmentType.SEO_ANALYSIS

    async def _get_client(self) -> SEMrushClient:
        """Get or create SEMrush client"""
        if not self._client:
            self._client = create_client("semrush")
        return self._client

    async def assess(self, url: str, business_data: Dict[str, Any]) -> AssessmentResult:
        """
        Get domain SEO metrics from SEMrush

        Args:
            url: Website URL to analyze
            business_data: Business information (includes lead_id for cost tracking)

        Returns:
            AssessmentResult with semrush_json data
        """
        try:
            # Extract domain from URL
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.replace("www.", "")

            if not domain:
                return AssessmentResult(
                    assessment_type=self.assessment_type,
                    status="failed",
                    error_message="Invalid URL - no domain found",
                )

            # Get SEMrush client
            client = await self._get_client()

            # Get domain overview
            semrush_data = await client.get_domain_overview(
                domain=domain, lead_id=business_data.get("id")
            )

            if not semrush_data:
                return AssessmentResult(
                    assessment_type=self.assessment_type,
                    status="completed",
                    data={
                        "semrush_json": {
                            "domain": domain,
                            "organic_keywords": 0,
                            "organic_traffic": 0,
                            "error": "No data available for domain",
                        }
                    },
                    metrics={"domain_analyzed": domain},
                )

            # Add domain to the data
            semrush_data["domain"] = domain

            # Extract key metrics for scoring
            organic_keywords = semrush_data.get("organic_keywords", 0)
            organic_traffic = semrush_data.get("organic_traffic", 0)

            return AssessmentResult(
                assessment_type=self.assessment_type,
                status="completed",
                data={
                    "semrush_json": semrush_data,
                    "organic_keywords": organic_keywords,  # For easy access in scoring
                    "organic_traffic": organic_traffic,
                },
                metrics={
                    "domain_analyzed": domain,
                    "organic_keywords_count": organic_keywords,
                    "monthly_organic_traffic": organic_traffic,
                    "api_cost_usd": 0.010,
                },
                cost=0.010,  # $0.010 per assessment
            )

        except AssessmentTimeoutError:
            raise
        except Exception as e:
            logger.error(f"SEMrush assessment failed for {url}: {e}")

            # Return partial result with error
            return AssessmentResult(
                assessment_type=self.assessment_type,
                status="completed",
                data={
                    "semrush_json": {
                        "error": str(e),
                        "domain": urlparse(url).netloc.replace("www.", ""),
                        "organic_keywords": 0,
                        "organic_traffic": 0,
                    }
                },
                error_message=f"SEMrush API error: {str(e)}",
            )

    def calculate_cost(self) -> float:
        """SEMrush costs $0.010 per domain overview"""
        return 0.010

    def is_available(self) -> bool:
        """Check if SEMrush is available"""
        return bool(settings.semrush_api_key) or settings.use_stubs
