"""
Pydantic schemas for lineage API
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class LineageResponse(BaseModel):
    """Response schema for lineage data"""

    lineage_id: str = Field(..., description="Unique lineage ID")
    report_generation_id: str = Field(..., description="Associated report generation ID")
    lead_id: str = Field(..., description="Lead ID")
    pipeline_run_id: str = Field(..., description="Pipeline run ID")
    template_version_id: str = Field(..., description="Template version used")
    pipeline_duration_seconds: float = Field(..., description="Pipeline execution duration")
    raw_inputs_size_bytes: int = Field(..., description="Size of raw inputs in bytes")
    compression_ratio: float = Field(..., description="Compression ratio percentage")
    created_at: datetime = Field(..., description="Creation timestamp")
    access_count: int = Field(..., description="Number of times accessed")
    last_accessed_at: datetime | None = Field(None, description="Last access timestamp")

    class Config:
        from_attributes = True


class LineageSearchParams(BaseModel):
    """Search parameters for lineage queries"""

    lead_id: str | None = Field(None, description="Filter by lead ID")
    pipeline_run_id: str | None = Field(None, description="Filter by pipeline run ID")
    start_date: datetime | None = Field(None, description="Filter by start date")
    end_date: datetime | None = Field(None, description="Filter by end date")
    limit: int = Field(100, ge=1, le=1000, description="Maximum results to return")


class LineageLogsResponse(BaseModel):
    """Response schema for lineage logs viewer"""

    lineage_id: str
    pipeline_logs: dict[str, Any]
    raw_inputs: dict[str, Any]
    pipeline_start_time: datetime
    pipeline_end_time: datetime
    truncated: bool = Field(False, description="Whether data was truncated")

    class Config:
        from_attributes = True


class LineageAuditLog(BaseModel):
    """Audit log entry for lineage access"""

    id: str
    action: str
    user_id: str | None
    ip_address: str | None
    user_agent: str | None
    accessed_at: datetime

    class Config:
        from_attributes = True


class TemplateDistribution(BaseModel):
    """Template distribution item"""

    version: str
    count: int


class PanelStatsResponse(BaseModel):
    """Response schema for lineage panel statistics"""

    total_records: int = Field(..., description="Total number of lineage records")
    recent_records_24h: int = Field(..., description="Records created in last 24 hours")
    template_distribution: list[TemplateDistribution] = Field(..., description="Distribution by template version")
    total_storage_mb: float = Field(..., description="Total storage used in MB")

    class Config:
        from_attributes = True
