"""
FastAPI endpoints for Batch Report Runner

Provides REST API for batch processing with cost preview, progress tracking,
and WebSocket real-time updates.
"""
from datetime import datetime
from typing import Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, WebSocket
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from core.exceptions import LeadFactoryError
from core.logging import get_logger
from core.metrics import metrics
from database.session import SessionLocal

from .cost_calculator import get_cost_calculator
from .models import BatchReport, BatchReportLead, BatchStatus, LeadProcessingStatus
from .processor import start_batch_processing
from .schemas import (
    BatchFilterSchema,
    BatchListResponseSchema,
    BatchPreviewSchema,
    BatchResponseSchema,
    BatchStatusResponseSchema,
    CreateBatchSchema,
    HealthCheckResponseSchema,
    PaginationSchema,
    StartBatchSchema,
)
from .websocket_manager import get_connection_manager, handle_websocket_connection

# Initialize logger
logger = get_logger("batch_runner_api", domain="batch_runner")

# Create router
router = APIRouter()


# Dependency for database session
def get_db() -> Session:
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_user_context(request) -> Dict[str, Optional[str]]:
    """Extract user context from request headers"""
    return {
        "user_id": getattr(request, "headers", {}).get("X-User-ID"),
        "user_ip": getattr(getattr(request, "client", None), "host", None),
        "user_agent": getattr(request, "headers", {}).get("User-Agent"),
    }


# Exception handler decorator
def handle_api_errors(func):
    """Decorator to handle common API errors"""
    from functools import wraps

    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except HTTPException:
            raise
        except ValidationError as e:
            logger.warning(f"Validation error in {func.__name__}: {str(e)}")
            raise HTTPException(status_code=422, detail=str(e))
        except IntegrityError as e:
            logger.error(f"Database integrity error in {func.__name__}: {str(e)}")
            raise HTTPException(status_code=409, detail="Resource conflict")
        except SQLAlchemyError as e:
            logger.error(f"Database error in {func.__name__}: {str(e)}")
            raise HTTPException(status_code=500, detail="Database operation failed")
        except LeadFactoryError as e:
            logger.error(f"LeadFactory error in {func.__name__}: {str(e)}")
            raise HTTPException(status_code=e.status_code, detail=e.message)
        except Exception as e:
            logger.exception(f"Unexpected error in {func.__name__}: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

    return wrapper


# Cost Preview Endpoint
@router.post("/batch/preview", response_model=BatchPreviewSchema)
@handle_api_errors
async def preview_batch_cost(request: CreateBatchSchema, db: Session = Depends(get_db)):
    """
    Preview cost for batch report generation

    Provides accurate cost estimation within ±5% before committing to processing.
    Response time: <200ms
    """
    logger.info(f"Previewing batch cost for {len(request.lead_ids)} leads")

    # Validate lead IDs exist
    from lead_explorer.repository import LeadRepository

    lead_repo = LeadRepository(db)

    valid_leads = []
    for lead_id in request.lead_ids:
        lead = lead_repo.get_lead_by_id(lead_id)
        if lead:
            valid_leads.append(lead_id)
        else:
            logger.warning(f"Lead {lead_id} not found for batch preview")

    if not valid_leads:
        raise HTTPException(status_code=400, detail="No valid leads found")

    if len(valid_leads) != len(request.lead_ids):
        logger.warning(f"Only {len(valid_leads)} of {len(request.lead_ids)} leads are valid")

    # Calculate cost preview
    cost_calculator = get_cost_calculator()
    cost_preview = cost_calculator.calculate_batch_preview(valid_leads, request.template_version)

    # Validate against budget
    budget_validation = cost_calculator.validate_budget(cost_preview["cost_breakdown"]["total_cost"])

    # Prepare response
    preview = BatchPreviewSchema(
        lead_count=len(valid_leads),
        valid_lead_ids=valid_leads,
        template_version=request.template_version,
        estimated_cost_usd=cost_preview["cost_breakdown"]["total_cost"],
        cost_breakdown=cost_preview["cost_breakdown"],
        provider_breakdown=cost_preview["provider_breakdown"],
        estimated_duration_minutes=cost_preview["estimated_duration_minutes"],
        cost_per_lead=cost_preview["cost_per_lead"],
        is_within_budget=budget_validation["is_within_budget"],
        budget_warning=budget_validation.get("warning_message"),
        accuracy_note=cost_preview["accuracy_note"],
    )

    metrics.increment_counter("batch_runner_previews_generated")
    logger.info(
        f"Cost preview generated: ${cost_preview['cost_breakdown']['total_cost']:.2f} for {len(valid_leads)} leads"
    )

    return preview


# Start Batch Processing
@router.post("/batch/start", response_model=BatchResponseSchema, status_code=201)
@handle_api_errors
async def start_batch_processing_endpoint(
    request: StartBatchSchema, background_tasks: BackgroundTasks, db: Session = Depends(get_db)
):
    """
    Start batch processing with background execution

    Creates batch record and starts processing in background with WebSocket URL.
    """
    logger.info(f"Starting batch processing for {len(request.lead_ids)} leads")

    # Validate leads again
    from lead_explorer.repository import LeadRepository

    lead_repo = LeadRepository(db)

    valid_leads = []
    for lead_id in request.lead_ids:
        lead = lead_repo.get_lead_by_id(lead_id)
        if lead:
            valid_leads.append(lead_id)

    if not valid_leads:
        raise HTTPException(status_code=400, detail="No valid leads found")

    # Create batch record
    batch = BatchReport(
        name=request.name,
        description=request.description,
        template_version=request.template_version,
        total_leads=len(valid_leads),
        estimated_cost_usd=request.estimated_cost_usd,
        cost_approved=request.cost_approved,
        max_concurrent=request.max_concurrent or 5,
        retry_failed=request.retry_failed,
        retry_count=request.retry_count or 3,
        created_by=request.created_by,
        websocket_url=f"/api/v1/batch/{None}/progress",  # Will be updated with actual ID
    )

    db.add(batch)
    db.commit()
    db.refresh(batch)

    # Update WebSocket URL with actual batch ID
    batch.websocket_url = f"/api/v1/batch/{batch.id}/progress"

    # Create lead records
    for i, lead_id in enumerate(valid_leads):
        batch_lead = BatchReportLead(
            batch_id=batch.id,
            lead_id=lead_id,
            order_index=i,
            estimated_cost_usd=request.estimated_cost_usd / len(valid_leads),
            max_retries=request.retry_count or 3,
        )
        db.add(batch_lead)

    db.commit()

    # Start background processing
    background_tasks.add_task(start_batch_processing, batch.id)

    metrics.increment_counter("batch_runner_batches_started")
    logger.info(f"Batch {batch.id} created and processing started")

    return BatchResponseSchema(
        id=batch.id,
        name=batch.name,
        description=batch.description,
        status=batch.status.value,
        total_leads=batch.total_leads,
        processed_leads=batch.processed_leads,
        successful_leads=batch.successful_leads,
        failed_leads=batch.failed_leads,
        progress_percentage=float(batch.progress_percentage),
        estimated_cost_usd=float(batch.estimated_cost_usd) if batch.estimated_cost_usd else None,
        actual_cost_usd=float(batch.actual_cost_usd) if batch.actual_cost_usd else None,
        template_version=batch.template_version,
        websocket_url=batch.websocket_url,
        created_at=batch.created_at,
        started_at=batch.started_at,
        completed_at=batch.completed_at,
        created_by=batch.created_by,
        error_message=batch.error_message,
    )


# Get Batch Status
@router.get("/batch/{batch_id}/status", response_model=BatchStatusResponseSchema)
@handle_api_errors
async def get_batch_status(batch_id: str, db: Session = Depends(get_db)):
    """
    Get current status of batch processing

    Response time: <500ms
    """
    logger.debug(f"Getting status for batch {batch_id}")

    batch = db.query(BatchReport).filter_by(id=batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    # Get recent lead results for context
    recent_leads = (
        db.query(BatchReportLead)
        .filter_by(batch_id=batch_id)
        .order_by(BatchReportLead.completed_at.desc())
        .limit(5)
        .all()
    )

    recent_results = []
    for lead in recent_leads:
        recent_results.append(
            {
                "lead_id": lead.lead_id,
                "status": lead.status.value,
                "error_message": lead.error_message,
                "processing_duration_ms": lead.processing_duration_ms,
                "completed_at": lead.completed_at.isoformat() if lead.completed_at else None,
            }
        )

    # Get error summary
    error_counts = {}
    if batch.failed_leads > 0:
        error_query = (
            db.query(BatchReportLead.error_code, db.func.count(BatchReportLead.id))
            .filter_by(batch_id=batch_id, status=LeadProcessingStatus.FAILED)
            .group_by(BatchReportLead.error_code)
            .all()
        )
        error_counts = {error_code: count for error_code, count in error_query}

    return BatchStatusResponseSchema(
        batch_id=batch.id,
        status=batch.status.value,
        progress_percentage=float(batch.progress_percentage),
        total_leads=batch.total_leads,
        processed_leads=batch.processed_leads,
        successful_leads=batch.successful_leads,
        failed_leads=batch.failed_leads,
        current_lead_id=batch.current_lead_id,
        estimated_cost_usd=float(batch.estimated_cost_usd) if batch.estimated_cost_usd else None,
        actual_cost_usd=float(batch.actual_cost_usd) if batch.actual_cost_usd else None,
        started_at=batch.started_at.isoformat() if batch.started_at else None,
        estimated_completion=None,  # Could calculate based on progress
        recent_results=recent_results,
        error_summary=error_counts,
        websocket_url=batch.websocket_url,
    )


# List Batches
@router.get("/batch", response_model=BatchListResponseSchema)
@handle_api_errors
async def list_batches(
    filters: BatchFilterSchema = Depends(), pagination: PaginationSchema = Depends(), db: Session = Depends(get_db)
):
    """
    List batch processing jobs with filtering and pagination
    """
    logger.debug("Listing batches")

    query = db.query(BatchReport)

    # Apply filters
    if filters.status:
        status_values = [BatchStatus(s) for s in filters.status]
        query = query.filter(BatchReport.status.in_(status_values))

    if filters.created_by:
        query = query.filter(BatchReport.created_by == filters.created_by)

    if filters.template_version:
        query = query.filter(BatchReport.template_version == filters.template_version)

    if filters.created_after:
        query = query.filter(BatchReport.created_at >= filters.created_after)

    if filters.created_before:
        query = query.filter(BatchReport.created_at <= filters.created_before)

    # Get total count
    total_count = query.count()

    # Apply sorting and pagination
    query = query.order_by(BatchReport.created_at.desc())
    batches = query.offset(pagination.skip).limit(pagination.limit).all()

    # Convert to response format
    batch_list = []
    for batch in batches:
        batch_list.append(
            BatchResponseSchema(
                id=batch.id,
                name=batch.name,
                description=batch.description,
                status=batch.status.value,
                total_leads=batch.total_leads,
                processed_leads=batch.processed_leads,
                successful_leads=batch.successful_leads,
                failed_leads=batch.failed_leads,
                progress_percentage=float(batch.progress_percentage),
                estimated_cost_usd=float(batch.estimated_cost_usd) if batch.estimated_cost_usd else None,
                actual_cost_usd=float(batch.actual_cost_usd) if batch.actual_cost_usd else None,
                template_version=batch.template_version,
                websocket_url=batch.websocket_url,
                created_at=batch.created_at,
                started_at=batch.started_at,
                completed_at=batch.completed_at,
                created_by=batch.created_by,
                error_message=batch.error_message,
            )
        )

    # Calculate pagination info
    page_info = {
        "current_page": (pagination.skip // pagination.limit) + 1,
        "total_pages": (total_count + pagination.limit - 1) // pagination.limit,
        "page_size": pagination.limit,
        "has_next": pagination.skip + pagination.limit < total_count,
        "has_previous": pagination.skip > 0,
    }

    return BatchListResponseSchema(batches=batch_list, total_count=total_count, page_info=page_info)


# Cancel Batch
@router.post("/batch/{batch_id}/cancel")
@handle_api_errors
async def cancel_batch(batch_id: str, db: Session = Depends(get_db)):
    """
    Cancel a running batch
    """
    logger.info(f"Cancelling batch {batch_id}")

    batch = db.query(BatchReport).filter_by(id=batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    if batch.status not in [BatchStatus.PENDING, BatchStatus.RUNNING]:
        raise HTTPException(status_code=400, detail="Batch cannot be cancelled in current status")

    # Mark batch as cancelled
    batch.status = BatchStatus.CANCELLED
    batch.completed_at = datetime.utcnow()
    batch.error_message = "Cancelled by user"

    # Mark pending leads as skipped
    pending_leads = db.query(BatchReportLead).filter_by(batch_id=batch_id, status=LeadProcessingStatus.PENDING).all()

    for lead in pending_leads:
        lead.status = LeadProcessingStatus.SKIPPED

    db.commit()

    # Broadcast cancellation
    connection_manager = get_connection_manager()
    await connection_manager.broadcast_error(batch_id, "Batch processing cancelled by user", "USER_CANCELLED")

    metrics.increment_counter("batch_runner_batches_cancelled")
    logger.info(f"Batch {batch_id} cancelled successfully")

    return {"message": "Batch cancelled successfully"}


# WebSocket Progress Endpoint
@router.websocket("/batch/{batch_id}/progress")
async def websocket_batch_progress(websocket: WebSocket, batch_id: str):
    """
    WebSocket endpoint for real-time batch progress updates

    Throttled to 1 message per 2 seconds to prevent client overwhelm
    """
    logger.info(f"WebSocket connection requested for batch {batch_id}")

    # Extract user ID from query params if available
    user_id = None
    if hasattr(websocket, "query_params"):
        user_id = websocket.query_params.get("user_id")

    await handle_websocket_connection(websocket, batch_id, user_id)


# Health Check
@router.get("/health", response_model=HealthCheckResponseSchema)
@handle_api_errors
async def batch_runner_health_check(db: Session = Depends(get_db)):
    """
    Health check for Batch Runner domain
    """
    try:
        # Test database connection
        db.execute("SELECT 1")

        # Get basic stats
        total_batches = db.query(BatchReport).count()
        running_batches = db.query(BatchReport).filter_by(status=BatchStatus.RUNNING).count()

        # Check WebSocket manager
        connection_manager = get_connection_manager()
        ws_stats = connection_manager.get_stats()

        return HealthCheckResponseSchema(
            status="ok",
            timestamp=datetime.utcnow(),
            database="connected",
            message=f"Batch Runner healthy - {total_batches} total batches, {running_batches} running, {ws_stats['active_connections']} active WebSocket connections",
        )
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=503, detail="Service unhealthy")


# Batch Analytics
@router.get("/batch/analytics")
@handle_api_errors
async def get_batch_analytics(days: int = Query(default=7, ge=1, le=90), db: Session = Depends(get_db)):
    """
    Get batch processing analytics and statistics
    """
    from datetime import timedelta

    start_date = datetime.utcnow() - timedelta(days=days)

    # Aggregate statistics
    stats_query = (
        db.query(
            db.func.count(BatchReport.id).label("total_batches"),
            db.func.avg(BatchReport.successful_leads).label("avg_successful"),
            db.func.avg(BatchReport.progress_percentage).label("avg_progress"),
            db.func.sum(BatchReport.actual_cost_usd).label("total_cost"),
            db.func.avg(db.func.extract("epoch", BatchReport.completed_at - BatchReport.started_at)).label(
                "avg_duration_seconds"
            ),
        )
        .filter(BatchReport.created_at >= start_date)
        .first()
    )

    # Status breakdown
    status_query = (
        db.query(BatchReport.status, db.func.count(BatchReport.id))
        .filter(BatchReport.created_at >= start_date)
        .group_by(BatchReport.status)
        .all()
    )

    status_breakdown = {status.value: count for status, count in status_query}

    return {
        "period_days": days,
        "start_date": start_date.isoformat(),
        "statistics": {
            "total_batches": stats_query.total_batches or 0,
            "average_successful_leads": float(stats_query.avg_successful or 0),
            "average_progress": float(stats_query.avg_progress or 0),
            "total_cost_usd": float(stats_query.total_cost or 0),
            "average_duration_seconds": float(stats_query.avg_duration_seconds or 0),
        },
        "status_breakdown": status_breakdown,
        "generated_at": datetime.utcnow().isoformat(),
    }


# Include the router in main app with:
# app.include_router(router, prefix="/api/v1", tags=["batch-runner"])
