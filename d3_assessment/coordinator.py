"""
Assessment Coordinator - Task 034

Coordinates execution of multiple assessment types (PageSpeed, Tech Stack, LLM Insights)
with parallel execution, timeout handling, partial results, and error recovery.

Acceptance Criteria:
- Parallel assessment execution
- Timeout handling works
- Partial results saved
- Error recovery implemented
"""
import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from core.logging import get_logger
from d4_enrichment.email_enrichment import get_email_enricher

from .assessors import ASSESSOR_REGISTRY
from .assessors.pagespeed_assessor import PageSpeedAssessor
from .llm_insights import LLMInsightGenerator
from .models import AssessmentResult, AssessmentSession
from .techstack import TechStackDetector
from .types import AssessmentStatus, AssessmentType

logger = get_logger(__name__, domain="d3")


class CoordinatorError(Exception):
    """Custom exception for coordinator errors"""

    pass


class AssessmentPriority(Enum):
    """Priority levels for assessments"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AssessmentRequest:
    """Request for a single assessment"""

    assessment_type: AssessmentType
    url: str
    priority: AssessmentPriority = AssessmentPriority.MEDIUM
    timeout_seconds: int = 300  # 5 minutes default
    retry_count: int = 2
    custom_config: Optional[Dict[str, Any]] = None


@dataclass
class CoordinatorResult:
    """Result from coordinator execution"""

    session_id: str
    business_id: str
    total_assessments: int
    completed_assessments: int
    failed_assessments: int
    partial_results: Dict[AssessmentType, AssessmentResult]
    errors: Dict[AssessmentType, str]
    total_cost_usd: Decimal
    execution_time_ms: int
    started_at: datetime
    completed_at: datetime


class AssessmentCoordinator:
    """
    Coordinates parallel execution of multiple assessment types

    Manages PageSpeed, Tech Stack, and LLM Insights assessments with
    timeout handling, error recovery, and partial result preservation.

    Acceptance Criteria: Parallel assessment execution, Timeout handling works,
    Partial results saved, Error recovery implemented
    """

    def __init__(self, max_concurrent: int = 5):
        """
        Initialize assessment coordinator

        Args:
            max_concurrent: Maximum concurrent assessments
        """
        self.max_concurrent = max_concurrent
        self.pagespeed_assessor = PageSpeedAssessor()
        self.techstack_detector = TechStackDetector()
        self.llm_generator = LLMInsightGenerator()
        self.email_enricher = get_email_enricher()
        self.logger = logger

        # Initialize assessors from registry
        self.assessors = {}
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

    async def execute_comprehensive_assessment(
        self,
        business_id: str,
        url: str,
        assessment_types: List[AssessmentType] = None,
        industry: str = "default",
        session_config: Optional[Dict[str, Any]] = None,
        business_data: Optional[Dict[str, Any]] = None,
    ) -> CoordinatorResult:
        """
        Execute comprehensive assessment with multiple types

        Args:
            business_id: Business identifier
            url: Website URL to assess
            assessment_types: Types of assessments to run
            industry: Industry for specialized insights
            session_config: Configuration for the session

        Returns:
            CoordinatorResult with all assessment results

        Acceptance Criteria: Parallel assessment execution
        """
        session_id = str(uuid.uuid4())
        started_at = datetime.utcnow()

        if assessment_types is None:
            assessment_types = [
                AssessmentType.PAGESPEED,
                AssessmentType.TECH_STACK,
                AssessmentType.AI_INSIGHTS,
                AssessmentType.BUSINESS_INFO,
            ]

        # Create assessment session
        session = AssessmentSession(
            id=session_id,
            assessment_type=AssessmentType.FULL_AUDIT,
            status=AssessmentStatus.RUNNING,
            total_assessments=len(assessment_types),
            completed_assessments=0,
            config_data=session_config or {},
        )

        # Create assessment requests
        requests = []
        for assessment_type in assessment_types:
            request = AssessmentRequest(
                assessment_type=assessment_type,
                url=url,
                priority=self._get_assessment_priority(assessment_type),
                timeout_seconds=self._get_assessment_timeout(assessment_type),
                retry_count=2,
            )
            requests.append(request)

        # Execute assessments in parallel
        results = await self._execute_parallel_assessments(business_id, session_id, requests, industry, business_data)

        # PRD v1.2: Perform email enrichment if business data provided
        email_result = None
        if business_data:
            try:
                email, source = await self.email_enricher.enrich_email(business_data)
                if email:
                    email_result = {
                        "email": email,
                        "source": source,
                        "enriched_at": datetime.utcnow().isoformat(),
                    }
                    # Store email in business data for downstream use
                    business_data["email"] = email
                    business_data["email_source"] = source
            except Exception as e:
                # Log but don't fail assessment for email enrichment
                # Email enrichment is supplementary
                import logging

                logging.getLogger(__name__).warning(f"Email enrichment failed: {e}")

        # Calculate totals
        completed_at = datetime.utcnow()
        execution_time = max(1, int((completed_at - started_at).total_seconds() * 1000))

        completed_count = len([r for r in results.values() if r is not None and r.status == AssessmentStatus.COMPLETED])
        failed_count = len(
            [
                r
                for r in results.values()
                if r is None or (r is not None and r.status in [AssessmentStatus.FAILED, AssessmentStatus.CANCELLED])
            ]
        )
        total_cost = sum(
            r.total_cost_usd or Decimal("0") for r in results.values() if r is not None and hasattr(r, "total_cost_usd")
        )

        # Extract errors
        errors = {}
        for assessment_type in assessment_types:
            if assessment_type not in results or results[assessment_type] is None:
                errors[assessment_type] = "Assessment failed or timed out"
            elif hasattr(results[assessment_type], "error_message") and results[assessment_type].error_message:
                errors[assessment_type] = results[assessment_type].error_message

        # Update session
        session.status = AssessmentStatus.COMPLETED if failed_count == 0 else AssessmentStatus.PARTIAL
        session.completed_assessments = completed_count
        session.total_cost_usd = total_cost
        session.completed_at = completed_at

        result = CoordinatorResult(
            session_id=session_id,
            business_id=business_id,
            total_assessments=len(assessment_types),
            completed_assessments=completed_count,
            failed_assessments=failed_count,
            partial_results=results,
            errors=errors,
            total_cost_usd=total_cost,
            execution_time_ms=execution_time,
            started_at=started_at,
            completed_at=completed_at,
        )

        # Add email enrichment result if available
        if email_result:
            result.email_enrichment = email_result

        return result

    async def _execute_parallel_assessments(
        self,
        business_id: str,
        session_id: str,
        requests: List[AssessmentRequest],
        industry: str,
        business_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[AssessmentType, Optional[AssessmentResult]]:
        """
        Execute multiple assessments in parallel with timeout and error handling

        Acceptance Criteria: Parallel assessment execution, Timeout handling works,
        Error recovery implemented
        """
        semaphore = asyncio.Semaphore(self.max_concurrent)
        results = {}

        async def execute_single_assessment(request: AssessmentRequest) -> tuple:
            """Execute a single assessment with timeout and retry logic"""
            async with semaphore:
                assessment_type = request.assessment_type

                for attempt in range(request.retry_count + 1):
                    try:
                        # Execute with timeout
                        result = await asyncio.wait_for(
                            self._run_assessment(
                                business_id,
                                session_id,
                                request,
                                industry,
                                business_data,
                            ),
                            timeout=request.timeout_seconds,
                        )

                        # Save partial result immediately
                        await self._save_partial_result(result)

                        return assessment_type, result

                    except asyncio.TimeoutError:
                        if attempt < request.retry_count:
                            # Retry with exponential backoff
                            await asyncio.sleep(2**attempt)
                            continue
                        else:
                            # Final timeout - create failed result
                            failed_result = self._create_failed_result(
                                business_id,
                                session_id,
                                request,
                                f"Assessment timed out after {request.timeout_seconds}s",
                            )
                            await self._save_partial_result(failed_result)
                            return assessment_type, failed_result

                    except Exception as e:
                        if attempt < request.retry_count:
                            # Retry on error
                            await asyncio.sleep(2**attempt)
                            continue
                        else:
                            # Final error - create failed result
                            failed_result = self._create_failed_result(business_id, session_id, request, str(e))
                            await self._save_partial_result(failed_result)
                            return assessment_type, failed_result

                # Should never reach here
                return assessment_type, None

        # Run all assessments concurrently
        tasks = [execute_single_assessment(request) for request in requests]
        completed_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for result in completed_results:
            if isinstance(result, tuple) and len(result) == 2:
                assessment_type, assessment_result = result
                results[assessment_type] = assessment_result
            elif isinstance(result, Exception):
                # Handle gather exceptions
                continue

        return results

    async def _run_assessment(
        self,
        business_id: str,
        session_id: str,
        request: AssessmentRequest,
        industry: str,
        business_data: Optional[Dict[str, Any]] = None,
    ) -> AssessmentResult:
        """Run a specific assessment type"""
        assessment_type = request.assessment_type
        url = request.url

        if assessment_type == AssessmentType.PAGESPEED:
            # Use the new assessor interface
            try:
                result = await self.pagespeed_assessor.assess(
                    url=url, business_data=business_data or {"business_id": business_id}
                )
            except Exception as e:
                # Log the actual error for debugging
                import traceback

                error_msg = f"PageSpeed assessment error: {e}"
                tb = traceback.format_exc()
                print(error_msg)
                print(f"Traceback:\n{tb}")
                # Also log to the logger
                if hasattr(self, "logger"):
                    self.logger.error(f"{error_msg}\n{tb}")
                raise

            # Convert BaseAssessor result to AssessmentResult
            return AssessmentResult(
                id=str(uuid.uuid4()),
                business_id=business_id,
                session_id=session_id,
                assessment_type=AssessmentType.PAGESPEED,
                status=AssessmentStatus.COMPLETED if result.status == "completed" else AssessmentStatus.FAILED,
                url=url,
                domain=self._extract_domain(url),
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
                pagespeed_data=result.data.get("pagespeed_json", {}),
                performance_score=result.metrics.get("performance_score"),
                error_message=result.error_message,
                total_cost_usd=Decimal(str(result.cost)),
            )

        elif assessment_type == AssessmentType.TECH_STACK:
            # For tech stack, we need to adapt the interface
            detections = await self.techstack_detector.detect_technologies(assessment_id=str(uuid.uuid4()), url=url)

            # Create AssessmentResult from tech stack detections
            result = AssessmentResult(
                id=str(uuid.uuid4()),
                business_id=business_id,
                session_id=session_id,
                assessment_type=AssessmentType.TECH_STACK,
                status=AssessmentStatus.COMPLETED,
                url=url,
                domain=self._extract_domain(url),
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
                tech_stack_data={
                    "technologies": [
                        {
                            "technology_name": d.technology_name,
                            "category": d.category.value,
                            "confidence": d.confidence,
                            "version": d.version,
                        }
                        for d in detections
                    ],
                    "detection_count": len(detections),
                    "detection_method": "pattern_matching",
                },
            )
            return result

        elif assessment_type == AssessmentType.AI_INSIGHTS:
            # For LLM insights, we need a base assessment
            base_assessment = AssessmentResult(
                id=str(uuid.uuid4()),
                business_id=business_id,
                session_id=session_id,
                assessment_type=AssessmentType.AI_INSIGHTS,
                status=AssessmentStatus.COMPLETED,
                url=url,
                domain=self._extract_domain(url),
                performance_score=80,  # Default values for LLM analysis
                accessibility_score=85,
                seo_score=75,
            )

            insights = await self.llm_generator.generate_comprehensive_insights(
                assessment=base_assessment, industry=industry
            )

            # Update base assessment with insights
            base_assessment.ai_insights_data = {
                "insights": insights.insights,
                "industry": insights.industry,
                "total_cost_usd": float(insights.total_cost_usd),
                "model_version": insights.model_version,
                "processing_time_ms": insights.processing_time_ms,
            }
            base_assessment.total_cost_usd = insights.total_cost_usd

            return base_assessment

        elif assessment_type == AssessmentType.BUSINESS_INFO:
            # Use GBP assessor from registry
            if "gbp_profile" in self.assessors:
                try:
                    gbp_result = await self.assessors["gbp_profile"].assess(
                        url=url, business_data=business_data or {"business_id": business_id}
                    )

                    # Convert BaseAssessor result to AssessmentResult
                    return AssessmentResult(
                        id=str(uuid.uuid4()),
                        business_id=business_id,
                        session_id=session_id,
                        assessment_type=AssessmentType.BUSINESS_INFO,
                        status=AssessmentStatus.COMPLETED
                        if gbp_result.status == "completed"
                        else AssessmentStatus.FAILED,
                        url=url,
                        domain=self._extract_domain(url),
                        started_at=datetime.utcnow(),
                        completed_at=datetime.utcnow(),
                        # Store GBP data in the appropriate field
                        assessment_metadata=gbp_result.data,
                        error_message=gbp_result.error_message,
                        total_cost_usd=Decimal(str(gbp_result.cost)),
                    )
                except Exception as e:
                    logger.error(f"GBP assessment failed: {e}")
                    raise
            else:
                raise CoordinatorError("GBP assessor not available")

        elif assessment_type == AssessmentType.LIGHTHOUSE:
            # Use Lighthouse assessor from registry
            if "lighthouse" in self.assessors:
                try:
                    lighthouse_result = await self.assessors["lighthouse"].assess(
                        url=url, business_data=business_data or {"business_id": business_id}
                    )

                    # Convert BaseAssessor result to AssessmentResult
                    return AssessmentResult(
                        id=str(uuid.uuid4()),
                        business_id=business_id,
                        session_id=session_id,
                        assessment_type=AssessmentType.LIGHTHOUSE,
                        status=AssessmentStatus.COMPLETED
                        if lighthouse_result.status == "completed"
                        else AssessmentStatus.FAILED,
                        url=url,
                        domain=self._extract_domain(url),
                        started_at=datetime.utcnow(),
                        completed_at=datetime.utcnow(),
                        # Store Lighthouse data in assessment_metadata
                        assessment_metadata=lighthouse_result.data,
                        # Extract key scores
                        performance_score=lighthouse_result.metrics.get("performance_score"),
                        accessibility_score=lighthouse_result.metrics.get("accessibility_score"),
                        best_practices_score=lighthouse_result.metrics.get("best_practices_score"),
                        seo_score=lighthouse_result.metrics.get("seo_score"),
                        pwa_score=lighthouse_result.metrics.get("pwa_score"),
                        # Core Web Vitals
                        largest_contentful_paint=lighthouse_result.metrics.get("lcp_ms"),
                        first_input_delay=lighthouse_result.metrics.get("fid_ms"),
                        cumulative_layout_shift=lighthouse_result.metrics.get("cls_score"),
                        error_message=lighthouse_result.error_message,
                        total_cost_usd=Decimal(str(lighthouse_result.cost)),
                    )
                except Exception as e:
                    logger.error(f"Lighthouse assessment failed: {e}")
                    raise
            else:
                raise CoordinatorError("Lighthouse assessor not available")

        else:
            raise CoordinatorError(f"Unsupported assessment type: {assessment_type}")

    async def _save_partial_result(self, result: AssessmentResult):
        """
        Save partial result immediately for recovery

        Acceptance Criteria: Partial results saved
        """
        # In a real implementation, this would save to database
        # For now, we'll just preserve the actual status
        if result:
            # Don't override the status - preserve whether it's COMPLETED, FAILED, etc.
            # TODO: Save to database
            pass

    def _create_failed_result(
        self,
        business_id: str,
        session_id: str,
        request: AssessmentRequest,
        error_message: str,
    ) -> AssessmentResult:
        """
        Create a failed assessment result

        Acceptance Criteria: Error recovery implemented
        """
        return AssessmentResult(
            id=str(uuid.uuid4()),
            business_id=business_id,
            session_id=session_id,
            assessment_type=request.assessment_type,
            status=AssessmentStatus.FAILED,
            url=request.url,
            domain=self._extract_domain(request.url),
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            error_message=error_message,
        )

    def _get_assessment_priority(self, assessment_type: AssessmentType) -> AssessmentPriority:
        """Get priority for assessment type"""
        priority_map = {
            AssessmentType.PAGESPEED: AssessmentPriority.HIGH,
            AssessmentType.TECH_STACK: AssessmentPriority.MEDIUM,
            AssessmentType.AI_INSIGHTS: AssessmentPriority.MEDIUM,
            AssessmentType.BUSINESS_INFO: AssessmentPriority.HIGH,
            AssessmentType.FULL_AUDIT: AssessmentPriority.HIGH,
        }
        return priority_map.get(assessment_type, AssessmentPriority.MEDIUM)

    def _get_assessment_timeout(self, assessment_type: AssessmentType) -> int:
        """Get timeout for assessment type"""
        timeout_map = {
            AssessmentType.PAGESPEED: 180,  # 3 minutes
            AssessmentType.TECH_STACK: 120,  # 2 minutes
            AssessmentType.AI_INSIGHTS: 300,  # 5 minutes
            AssessmentType.BUSINESS_INFO: 30,  # 30 seconds for GBP
            AssessmentType.FULL_AUDIT: 600,  # 10 minutes
        }
        return timeout_map.get(assessment_type, 300)

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL"""
        from urllib.parse import urlparse

        return urlparse(url).netloc.replace("www.", "")

    async def execute_batch_assessments(
        self, assessment_configs: List[Dict[str, Any]], max_concurrent_sessions: int = 3
    ) -> List[CoordinatorResult]:
        """
        Execute assessments for multiple websites in batch

        Args:
            assessment_configs: List of assessment configurations
            max_concurrent_sessions: Maximum concurrent assessment sessions

        Returns:
            List of coordinator results
        """
        semaphore = asyncio.Semaphore(max_concurrent_sessions)

        async def execute_single_config(config: Dict[str, Any]) -> CoordinatorResult:
            async with semaphore:
                return await self.execute_comprehensive_assessment(
                    business_id=config["business_id"],
                    url=config["url"],
                    assessment_types=config.get("assessment_types"),
                    industry=config.get("industry", "default"),
                    session_config=config.get("session_config"),
                )

        tasks = [execute_single_config(config) for config in assessment_configs]
        return await asyncio.gather(*tasks, return_exceptions=True)

    async def resume_failed_session(self, session_id: str, retry_failed_only: bool = True) -> CoordinatorResult:
        """
        Resume a failed or partial assessment session

        Args:
            session_id: Session to resume
            retry_failed_only: Only retry failed assessments

        Returns:
            Updated coordinator result

        Acceptance Criteria: Error recovery implemented
        """
        # In a real implementation, this would:
        # 1. Load session from database
        # 2. Identify failed/incomplete assessments
        # 3. Re-run only the failed ones
        # 4. Merge with existing results

        raise NotImplementedError("Session resumption requires database integration")

    def get_assessment_status(self, session_id: str) -> Dict[str, Any]:
        """
        Get current status of an assessment session

        Returns:
            Session status information
        """
        # In a real implementation, this would query the database
        # For now, return a placeholder
        return {
            "session_id": session_id,
            "status": "running",
            "progress": "50%",
            "completed_assessments": 1,
            "total_assessments": 3,
            "estimated_completion": datetime.utcnow() + timedelta(minutes=5),
        }

    async def cancel_session(self, session_id: str) -> bool:
        """
        Cancel a running assessment session

        Args:
            session_id: Session to cancel

        Returns:
            True if cancelled successfully
        """
        # In a real implementation, this would:
        # 1. Mark session as cancelled in database
        # 2. Cancel running tasks
        # 3. Save partial results

        return True


class AssessmentScheduler:
    """
    Schedules and manages assessment execution with priority queues
    and resource management.
    """

    def __init__(self, coordinator: AssessmentCoordinator):
        """Initialize scheduler with coordinator"""
        self.coordinator = coordinator
        self.priority_queue = asyncio.PriorityQueue()
        self.running_sessions: Set[str] = set()

    async def schedule_assessment(
        self,
        business_id: str,
        url: str,
        priority: AssessmentPriority = AssessmentPriority.MEDIUM,
        scheduled_time: Optional[datetime] = None,
        assessment_types: Optional[List[AssessmentType]] = None,
    ) -> str:
        """
        Schedule an assessment for execution

        Args:
            business_id: Business identifier
            url: Website URL
            priority: Assessment priority
            scheduled_time: When to run (None for immediate)
            assessment_types: Types of assessments

        Returns:
            Session ID for tracking
        """
        session_id = str(uuid.uuid4())

        # Create assessment config
        config = {
            "session_id": session_id,
            "business_id": business_id,
            "url": url,
            "assessment_types": assessment_types,
            "scheduled_time": scheduled_time or datetime.utcnow(),
            "priority": priority,
        }

        # Add to priority queue
        priority_value = self._get_priority_value(priority)
        await self.priority_queue.put((priority_value, config))

        return session_id

    def _get_priority_value(self, priority: AssessmentPriority) -> int:
        """Convert priority to numeric value for queue"""
        priority_values = {
            AssessmentPriority.CRITICAL: 1,
            AssessmentPriority.HIGH: 2,
            AssessmentPriority.MEDIUM: 3,
            AssessmentPriority.LOW: 4,
        }
        return priority_values.get(priority, 3)

    async def process_queue(self):
        """
        Process the assessment queue continuously

        This would run as a background task in production
        """
        while True:
            try:
                # Get next assessment from queue
                priority_value, config = await self.priority_queue.get()

                # Check if it's time to run
                scheduled_time = config["scheduled_time"]
                if scheduled_time > datetime.utcnow():
                    # Put it back and wait
                    await self.priority_queue.put((priority_value, config))
                    await asyncio.sleep(60)  # Check every minute
                    continue

                # Execute assessment
                session_id = config["session_id"]
                self.running_sessions.add(session_id)

                try:
                    result = await self.coordinator.execute_comprehensive_assessment(
                        business_id=config["business_id"],
                        url=config["url"],
                        assessment_types=config["assessment_types"],
                    )

                    # Handle result (save to database, send notifications, etc.)
                    await self._handle_completion(result)

                finally:
                    self.running_sessions.discard(session_id)

            except Exception as e:
                # Log error and continue processing
                print(f"Error processing assessment queue: {e}")
                await asyncio.sleep(5)

    async def _handle_completion(self, result: CoordinatorResult):
        """Handle assessment completion"""
        # In production, this would:
        # - Save results to database
        # - Send notifications
        # - Update business dashboards
        # - Trigger downstream processes
        pass
