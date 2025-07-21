"""
Pydantic schemas for D1 Targeting API endpoints

Provides request/response validation and OpenAPI documentation generation.
"""

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, model_validator

from .types import BatchProcessingStatus, CampaignStatus, GeographyLevel, VerticalMarket


# Base schemas
class BaseResponseSchema(BaseModel):
    """Base response schema with common fields"""

    success: bool = True
    message: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ErrorResponseSchema(BaseModel):
    """Error response schema"""

    success: bool = False
    error_code: str
    message: str
    details: dict[str, Any] | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PaginationSchema(BaseModel):
    """Pagination parameters"""

    page: int = Field(default=1, ge=1, description="Page number (1-based)")
    size: int = Field(default=20, ge=1, le=100, description="Items per page")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


class PaginatedResponseSchema(BaseResponseSchema):
    """Paginated response wrapper"""

    pagination: dict[str, Any]
    data: list[Any]


# Target Universe schemas
class GeographicConstraintSchema(BaseModel):
    """Geographic constraint for targeting"""

    level: GeographyLevel
    values: list[str] = Field(..., min_items=1, description="Geographic values (states, cities, etc.)")
    radius_miles: float | None = Field(None, gt=0, description="Radius in miles for location-based targeting")
    center_lat: float | None = Field(None, ge=-90, le=90)
    center_lng: float | None = Field(None, ge=-180, le=180)

    @model_validator(mode="after")
    def validate_radius_constraints(self):
        if self.radius_miles is not None and (self.center_lat is None or self.center_lng is None):
            raise ValueError("center_lat and center_lng are required when radius_miles is specified")
        return self


class TargetingCriteriaSchema(BaseModel):
    """Targeting criteria for universe creation"""

    verticals: list[VerticalMarket] = Field(..., min_items=1, description="Target vertical markets")
    geographic_constraints: list[GeographicConstraintSchema] = Field(..., min_items=1)
    business_size_min: int | None = Field(None, ge=1, description="Minimum business size (employees)")
    business_size_max: int | None = Field(None, ge=1, description="Maximum business size (employees)")
    website_required: bool = Field(default=True, description="Require business to have website")
    phone_required: bool = Field(default=True, description="Require business to have phone")
    email_required: bool = Field(default=False, description="Require business to have email")
    min_rating: float | None = Field(None, ge=0, le=5, description="Minimum rating requirement")
    max_age_days: int | None = Field(None, ge=1, description="Maximum age of business data in days")


class CreateTargetUniverseSchema(BaseModel):
    """Request schema for creating target universe"""

    name: str = Field(..., min_length=1, max_length=255, description="Universe name")
    description: str | None = Field(None, max_length=1000, description="Universe description")
    targeting_criteria: TargetingCriteriaSchema
    estimated_size: int | None = Field(None, ge=0, description="Estimated universe size")


class UpdateTargetUniverseSchema(BaseModel):
    """Request schema for updating target universe"""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=1000)
    is_active: bool | None = None


class TargetUniverseResponseSchema(BaseModel):
    """Response schema for target universe"""

    id: str
    name: str
    description: str | None
    verticals: list[str]
    geography_config: dict[str, Any]
    estimated_size: int | None
    actual_size: int
    qualified_count: int
    last_refresh: datetime | None
    created_at: datetime
    updated_at: datetime
    created_by: str | None
    is_active: bool

    class Config:
        from_attributes = True


# Campaign schemas
class BatchSettingsSchema(BaseModel):
    """Batch processing settings"""

    batch_size: int = Field(default=100, ge=1, le=1000, description="Targets per batch")
    max_concurrent_batches: int = Field(default=5, ge=1, le=20, description="Maximum concurrent batches")
    delay_between_batches_seconds: int = Field(default=60, ge=0, description="Delay between batches in seconds")
    retry_failed_attempts: int = Field(default=3, ge=0, le=10, description="Retry attempts for failed batches")
    max_daily_targets: int | None = Field(None, ge=1, description="Maximum targets to process per day")
    allowed_hours_start: time = Field(default=time(9, 0), description="Start of allowed processing hours")
    allowed_hours_end: time = Field(default=time(17, 0), description="End of allowed processing hours")


class CreateCampaignSchema(BaseModel):
    """Request schema for creating campaign"""

    name: str = Field(..., min_length=1, max_length=255, description="Campaign name")
    description: str | None = Field(None, max_length=1000, description="Campaign description")
    target_universe_id: str = Field(..., description="Target universe ID")
    campaign_type: str = Field(default="lead_generation", description="Campaign type")
    batch_settings: BatchSettingsSchema | None = None
    scheduled_start: datetime | None = Field(None, description="Scheduled start time")
    scheduled_end: datetime | None = Field(None, description="Scheduled end time")

    @model_validator(mode="after")
    def validate_end_after_start(self):
        if self.scheduled_end and self.scheduled_start:
            if self.scheduled_end <= self.scheduled_start:
                raise ValueError("scheduled_end must be after scheduled_start")
        return self


class UpdateCampaignSchema(BaseModel):
    """Request schema for updating campaign"""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=1000)
    status: CampaignStatus | None = None
    batch_settings: BatchSettingsSchema | None = None
    scheduled_start: datetime | None = None
    scheduled_end: datetime | None = None


class CampaignResponseSchema(BaseModel):
    """Response schema for campaign"""

    id: str
    name: str
    description: str | None
    target_universe_id: str
    status: str
    campaign_type: str
    scheduled_start: datetime | None
    scheduled_end: datetime | None
    actual_start: datetime | None
    actual_end: datetime | None
    total_targets: int
    contacted_targets: int
    responded_targets: int
    converted_targets: int
    excluded_targets: int
    total_cost: float
    cost_per_contact: float | None
    cost_per_conversion: float | None
    created_at: datetime
    updated_at: datetime
    created_by: str | None

    class Config:
        from_attributes = True


# Batch schemas
class BatchResponseSchema(BaseModel):
    """Response schema for campaign batch"""

    id: str
    campaign_id: str
    batch_number: int
    batch_size: int
    status: str
    scheduled_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    targets_processed: int
    targets_contacted: int
    targets_failed: int
    error_message: str | None
    retry_count: int
    batch_cost: float

    class Config:
        from_attributes = True


class CreateBatchesSchema(BaseModel):
    """Request schema for creating batches"""

    campaign_ids: list[str] | None = Field(None, description="Specific campaign IDs (optional)")
    target_date: date | None = Field(None, description="Date to create batches for (defaults to today)")
    force_recreate: bool = Field(default=False, description="Force recreation of existing batches")


class BatchStatusUpdateSchema(BaseModel):
    """Request schema for updating batch status"""

    status: BatchProcessingStatus
    targets_processed: int | None = Field(None, ge=0)
    targets_contacted: int | None = Field(None, ge=0)
    targets_failed: int | None = Field(None, ge=0)
    error_message: str | None = Field(None, max_length=1000)


# Priority and scheduling schemas
class UniversePriorityResponseSchema(BaseModel):
    """Response schema for universe priority"""

    universe_id: str
    universe_name: str
    priority_score: float
    freshness_score: float
    total_score: float
    last_refresh: datetime | None
    estimated_refresh_time: datetime | None


class QuotaAllocationResponseSchema(BaseModel):
    """Response schema for quota allocation"""

    total_daily_quota: int
    used_quota: int
    remaining_quota: int
    campaign_allocations: dict[str, dict[str, Any]]
    utilization_rate: float


class RefreshUniverseSchema(BaseModel):
    """Request schema for refreshing universe"""

    universe_id: str
    force_full_refresh: bool = Field(default=False, description="Force complete refresh vs incremental")


# Metrics and analytics schemas
class TargetingMetricsResponseSchema(BaseModel):
    """Response schema for targeting metrics"""

    universe_id: str
    universe_name: str
    total_targets: int
    qualified_targets: int
    qualification_rate: float
    last_updated: datetime
    geographical_distribution: dict[str, int]
    vertical_distribution: dict[str, int]
    data_quality_score: float


class CampaignMetricsResponseSchema(BaseModel):
    """Response schema for campaign metrics"""

    campaign_id: str
    campaign_name: str
    total_targets: int
    contacted_targets: int
    responded_targets: int
    converted_targets: int
    contact_rate: float
    response_rate: float
    conversion_rate: float
    total_cost: Decimal
    cost_per_contact: Decimal | None
    cost_per_conversion: Decimal | None
    days_running: int
    avg_daily_contacts: float
    projected_completion: datetime | None


# Geographic boundary schemas
class CreateGeographicBoundarySchema(BaseModel):
    """Request schema for creating geographic boundary"""

    name: str = Field(..., min_length=1, max_length=255)
    level: GeographyLevel
    parent_id: str | None = None
    code: str | None = Field(None, max_length=20, description="State code, ZIP, etc.")
    fips_code: str | None = Field(None, max_length=20, description="Federal Information Processing Standard code")
    center_latitude: float | None = Field(None, ge=-90, le=90)
    center_longitude: float | None = Field(None, ge=-180, le=180)
    country: str = Field(default="US", max_length=10)
    state_code: str | None = Field(None, max_length=10)
    population: int | None = Field(None, ge=0)
    area_sq_miles: float | None = Field(None, gt=0)


class GeographicBoundaryResponseSchema(BaseModel):
    """Response schema for geographic boundary"""

    id: str
    name: str
    level: str
    parent_id: str | None
    code: str | None
    fips_code: str | None
    center_latitude: float | None
    center_longitude: float | None
    country: str
    state_code: str | None
    county_name: str | None
    population: int | None
    area_sq_miles: float | None
    data_source: str | None
    last_updated: datetime

    class Config:
        from_attributes = True


# Bulk operation schemas
class BulkOperationResponseSchema(BaseModel):
    """Response schema for bulk operations"""

    operation_id: str
    operation_type: str
    total_items: int
    processed_items: int
    successful_items: int
    failed_items: int
    errors: list[dict[str, Any]]
    started_at: datetime
    completed_at: datetime | None
    status: str


# Search and filter schemas
class TargetUniverseFilterSchema(BaseModel):
    """Filter schema for target universe search"""

    name_contains: str | None = Field(None, description="Filter by name containing text")
    verticals: list[VerticalMarket] | None = Field(None, description="Filter by verticals")
    is_active: bool | None = Field(None, description="Filter by active status")
    min_size: int | None = Field(None, ge=0, description="Minimum universe size")
    max_size: int | None = Field(None, ge=0, description="Maximum universe size")
    created_after: datetime | None = Field(None, description="Created after date")
    created_before: datetime | None = Field(None, description="Created before date")


class CampaignFilterSchema(BaseModel):
    """Filter schema for campaign search"""

    name_contains: str | None = Field(None, description="Filter by name containing text")
    status: list[CampaignStatus] | None = Field(None, description="Filter by status")
    campaign_type: str | None = Field(None, description="Filter by campaign type")
    target_universe_id: str | None = Field(None, description="Filter by target universe")
    created_after: datetime | None = Field(None, description="Created after date")
    created_before: datetime | None = Field(None, description="Created before date")


class BatchFilterSchema(BaseModel):
    """Filter schema for batch search"""

    campaign_id: str | None = Field(None, description="Filter by campaign")
    status: list[BatchProcessingStatus] | None = Field(None, description="Filter by status")
    scheduled_after: datetime | None = Field(None, description="Scheduled after date")
    scheduled_before: datetime | None = Field(None, description="Scheduled before date")
    has_errors: bool | None = Field(None, description="Filter batches with/without errors")
