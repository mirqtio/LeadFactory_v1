"""
FastAPI endpoints for Lead Explorer Domain

Provides REST API for lead management with CRUD operations,
audit logging, and enrichment tracking.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import ValidationError
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from account_management.models import AccountUser
from core.auth import get_current_user_dependency, require_organization_access
from core.exceptions import LeadFactoryError
from core.exceptions import ValidationError as CoreValidationError
from core.logging import get_logger
from core.metrics import metrics
from database.session import get_db

from .audit import AuditContext
from .enrichment_coordinator import get_enrichment_coordinator
from .permissions import BadgePermissionMiddleware, get_user_badge_permissions
from .repository import AuditRepository, LeadRepository
from .schemas import (  # Badge schemas
    AssignBadgeSchema,
    AuditTrailResponseSchema,
    BadgeFilterSchema,
    BadgeListResponseSchema,
    BadgeResponseSchema,
    CreateBadgeSchema,
    CreateLeadSchema,
    EnrichmentStatusEnum,
    HealthCheckResponseSchema,
    LeadBadgeListResponseSchema,
    LeadBadgeResponseSchema,
    LeadFilterSchema,
    LeadListResponseSchema,
    LeadResponseSchema,
    PaginationSchema,
    QuickAddLeadSchema,
    QuickAddResponseSchema,
    UpdateLeadSchema,
)

# Initialize logger
logger = get_logger("lead_explorer_api", domain="lead_explorer")

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# Create router
router = APIRouter()


# Using global get_db dependency from database.session


def get_user_context(request: Request) -> dict[str, str | None]:
    """Extract user context from request for audit logging"""
    return {
        "user_id": request.headers.get("X-User-ID"),
        "user_ip": request.client.host if request.client else None,
        "user_agent": request.headers.get("User-Agent"),
    }


# Exception handler decorator with audit context
def handle_api_errors(func):
    """Decorator to handle common API errors and set audit context"""
    from functools import wraps

    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Set audit context from request if available
        request = None
        for arg in args:
            if hasattr(arg, "headers"):  # This is the Request object
                request = arg
                break
        for key, value in kwargs.items():
            if hasattr(value, "headers"):  # This is the Request object
                request = value
                break

        if request:
            user_context = get_user_context(request)
            AuditContext.set_user_context(
                user_id=user_context["user_id"], user_ip=user_context["user_ip"], user_agent=user_context["user_agent"]
            )

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
            raise HTTPException(status_code=409, detail="Lead with this email or domain already exists")
        except SQLAlchemyError as e:
            logger.error(f"Database error in {func.__name__}: {str(e)}")
            raise HTTPException(status_code=500, detail="Database operation failed")
        except LeadFactoryError as e:
            logger.error(f"LeadFactory error in {func.__name__}: {str(e)}")
            raise HTTPException(status_code=e.status_code, detail=e.message)
        except Exception as e:
            logger.exception(f"Unexpected error in {func.__name__}: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")
        finally:
            # Clear audit context
            AuditContext.clear_user_context()

    return wrapper


# Lead CRUD endpoints
@router.post("/leads", response_model=LeadResponseSchema, status_code=201)
@limiter.limit("10/second")
@handle_api_errors
async def create_lead(
    lead_data: CreateLeadSchema,
    request: Request,
    db: Session = Depends(get_db),
    current_user: AccountUser = Depends(get_current_user_dependency),
    organization_id: str = Depends(require_organization_access),
):
    """
    Create a new lead with audit logging.

    Acceptance Criteria:
    - Validates input data (email/domain required)
    - Creates lead record with enrichment tracking
    - Logs create action in audit trail
    - Returns 201 with lead data
    """
    logger.info(f"Creating new lead with email={lead_data.email}, domain={lead_data.domain}")

    user_context = get_user_context(request)
    lead_repo = LeadRepository(db)

    # Create the lead (audit logging handled by event listeners)
    lead = lead_repo.create_lead(
        email=lead_data.email,
        domain=lead_data.domain,
        company_name=lead_data.company_name,
        contact_name=lead_data.contact_name,
        is_manual=lead_data.is_manual,
        source=lead_data.source,
        created_by=user_context["user_id"],
    )

    metrics.increment_counter("lead_explorer_leads_created")
    logger.info(f"Successfully created lead: {lead.id}")

    return lead


@router.get("/leads", response_model=LeadListResponseSchema)
@handle_api_errors
async def list_leads(
    filters: LeadFilterSchema = Depends(),
    pagination: PaginationSchema = Depends(),
    db: Session = Depends(get_db),
    current_user: AccountUser = Depends(get_current_user_dependency),
    organization_id: str = Depends(require_organization_access),
):
    """
    List leads with filtering and pagination.

    Supports filtering by:
    - is_manual: Whether lead was manually added
    - enrichment_status: Current enrichment status
    - search: Search in email, domain, company, contact name
    - badge_ids: Filter by specific badge IDs
    - badge_types: Filter by badge types
    - has_badges: Filter leads with/without badges
    - exclude_badge_ids: Exclude leads with specific badges
    """
    logger.info(
        f"Listing leads with filters: is_manual={filters.is_manual}, "
        f"enrichment_status={filters.enrichment_status}, search={filters.search}, "
        f"badge_ids={filters.badge_ids}, badge_types={filters.badge_types}, "
        f"has_badges={filters.has_badges}, exclude_badge_ids={filters.exclude_badge_ids}"
    )

    lead_repo = LeadRepository(db)

    # Convert enum to database enum if provided
    enrichment_status = None
    if filters.enrichment_status:
        from database.models import EnrichmentStatus

        enrichment_status = EnrichmentStatus(filters.enrichment_status.value)

    # Convert badge type enums to strings
    badge_types = None
    if filters.badge_types:
        badge_types = [bt.value for bt in filters.badge_types]

    leads, total_count = lead_repo.list_leads(
        skip=pagination.skip,
        limit=pagination.limit,
        is_manual=filters.is_manual,
        enrichment_status=enrichment_status,
        search=filters.search,
        sort_by=pagination.sort_by,
        sort_order=pagination.sort_order,
        # P0-021: Badge-based filtering
        badge_ids=filters.badge_ids,
        badge_types=badge_types,
        has_badges=filters.has_badges,
        exclude_badge_ids=filters.exclude_badge_ids,
    )

    # Calculate pagination info
    page_info = {
        "current_page": (pagination.skip // pagination.limit) + 1,
        "total_pages": (total_count + pagination.limit - 1) // pagination.limit,
        "page_size": pagination.limit,
        "has_next": pagination.skip + pagination.limit < total_count,
        "has_previous": pagination.skip > 0,
    }

    return LeadListResponseSchema(leads=leads, total_count=total_count, page_info=page_info)


# Search endpoint - convenience wrapper around the list endpoint with search parameter
@router.get("/leads/search", response_model=LeadListResponseSchema)
@handle_api_errors
@limiter.limit("5/minute")
async def search_leads(
    request: Request,
    q: str = Query(..., description="Search query"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Search leads by email, domain, company name, or contact name.

    This is a convenience endpoint that wraps the list endpoint with search functionality.
    """
    skip = (page - 1) * page_size
    filters = LeadFilterSchema(search=q)
    pagination = PaginationSchema(skip=skip, limit=page_size)

    logger.info(f"Searching leads with query: {q}")

    # Use the repository to search
    lead_repo = LeadRepository(db)
    leads, total_count = lead_repo.list_leads(
        skip=skip,
        limit=page_size,
        search=q,
    )

    # Calculate pagination info
    page_info = {
        "current_page": page,
        "total_pages": (total_count + page_size - 1) // page_size,
        "page_size": page_size,
        "has_next": skip + page_size < total_count,
        "has_previous": page > 1,
    }

    return LeadListResponseSchema(leads=leads, total_count=total_count, page_info=page_info)


@router.get("/leads/{lead_id}", response_model=LeadResponseSchema)
@handle_api_errors
async def get_lead(
    lead_id: str,
    db: Session = Depends(get_db),
    current_user: AccountUser = Depends(get_current_user_dependency),
    organization_id: str = Depends(require_organization_access),
):
    """
    Get a specific lead by ID.
    """
    logger.info(f"Getting lead: {lead_id}")

    lead_repo = LeadRepository(db)
    lead = lead_repo.get_lead_by_id(lead_id)

    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    return lead


@router.put("/leads/{lead_id}", response_model=LeadResponseSchema)
@limiter.limit("10/second")
@handle_api_errors
async def update_lead(
    lead_id: str,
    lead_data: UpdateLeadSchema,
    request: Request,
    db: Session = Depends(get_db),
    current_user: AccountUser = Depends(get_current_user_dependency),
    organization_id: str = Depends(require_organization_access),
):
    """
    Update a lead with audit logging.
    """
    logger.info(f"Updating lead: {lead_id}")

    user_context = get_user_context(request)
    lead_repo = LeadRepository(db)

    # Apply updates (audit logging handled by event listeners)
    update_data = lead_data.dict(exclude_unset=True)
    updated_lead = lead_repo.update_lead(lead_id=lead_id, updates=update_data, updated_by=user_context["user_id"])

    if not updated_lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    metrics.increment_counter("lead_explorer_leads_updated")
    logger.info(f"Successfully updated lead: {lead_id}")

    return updated_lead


@router.delete("/leads/{lead_id}", response_model=LeadResponseSchema)
@limiter.limit("10/second")
@handle_api_errors
async def delete_lead(
    lead_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: AccountUser = Depends(get_current_user_dependency),
    organization_id: str = Depends(require_organization_access),
):
    """
    Soft delete a lead with audit logging.
    """
    logger.info(f"Deleting lead: {lead_id}")

    user_context = get_user_context(request)
    lead_repo = LeadRepository(db)

    # Get current lead before deletion
    current_lead = lead_repo.get_lead_by_id(lead_id)
    if not current_lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    # Perform soft delete (audit logging handled by event listeners)
    success = lead_repo.soft_delete_lead(lead_id=lead_id, deleted_by=user_context["user_id"])

    if not success:
        raise HTTPException(status_code=404, detail="Lead not found")

    metrics.increment_counter("lead_explorer_leads_deleted")
    logger.info(f"Successfully deleted lead: {lead_id}")

    return current_lead


@router.post("/leads/quick-add", response_model=QuickAddResponseSchema, status_code=201)
@limiter.limit("10/second")
@handle_api_errors
async def quick_add_lead(lead_data: QuickAddLeadSchema, request: Request, db: Session = Depends(get_db)):
    """
    Quick-add a lead with immediate enrichment scheduling.

    Creates a lead and immediately starts enrichment process.
    """
    logger.info(f"Quick-adding lead with enrichment: email={lead_data.email}, domain={lead_data.domain}")

    user_context = get_user_context(request)
    lead_repo = LeadRepository(db)

    # Create the lead (audit logging handled by event listeners)
    lead = lead_repo.create_lead(
        email=lead_data.email,
        domain=lead_data.domain,
        company_name=lead_data.company_name,
        contact_name=lead_data.contact_name,
        is_manual=True,  # Quick-add leads are manual
        source="quick_add",
        created_by=user_context["user_id"],
    )

    # Start real enrichment process using enrichment coordinator
    coordinator = get_enrichment_coordinator()

    lead_data = {"id": lead.id, "email": lead.email, "domain": lead.domain, "company_name": lead.company_name}

    enrichment_task_id = await coordinator.start_enrichment(lead.id, lead_data)

    # Refresh lead to get updated enrichment status
    db.refresh(lead)

    metrics.increment_counter("lead_explorer_quick_add_created")
    logger.info(f"Successfully quick-added lead: {lead.id} with task: {enrichment_task_id}")

    return QuickAddResponseSchema(
        lead=lead, enrichment_task_id=enrichment_task_id, message="Lead created and enrichment started"
    )


@router.get("/leads/{lead_id}/audit-trail", response_model=AuditTrailResponseSchema)
@handle_api_errors
async def get_audit_trail(lead_id: str, limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db)):
    """
    Get audit trail for a lead.
    """
    logger.info(f"Getting audit trail for lead: {lead_id}")

    # Verify lead exists
    lead_repo = LeadRepository(db)
    lead = lead_repo.get_lead_by_id(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    audit_repo = AuditRepository(db)
    audit_logs = audit_repo.get_audit_trail(lead_id, limit=limit)

    return AuditTrailResponseSchema(lead_id=lead_id, audit_logs=audit_logs, total_count=len(audit_logs))


@router.put("/leads/{lead_id}/enrichment-status")
@limiter.limit("10/second")
@handle_api_errors
async def update_enrichment_status(
    lead_id: str,
    status: EnrichmentStatusEnum,
    request: Request,
    task_id: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    """
    Update enrichment status for a lead.

    Used by enrichment coordinators to update status.
    """
    logger.info(f"Updating enrichment status for lead: {lead_id}, status={status.value}, task_id={task_id}")

    lead_repo = LeadRepository(db)

    # Convert schema enum to database enum
    from database.models import EnrichmentStatus

    db_status = EnrichmentStatus(status.value)

    success = lead_repo.update_enrichment_status(lead_id=lead_id, status=db_status, task_id=task_id, error=error)

    if not success:
        raise HTTPException(status_code=404, detail="Lead not found")

    metrics.increment_counter("lead_explorer_enrichment_status_updated")
    logger.info(f"Successfully updated enrichment status for lead: {lead_id}")

    return {"message": "Enrichment status updated successfully"}


@router.get("/leads/{lead_id}/enrichment-status")
@handle_api_errors
async def get_enrichment_status(lead_id: str):
    """
    Get enrichment status for a lead.
    """
    logger.info(f"Getting enrichment status for lead: {lead_id}")

    coordinator = get_enrichment_coordinator()
    status = coordinator.get_lead_enrichment_status(lead_id)

    if not status:
        raise HTTPException(status_code=404, detail="Lead not found")

    return status


@router.get("/enrichment/task/{task_id}")
@handle_api_errors
async def get_task_status(task_id: str):
    """
    Get status of an enrichment task.
    """
    logger.info(f"Getting status for enrichment task: {task_id}")

    coordinator = get_enrichment_coordinator()
    task_status = coordinator.get_task_status(task_id)

    if not task_status:
        raise HTTPException(status_code=404, detail="Task not found")

    return task_status


# Health check endpoint
@router.get("/health", response_model=HealthCheckResponseSchema)
@handle_api_errors
async def lead_explorer_health_check(db: Session = Depends(get_db)):
    """
    Health check for Lead Explorer domain.
    """
    try:
        # Test database connection
        db.execute(text("SELECT 1"))

        # Get basic stats
        from database.models import Lead

        total_leads = db.query(Lead).filter(~Lead.is_deleted).count()
        manual_leads = db.query(Lead).filter(~Lead.is_deleted, Lead.is_manual).count()

        return HealthCheckResponseSchema(
            status="ok",
            timestamp=datetime.utcnow(),
            database="connected",
            message=f"Lead Explorer is healthy - {total_leads} total leads ({manual_leads} manual)",
        )
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=503, detail="Service unhealthy")


# P0-021: Badge Management API Endpoints
@router.post("/badges", response_model=BadgeResponseSchema, status_code=201)
@limiter.limit("10/second")
@handle_api_errors
async def create_badge(
    badge_data: CreateBadgeSchema,
    request: Request,
    db: Session = Depends(get_db),
    current_user: AccountUser = Depends(get_current_user_dependency),
    organization_id: str = Depends(require_organization_access),
):
    """
    Create a new badge for categorizing leads.

    Only users with proper permissions can create badges.
    System badges can only be created by CPO or admin users.
    Badge types are restricted based on user roles.
    """
    logger.info(f"Creating new badge: {badge_data.name} by user: {current_user.email}")

    # Check permissions using middleware
    badge_dict = badge_data.dict()
    BadgePermissionMiddleware.check_create_badge_permission(current_user, badge_dict, db)

    # Import badge repository here to avoid circular imports
    from .repository import BadgeRepository

    user_context = get_user_context(request)
    badge_repo = BadgeRepository(db)

    # Create the badge
    badge = badge_repo.create_badge(
        name=badge_data.name,
        description=badge_data.description,
        badge_type=badge_data.badge_type.value,
        color=badge_data.color,
        icon=badge_data.icon,
        is_system=badge_data.is_system,
        is_active=badge_data.is_active,
        created_by=user_context["user_id"],
    )

    metrics.increment_counter("lead_explorer_badges_created")
    logger.info(f"Successfully created badge: {badge.id} by user: {current_user.email}")

    return badge


@router.get("/badges", response_model=BadgeListResponseSchema)
@handle_api_errors
async def list_badges(
    filters: BadgeFilterSchema = Depends(),
    pagination: PaginationSchema = Depends(),
    db: Session = Depends(get_db),
    current_user: AccountUser = Depends(get_current_user_dependency),
    organization_id: str = Depends(require_organization_access),
):
    """
    List all available badges with filtering and pagination.

    Supports filtering by badge type, system status, and active status.
    """
    logger.info(f"Listing badges with filters: {filters}")

    from .repository import BadgeRepository

    badge_repo = BadgeRepository(db)

    badges, total_count = badge_repo.list_badges(
        skip=pagination.skip,
        limit=pagination.limit,
        badge_type=filters.badge_type.value if filters.badge_type else None,
        is_system=filters.is_system,
        is_active=filters.is_active,
        search=filters.search,
        sort_by=pagination.sort_by,
        sort_order=pagination.sort_order,
    )

    # Calculate pagination info
    page_info = {
        "current_page": (pagination.skip // pagination.limit) + 1,
        "total_pages": (total_count + pagination.limit - 1) // pagination.limit,
        "page_size": pagination.limit,
        "has_next": pagination.skip + pagination.limit < total_count,
        "has_previous": pagination.skip > 0,
    }

    return BadgeListResponseSchema(badges=badges, total_count=total_count, page_info=page_info)


@router.post("/leads/{lead_id}/badges", response_model=LeadBadgeResponseSchema, status_code=201)
@limiter.limit("10/second")
@handle_api_errors
async def assign_badge_to_lead(
    lead_id: str,
    badge_data: AssignBadgeSchema,
    request: Request,
    db: Session = Depends(get_db),
    current_user: AccountUser = Depends(get_current_user_dependency),
    organization_id: str = Depends(require_organization_access),
):
    """
    Assign a badge to a lead with audit logging.

    Requires appropriate permissions based on user role and badge type.
    """
    logger.info(f"Assigning badge {badge_data.badge_id} to lead: {lead_id} by user: {current_user.email}")

    # Check permissions using middleware
    BadgePermissionMiddleware.check_assign_badge_permission(current_user, badge_data.badge_id, lead_id, db)

    from .repository import BadgeRepository

    user_context = get_user_context(request)
    badge_repo = BadgeRepository(db)

    # Verify lead exists
    lead_repo = LeadRepository(db)
    lead = lead_repo.get_lead_by_id(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    # Assign the badge
    lead_badge = badge_repo.assign_badge_to_lead(
        lead_id=lead_id,
        badge_id=badge_data.badge_id,
        assigned_by=user_context["user_id"],
        notes=badge_data.notes,
        expires_at=badge_data.expires_at,
    )

    metrics.increment_counter("lead_explorer_badges_assigned")
    logger.info(f"Successfully assigned badge {badge_data.badge_id} to lead: {lead_id} by user: {current_user.email}")

    return lead_badge


@router.get("/leads/{lead_id}/badges", response_model=LeadBadgeListResponseSchema)
@handle_api_errors
async def get_lead_badges(
    lead_id: str,
    include_inactive: bool = Query(False, description="Include inactive badge assignments"),
    db: Session = Depends(get_db),
    current_user: AccountUser = Depends(get_current_user_dependency),
    organization_id: str = Depends(require_organization_access),
):
    """Get all badges assigned to a lead."""
    logger.info(f"Getting badges for lead: {lead_id}")

    from .repository import BadgeRepository

    # Verify lead exists
    lead_repo = LeadRepository(db)
    lead = lead_repo.get_lead_by_id(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    badge_repo = BadgeRepository(db)
    lead_badges = badge_repo.get_lead_badges(lead_id=lead_id, include_inactive=include_inactive)

    return LeadBadgeListResponseSchema(lead_badges=lead_badges, total_count=len(lead_badges))


# P0-021: Badge Permission Endpoints
@router.get("/badges/permissions", response_model=dict)
@handle_api_errors
async def get_badge_permissions(
    db: Session = Depends(get_db),
    current_user: AccountUser = Depends(get_current_user_dependency),
    organization_id: str = Depends(require_organization_access),
):
    """
    Get badge management permissions for the current user.

    Returns the user's role, allowed actions, and badge type restrictions.
    """
    logger.info(f"Getting badge permissions for user: {current_user.email}")

    permissions = get_user_badge_permissions(current_user, db)

    return {"user_id": current_user.id, "user_email": current_user.email, "badge_permissions": permissions}


@router.delete("/leads/{lead_id}/badges/{badge_id}", response_model=dict)
@limiter.limit("10/second")
@handle_api_errors
async def remove_badge_from_lead(
    lead_id: str,
    badge_id: str,
    removal_reason: str = Query(None, description="Reason for badge removal"),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: AccountUser = Depends(get_current_user_dependency),
    organization_id: str = Depends(require_organization_access),
):
    """
    Remove a badge from a lead with audit logging.

    Requires appropriate permissions based on user role and badge type.
    """
    logger.info(f"Removing badge {badge_id} from lead: {lead_id} by user: {current_user.email}")

    # Check permissions - removing badges requires same permissions as assigning
    BadgePermissionMiddleware.check_assign_badge_permission(current_user, badge_id, lead_id, db)

    from .repository import BadgeRepository

    user_context = get_user_context(request)
    badge_repo = BadgeRepository(db)

    # Verify lead exists
    lead_repo = LeadRepository(db)
    lead = lead_repo.get_lead_by_id(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    # Remove the badge
    lead_badge = badge_repo.remove_badge_from_lead(
        lead_id=lead_id,
        badge_id=badge_id,
        removed_by=user_context["user_id"],
        removal_reason=removal_reason,
    )

    if not lead_badge:
        raise HTTPException(status_code=404, detail="Badge assignment not found")

    metrics.increment_counter("lead_explorer_badges_removed")
    logger.info(f"Successfully removed badge {badge_id} from lead: {lead_id} by user: {current_user.email}")

    return {"message": "Badge removed successfully", "lead_badge_id": lead_badge.id}


# Include the router in main app with:
# app.include_router(router, prefix="/api/v1/lead-explorer", tags=["lead-explorer"])
