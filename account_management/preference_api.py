"""
User Preferences API Endpoints
FastAPI endpoints for user preferences, saved searches, and personalization
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from account_management.models import AccountUser
from account_management.preference_models import (
    PreferenceCategory,
    SavedSearch,
    SearchType,
    UserDashboardLayout,
    UserNotificationPreference,
    UserPreference,
    UserRecentActivity,
)
from account_management.preference_schemas import (
    DashboardLayoutRequest,
    DashboardLayoutResponse,
    NotificationPreferenceRequest,
    NotificationPreferenceResponse,
    PreferencesListResponse,
    RecentActivityResponse,
    SavedSearchesListResponse,
    SavedSearchRequest,
    SavedSearchResponse,
    SavedSearchUpdate,
    UserPreferenceRequest,
    UserPreferenceResponse,
)
from core.auth import get_current_user_dependency
from core.logging import get_logger
from database.session import get_db

logger = get_logger(__name__)

# Create router
router = APIRouter(prefix="/api/v1/preferences", tags=["user-preferences"])


# User Preferences Endpoints
@router.get("/", response_model=PreferencesListResponse)
async def list_user_preferences(
    category: PreferenceCategory | None = Query(None, description="Filter by category"),
    current_user: AccountUser = Depends(get_current_user_dependency),
    db: Session = Depends(get_db),
):
    """List user preferences with optional category filter"""

    query = db.query(UserPreference).filter(UserPreference.user_id == current_user.id)

    if category:
        query = query.filter(UserPreference.category == category)

    preferences = query.order_by(UserPreference.category, UserPreference.key).all()

    # Get available categories for this user
    categories = db.query(UserPreference.category).filter(UserPreference.user_id == current_user.id).distinct().all()

    return PreferencesListResponse(
        preferences=[UserPreferenceResponse.model_validate(p) for p in preferences],
        total=len(preferences),
        categories=[cat[0] for cat in categories],
    )


@router.post("/", response_model=UserPreferenceResponse, status_code=status.HTTP_201_CREATED)
async def create_user_preference(
    preference_data: UserPreferenceRequest,
    current_user: AccountUser = Depends(get_current_user_dependency),
    db: Session = Depends(get_db),
):
    """Create or update a user preference"""

    # Check if preference already exists
    existing = (
        db.query(UserPreference)
        .filter(
            and_(
                UserPreference.user_id == current_user.id,
                UserPreference.category == preference_data.category,
                UserPreference.key == preference_data.key,
            )
        )
        .first()
    )

    if existing:
        # Update existing preference
        existing.value = preference_data.value
        existing.description = preference_data.description
        existing.organization_id = preference_data.organization_id
        existing.team_id = preference_data.team_id
        existing.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(existing)

        return UserPreferenceResponse.model_validate(existing)

    # Create new preference
    preference = UserPreference(
        user_id=current_user.id,
        category=preference_data.category,
        key=preference_data.key,
        value=preference_data.value,
        description=preference_data.description,
        organization_id=preference_data.organization_id,
        team_id=preference_data.team_id,
    )

    db.add(preference)
    db.commit()
    db.refresh(preference)

    logger.info(f"Created preference {preference_data.category}.{preference_data.key} for user {current_user.id}")

    return UserPreferenceResponse.model_validate(preference)


@router.get("/{preference_id}", response_model=UserPreferenceResponse)
async def get_user_preference(
    preference_id: str,
    current_user: AccountUser = Depends(get_current_user_dependency),
    db: Session = Depends(get_db),
):
    """Get specific user preference"""

    preference = (
        db.query(UserPreference)
        .filter(and_(UserPreference.id == preference_id, UserPreference.user_id == current_user.id))
        .first()
    )

    if not preference:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Preference not found")

    return UserPreferenceResponse.model_validate(preference)


@router.delete("/{preference_id}")
async def delete_user_preference(
    preference_id: str,
    current_user: AccountUser = Depends(get_current_user_dependency),
    db: Session = Depends(get_db),
):
    """Delete user preference"""

    preference = (
        db.query(UserPreference)
        .filter(and_(UserPreference.id == preference_id, UserPreference.user_id == current_user.id))
        .first()
    )

    if not preference:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Preference not found")

    db.delete(preference)
    db.commit()

    logger.info(f"Deleted preference {preference_id} for user {current_user.id}")

    return {"message": "Preference deleted successfully"}


# Saved Searches Endpoints
@router.get("/searches", response_model=SavedSearchesListResponse)
async def list_saved_searches(
    search_type: SearchType | None = Query(None, description="Filter by search type"),
    include_public: bool = Query(True, description="Include public searches"),
    current_user: AccountUser = Depends(get_current_user_dependency),
    db: Session = Depends(get_db),
):
    """List user's saved searches with optional filtering"""

    query = db.query(SavedSearch).filter(
        SavedSearch.user_id == current_user.id
        if not include_public
        else SavedSearch.user_id == current_user.id or SavedSearch.is_public == True
    )

    if search_type:
        query = query.filter(SavedSearch.search_type == search_type)

    searches = query.order_by(SavedSearch.last_used_at.desc().nullslast(), SavedSearch.usage_count.desc()).all()

    # Get search counts by type
    type_counts = (
        db.query(SavedSearch.search_type, func.count(SavedSearch.id))
        .filter(SavedSearch.user_id == current_user.id)
        .group_by(SavedSearch.search_type)
        .all()
    )

    by_type = {search_type: count for search_type, count in type_counts}

    return SavedSearchesListResponse(
        searches=[SavedSearchResponse.model_validate(s) for s in searches],
        total=len(searches),
        by_type=by_type,
    )


@router.post("/searches", response_model=SavedSearchResponse, status_code=status.HTTP_201_CREATED)
async def create_saved_search(
    search_data: SavedSearchRequest,
    current_user: AccountUser = Depends(get_current_user_dependency),
    db: Session = Depends(get_db),
):
    """Create a new saved search"""

    # Check for name uniqueness for this user
    existing = (
        db.query(SavedSearch)
        .filter(
            and_(
                SavedSearch.user_id == current_user.id,
                SavedSearch.name == search_data.name,
                SavedSearch.search_type == search_data.search_type,
            )
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Search with name '{search_data.name}' already exists for this search type",
        )

    # If setting as default, unset other defaults for this search type
    if search_data.is_default:
        db.query(SavedSearch).filter(
            and_(
                SavedSearch.user_id == current_user.id,
                SavedSearch.search_type == search_data.search_type,
                SavedSearch.is_default == True,
            )
        ).update({"is_default": False})

    search = SavedSearch(
        user_id=current_user.id,
        name=search_data.name,
        description=search_data.description,
        search_type=search_data.search_type,
        query_params=search_data.query_params,
        sort_config=search_data.sort_config,
        display_config=search_data.display_config,
        is_public=search_data.is_public,
        is_default=search_data.is_default,
        organization_id=search_data.organization_id,
        team_id=search_data.team_id,
    )

    db.add(search)
    db.commit()
    db.refresh(search)

    logger.info(f"Created saved search '{search_data.name}' for user {current_user.id}")

    return SavedSearchResponse.model_validate(search)


@router.get("/searches/{search_id}", response_model=SavedSearchResponse)
async def get_saved_search(
    search_id: str,
    current_user: AccountUser = Depends(get_current_user_dependency),
    db: Session = Depends(get_db),
):
    """Get specific saved search and increment usage count"""

    search = (
        db.query(SavedSearch)
        .filter(
            and_(
                SavedSearch.id == search_id,
                SavedSearch.user_id == current_user.id or SavedSearch.is_public == True,
            )
        )
        .first()
    )

    if not search:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved search not found")

    # Increment usage count and update last used timestamp
    search.usage_count += 1
    search.last_used_at = datetime.utcnow()
    db.commit()

    return SavedSearchResponse.model_validate(search)


@router.put("/searches/{search_id}", response_model=SavedSearchResponse)
async def update_saved_search(
    search_id: str,
    search_data: SavedSearchUpdate,
    current_user: AccountUser = Depends(get_current_user_dependency),
    db: Session = Depends(get_db),
):
    """Update saved search"""

    search = (
        db.query(SavedSearch).filter(and_(SavedSearch.id == search_id, SavedSearch.user_id == current_user.id)).first()
    )

    if not search:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved search not found")

    # Check name uniqueness if changing name
    if search_data.name and search_data.name != search.name:
        existing = (
            db.query(SavedSearch)
            .filter(
                and_(
                    SavedSearch.user_id == current_user.id,
                    SavedSearch.name == search_data.name,
                    SavedSearch.search_type == search.search_type,
                    SavedSearch.id != search_id,
                )
            )
            .first()
        )

        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Search with name '{search_data.name}' already exists for this search type",
            )

    # If setting as default, unset other defaults
    if search_data.is_default:
        db.query(SavedSearch).filter(
            and_(
                SavedSearch.user_id == current_user.id,
                SavedSearch.search_type == search.search_type,
                SavedSearch.is_default == True,
                SavedSearch.id != search_id,
            )
        ).update({"is_default": False})

    # Update fields
    update_data = search_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(search, field, value)

    search.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(search)

    logger.info(f"Updated saved search {search_id} for user {current_user.id}")

    return SavedSearchResponse.model_validate(search)


@router.delete("/searches/{search_id}")
async def delete_saved_search(
    search_id: str,
    current_user: AccountUser = Depends(get_current_user_dependency),
    db: Session = Depends(get_db),
):
    """Delete saved search"""

    search = (
        db.query(SavedSearch).filter(and_(SavedSearch.id == search_id, SavedSearch.user_id == current_user.id)).first()
    )

    if not search:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved search not found")

    db.delete(search)
    db.commit()

    logger.info(f"Deleted saved search {search_id} for user {current_user.id}")

    return {"message": "Saved search deleted successfully"}


# Dashboard Layout Endpoints
@router.get("/dashboard-layouts", response_model=list[DashboardLayoutResponse])
async def list_dashboard_layouts(
    current_user: AccountUser = Depends(get_current_user_dependency),
    db: Session = Depends(get_db),
):
    """List user's dashboard layouts"""

    layouts = (
        db.query(UserDashboardLayout)
        .filter(UserDashboardLayout.user_id == current_user.id)
        .order_by(UserDashboardLayout.is_default.desc(), UserDashboardLayout.name)
        .all()
    )

    return [DashboardLayoutResponse.model_validate(layout) for layout in layouts]


@router.post("/dashboard-layouts", response_model=DashboardLayoutResponse, status_code=status.HTTP_201_CREATED)
async def create_dashboard_layout(
    layout_data: DashboardLayoutRequest,
    current_user: AccountUser = Depends(get_current_user_dependency),
    db: Session = Depends(get_db),
):
    """Create dashboard layout"""

    # If setting as default, unset other defaults
    if layout_data.is_default:
        db.query(UserDashboardLayout).filter(
            and_(
                UserDashboardLayout.user_id == current_user.id,
                UserDashboardLayout.is_default == True,
            )
        ).update({"is_default": False})

    layout = UserDashboardLayout(
        user_id=current_user.id,
        name=layout_data.name,
        layout_config=layout_data.layout_config,
        widget_config=layout_data.widget_config,
        is_default=layout_data.is_default,
        organization_id=layout_data.organization_id,
    )

    db.add(layout)
    db.commit()
    db.refresh(layout)

    logger.info(f"Created dashboard layout '{layout_data.name}' for user {current_user.id}")

    return DashboardLayoutResponse.model_validate(layout)


# Notification Preferences Endpoints
@router.get("/notifications", response_model=list[NotificationPreferenceResponse])
async def list_notification_preferences(
    current_user: AccountUser = Depends(get_current_user_dependency),
    db: Session = Depends(get_db),
):
    """List user's notification preferences"""

    preferences = (
        db.query(UserNotificationPreference)
        .filter(UserNotificationPreference.user_id == current_user.id)
        .order_by(UserNotificationPreference.event_type)
        .all()
    )

    return [NotificationPreferenceResponse.model_validate(pref) for pref in preferences]


@router.put("/notifications/{event_type}", response_model=NotificationPreferenceResponse)
async def update_notification_preference(
    event_type: str,
    preference_data: NotificationPreferenceRequest,
    current_user: AccountUser = Depends(get_current_user_dependency),
    db: Session = Depends(get_db),
):
    """Update notification preference for specific event type"""

    # Find existing preference or create new one
    preference = (
        db.query(UserNotificationPreference)
        .filter(
            and_(
                UserNotificationPreference.user_id == current_user.id,
                UserNotificationPreference.event_type == event_type,
            )
        )
        .first()
    )

    if preference:
        # Update existing
        preference.email_enabled = preference_data.email_enabled
        preference.in_app_enabled = preference_data.in_app_enabled
        preference.sms_enabled = preference_data.sms_enabled
        preference.push_enabled = preference_data.push_enabled
        preference.frequency = preference_data.frequency
        preference.quiet_hours_start = preference_data.quiet_hours_start
        preference.quiet_hours_end = preference_data.quiet_hours_end
        preference.config = preference_data.config
        preference.updated_at = datetime.utcnow()
    else:
        # Create new
        preference = UserNotificationPreference(
            user_id=current_user.id,
            event_type=event_type,
            email_enabled=preference_data.email_enabled,
            in_app_enabled=preference_data.in_app_enabled,
            sms_enabled=preference_data.sms_enabled,
            push_enabled=preference_data.push_enabled,
            frequency=preference_data.frequency,
            quiet_hours_start=preference_data.quiet_hours_start,
            quiet_hours_end=preference_data.quiet_hours_end,
            config=preference_data.config,
        )
        db.add(preference)

    db.commit()
    db.refresh(preference)

    logger.info(f"Updated notification preference for {event_type} for user {current_user.id}")

    return NotificationPreferenceResponse.model_validate(preference)


# Recent Activity Endpoint
@router.get("/recent-activity", response_model=list[RecentActivityResponse])
async def get_recent_activity(
    limit: int = Query(20, ge=1, le=100, description="Number of recent activities to return"),
    activity_type: str | None = Query(None, description="Filter by activity type"),
    current_user: AccountUser = Depends(get_current_user_dependency),
    db: Session = Depends(get_db),
):
    """Get user's recent activity"""

    query = db.query(UserRecentActivity).filter(UserRecentActivity.user_id == current_user.id)

    if activity_type:
        query = query.filter(UserRecentActivity.activity_type == activity_type)

    activities = query.order_by(UserRecentActivity.last_accessed_at.desc()).limit(limit).all()

    return [RecentActivityResponse.model_validate(activity) for activity in activities]


@router.post("/track-activity")
async def track_user_activity(
    activity_type: str,
    resource_type: str,
    resource_id: str | None = None,
    metadata: dict | None = None,
    current_user: AccountUser = Depends(get_current_user_dependency),
    db: Session = Depends(get_db),
):
    """Track user activity for recommendations"""

    # Find existing activity or create new one
    activity = (
        db.query(UserRecentActivity)
        .filter(
            and_(
                UserRecentActivity.user_id == current_user.id,
                UserRecentActivity.activity_type == activity_type,
                UserRecentActivity.resource_type == resource_type,
                UserRecentActivity.resource_id == resource_id,
            )
        )
        .first()
    )

    if activity:
        # Update existing
        activity.access_count += 1
        activity.last_accessed_at = datetime.utcnow()
        if metadata:
            activity.activity_metadata = metadata
    else:
        # Create new
        activity = UserRecentActivity(
            user_id=current_user.id,
            activity_type=activity_type,
            resource_type=resource_type,
            resource_id=resource_id,
            activity_metadata=metadata,
        )
        db.add(activity)

    db.commit()

    return {"message": "Activity tracked successfully"}
