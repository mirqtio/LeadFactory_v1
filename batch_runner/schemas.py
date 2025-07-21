"""
Pydantic schemas for Batch Report Runner API validation

Provides request/response schemas with comprehensive validation
for batch processing operations.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, validator


class BatchStatusEnum(str, Enum):
    """Batch processing status values"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class LeadProcessingStatusEnum(str, Enum):
    """Individual lead processing status values"""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


# Base schemas
class BaseResponseSchema(BaseModel):
    """Base response schema with common fields"""

    class Config:
        from_attributes = True


# Request schemas
class CreateBatchSchema(BaseModel):
    """Schema for creating batch cost preview"""

    lead_ids: list[str] = Field(..., min_items=1, max_items=1000, description="List of lead IDs to process")
    template_version: str = Field(default="v1", description="Report template version")

    @validator("lead_ids")
    def validate_lead_ids(cls, v):
        """Validate lead IDs format"""
        if not v:
            raise ValueError("At least one lead ID is required")

        if len(v) > 1000:
            raise ValueError("Maximum 1000 leads per batch")

        # Check for duplicates
        if len(v) != len(set(v)):
            raise ValueError("Duplicate lead IDs are not allowed")

        return v


class StartBatchSchema(BaseModel):
    """Schema for starting batch processing"""

    lead_ids: list[str] = Field(..., min_items=1, max_items=1000)
    name: str | None = Field(None, max_length=255, description="Batch name")
    description: str | None = Field(None, max_length=1000, description="Batch description")
    template_version: str = Field(default="v1", description="Report template version")
    estimated_cost_usd: float = Field(..., ge=0, description="Estimated cost from preview")
    cost_approved: bool = Field(..., description="User approval of estimated cost")
    max_concurrent: int | None = Field(5, ge=1, le=20, description="Maximum concurrent lead processing")
    retry_failed: bool = Field(True, description="Whether to retry failed leads")
    retry_count: int | None = Field(3, ge=0, le=5, description="Maximum retry attempts")
    created_by: str | None = Field(None, description="User who created the batch")

    @validator("lead_ids")
    def validate_lead_ids(cls, v):
        """Validate lead IDs format"""
        if len(v) > 1000:
            raise ValueError("Maximum 1000 leads per batch")

        if len(v) != len(set(v)):
            raise ValueError("Duplicate lead IDs are not allowed")

        return v


class BatchFilterSchema(BaseModel):
    """Schema for filtering batch list"""

    status: list[str] | None = Field(None, description="Filter by batch status")
    created_by: str | None = Field(None, description="Filter by creator")
    template_version: str | None = Field(None, description="Filter by template version")
    created_after: datetime | None = Field(None, description="Filter by creation date")
    created_before: datetime | None = Field(None, description="Filter by creation date")

    @validator("status")
    def validate_status(cls, v):
        """Validate status values"""
        if v:
            valid_statuses = [status.value for status in BatchStatusEnum]
            for status in v:
                if status not in valid_statuses:
                    raise ValueError(f"Invalid status: {status}")
        return v


class PaginationSchema(BaseModel):
    """Schema for pagination parameters"""

    skip: int = Field(0, ge=0, description="Number of records to skip")
    limit: int = Field(50, ge=1, le=200, description="Number of records to return")


# Response schemas
class BatchPreviewSchema(BaseModel):
    """Schema for batch cost preview response"""

    lead_count: int = Field(description="Number of leads to process")
    valid_lead_ids: list[str] = Field(description="Valid lead IDs found")
    template_version: str = Field(description="Report template version")
    estimated_cost_usd: float = Field(description="Total estimated cost")
    cost_breakdown: dict[str, float] = Field(description="Detailed cost breakdown")
    provider_breakdown: dict[str, dict[str, Any]] = Field(description="Cost breakdown by provider")
    estimated_duration_minutes: int = Field(description="Estimated processing time")
    cost_per_lead: float = Field(description="Average cost per lead")
    is_within_budget: bool = Field(description="Whether cost is within daily budget")
    budget_warning: str | None = Field(description="Budget warning message if applicable")
    accuracy_note: str = Field(description="Cost accuracy disclaimer")


class BatchResponseSchema(BaseModel):
    """Schema for batch processing response"""

    id: str = Field(description="Batch ID")
    name: str | None = Field(description="Batch name")
    description: str | None = Field(description="Batch description")
    status: str = Field(description="Current batch status")
    total_leads: int = Field(description="Total leads in batch")
    processed_leads: int = Field(description="Number of processed leads")
    successful_leads: int = Field(description="Number of successfully processed leads")
    failed_leads: int = Field(description="Number of failed leads")
    progress_percentage: float = Field(description="Progress percentage (0-100)")
    estimated_cost_usd: float | None = Field(description="Estimated cost")
    actual_cost_usd: float | None = Field(description="Actual cost incurred")
    template_version: str = Field(description="Report template version")
    websocket_url: str | None = Field(description="WebSocket URL for progress updates")
    created_at: datetime = Field(description="Creation timestamp")
    started_at: datetime | None = Field(description="Processing start timestamp")
    completed_at: datetime | None = Field(description="Completion timestamp")
    created_by: str | None = Field(description="User who created the batch")
    error_message: str | None = Field(description="Error message if failed")

    class Config:
        from_attributes = True


class BatchStatusResponseSchema(BaseModel):
    """Schema for detailed batch status response"""

    batch_id: str = Field(description="Batch ID")
    status: str = Field(description="Current status")
    progress_percentage: float = Field(description="Progress percentage")
    total_leads: int = Field(description="Total leads")
    processed_leads: int = Field(description="Processed leads")
    successful_leads: int = Field(description="Successful leads")
    failed_leads: int = Field(description="Failed leads")
    current_lead_id: str | None = Field(description="Currently processing lead")
    estimated_cost_usd: float | None = Field(description="Estimated cost")
    actual_cost_usd: float | None = Field(description="Actual cost")
    started_at: str | None = Field(description="Start time ISO string")
    estimated_completion: str | None = Field(description="Estimated completion time")
    recent_results: list[dict[str, Any]] = Field(description="Recent processing results")
    error_summary: dict[str, int] = Field(description="Error summary by type")
    websocket_url: str | None = Field(description="WebSocket URL for real-time updates")


class BatchListResponseSchema(BaseModel):
    """Schema for batch list response"""

    batches: list[BatchResponseSchema] = Field(description="List of batches")
    total_count: int = Field(description="Total number of batches")
    page_info: dict[str, Any] = Field(description="Pagination information")


class LeadResultSchema(BaseModel):
    """Schema for individual lead processing result"""

    lead_id: str = Field(description="Lead ID")
    status: str = Field(description="Processing status")
    report_url: str | None = Field(None, description="Generated report URL")
    actual_cost_usd: float | None = Field(None, description="Actual processing cost")
    processing_duration_ms: int | None = Field(None, description="Processing time in milliseconds")
    quality_score: float | None = Field(None, description="Report quality score")
    error_message: str | None = Field(None, description="Error message if failed")
    error_code: str | None = Field(None, description="Error code if failed")
    retry_count: int = Field(description="Number of retry attempts")
    completed_at: datetime | None = Field(None, description="Completion timestamp")


class WebSocketMessageSchema(BaseModel):
    """Schema for WebSocket progress messages"""

    type: str = Field(description="Message type")
    batch_id: str = Field(description="Batch ID")
    timestamp: str = Field(description="Message timestamp")
    processed: int | None = Field(None, description="Number of processed leads")
    total: int | None = Field(None, description="Total leads")
    successful: int | None = Field(None, description="Successful leads")
    failed: int | None = Field(None, description="Failed leads")
    progress_percentage: float | None = Field(None, description="Progress percentage")
    current_lead: str | None = Field(None, description="Currently processing lead")
    message: str | None = Field(None, description="Status message")
    error_message: str | None = Field(None, description="Error message")
    error_code: str | None = Field(None, description="Error code")


class ErrorResponseSchema(BaseModel):
    """Schema for error responses"""

    error: str = Field(description="Error type")
    message: str = Field(description="Error message")
    details: dict[str, Any] | None = Field(None, description="Additional error details")


class ValidationErrorSchema(BaseModel):
    """Schema for validation error responses"""

    error: str = Field(default="VALIDATION_ERROR", description="Error type")
    message: str = Field(description="Validation error message")
    validation_errors: list[dict[str, str]] = Field(description="Detailed validation errors")


class HealthCheckResponseSchema(BaseModel):
    """Schema for health check response"""

    status: str = Field(default="ok", description="Service status")
    timestamp: datetime = Field(description="Health check timestamp")
    database: str = Field(default="connected", description="Database status")
    message: str = Field(description="Health status message")


class BatchAnalyticsSchema(BaseModel):
    """Schema for batch analytics response"""

    period_days: int = Field(description="Analysis period in days")
    start_date: str = Field(description="Analysis start date")
    statistics: dict[str, float] = Field(description="Aggregate statistics")
    status_breakdown: dict[str, int] = Field(description="Batches by status")
    cost_trends: list[dict[str, Any]] | None = Field(description="Cost trend data")
    performance_metrics: dict[str, float] | None = Field(description="Performance metrics")
    generated_at: str = Field(description="Report generation timestamp")


class CostBreakdownSchema(BaseModel):
    """Schema for detailed cost breakdown"""

    base_cost: float = Field(description="Base report generation cost")
    provider_costs: float = Field(description="Total provider costs")
    subtotal: float = Field(description="Subtotal before discounts")
    volume_discount_rate: float = Field(description="Volume discount rate applied")
    volume_discount_amount: float = Field(description="Volume discount amount")
    discounted_subtotal: float = Field(description="Subtotal after discounts")
    overhead_cost: float = Field(description="Processing overhead cost")
    total_cost: float = Field(description="Final total cost")


class ProviderBreakdownSchema(BaseModel):
    """Schema for provider-specific cost breakdown"""

    leads_processed: int = Field(description="Number of leads processed by this provider")
    cost_per_lead: float = Field(description="Cost per lead for this provider")
    total_cost: float = Field(description="Total cost for this provider")


class BatchConfigurationSchema(BaseModel):
    """Schema for batch processing configuration"""

    max_concurrent_leads: int = Field(default=5, ge=1, le=20, description="Maximum concurrent processing")
    timeout_seconds: int = Field(default=30, ge=10, le=300, description="Processing timeout per lead")
    retry_failed_leads: bool = Field(default=True, description="Whether to retry failed leads")
    max_retry_attempts: int = Field(default=3, ge=0, le=5, description="Maximum retry attempts")
    cost_approval_required: bool = Field(default=True, description="Whether cost approval is required")
    websocket_throttle_seconds: float = Field(default=2.0, ge=0.5, le=10.0, description="WebSocket message throttling")


class BatchSummarySchema(BaseModel):
    """Schema for batch completion summary"""

    batch_id: str = Field(description="Batch ID")
    total_leads: int = Field(description="Total leads processed")
    successful_leads: int = Field(description="Successfully processed leads")
    failed_leads: int = Field(description="Failed leads")
    skipped_leads: int = Field(description="Skipped leads")
    success_rate_percentage: float = Field(description="Success rate percentage")
    total_cost_usd: float = Field(description="Total actual cost")
    average_cost_per_lead: float = Field(description="Average cost per lead")
    processing_duration_seconds: float = Field(description="Total processing duration")
    average_processing_time_per_lead: float = Field(description="Average processing time per lead")
    reports_generated: int = Field(description="Number of reports generated")
    error_summary: dict[str, int] = Field(description="Errors by type")
    completed_at: datetime = Field(description="Completion timestamp")
