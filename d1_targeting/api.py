"""
FastAPI endpoints for D1 Targeting Domain

Provides REST API for target universe management, campaign operations,
batch scheduling, and targeting analytics.
"""

from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from account_management.models import AccountUser
from core.auth import require_authenticated_user, require_delete_permission, require_write_permission
from core.exceptions import LeadFactoryError
from core.exceptions import ValidationError as CoreValidationError
from core.logging import get_logger
from core.metrics import metrics
from core.rbac import Resource
from database.session import SessionLocal

from .batch_scheduler import BatchScheduler
from .models import Campaign, CampaignBatch, GeographicBoundary, TargetUniverse
from .quota_tracker import QuotaTracker
from .schemas import BaseResponseSchema  # Request schemas; Response schemas
from .schemas import (
    BatchFilterSchema,
    BatchResponseSchema,
    BatchStatusUpdateSchema,
    CampaignFilterSchema,
    CampaignResponseSchema,
    CreateBatchesSchema,
    CreateCampaignSchema,
    CreateGeographicBoundarySchema,
    CreateTargetUniverseSchema,
    GeographicBoundaryResponseSchema,
    PaginationSchema,
    QuotaAllocationResponseSchema,
    RefreshUniverseSchema,
    TargetUniverseResponseSchema,
    UniversePriorityResponseSchema,
    UpdateCampaignSchema,
    UpdateTargetUniverseSchema,
)
from .target_universe import TargetUniverseManager
from .types import VerticalMarket

# Initialize logger
logger = get_logger("d1_targeting_api", domain="d1")

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


# Exception handler decorator
def handle_api_errors(func):
    """Decorator to handle common API errors"""
    from functools import wraps

    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except HTTPException:
            # Re-raise HTTPException as-is (these are intentional HTTP responses)
            raise
        except ValidationError as e:
            logger.warning(f"Validation error in {func.__name__}: {str(e)}")
            raise HTTPException(status_code=422, detail=str(e))
        except CoreValidationError as e:
            logger.warning(f"Core validation error in {func.__name__}: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))
        except IntegrityError as e:
            logger.error(f"Database integrity error in {func.__name__}: {str(e)}")
            raise HTTPException(status_code=409, detail="Resource conflict or constraint violation")
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


# Target Universe endpoints
@router.post("/universes", response_model=TargetUniverseResponseSchema, status_code=201)
@handle_api_errors
async def create_target_universe(
    request: CreateTargetUniverseSchema,
    db: Session = Depends(get_db),
    current_user: AccountUser = require_write_permission(Resource.TARGETING),
):
    """
    Create a new target universe with specified targeting criteria.

    Acceptance Criteria:
    - FastAPI routes work
    - Validation complete
    - Error handling proper
    - Documentation generated
    """
    logger.info(f"Creating target universe: {request.name}")

    manager = TargetUniverseManager(session=db)

    # Convert targeting criteria to the format expected by manager
    geography_config = {
        "constraints": [
            {
                "level": constraint.level.value,
                "values": constraint.values,
                "radius_miles": constraint.radius_miles,
                "center_lat": constraint.center_lat,
                "center_lng": constraint.center_lng,
            }
            for constraint in request.targeting_criteria.geographic_constraints
        ]
    }

    universe = manager.create_universe(
        name=request.name,
        description=request.description,
        verticals=[v.value for v in request.targeting_criteria.verticals],
        geography_config=geography_config,
    )

    metrics.increment_counter("targeting_universes_created")
    logger.info(f"Successfully created target universe: {universe.id}")

    return universe


@router.get("/universes", response_model=list[TargetUniverseResponseSchema])
async def list_target_universes(
    db: Session = Depends(get_db),
    current_user: AccountUser = require_authenticated_user(),
    page: int = Query(default=1, ge=1, description="Page number"),
    size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    name_contains: str | None = Query(None, description="Filter by name containing text"),
    verticals: list[VerticalMarket] | None = Query(None, description="Filter by verticals"),
    is_active: bool | None = Query(None, description="Filter by active status"),
    min_size: int | None = Query(None, ge=0, description="Minimum universe size"),
    max_size: int | None = Query(None, ge=0, description="Maximum universe size"),
    created_after: datetime | None = Query(None, description="Created after date"),
    created_before: datetime | None = Query(None, description="Created before date"),
):
    """
    List target universes with optional filtering and pagination.
    """
    logger.info("Listing target universes")

    query = db.query(TargetUniverse)

    # Apply filters
    if name_contains:
        query = query.filter(TargetUniverse.name.contains(name_contains))
    if verticals:
        # Filter by any of the specified verticals
        vertical_values = [v.value for v in verticals]
        query = query.filter(TargetUniverse.verticals.op("?|")(vertical_values))
    if is_active is not None:
        query = query.filter(TargetUniverse.is_active == is_active)
    if min_size is not None:
        query = query.filter(TargetUniverse.actual_size >= min_size)
    if max_size is not None:
        query = query.filter(TargetUniverse.actual_size <= max_size)
    if created_after:
        query = query.filter(TargetUniverse.created_at >= created_after)
    if created_before:
        query = query.filter(TargetUniverse.created_at <= created_before)

    # Apply pagination
    offset = (page - 1) * size
    universes = query.offset(offset).limit(size).all()

    return universes


@router.get("/universes/{universe_id}", response_model=TargetUniverseResponseSchema)
@handle_api_errors
async def get_target_universe(universe_id: str, db: Session = Depends(get_db)):
    """
    Get a specific target universe by ID.
    """
    logger.info(f"Getting target universe: {universe_id}")

    manager = TargetUniverseManager(session=db)
    universe = manager.get_universe(universe_id)

    if not universe:
        raise HTTPException(status_code=404, detail="Target universe not found")

    return universe


@router.put("/universes/{universe_id}", response_model=TargetUniverseResponseSchema)
@handle_api_errors
async def update_target_universe(
    universe_id: str,
    request: UpdateTargetUniverseSchema,
    db: Session = Depends(get_db),
    current_user: AccountUser = require_write_permission(Resource.TARGETING),
):
    """
    Update a target universe.
    """
    logger.info(f"Updating target universe: {universe_id}")

    manager = TargetUniverseManager(session=db)

    # Get update fields
    update_data = request.dict(exclude_unset=True)

    universe = manager.update_universe(universe_id, **update_data)

    if not universe:
        raise HTTPException(status_code=404, detail="Target universe not found")

    metrics.increment_counter("targeting_universes_updated")
    logger.info(f"Successfully updated target universe: {universe_id}")

    return universe


@router.delete("/universes/{universe_id}", response_model=BaseResponseSchema)
@handle_api_errors
async def delete_target_universe(
    universe_id: str,
    db: Session = Depends(get_db),
    current_user: AccountUser = require_delete_permission(Resource.TARGETING),
):
    """
    Delete (soft delete) a target universe.
    """
    logger.info(f"Deleting target universe: {universe_id}")

    manager = TargetUniverseManager(session=db)
    success = manager.delete_universe(universe_id)

    if not success:
        raise HTTPException(status_code=404, detail="Target universe not found")

    metrics.increment_counter("targeting_universes_deleted")
    logger.info(f"Successfully deleted target universe: {universe_id}")

    return BaseResponseSchema(message="Target universe deleted successfully")


@router.post("/universes/{universe_id}/refresh", response_model=BaseResponseSchema)
@handle_api_errors
async def refresh_target_universe(
    universe_id: str,
    request: RefreshUniverseSchema,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Refresh target universe data (background task).
    """
    logger.info(f"Refreshing target universe: {universe_id}")

    manager = TargetUniverseManager(session=db)
    universe = manager.get_universe(universe_id)

    if not universe:
        raise HTTPException(status_code=404, detail="Target universe not found")

    # Add background task for refresh
    background_tasks.add_task(manager.update_freshness_metrics, universe_id)

    return BaseResponseSchema(message="Universe refresh started")


# Campaign endpoints
@router.post("/campaigns", response_model=CampaignResponseSchema, status_code=201)
@handle_api_errors
async def create_campaign(request: CreateCampaignSchema, db: Session = Depends(get_db)):
    """
    Create a new campaign.
    """
    logger.info(f"Creating campaign: {request.name}")

    # Verify target universe exists
    universe = db.query(TargetUniverse).filter_by(id=request.target_universe_id).first()
    if not universe:
        raise HTTPException(status_code=404, detail="Target universe not found")

    # Create campaign
    campaign_data = request.dict()
    if campaign_data.get("batch_settings"):
        campaign_data["batch_settings"] = campaign_data["batch_settings"].dict()

    campaign = Campaign(**campaign_data)
    db.add(campaign)
    db.commit()
    db.refresh(campaign)

    metrics.increment_counter("targeting_campaigns_created")
    logger.info(f"Successfully created campaign: {campaign.id}")

    return campaign


@router.get("/campaigns", response_model=list[CampaignResponseSchema])
@handle_api_errors
async def list_campaigns(
    filters: CampaignFilterSchema = Depends(),
    pagination: PaginationSchema = Depends(),
    db: Session = Depends(get_db),
):
    """
    List campaigns with optional filtering and pagination.
    """
    logger.info("Listing campaigns")

    query = db.query(Campaign)

    # Apply filters
    if filters.name_contains:
        query = query.filter(Campaign.name.contains(filters.name_contains))
    if filters.status:
        status_values = [s.value for s in filters.status]
        query = query.filter(Campaign.status.in_(status_values))
    if filters.campaign_type:
        query = query.filter(Campaign.campaign_type == filters.campaign_type)
    if filters.target_universe_id:
        query = query.filter(Campaign.target_universe_id == filters.target_universe_id)
    if filters.created_after:
        query = query.filter(Campaign.created_at >= filters.created_after)
    if filters.created_before:
        query = query.filter(Campaign.created_at <= filters.created_before)

    # Apply pagination
    campaigns = query.offset(pagination.offset).limit(pagination.size).all()

    return campaigns


@router.get("/campaigns/{campaign_id}", response_model=CampaignResponseSchema)
@handle_api_errors
async def get_campaign(campaign_id: str, db: Session = Depends(get_db)):
    """
    Get a specific campaign by ID.
    """
    logger.info(f"Getting campaign: {campaign_id}")

    campaign = db.query(Campaign).filter_by(id=campaign_id).first()

    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    return campaign


@router.put("/campaigns/{campaign_id}", response_model=CampaignResponseSchema)
@handle_api_errors
async def update_campaign(campaign_id: str, request: UpdateCampaignSchema, db: Session = Depends(get_db)):
    """
    Update a campaign.
    """
    logger.info(f"Updating campaign: {campaign_id}")

    campaign = db.query(Campaign).filter_by(id=campaign_id).first()

    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Update fields
    update_data = request.dict(exclude_unset=True)
    if "batch_settings" in update_data and update_data["batch_settings"]:
        update_data["batch_settings"] = update_data["batch_settings"].dict()

    for field, value in update_data.items():
        setattr(campaign, field, value)

    campaign.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(campaign)

    metrics.increment_counter("targeting_campaigns_updated")
    logger.info(f"Successfully updated campaign: {campaign_id}")

    return campaign


# Batch endpoints
@router.post("/batches", response_model=dict[str, Any])
@handle_api_errors
async def create_batches(request: CreateBatchesSchema, db: Session = Depends(get_db)):
    """
    Create daily batches for campaigns.

    Acceptance Criteria:
    - Daily batch creation works
    - No duplicate batches
    """
    logger.info("Creating daily batches")

    scheduler = BatchScheduler(session=db)

    target_date = request.target_date or date.today()
    batch_ids = scheduler.create_daily_batches(datetime.combine(target_date, datetime.min.time()))

    metrics.increment_counter("targeting_batches_created", len(batch_ids))
    logger.info(f"Successfully created {len(batch_ids)} batches")

    return {
        "success": True,
        "message": f"Created {len(batch_ids)} batches",
        "batch_ids": batch_ids,
        "target_date": target_date.isoformat(),
    }


@router.get("/batches", response_model=list[BatchResponseSchema])
@handle_api_errors
async def list_batches(
    filters: BatchFilterSchema = Depends(),
    pagination: PaginationSchema = Depends(),
    db: Session = Depends(get_db),
):
    """
    List campaign batches with optional filtering and pagination.
    """
    logger.info("Listing batches")

    query = db.query(CampaignBatch)

    # Apply filters
    if filters.campaign_id:
        query = query.filter(CampaignBatch.campaign_id == filters.campaign_id)
    if filters.status:
        status_values = [s.value for s in filters.status]
        query = query.filter(CampaignBatch.status.in_(status_values))
    if filters.scheduled_after:
        query = query.filter(CampaignBatch.scheduled_at >= filters.scheduled_after)
    if filters.scheduled_before:
        query = query.filter(CampaignBatch.scheduled_at <= filters.scheduled_before)
    if filters.has_errors is not None:
        if filters.has_errors:
            query = query.filter(CampaignBatch.error_message.isnot(None))
        else:
            query = query.filter(CampaignBatch.error_message.is_(None))

    # Apply pagination
    batches = query.offset(pagination.offset).limit(pagination.size).all()

    return batches


@router.get("/batches/pending", response_model=list[BatchResponseSchema])
@handle_api_errors
async def get_pending_batches(limit: int | None = Query(None, ge=1, le=100), db: Session = Depends(get_db)):
    """
    Get batches ready for processing.
    """
    logger.info("Getting pending batches")

    scheduler = BatchScheduler(session=db)
    batches = scheduler.get_pending_batches(limit=limit)

    return batches


@router.put("/batches/{batch_id}/status", response_model=BaseResponseSchema)
@handle_api_errors
async def update_batch_status(batch_id: str, request: BatchStatusUpdateSchema, db: Session = Depends(get_db)):
    """
    Update batch processing status.
    """
    logger.info(f"Updating batch status: {batch_id}")

    scheduler = BatchScheduler(session=db)

    if request.status.value == "processing":
        success = scheduler.mark_batch_processing(batch_id)
    elif request.status.value == "completed":
        success = scheduler.mark_batch_completed(
            batch_id,
            request.targets_processed or 0,
            request.targets_contacted or 0,
            request.targets_failed or 0,
        )
    elif request.status.value == "failed":
        success = scheduler.mark_batch_failed(batch_id, request.error_message or "Unknown error")
    else:
        raise HTTPException(status_code=400, detail="Invalid status update")

    if not success:
        raise HTTPException(status_code=404, detail="Batch not found")

    metrics.increment_counter("targeting_batches_updated")
    logger.info(f"Successfully updated batch status: {batch_id}")

    return BaseResponseSchema(message="Batch status updated successfully")


# Analytics endpoints
@router.get("/analytics/quota", response_model=QuotaAllocationResponseSchema)
@handle_api_errors
async def get_quota_allocation(target_date: date | None = Query(None), db: Session = Depends(get_db)):
    """
    Get current quota allocation and usage.

    Acceptance Criteria:
    - Quota allocation fair
    """
    logger.info("Getting quota allocation")

    quota_tracker = QuotaTracker(session=db)

    target_date = target_date or date.today()

    total_quota = quota_tracker.get_daily_quota(target_date)
    used_quota = quota_tracker.get_used_quota(target_date)
    remaining_quota = quota_tracker.get_remaining_quota(target_date)

    # Get campaign allocations
    active_campaigns = db.query(Campaign).filter(Campaign.status == "running").all()
    campaign_allocations = {}

    for campaign in active_campaigns:
        allocation = quota_tracker.get_campaign_quota_allocation(campaign.id, target_date)
        campaign_allocations[campaign.id] = {
            "campaign_name": campaign.name,
            **allocation,
        }

    utilization_rate = (used_quota / total_quota * 100) if total_quota > 0 else 0

    return QuotaAllocationResponseSchema(
        total_daily_quota=total_quota,
        used_quota=used_quota,
        remaining_quota=remaining_quota,
        campaign_allocations=campaign_allocations,
        utilization_rate=utilization_rate,
    )


@router.get("/analytics/priorities", response_model=list[UniversePriorityResponseSchema])
@handle_api_errors
async def get_universe_priorities(limit: int | None = Query(10, ge=1, le=50), db: Session = Depends(get_db)):
    """
    Get target universe priorities for scheduling.

    Acceptance Criteria:
    - Priority-based scheduling
    """
    logger.info("Getting universe priorities")

    manager = TargetUniverseManager(session=db)
    priorities = manager.rank_universes_by_priority(limit=limit)

    result = []
    for universe, priority_score in priorities:
        freshness_score = manager.calculate_freshness_score(universe)
        total_score = (priority_score + freshness_score) / 2

        result.append(
            UniversePriorityResponseSchema(
                universe_id=universe.id,
                universe_name=universe.name,
                priority_score=priority_score,
                freshness_score=freshness_score,
                total_score=total_score,
                last_refresh=universe.last_refresh,
                estimated_refresh_time=None,  # Could be calculated based on priority
            )
        )

    return result


# Geographic boundary endpoints
@router.post(
    "/geographic-boundaries",
    response_model=GeographicBoundaryResponseSchema,
    status_code=201,
)
@handle_api_errors
async def create_geographic_boundary(request: CreateGeographicBoundarySchema, db: Session = Depends(get_db)):
    """
    Create a new geographic boundary.
    """
    logger.info(f"Creating geographic boundary: {request.name}")

    boundary = GeographicBoundary(**request.dict())
    db.add(boundary)
    db.commit()
    db.refresh(boundary)

    metrics.increment_counter("targeting_boundaries_created")
    logger.info(f"Successfully created geographic boundary: {boundary.id}")

    return boundary


@router.get("/geographic-boundaries", response_model=list[GeographicBoundaryResponseSchema])
@handle_api_errors
async def list_geographic_boundaries(
    level: str | None = Query(None, description="Filter by geography level"),
    country: str | None = Query("US", description="Filter by country"),
    pagination: PaginationSchema = Depends(),
    db: Session = Depends(get_db),
):
    """
    List geographic boundaries with optional filtering.
    """
    logger.info("Listing geographic boundaries")

    query = db.query(GeographicBoundary)

    if level:
        query = query.filter(GeographicBoundary.level == level)
    if country:
        query = query.filter(GeographicBoundary.country == country)

    # Apply pagination
    boundaries = query.offset(pagination.offset).limit(pagination.size).all()

    return boundaries


# Validation endpoint
@router.post("/validate", response_model=dict[str, Any])
@handle_api_errors
async def validate_targeting_criteria(request: dict[str, Any], db: Session = Depends(get_db)):
    """
    Validate targeting criteria for locations and industries.
    """
    logger.info("Validating targeting criteria")

    # Basic validation logic
    locations = request.get("locations", [])
    industries = request.get("industries", [])

    # Mock validation - in real implementation, would validate against known data
    valid_locations = []
    invalid_locations = []

    for location in locations:
        if location and len(location) > 2:  # Basic validation
            valid_locations.append(location)
        else:
            invalid_locations.append(location)

    valid_industries = []
    invalid_industries = []

    for industry in industries:
        if industry and len(industry) > 2:  # Basic validation
            valid_industries.append(industry)
        else:
            invalid_industries.append(industry)

    return {
        "valid": len(invalid_locations) == 0 and len(invalid_industries) == 0,
        "valid_locations": valid_locations,
        "invalid_locations": invalid_locations,
        "valid_industries": valid_industries,
        "invalid_industries": invalid_industries,
        "message": "Validation completed",
    }


# Universe endpoint alias for backward compatibility
@router.post("/universe", response_model=TargetUniverseResponseSchema, status_code=201)
@handle_api_errors
async def create_target_universe_alias(request: CreateTargetUniverseSchema, db: Session = Depends(get_db)):
    """
    Create a new target universe (alias endpoint for backward compatibility).
    """
    return await create_target_universe(request, db)


# Quota endpoint alias for backward compatibility
@router.get("/quota", response_model=QuotaAllocationResponseSchema)
@handle_api_errors
async def get_quota_allocation_alias(target_date: date | None = Query(None), db: Session = Depends(get_db)):
    """
    Get current quota allocation and usage (alias endpoint for backward compatibility).
    """
    return await get_quota_allocation(target_date, db)


# Health check endpoint
@router.get("/health", response_model=dict[str, Any])
@handle_api_errors
async def targeting_health_check(db: Session = Depends(get_db)):
    """
    Health check for targeting domain.
    """
    try:
        # Test database connection
        db.execute("SELECT 1")

        # Get basic stats
        universe_count = db.query(TargetUniverse).filter(TargetUniverse.is_active).count()
        campaign_count = db.query(Campaign).filter(Campaign.status == "running").count()

        return {
            "status": "healthy",
            "database": "connected",
            "active_universes": universe_count,
            "running_campaigns": campaign_count,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=503, detail="Service unhealthy")


# Include the router in main app with:
# app.include_router(router, prefix="/api/v1/targeting", tags=["targeting"])
