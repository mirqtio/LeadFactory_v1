"""
Assessment Coordinator v2 for PRD v1.2
Coordinates the 7-assessor stack with proper timeout and error handling
"""
import asyncio
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Set
from decimal import Decimal

from d3_assessment.assessors import ASSESSOR_REGISTRY
from d3_assessment.models import AssessmentResult as AssessmentResultModel
from core.logging import get_logger
from database.session import get_db

logger = get_logger(__name__, domain="d3")


class AssessmentCoordinatorV2:
    """
    Coordinates PRD v1.2 assessment stack:
    - PageSpeed
    - BeautifulSoup
    - SEMrush
    - YelpSearchFields
    - GBPProfile
    - ScreenshotOne
    - GPT-4o Vision
    """

    # PRD v1.2 default assessors
    DEFAULT_ASSESSORS = [
        "pagespeed",
        "beautifulsoup",
        "semrush",
        "yelp_fields",
        "gbp_profile",
        "screenshot",
        "vision",
    ]

    def __init__(self, max_concurrent: int = 3):
        """Initialize coordinator with assessor instances"""
        self.max_concurrent = max_concurrent
        self.assessors = {}

        # Initialize available assessors
        for name, assessor_class in ASSESSOR_REGISTRY.items():
            try:
                assessor = assessor_class()
                if assessor.is_available():
                    self.assessors[name] = assessor
                    logger.info(f"Initialized assessor: {name}")
                else:
                    logger.warning(f"Assessor {name} not available (missing API key?)")
            except Exception as e:
                logger.error(f"Failed to initialize assessor {name}: {e}")

    async def assess_business(
        self, business_data: Dict[str, Any], assessor_names: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Run assessments for a business

        Args:
            business_data: Business information including website URL
            assessor_names: List of assessors to run (defaults to all)

        Returns:
            Assessment results dictionary
        """
        if not assessor_names:
            assessor_names = self.DEFAULT_ASSESSORS

        # Filter to available assessors
        available_assessors = [
            name for name in assessor_names if name in self.assessors
        ]

        if not available_assessors:
            logger.error("No assessors available")
            return {
                "business_id": business_data.get("id"),
                "status": "failed",
                "error": "No assessors available",
            }

        # Get website URL
        url = business_data.get("website", "")
        if not url:
            return {
                "business_id": business_data.get("id"),
                "status": "failed",
                "error": "No website URL provided",
            }

        # Run assessments in parallel with semaphore
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def run_single_assessment(assessor_name: str) -> tuple:
            """Run a single assessment with error handling"""
            async with semaphore:
                try:
                    assessor = self.assessors[assessor_name]
                    logger.info(f"Running {assessor_name} for {url}")

                    # Run assessment with timeout
                    timeout = assessor.get_timeout()
                    result = await asyncio.wait_for(
                        assessor.assess(url, business_data), timeout=timeout
                    )

                    logger.info(f"Completed {assessor_name} for {url}")
                    return assessor_name, result

                except asyncio.TimeoutError:
                    logger.error(f"{assessor_name} timed out for {url}")
                    return assessor_name, None
                except Exception as e:
                    logger.error(f"{assessor_name} failed for {url}: {e}")
                    return assessor_name, None

        # Execute all assessments
        tasks = [run_single_assessment(name) for name in available_assessors]
        results = await asyncio.gather(*tasks)

        # Process results
        assessment_data = {}
        total_cost = 0.0
        successful_count = 0

        for assessor_name, result in results:
            if result:
                # Merge assessment data
                assessment_data.update(result.data)
                total_cost += result.cost
                successful_count += 1

        # Save to database
        await self._save_assessment_results(
            business_data=business_data,
            assessment_data=assessment_data,
            total_cost=total_cost,
        )

        return {
            "business_id": business_data.get("id"),
            "url": url,
            "status": "completed" if successful_count > 0 else "failed",
            "assessments_run": len(available_assessors),
            "assessments_successful": successful_count,
            "total_cost": total_cost,
            "data": assessment_data,
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def _save_assessment_results(
        self,
        business_data: Dict[str, Any],
        assessment_data: Dict[str, Any],
        total_cost: float,
    ):
        """Save assessment results to database"""
        try:
            async with get_db() as db:
                # Check if assessment already exists
                existing = await db.fetchone(
                    """
                    SELECT id FROM d3_assessment_results 
                    WHERE business_id = $1 
                    ORDER BY created_at DESC 
                    LIMIT 1
                    """,
                    business_data.get("id"),
                )

                if existing:
                    # Update existing record
                    await db.execute(
                        """
                        UPDATE d3_assessment_results 
                        SET 
                            pagespeed_json = $2,
                            bsoup_json = $3,
                            semrush_json = $4,
                            yelp_json = $5,
                            gbp_json = $6,
                            screenshot_url = $7,
                            vision_scores_json = $8,
                            vision_warnings = $9,
                            vision_quickwins = $10,
                            total_cost_usd = $11,
                            updated_at = NOW()
                        WHERE id = $1
                        """,
                        existing["id"],
                        assessment_data.get("pagespeed_json"),
                        assessment_data.get("bsoup_json"),
                        assessment_data.get("semrush_json"),
                        assessment_data.get("yelp_json"),
                        assessment_data.get("gbp_json"),
                        assessment_data.get("screenshot_url"),
                        assessment_data.get("visual_scores_json"),
                        assessment_data.get("visual_warnings"),
                        assessment_data.get("visual_quickwins"),
                        Decimal(str(total_cost)),
                    )
                else:
                    # Create new record
                    await db.execute(
                        """
                        INSERT INTO d3_assessment_results (
                            id, business_id, url, domain,
                            pagespeed_json, bsoup_json, semrush_json,
                            yelp_json, gbp_json, screenshot_url,
                            vision_scores_json, vision_warnings, vision_quickwins,
                            total_cost_usd, status, assessment_type,
                            created_at, updated_at
                        ) VALUES (
                            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                            $11, $12, $13, $14, $15, $16, NOW(), NOW()
                        )
                        """,
                        str(uuid.uuid4()),
                        business_data.get("id"),
                        business_data.get("website"),
                        self._extract_domain(business_data.get("website", "")),
                        assessment_data.get("pagespeed_json"),
                        assessment_data.get("bsoup_json"),
                        assessment_data.get("semrush_json"),
                        assessment_data.get("yelp_json"),
                        assessment_data.get("gbp_json"),
                        assessment_data.get("screenshot_url"),
                        assessment_data.get("visual_scores_json"),
                        assessment_data.get("visual_warnings"),
                        assessment_data.get("visual_quickwins"),
                        Decimal(str(total_cost)),
                        "COMPLETED",
                        "FULL_AUDIT",
                    )

        except Exception as e:
            logger.error(f"Failed to save assessment results: {e}")

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL"""
        from urllib.parse import urlparse

        try:
            return urlparse(url).netloc.replace("www.", "")
        except:
            return ""

    async def assess_batch(
        self,
        businesses: List[Dict[str, Any]],
        assessor_names: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Assess multiple businesses

        Args:
            businesses: List of business data dictionaries
            assessor_names: Assessors to run

        Returns:
            List of assessment results
        """
        tasks = [
            self.assess_business(business, assessor_names) for business in businesses
        ]

        return await asyncio.gather(*tasks)
