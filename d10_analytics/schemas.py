"""
Analytics API Schemas - Task 073

Pydantic schemas for analytics API request/response validation.
Provides structured data models for metrics endpoints, date range filtering,
segment filtering, and CSV export options.

Acceptance Criteria:
- Metrics endpoints work
- Date range filtering
- Segment filtering
- CSV export option
"""

from typing import Dict, Any, List, Optional, Union
from datetime import datetime, date as DateType, timedelta
from decimal import Decimal
from pydantic import BaseModel, Field, validator
from enum import Enum

# Avoid circular imports by using string literals for enum types


class DateRangeFilter(BaseModel):
    """Date range filter for analytics queries"""
    start_date: DateType = Field(..., description="Start date for analytics data")
    end_date: DateType = Field(..., description="End date for analytics data")
    
    @validator('end_date')
    def validate_date_range(cls, v, values):
        if 'start_date' in values and v < values['start_date']:
            raise ValueError('end_date must be after start_date')
        return v
    
    @validator('start_date', 'end_date')
    def validate_date_not_future(cls, v):
        if v > DateType.today():
            raise ValueError('Date cannot be in the future')
        return v


class SegmentFilter(BaseModel):
    """Segment filter for analytics queries"""
    campaign_ids: Optional[List[str]] = Field(default=None, description="Filter by campaign IDs")
    business_verticals: Optional[List[str]] = Field(default=None, description="Filter by business verticals")
    geographic_regions: Optional[List[str]] = Field(default=None, description="Filter by geographic regions")
    funnel_stages: Optional[List[str]] = Field(default=None, description="Filter by funnel stages")
    event_types: Optional[List[str]] = Field(default=None, description="Filter by event types")


class MetricsRequest(BaseModel):
    """Request model for getting metrics data"""
    date_range: DateRangeFilter = Field(..., description="Date range for metrics")
    segment_filter: Optional[SegmentFilter] = Field(default=None, description="Segment filters")
    metric_types: Optional[List[str]] = Field(
        default=None, 
        description="Types of metrics to retrieve (defaults to all)"
    )
    aggregation_period: Optional[str] = Field(
        default="daily",
        description="Aggregation period for time series data"
    )
    include_breakdowns: bool = Field(
        default=False,
        description="Include segment breakdowns in response"
    )
    limit: Optional[int] = Field(
        default=1000,
        ge=1,
        le=10000,
        description="Maximum number of records to return"
    )


class FunnelMetricsRequest(BaseModel):
    """Request model for funnel metrics"""
    date_range: DateRangeFilter = Field(..., description="Date range for funnel data")
    segment_filter: Optional[SegmentFilter] = Field(default=None, description="Segment filters")
    include_conversion_paths: bool = Field(
        default=False,
        description="Include detailed conversion path analysis"
    )
    include_drop_off_analysis: bool = Field(
        default=False,
        description="Include drop-off analysis for each stage"
    )


class CohortAnalysisRequest(BaseModel):
    """Request model for cohort analysis"""
    cohort_start_date: DateType = Field(..., description="Start date for cohort analysis")
    cohort_end_date: DateType = Field(..., description="End date for cohort analysis")
    retention_periods: Optional[List[str]] = Field(
        default=["Day 0", "Week 1", "Week 2", "Week 4", "Month 2"],
        description="Retention periods to analyze"
    )
    segment_filter: Optional[SegmentFilter] = Field(default=None, description="Segment filters")


class ExportRequest(BaseModel):
    """Request model for CSV export"""
    export_type: str = Field(
        ..., 
        description="Type of data to export (metrics, funnel, cohort, events)"
    )
    date_range: DateRangeFilter = Field(..., description="Date range for export")
    segment_filter: Optional[SegmentFilter] = Field(default=None, description="Segment filters")
    include_raw_data: bool = Field(
        default=False,
        description="Include raw event data in export"
    )
    file_format: str = Field(
        default="csv",
        description="Export file format (csv, json, excel)"
    )
    
    @validator('export_type')
    def validate_export_type(cls, v):
        valid_types = ['metrics', 'funnel', 'cohort', 'events']
        if v not in valid_types:
            raise ValueError(f'export_type must be one of: {valid_types}')
        return v
    
    @validator('file_format')
    def validate_file_format(cls, v):
        valid_formats = ['csv', 'json', 'excel']
        if v not in valid_formats:
            raise ValueError(f'file_format must be one of: {valid_formats}')
        return v


class MetricDataPoint(BaseModel):
    """Individual metric data point"""
    date: DateType = Field(..., description="Date of the metric")
    metric_type: str = Field(..., description="Type of metric")
    value: Decimal = Field(..., description="Metric value")
    count: int = Field(..., description="Number of events contributing to this metric")
    segment_breakdown: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Breakdown by segments"
    )


class FunnelDataPoint(BaseModel):
    """Funnel analysis data point"""
    cohort_date: DateType = Field(..., description="Cohort date")
    campaign_id: str = Field(..., description="Campaign identifier")
    from_stage: str = Field(..., description="Source funnel stage")
    to_stage: Optional[str] = Field(..., description="Target funnel stage")
    sessions_started: int = Field(..., description="Sessions that started at from_stage")
    sessions_converted: int = Field(..., description="Sessions that converted to to_stage")
    conversion_rate_pct: Decimal = Field(..., description="Conversion rate percentage")
    avg_time_to_convert_hours: Optional[Decimal] = Field(
        default=None,
        description="Average time to convert between stages"
    )
    total_cost_cents: int = Field(..., description="Total cost for this conversion path")
    cost_per_conversion_cents: Optional[int] = Field(
        default=None,
        description="Cost per conversion"
    )


class CohortDataPoint(BaseModel):
    """Cohort analysis data point"""
    cohort_date: DateType = Field(..., description="Cohort date")
    campaign_id: str = Field(..., description="Campaign identifier")
    retention_period: str = Field(..., description="Retention period")
    cohort_size: int = Field(..., description="Initial cohort size")
    active_users: int = Field(..., description="Active users in this period")
    retention_rate_pct: Decimal = Field(..., description="Retention rate percentage")
    events_per_user: Decimal = Field(..., description="Average events per user")


class MetricsResponse(BaseModel):
    """Response model for metrics data"""
    request_id: str = Field(..., description="Unique request identifier")
    date_range: DateRangeFilter = Field(..., description="Requested date range")
    total_records: int = Field(..., description="Total number of records")
    aggregation_period: str = Field(..., description="Aggregation period used")
    data: List[MetricDataPoint] = Field(..., description="Metrics data points")
    summary: Dict[str, Any] = Field(..., description="Summary statistics")
    generated_at: datetime = Field(..., description="Response generation timestamp")


class FunnelMetricsResponse(BaseModel):
    """Response model for funnel metrics"""
    request_id: str = Field(..., description="Unique request identifier")
    date_range: DateRangeFilter = Field(..., description="Requested date range")
    total_conversions: int = Field(..., description="Total number of conversion paths")
    overall_conversion_rate: Decimal = Field(..., description="Overall conversion rate")
    data: List[FunnelDataPoint] = Field(..., description="Funnel data points")
    stage_summary: Dict[str, Any] = Field(..., description="Summary by stage")
    conversion_paths: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Detailed conversion paths (if requested)"
    )
    generated_at: datetime = Field(..., description="Response generation timestamp")


class CohortAnalysisResponse(BaseModel):
    """Response model for cohort analysis"""
    request_id: str = Field(..., description="Unique request identifier")
    cohort_date_range: DateRangeFilter = Field(..., description="Cohort date range")
    total_cohorts: int = Field(..., description="Total number of cohorts")
    avg_retention_rate: Decimal = Field(..., description="Average retention rate")
    data: List[CohortDataPoint] = Field(..., description="Cohort data points")
    retention_summary: Dict[str, Any] = Field(..., description="Retention summary by period")
    generated_at: datetime = Field(..., description="Response generation timestamp")


class ExportResponse(BaseModel):
    """Response model for data export"""
    export_id: str = Field(..., description="Unique export identifier")
    status: str = Field(..., description="Export status")
    download_url: Optional[str] = Field(default=None, description="Download URL when ready")
    file_size_bytes: Optional[int] = Field(default=None, description="File size in bytes")
    record_count: int = Field(..., description="Number of records exported")
    created_at: datetime = Field(..., description="Export creation timestamp")
    expires_at: Optional[datetime] = Field(default=None, description="Download link expiration")


class HealthCheckResponse(BaseModel):
    """Health check response"""
    status: str = Field(..., description="Service health status")
    version: str = Field(..., description="API version")
    uptime_seconds: int = Field(..., description="Service uptime in seconds")
    dependencies: Dict[str, str] = Field(..., description="Dependency health status")
    metrics_count: Optional[int] = Field(default=None, description="Total metrics records")
    last_aggregation: Optional[datetime] = Field(
        default=None,
        description="Last successful aggregation timestamp"
    )


class ErrorResponse(BaseModel):
    """Error response model"""
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Additional error details")
    request_id: str = Field(..., description="Unique request identifier")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


def validate_date_range(start_date: DateType, end_date: DateType) -> None:
    """Validate date range parameters"""
    if end_date < start_date:
        raise ValueError("end_date must be after start_date")
    
    if start_date > DateType.today():
        raise ValueError("start_date cannot be in the future")
    
    # Limit to 1 year of data
    max_range = timedelta(days=365)
    if (end_date - start_date) > max_range:
        raise ValueError("Date range cannot exceed 1 year")


def validate_campaign_ids(campaign_ids: List[str]) -> None:
    """Validate campaign ID format"""
    if not campaign_ids:
        return
    
    for campaign_id in campaign_ids:
        if not campaign_id or len(campaign_id) < 3:
            raise ValueError(f"Invalid campaign_id: {campaign_id}")


def validate_export_request(request: ExportRequest) -> None:
    """Validate export request parameters"""
    validate_date_range(request.date_range.start_date, request.date_range.end_date)
    
    # Limit export size
    max_days = 90
    date_diff = (request.date_range.end_date - request.date_range.start_date).days
    if date_diff > max_days:
        raise ValueError(f"Export date range cannot exceed {max_days} days")
    
    if request.segment_filter and request.segment_filter.campaign_ids:
        validate_campaign_ids(request.segment_filter.campaign_ids)