"""
D11 Orchestration Schemas - Task 078

Pydantic schemas for orchestration API endpoints including pipeline triggers,
status checking, experiment management, and run history APIs.

Acceptance Criteria:
- Pipeline trigger API ✓
- Status checking works ✓
- Experiment management ✓
- Run history API ✓
"""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, validator

from .models import ExperimentStatus, PipelineRunStatus, PipelineType, VariantType

# Request/Response schemas for Pipeline API


class PipelineTriggerRequest(BaseModel):
    """Request schema for triggering a pipeline run"""

    pipeline_name: str = Field(..., description="Name of the pipeline to run")
    pipeline_type: PipelineType = Field(default=PipelineType.MANUAL, description="Type of pipeline execution")
    triggered_by: str | None = Field(None, description="User or system triggering the pipeline")
    trigger_reason: str | None = Field(None, description="Reason for triggering the pipeline")
    parameters: dict[str, Any] | None = Field(None, description="Pipeline execution parameters")
    config: dict[str, Any] | None = Field(None, description="Pipeline configuration overrides")
    environment: str = Field(default="production", description="Execution environment")
    scheduled_at: datetime | None = Field(None, description="When to schedule the pipeline")

    @validator("pipeline_name")
    def validate_pipeline_name(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError("Pipeline name cannot be empty")
        return v.strip()


class PipelineRunResponse(BaseModel):
    """Response schema for pipeline run information"""

    run_id: str
    pipeline_name: str
    pipeline_version: str
    status: PipelineRunStatus
    pipeline_type: PipelineType
    triggered_by: str | None
    trigger_reason: str | None

    # Timing information
    scheduled_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    # Execution details
    execution_time_seconds: int | None
    retry_count: int
    max_retries: int
    error_message: str | None
    error_details: dict[str, Any] | None

    # Configuration and parameters
    config: dict[str, Any] | None
    parameters: dict[str, Any] | None
    environment: str

    # Metrics and performance
    records_processed: int | None
    records_failed: int | None
    bytes_processed: int | None
    cost_cents: int | None

    # External system integration
    external_run_id: str | None
    external_system: str | None
    logs_url: str | None

    # Computed properties
    is_complete: bool = Field(..., description="Whether the pipeline is in a terminal state")
    success_rate: float = Field(..., description="Success rate for processed records")

    class Config:
        from_attributes = True


class PipelineStatusResponse(BaseModel):
    """Response schema for pipeline status checking"""

    run_id: str
    status: PipelineRunStatus
    progress_pct: float | None = Field(None, description="Estimated progress percentage")
    current_task: str | None = Field(None, description="Currently executing task")
    tasks_completed: int = Field(0, description="Number of tasks completed")
    tasks_total: int = Field(0, description="Total number of tasks")
    execution_time_seconds: int | None
    estimated_remaining_seconds: int | None
    error_message: str | None
    last_updated: datetime

    class Config:
        from_attributes = True


class PipelineRunHistoryRequest(BaseModel):
    """Request schema for pipeline run history"""

    pipeline_name: str | None = Field(None, description="Filter by pipeline name")
    status: PipelineRunStatus | None = Field(None, description="Filter by status")
    pipeline_type: PipelineType | None = Field(None, description="Filter by pipeline type")
    environment: str | None = Field(None, description="Filter by environment")
    triggered_by: str | None = Field(None, description="Filter by who triggered")

    # Date range filtering
    start_date: datetime | None = Field(None, description="Filter runs after this date")
    end_date: datetime | None = Field(None, description="Filter runs before this date")

    # Pagination
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=50, ge=1, le=1000, description="Number of items per page")

    # Sorting
    sort_by: str = Field(default="created_at", description="Field to sort by")
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$", description="Sort order")

    @validator("end_date")
    def validate_date_range(cls, v, values):
        if v and values.get("start_date") and v < values["start_date"]:
            raise ValueError("end_date must be after start_date")
        return v


class PipelineRunHistoryResponse(BaseModel):
    """Response schema for pipeline run history"""

    runs: list[PipelineRunResponse]
    total_count: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool

    class Config:
        from_attributes = True


# Request/Response schemas for Experiment API


class ExperimentCreateRequest(BaseModel):
    """Request schema for creating a new experiment"""

    name: str = Field(..., description="Unique experiment name")
    description: str | None = Field(None, description="Experiment description")
    hypothesis: str | None = Field(None, description="Experiment hypothesis")
    created_by: str = Field(..., description="User creating the experiment")

    # Timing
    start_date: date | None = Field(None, description="When to start the experiment")
    end_date: date | None = Field(None, description="When to end the experiment")

    # Targeting and traffic
    target_audience: dict[str, Any] | None = Field(None, description="Audience selection criteria")
    traffic_allocation_pct: float = Field(default=100.0, ge=0, le=100, description="% of users in experiment")
    minimum_sample_size: int | None = Field(None, description="Minimum sample size needed")
    maximum_duration_days: int = Field(default=30, gt=0, description="Maximum experiment duration")

    # Metrics and success criteria
    primary_metric: str = Field(..., description="Main success metric")
    secondary_metrics: list[str] | None = Field(None, description="Additional metrics to track")
    success_criteria: dict[str, Any] | None = Field(None, description="Statistical significance criteria")

    # Configuration
    randomization_unit: str = Field(default="user_id", description="Unit for random assignment")
    holdout_pct: float = Field(default=0.0, ge=0, le=100, description="% held out from experiment")
    confidence_level: float = Field(default=0.95, gt=0, lt=1, description="Statistical confidence level")

    @validator("name")
    def validate_name(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError("Experiment name cannot be empty")
        return v.strip()

    @validator("end_date")
    def validate_end_date(cls, v, values):
        if v and values.get("start_date") and v <= values["start_date"]:
            raise ValueError("end_date must be after start_date")
        return v


class ExperimentVariantCreateRequest(BaseModel):
    """Request schema for creating experiment variants"""

    variant_key: str = Field(..., description="Unique variant key")
    name: str = Field(..., description="Variant display name")
    description: str | None = Field(None, description="Variant description")
    variant_type: VariantType = Field(default=VariantType.TREATMENT, description="Type of variant")
    weight: float = Field(default=1.0, ge=0, description="Relative weight for assignment")
    is_control: bool = Field(default=False, description="Whether this is the control variant")
    config: dict[str, Any] | None = Field(None, description="Variant-specific configuration")
    feature_overrides: dict[str, Any] | None = Field(None, description="Feature flag overrides")

    @validator("variant_key")
    def validate_variant_key(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError("Variant key cannot be empty")
        return v.strip()


class ExperimentVariantResponse(BaseModel):
    """Response schema for experiment variants"""

    variant_id: str
    experiment_id: str
    variant_key: str
    name: str
    description: str | None
    variant_type: VariantType
    weight: float
    is_control: bool
    config: dict[str, Any] | None
    feature_overrides: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ExperimentResponse(BaseModel):
    """Response schema for experiment information"""

    experiment_id: str
    name: str
    description: str | None
    hypothesis: str | None
    status: ExperimentStatus
    created_by: str
    approved_by: str | None

    # Timing
    start_date: date | None
    end_date: date | None
    created_at: datetime
    updated_at: datetime

    # Targeting and traffic
    target_audience: dict[str, Any] | None
    traffic_allocation_pct: float
    minimum_sample_size: int | None
    maximum_duration_days: int

    # Metrics and success criteria
    primary_metric: str
    secondary_metrics: list[str] | None
    success_criteria: dict[str, Any] | None

    # Configuration
    randomization_unit: str
    holdout_pct: float
    confidence_level: float

    # Results and analysis
    results: dict[str, Any] | None
    statistical_power: float | None

    # External integration
    analytics_tracking_id: str | None
    feature_flag_key: str | None

    # Relationships
    variants: list[ExperimentVariantResponse] = []

    # Computed properties
    is_active: bool = Field(..., description="Whether experiment is currently active")
    total_traffic_pct: float = Field(..., description="Total traffic percentage including holdout")

    class Config:
        from_attributes = True


class ExperimentUpdateRequest(BaseModel):
    """Request schema for updating an experiment"""

    description: str | None = None
    hypothesis: str | None = None
    status: ExperimentStatus | None = None
    approved_by: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    target_audience: dict[str, Any] | None = None
    traffic_allocation_pct: float | None = Field(None, ge=0, le=100)
    minimum_sample_size: int | None = None
    maximum_duration_days: int | None = Field(None, gt=0)
    secondary_metrics: list[str] | None = None
    success_criteria: dict[str, Any] | None = None
    holdout_pct: float | None = Field(None, ge=0, le=100)
    confidence_level: float | None = Field(None, gt=0, lt=1)
    results: dict[str, Any] | None = None
    statistical_power: float | None = None

    @validator("end_date")
    def validate_end_date(cls, v, values):
        if v and values.get("start_date") and v <= values["start_date"]:
            raise ValueError("end_date must be after start_date")
        return v


class ExperimentListRequest(BaseModel):
    """Request schema for listing experiments"""

    status: ExperimentStatus | None = Field(None, description="Filter by status")
    created_by: str | None = Field(None, description="Filter by creator")

    # Date range filtering
    created_after: datetime | None = Field(None, description="Filter experiments created after this date")
    created_before: datetime | None = Field(None, description="Filter experiments created before this date")

    # Pagination
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=50, ge=1, le=1000, description="Number of items per page")

    # Sorting
    sort_by: str = Field(default="created_at", description="Field to sort by")
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$", description="Sort order")


class ExperimentListResponse(BaseModel):
    """Response schema for experiment listing"""

    experiments: list[ExperimentResponse]
    total_count: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool

    class Config:
        from_attributes = True


# Assignment tracking schemas


class VariantAssignmentRequest(BaseModel):
    """Request schema for variant assignment"""

    experiment_id: str = Field(..., description="Experiment ID")
    assignment_unit: str = Field(..., description="Unit to assign (user_id, session_id, etc.)")
    user_id: str | None = Field(None, description="User identifier")
    session_id: str | None = Field(None, description="Session identifier")
    assignment_context: dict[str, Any] | None = Field(None, description="Context data at assignment time")
    user_properties: dict[str, Any] | None = Field(None, description="User properties at assignment")


class VariantAssignmentResponse(BaseModel):
    """Response schema for variant assignment"""

    assignment_id: str
    experiment_id: str
    variant_id: str
    variant_key: str
    assignment_unit: str
    user_id: str | None
    session_id: str | None
    assigned_at: datetime
    first_exposure_at: datetime | None
    is_forced: bool
    is_holdout: bool
    assignment_context: dict[str, Any] | None

    class Config:
        from_attributes = True


# Common response schemas


class ErrorResponse(BaseModel):
    """Standard error response schema"""

    error: str = Field(..., description="Error message")
    error_code: str | None = Field(None, description="Error code")
    details: dict[str, Any] | None = Field(None, description="Additional error details")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")


class SuccessResponse(BaseModel):
    """Standard success response schema"""

    message: str = Field(..., description="Success message")
    data: dict[str, Any] | None = Field(None, description="Additional response data")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")


# Health check schema


class HealthResponse(BaseModel):
    """Health check response schema"""

    status: str = Field(..., description="Service status")
    version: str = Field(..., description="API version")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Health check timestamp")
    components: dict[str, str] = Field(..., description="Component health status")
