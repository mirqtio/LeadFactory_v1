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

from datetime import datetime, date
from typing import Optional, Dict, Any, List
from enum import Enum

from pydantic import BaseModel, Field, validator
from decimal import Decimal

from .models import PipelineRunStatus, ExperimentStatus, PipelineType, VariantType


# Request/Response schemas for Pipeline API

class PipelineTriggerRequest(BaseModel):
    """Request schema for triggering a pipeline run"""
    pipeline_name: str = Field(..., description="Name of the pipeline to run")
    pipeline_type: PipelineType = Field(default=PipelineType.MANUAL, description="Type of pipeline execution")
    triggered_by: Optional[str] = Field(None, description="User or system triggering the pipeline")
    trigger_reason: Optional[str] = Field(None, description="Reason for triggering the pipeline")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Pipeline execution parameters")
    config: Optional[Dict[str, Any]] = Field(None, description="Pipeline configuration overrides")
    environment: str = Field(default="production", description="Execution environment")
    scheduled_at: Optional[datetime] = Field(None, description="When to schedule the pipeline")

    @validator('pipeline_name')
    def validate_pipeline_name(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Pipeline name cannot be empty')
        return v.strip()


class PipelineRunResponse(BaseModel):
    """Response schema for pipeline run information"""
    run_id: str
    pipeline_name: str
    pipeline_version: str
    status: PipelineRunStatus
    pipeline_type: PipelineType
    triggered_by: Optional[str]
    trigger_reason: Optional[str]
    
    # Timing information
    scheduled_at: Optional[datetime]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    # Execution details
    execution_time_seconds: Optional[int]
    retry_count: int
    max_retries: int
    error_message: Optional[str]
    error_details: Optional[Dict[str, Any]]
    
    # Configuration and parameters
    config: Optional[Dict[str, Any]]
    parameters: Optional[Dict[str, Any]]
    environment: str
    
    # Metrics and performance
    records_processed: Optional[int]
    records_failed: Optional[int]
    bytes_processed: Optional[int]
    cost_cents: Optional[int]
    
    # External system integration
    external_run_id: Optional[str]
    external_system: Optional[str]
    logs_url: Optional[str]
    
    # Computed properties
    is_complete: bool = Field(..., description="Whether the pipeline is in a terminal state")
    success_rate: float = Field(..., description="Success rate for processed records")

    class Config:
        from_attributes = True


class PipelineStatusResponse(BaseModel):
    """Response schema for pipeline status checking"""
    run_id: str
    status: PipelineRunStatus
    progress_pct: Optional[float] = Field(None, description="Estimated progress percentage")
    current_task: Optional[str] = Field(None, description="Currently executing task")
    tasks_completed: int = Field(0, description="Number of tasks completed")
    tasks_total: int = Field(0, description="Total number of tasks")
    execution_time_seconds: Optional[int]
    estimated_remaining_seconds: Optional[int]
    error_message: Optional[str]
    last_updated: datetime

    class Config:
        from_attributes = True


class PipelineRunHistoryRequest(BaseModel):
    """Request schema for pipeline run history"""
    pipeline_name: Optional[str] = Field(None, description="Filter by pipeline name")
    status: Optional[PipelineRunStatus] = Field(None, description="Filter by status")
    pipeline_type: Optional[PipelineType] = Field(None, description="Filter by pipeline type")
    environment: Optional[str] = Field(None, description="Filter by environment")
    triggered_by: Optional[str] = Field(None, description="Filter by who triggered")
    
    # Date range filtering
    start_date: Optional[datetime] = Field(None, description="Filter runs after this date")
    end_date: Optional[datetime] = Field(None, description="Filter runs before this date")
    
    # Pagination
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=50, ge=1, le=1000, description="Number of items per page")
    
    # Sorting
    sort_by: str = Field(default="created_at", description="Field to sort by")
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$", description="Sort order")

    @validator('end_date')
    def validate_date_range(cls, v, values):
        if v and values.get('start_date') and v < values['start_date']:
            raise ValueError('end_date must be after start_date')
        return v


class PipelineRunHistoryResponse(BaseModel):
    """Response schema for pipeline run history"""
    runs: List[PipelineRunResponse]
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
    description: Optional[str] = Field(None, description="Experiment description")
    hypothesis: Optional[str] = Field(None, description="Experiment hypothesis")
    created_by: str = Field(..., description="User creating the experiment")
    
    # Timing
    start_date: Optional[date] = Field(None, description="When to start the experiment")
    end_date: Optional[date] = Field(None, description="When to end the experiment")
    
    # Targeting and traffic
    target_audience: Optional[Dict[str, Any]] = Field(None, description="Audience selection criteria")
    traffic_allocation_pct: float = Field(default=100.0, ge=0, le=100, description="% of users in experiment")
    minimum_sample_size: Optional[int] = Field(None, description="Minimum sample size needed")
    maximum_duration_days: int = Field(default=30, gt=0, description="Maximum experiment duration")
    
    # Metrics and success criteria
    primary_metric: str = Field(..., description="Main success metric")
    secondary_metrics: Optional[List[str]] = Field(None, description="Additional metrics to track")
    success_criteria: Optional[Dict[str, Any]] = Field(None, description="Statistical significance criteria")
    
    # Configuration
    randomization_unit: str = Field(default="user_id", description="Unit for random assignment")
    holdout_pct: float = Field(default=0.0, ge=0, le=100, description="% held out from experiment")
    confidence_level: float = Field(default=0.95, gt=0, lt=1, description="Statistical confidence level")

    @validator('name')
    def validate_name(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Experiment name cannot be empty')
        return v.strip()

    @validator('end_date')
    def validate_end_date(cls, v, values):
        if v and values.get('start_date') and v <= values['start_date']:
            raise ValueError('end_date must be after start_date')
        return v


class ExperimentVariantCreateRequest(BaseModel):
    """Request schema for creating experiment variants"""
    variant_key: str = Field(..., description="Unique variant key")
    name: str = Field(..., description="Variant display name")
    description: Optional[str] = Field(None, description="Variant description")
    variant_type: VariantType = Field(default=VariantType.TREATMENT, description="Type of variant")
    weight: float = Field(default=1.0, ge=0, description="Relative weight for assignment")
    is_control: bool = Field(default=False, description="Whether this is the control variant")
    config: Optional[Dict[str, Any]] = Field(None, description="Variant-specific configuration")
    feature_overrides: Optional[Dict[str, Any]] = Field(None, description="Feature flag overrides")

    @validator('variant_key')
    def validate_variant_key(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Variant key cannot be empty')
        return v.strip()


class ExperimentVariantResponse(BaseModel):
    """Response schema for experiment variants"""
    variant_id: str
    experiment_id: str
    variant_key: str
    name: str
    description: Optional[str]
    variant_type: VariantType
    weight: float
    is_control: bool
    config: Optional[Dict[str, Any]]
    feature_overrides: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ExperimentResponse(BaseModel):
    """Response schema for experiment information"""
    experiment_id: str
    name: str
    description: Optional[str]
    hypothesis: Optional[str]
    status: ExperimentStatus
    created_by: str
    approved_by: Optional[str]
    
    # Timing
    start_date: Optional[date]
    end_date: Optional[date]
    created_at: datetime
    updated_at: datetime
    
    # Targeting and traffic
    target_audience: Optional[Dict[str, Any]]
    traffic_allocation_pct: float
    minimum_sample_size: Optional[int]
    maximum_duration_days: int
    
    # Metrics and success criteria
    primary_metric: str
    secondary_metrics: Optional[List[str]]
    success_criteria: Optional[Dict[str, Any]]
    
    # Configuration
    randomization_unit: str
    holdout_pct: float
    confidence_level: float
    
    # Results and analysis
    results: Optional[Dict[str, Any]]
    statistical_power: Optional[float]
    
    # External integration
    analytics_tracking_id: Optional[str]
    feature_flag_key: Optional[str]
    
    # Relationships
    variants: List[ExperimentVariantResponse] = []
    
    # Computed properties
    is_active: bool = Field(..., description="Whether experiment is currently active")
    total_traffic_pct: float = Field(..., description="Total traffic percentage including holdout")

    class Config:
        from_attributes = True


class ExperimentUpdateRequest(BaseModel):
    """Request schema for updating an experiment"""
    description: Optional[str] = None
    hypothesis: Optional[str] = None
    status: Optional[ExperimentStatus] = None
    approved_by: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    target_audience: Optional[Dict[str, Any]] = None
    traffic_allocation_pct: Optional[float] = Field(None, ge=0, le=100)
    minimum_sample_size: Optional[int] = None
    maximum_duration_days: Optional[int] = Field(None, gt=0)
    secondary_metrics: Optional[List[str]] = None
    success_criteria: Optional[Dict[str, Any]] = None
    holdout_pct: Optional[float] = Field(None, ge=0, le=100)
    confidence_level: Optional[float] = Field(None, gt=0, lt=1)
    results: Optional[Dict[str, Any]] = None
    statistical_power: Optional[float] = None

    @validator('end_date')
    def validate_end_date(cls, v, values):
        if v and values.get('start_date') and v <= values['start_date']:
            raise ValueError('end_date must be after start_date')
        return v


class ExperimentListRequest(BaseModel):
    """Request schema for listing experiments"""
    status: Optional[ExperimentStatus] = Field(None, description="Filter by status")
    created_by: Optional[str] = Field(None, description="Filter by creator")
    
    # Date range filtering
    created_after: Optional[datetime] = Field(None, description="Filter experiments created after this date")
    created_before: Optional[datetime] = Field(None, description="Filter experiments created before this date")
    
    # Pagination
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=50, ge=1, le=1000, description="Number of items per page")
    
    # Sorting
    sort_by: str = Field(default="created_at", description="Field to sort by")
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$", description="Sort order")


class ExperimentListResponse(BaseModel):
    """Response schema for experiment listing"""
    experiments: List[ExperimentResponse]
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
    user_id: Optional[str] = Field(None, description="User identifier")
    session_id: Optional[str] = Field(None, description="Session identifier")
    assignment_context: Optional[Dict[str, Any]] = Field(None, description="Context data at assignment time")
    user_properties: Optional[Dict[str, Any]] = Field(None, description="User properties at assignment")


class VariantAssignmentResponse(BaseModel):
    """Response schema for variant assignment"""
    assignment_id: str
    experiment_id: str
    variant_id: str
    variant_key: str
    assignment_unit: str
    user_id: Optional[str]
    session_id: Optional[str]
    assigned_at: datetime
    first_exposure_at: Optional[datetime]
    is_forced: bool
    is_holdout: bool
    assignment_context: Optional[Dict[str, Any]]

    class Config:
        from_attributes = True


# Common response schemas

class ErrorResponse(BaseModel):
    """Standard error response schema"""
    error: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Error code")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")


class SuccessResponse(BaseModel):
    """Standard success response schema"""
    message: str = Field(..., description="Success message")
    data: Optional[Dict[str, Any]] = Field(None, description="Additional response data")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")


# Health check schema

class HealthResponse(BaseModel):
    """Health check response schema"""
    status: str = Field(..., description="Service status")
    version: str = Field(..., description="API version")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Health check timestamp")
    components: Dict[str, str] = Field(..., description="Component health status")