"""
Assessment API Endpoints - Task 035

FastAPI endpoints for triggering assessments, checking status, and retrieving results.
Provides REST API interface with proper error handling for assessment functionality.

Acceptance Criteria:
- Trigger assessment endpoint
- Status checking works
- Results retrieval API
- Proper error responses
"""

import logging
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from .coordinator import AssessmentCoordinator, CoordinatorResult
from .schemas import (
    AIInsightsResult,
    AssessmentResults,
    AssessmentStatusResponse,
    BatchAssessmentRequest,
    BatchAssessmentResponse,
    ErrorResponse,
    HealthCheckResponse,
    PageSpeedMetrics,
    TechStackResult,
    TriggerAssessmentRequest,
    TriggerAssessmentResponse,
    validate_business_id,
    validate_session_id,
)
from .types import AssessmentStatus, AssessmentType

# Setup logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/v1/assessments", tags=["assessments"])

# Global coordinator instance
coordinator = AssessmentCoordinator(max_concurrent=5)

# In-memory storage for demo (would use database in production)
assessment_sessions: dict[str, CoordinatorResult] = {}
batch_sessions: dict[str, list[str]] = {}


def get_coordinator() -> AssessmentCoordinator:
    """Dependency to get coordinator instance"""
    return coordinator


async def store_assessment_result(session_id: str, result: CoordinatorResult):
    """Store assessment result (would use database in production)"""
    assessment_sessions[session_id] = result
    logger.info(f"Stored assessment result for session {session_id}")


def create_error_response(
    error_type: str,
    message: str,
    details: dict | None = None,
    status_code: int = 400,
) -> HTTPException:
    """Create standardized error response"""
    error_data = ErrorResponse(error=error_type, message=message, details=details, request_id=str(uuid.uuid4()))
    # Convert to dict with JSON-serializable datetime
    error_dict = error_data.dict()
    if "timestamp" in error_dict and error_dict["timestamp"]:
        error_dict["timestamp"] = error_dict["timestamp"].isoformat()
    return HTTPException(status_code=status_code, detail=error_dict)


@router.post(
    "/trigger",
    response_model=TriggerAssessmentResponse,
    summary="Trigger Website Assessment",
    description="Start a comprehensive website assessment including PageSpeed, tech stack, and AI insights",
)
async def trigger_assessment(
    request: TriggerAssessmentRequest,
    background_tasks: BackgroundTasks,
    coord: AssessmentCoordinator = Depends(get_coordinator),
) -> TriggerAssessmentResponse:
    """
    Trigger a new website assessment

    Acceptance Criteria: Trigger assessment endpoint
    """
    try:
        # Validate inputs
        validate_business_id(request.business_id)

        # Set default assessment types if not provided
        assessment_types = request.assessment_types
        if not assessment_types:
            assessment_types = [
                AssessmentType.PAGESPEED,
                AssessmentType.TECH_STACK,
                AssessmentType.AI_INSIGHTS,
            ]

        # Generate session ID
        session_id = f"sess_{uuid.uuid4().hex[:12]}"

        # Calculate estimated completion time
        base_time_per_assessment = 60  # seconds
        total_estimated_seconds = len(assessment_types) * base_time_per_assessment
        estimated_completion = datetime.utcnow() + timedelta(seconds=total_estimated_seconds)

        # Start assessment in background
        async def run_assessment():
            try:
                result = await coord.execute_comprehensive_assessment(
                    business_id=request.business_id,
                    url=str(request.url),
                    assessment_types=assessment_types,
                    industry=request.industry,
                    session_config=request.session_config,
                    business_data=request.business_data,
                )
                result.session_id = session_id  # Ensure session ID matches
                await store_assessment_result(session_id, result)

                # Send callback if provided
                if request.callback_url:
                    # In production, would make HTTP POST to callback URL
                    logger.info(f"Would send callback to {request.callback_url} for session {session_id}")

            except Exception as e:
                logger.error(f"Assessment failed for session {session_id}: {str(e)}")
                # Store failed result
                failed_result = CoordinatorResult(
                    session_id=session_id,
                    business_id=request.business_id,
                    total_assessments=len(assessment_types),
                    completed_assessments=0,
                    failed_assessments=len(assessment_types),
                    partial_results={},
                    errors={"system": str(e)},
                    total_cost_usd=Decimal("0"),
                    execution_time_ms=0,
                    started_at=datetime.utcnow(),
                    completed_at=datetime.utcnow(),
                )
                await store_assessment_result(session_id, failed_result)

        # Add to background tasks
        background_tasks.add_task(run_assessment)

        return TriggerAssessmentResponse(
            session_id=session_id,
            business_id=request.business_id,
            status=AssessmentStatus.RUNNING,
            total_assessments=len(assessment_types),
            estimated_completion_time=estimated_completion,
            tracking_url=f"/api/v1/assessments/{session_id}/status",
        )

    except ValueError as e:
        raise create_error_response("validation_error", str(e))
    except Exception as e:
        logger.error(f"Error triggering assessment: {str(e)}")
        raise create_error_response("internal_error", "Failed to trigger assessment", status_code=500)


@router.post(
    "/assess",
    response_model=TriggerAssessmentResponse,
    summary="Trigger Website Assessment (Legacy)",
    description="Start a comprehensive website assessment (legacy endpoint for backward compatibility)",
)
async def assess_website(
    request: dict[str, Any],
    background_tasks: BackgroundTasks,
    coord: AssessmentCoordinator = Depends(get_coordinator),
) -> TriggerAssessmentResponse:
    """
    Legacy endpoint for triggering website assessments
    Accepts flexible request format for backward compatibility
    """
    try:
        # Extract URL and convert email to business_id if needed
        url = request.get("url")
        if not url:
            raise ValueError("URL is required")

        # Use email as business_id if present, otherwise generate one
        business_id = request.get("email", request.get("business_id"))
        if not business_id:
            business_id = f"biz_{uuid.uuid4().hex[:12]}"

        # Create properly formatted request
        assessment_request = TriggerAssessmentRequest(
            business_id=business_id,
            url=url,
            assessment_types=request.get("assessment_types"),
            industry=request.get("industry", "default"),
            priority=request.get("priority", "medium"),
            session_config=request.get("session_config"),
            business_data=request.get("business_data"),
            callback_url=request.get("callback_url"),
        )

        return await trigger_assessment(assessment_request, background_tasks, coord)

    except Exception as e:
        logger.error(f"Error in assess_website: {str(e)}")
        raise create_error_response("validation_error", str(e))


@router.get(
    "/{session_id}/status",
    response_model=AssessmentStatusResponse,
    summary="Check Assessment Status",
    description="Get the current status and progress of a running assessment",
)
async def get_assessment_status(
    session_id: str, coord: AssessmentCoordinator = Depends(get_coordinator)
) -> AssessmentStatusResponse:
    """
    Check assessment status and progress

    Acceptance Criteria: Status checking works
    """
    try:
        validate_session_id(session_id)

        # Check if assessment is completed
        if session_id in assessment_sessions:
            result = assessment_sessions[session_id]

            # Calculate progress
            progress = f"{result.completed_assessments}/{result.total_assessments} complete"

            # Determine status
            if result.failed_assessments == result.total_assessments:
                status = AssessmentStatus.FAILED
            elif result.completed_assessments == result.total_assessments:
                status = AssessmentStatus.COMPLETED
            elif result.completed_assessments > 0:
                status = AssessmentStatus.PARTIAL
            else:
                status = AssessmentStatus.RUNNING

            # Extract error messages
            errors = None
            if result.errors:
                errors = [f"{k}: {v}" for k, v in result.errors.items()]

            return AssessmentStatusResponse(
                session_id=session_id,
                business_id=result.business_id,
                status=status,
                progress=progress,
                total_assessments=result.total_assessments,
                completed_assessments=result.completed_assessments,
                failed_assessments=result.failed_assessments,
                started_at=result.started_at,
                estimated_completion=None
                if status in [AssessmentStatus.COMPLETED, AssessmentStatus.FAILED]
                else datetime.utcnow() + timedelta(minutes=2),
                completed_at=result.completed_at
                if status in [AssessmentStatus.COMPLETED, AssessmentStatus.FAILED]
                else None,
                current_step=_get_current_step(result),
                errors=errors,
            )
        # Assessment still running or not found - use coordinator status
        status_info = coord.get_assessment_status(session_id)

        return AssessmentStatusResponse(
            session_id=session_id,
            business_id="unknown",  # Would get from database in production
            status=AssessmentStatus.RUNNING,
            progress=status_info.get("progress", "Starting..."),
            total_assessments=status_info.get("total_assessments", 3),
            completed_assessments=status_info.get("completed_assessments", 0),
            failed_assessments=0,
            started_at=datetime.utcnow() - timedelta(minutes=1),  # Estimate
            estimated_completion=status_info.get("estimated_completion"),
            completed_at=None,
            current_step="Processing assessments...",
            errors=None,
        )

    except ValueError as e:
        raise create_error_response("validation_error", str(e))
    except Exception as e:
        logger.error(f"Error getting assessment status: {str(e)}")
        raise create_error_response("internal_error", "Failed to get assessment status", status_code=500)


@router.get(
    "/{session_id}/results",
    response_model=AssessmentResults,
    summary="Get Assessment Results",
    description="Retrieve the complete results of a finished assessment",
)
async def get_assessment_results(
    session_id: str,
    include_raw_data: bool = Query(False, description="Include raw assessment data"),
) -> AssessmentResults:
    """
    Get complete assessment results

    Acceptance Criteria: Results retrieval API
    """
    try:
        validate_session_id(session_id)

        # Check if results are available
        if session_id not in assessment_sessions:
            raise create_error_response(
                "not_found",
                f"Assessment session {session_id} not found or still running",
                status_code=404,
            )

        result = assessment_sessions[session_id]

        # Check if assessment is complete
        if result.completed_assessments + result.failed_assessments < result.total_assessments:
            raise create_error_response(
                "assessment_running",
                "Assessment is still running. Check status first.",
                {"session_id": session_id, "status": "running"},
                status_code=409,
            )

        # Extract results by type
        pagespeed_results = None
        tech_stack_results = None
        ai_insights_results = None

        # Process PageSpeed results
        if AssessmentType.PAGESPEED in result.partial_results:
            ps_result = result.partial_results[AssessmentType.PAGESPEED]
            if ps_result and ps_result.status == AssessmentStatus.COMPLETED:
                pagespeed_results = PageSpeedMetrics(
                    performance_score=ps_result.performance_score or 0,
                    accessibility_score=ps_result.accessibility_score,
                    seo_score=ps_result.seo_score,
                    best_practices_score=ps_result.best_practices_score,
                    largest_contentful_paint=ps_result.largest_contentful_paint,
                    first_input_delay=ps_result.first_input_delay,
                    cumulative_layout_shift=ps_result.cumulative_layout_shift,
                    speed_index=ps_result.speed_index,
                    time_to_interactive=ps_result.time_to_interactive,
                )

        # Process Tech Stack results
        if AssessmentType.TECH_STACK in result.partial_results:
            ts_result = result.partial_results[AssessmentType.TECH_STACK]
            if ts_result and ts_result.tech_stack_data:
                tech_stack_results = [
                    TechStackResult(
                        technology_name=tech["technology_name"],
                        category=tech["category"],
                        confidence=tech["confidence"],
                        version=tech.get("version"),
                    )
                    for tech in ts_result.tech_stack_data.get("technologies", [])
                ]

        # Process AI Insights results
        if AssessmentType.AI_INSIGHTS in result.partial_results:
            ai_result = result.partial_results[AssessmentType.AI_INSIGHTS]
            if ai_result and ai_result.ai_insights_data:
                insights_data = ai_result.ai_insights_data["insights"]
                ai_insights_results = AIInsightsResult(
                    recommendations=insights_data.get("recommendations", []),
                    industry_insights=insights_data.get("industry_insights", {}),
                    summary=insights_data.get("summary", {}),
                    ai_model_version=ai_result.ai_insights_data.get("model_version", "unknown"),
                    processing_cost_usd=Decimal(str(ai_result.ai_insights_data.get("total_cost_usd", 0))),
                )

        # Determine final status
        final_status = AssessmentStatus.COMPLETED
        if result.failed_assessments > 0:
            if result.completed_assessments == 0:
                final_status = AssessmentStatus.FAILED
            else:
                final_status = AssessmentStatus.PARTIAL

        return AssessmentResults(
            session_id=session_id,
            business_id=result.business_id,
            url=next(iter(result.partial_results.values())).url if result.partial_results else "unknown",
            domain=next(iter(result.partial_results.values())).domain if result.partial_results else "unknown",
            industry="unknown",  # Would store in session data
            status=final_status,
            total_assessments=result.total_assessments,
            completed_assessments=result.completed_assessments,
            failed_assessments=result.failed_assessments,
            pagespeed_results=pagespeed_results,
            tech_stack_results=tech_stack_results,
            ai_insights_results=ai_insights_results,
            started_at=result.started_at,
            completed_at=result.completed_at,
            execution_time_ms=result.execution_time_ms,
            total_cost_usd=result.total_cost_usd,
            errors=result.errors if result.errors else None,
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise create_error_response("validation_error", str(e))
    except Exception as e:
        logger.error(f"Error getting assessment results: {str(e)}")
        raise create_error_response("internal_error", "Failed to get assessment results", status_code=500)


@router.post(
    "/batch",
    response_model=BatchAssessmentResponse,
    summary="Trigger Batch Assessments",
    description="Start multiple website assessments in parallel",
)
async def trigger_batch_assessment(
    request: BatchAssessmentRequest,
    background_tasks: BackgroundTasks,
    coord: AssessmentCoordinator = Depends(get_coordinator),
) -> BatchAssessmentResponse:
    """Trigger batch assessment for multiple websites"""
    try:
        batch_id = request.batch_id or f"batch_{uuid.uuid4().hex[:12]}"
        session_ids = []

        # Validate all requests first
        for i, assessment in enumerate(request.assessments):
            try:
                validate_business_id(assessment.business_id)
            except ValueError as e:
                raise create_error_response(
                    "validation_error",
                    f"Invalid assessment {i + 1}: {str(e)}",
                    {"assessment_index": i, "business_id": assessment.business_id},
                )

        # Convert requests to coordinator configs
        assessment_configs = []
        for assessment in request.assessments:
            session_id = f"sess_{uuid.uuid4().hex[:12]}"
            session_ids.append(session_id)

            assessment_types = assessment.assessment_types
            if not assessment_types:
                assessment_types = [
                    AssessmentType.PAGESPEED,
                    AssessmentType.TECH_STACK,
                    AssessmentType.AI_INSIGHTS,
                ]

            config = {
                "business_id": assessment.business_id,
                "url": str(assessment.url),
                "assessment_types": assessment_types,
                "industry": assessment.industry,
                "session_config": assessment.session_config,
            }
            assessment_configs.append(config)

        # Store batch info
        batch_sessions[batch_id] = session_ids

        # Start batch processing in background
        async def run_batch_assessment():
            try:
                results = await coord.execute_batch_assessments(
                    assessment_configs=assessment_configs,
                    max_concurrent_sessions=request.max_concurrent,
                )

                # Store individual results
                for i, result in enumerate(results):
                    if isinstance(result, CoordinatorResult):
                        result.session_id = session_ids[i]
                        await store_assessment_result(session_ids[i], result)
                    else:
                        # Handle failed result
                        logger.error(f"Batch assessment failed for session {session_ids[i]}: {result}")

            except Exception as e:
                logger.error(f"Batch assessment failed for batch {batch_id}: {str(e)}")

        background_tasks.add_task(run_batch_assessment)

        # Calculate estimated completion time
        avg_time_per_assessment = 90  # seconds
        estimated_completion = datetime.utcnow() + timedelta(
            seconds=avg_time_per_assessment * len(request.assessments) / request.max_concurrent
        )

        return BatchAssessmentResponse(
            batch_id=batch_id,
            total_assessments=len(request.assessments),
            session_ids=session_ids,
            estimated_completion_time=estimated_completion,
            tracking_url=f"/api/v1/assessments/batch/{batch_id}/status",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering batch assessment: {str(e)}")
        raise create_error_response("internal_error", "Failed to trigger batch assessment", status_code=500)


@router.delete(
    "/{session_id}",
    summary="Cancel Assessment",
    description="Cancel a running assessment",
)
async def cancel_assessment(session_id: str, coord: AssessmentCoordinator = Depends(get_coordinator)) -> JSONResponse:
    """Cancel a running assessment"""
    try:
        validate_session_id(session_id)

        # Check if assessment exists
        if session_id in assessment_sessions:
            result = assessment_sessions[session_id]
            if result.completed_assessments + result.failed_assessments >= result.total_assessments:
                raise create_error_response(
                    "already_completed",
                    "Cannot cancel completed assessment",
                    status_code=409,
                )

        # Attempt to cancel
        cancelled = await coord.cancel_session(session_id)

        if cancelled:
            return JSONResponse(
                content={"message": f"Assessment {session_id} cancelled successfully"},
                status_code=200,
            )
        raise create_error_response("cancellation_failed", "Failed to cancel assessment", status_code=500)

    except HTTPException:
        raise
    except ValueError as e:
        raise create_error_response("validation_error", str(e))
    except Exception as e:
        logger.error(f"Error cancelling assessment: {str(e)}")
        raise create_error_response("internal_error", "Failed to cancel assessment", status_code=500)


@router.get(
    "/health",
    response_model=HealthCheckResponse,
    summary="Health Check",
    description="Check the health status of the assessment service",
)
async def health_check() -> HealthCheckResponse:
    """
    Health check endpoint

    Acceptance Criteria: Proper error responses (includes health monitoring)
    """
    try:
        # Check dependencies (would be actual health checks in production)
        dependencies = {
            "database": "healthy",
            "pagespeed_api": "healthy",
            "llm_service": "healthy",
            "assessment_coordinator": "healthy",
        }

        # Calculate uptime (would use actual start time in production)
        uptime_seconds = 86400  # 24 hours for demo

        return HealthCheckResponse(
            status="healthy",
            version="1.0.0",
            uptime_seconds=uptime_seconds,
            dependencies=dependencies,
        )

    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return HealthCheckResponse(
            status="unhealthy",
            version="1.0.0",
            uptime_seconds=0,
            dependencies={"error": str(e)},
        )


def _get_current_step(result: CoordinatorResult) -> str | None:
    """Determine current processing step based on assessment progress"""
    if result.completed_assessments == 0:
        return "Initializing assessments..."
    if result.completed_assessments == 1:
        return "Running performance analysis..."
    if result.completed_assessments == 2:
        return "Analyzing technology stack..."
    if result.completed_assessments < result.total_assessments:
        return "Generating AI insights..."
    return "Finalizing results..."


# Note: Exception handlers would be added at the app level, not router level
# These would be implemented in the main FastAPI app:
# @app.exception_handler(404)
# @app.exception_handler(422)
# @app.exception_handler(500)
