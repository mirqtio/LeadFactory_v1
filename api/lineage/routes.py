"""
Lineage API routes
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, get_current_user_optional
from d6_reports.lineage.compressor import decompress_lineage_data
from d6_reports.lineage.models import ReportLineage
from d6_reports.lineage.tracker import LineageTracker

from .schemas import (
    LineageResponse,
    LineageLogsResponse,
)

router = APIRouter(prefix="/api/lineage", tags=["lineage"])


@router.get("/{report_id}", response_model=LineageResponse)
async def get_lineage_by_report(
    report_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional),
):
    """
    Retrieve lineage data for a specific report generation
    """
    tracker = LineageTracker(db)
    
    # Get lineage data
    lineage = await tracker.get_lineage_by_report(report_id)
    if not lineage:
        raise HTTPException(status_code=404, detail="Lineage not found for this report")
    
    # Record access
    await tracker.record_access(
        lineage_id=lineage.id,
        action="view",
        user_id=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )
    
    return LineageResponse(
        lineage_id=lineage.id,
        report_generation_id=lineage.report_generation_id,
        lead_id=lineage.lead_id,
        pipeline_run_id=lineage.pipeline_run_id,
        template_version_id=lineage.template_version_id,
        pipeline_duration_seconds=lineage.pipeline_duration_seconds,
        raw_inputs_size_bytes=lineage.raw_inputs_size_bytes or 0,
        compression_ratio=float(lineage.compression_ratio or 0),
        created_at=lineage.created_at,
        access_count=lineage.access_count,
        last_accessed_at=lineage.last_accessed_at,
    )


@router.get("/search", response_model=list[LineageResponse])
async def search_lineage(
    lead_id: Optional[str] = Query(None, description="Filter by lead ID"),
    pipeline_run_id: Optional[str] = Query(None, description="Filter by pipeline run ID"),
    start_date: Optional[str] = Query(None, description="Filter by start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="Filter by end date (ISO format)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
    db: AsyncSession = Depends(get_db),
):
    """
    Search lineage records by various criteria
    """
    from datetime import datetime
    
    # Parse dates if provided
    start_dt = None
    end_dt = None
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format")
    
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_date format")
    
    tracker = LineageTracker(db)
    results = await tracker.search_lineage(
        lead_id=lead_id,
        pipeline_run_id=pipeline_run_id,
        start_date=start_dt,
        end_date=end_dt,
        limit=limit,
    )
    
    return [
        LineageResponse(
            lineage_id=lineage.id,
            report_generation_id=lineage.report_generation_id,
            lead_id=lineage.lead_id,
            pipeline_run_id=lineage.pipeline_run_id,
            template_version_id=lineage.template_version_id,
            pipeline_duration_seconds=lineage.pipeline_duration_seconds,
            raw_inputs_size_bytes=lineage.raw_inputs_size_bytes or 0,
            compression_ratio=float(lineage.compression_ratio or 0),
            created_at=lineage.created_at,
            access_count=lineage.access_count,
            last_accessed_at=lineage.last_accessed_at,
        )
        for lineage in results
    ]


@router.get("/{lineage_id}/logs", response_model=LineageLogsResponse)
async def view_lineage_logs(
    lineage_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional),
):
    """
    View JSON logs and raw inputs for a lineage record
    Loads in < 500ms as per requirement
    """
    # Get lineage record
    lineage = await db.get(ReportLineage, lineage_id)
    if not lineage:
        raise HTTPException(status_code=404, detail="Lineage not found")
    
    # Record access
    tracker = LineageTracker(db)
    await tracker.record_access(
        lineage_id=lineage_id,
        action="view_logs",
        user_id=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )
    
    # Decompress raw inputs
    decompressed_data = {}
    truncated = False
    
    if lineage.raw_inputs_compressed:
        decompressed_data = decompress_lineage_data(lineage.raw_inputs_compressed)
        
        # Check if data was truncated
        if "pipeline_logs_truncated" in decompressed_data or "raw_inputs_truncated" in decompressed_data:
            truncated = True
    
    return LineageLogsResponse(
        lineage_id=lineage_id,
        pipeline_logs=lineage.pipeline_logs or decompressed_data.get("pipeline_logs", {}),
        raw_inputs=decompressed_data.get("raw_inputs", decompressed_data.get("raw_inputs_sample", {})),
        pipeline_start_time=lineage.pipeline_start_time,
        pipeline_end_time=lineage.pipeline_end_time,
        truncated=truncated,
    )


@router.get("/{lineage_id}/download")
async def download_raw_inputs(
    lineage_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[str] = Depends(get_current_user_optional),
):
    """
    Download compressed raw inputs (≤2MB with gzip)
    """
    import io
    
    # Get lineage record
    lineage = await db.get(ReportLineage, lineage_id)
    if not lineage:
        raise HTTPException(status_code=404, detail="Lineage not found")
    
    # Record access
    tracker = LineageTracker(db)
    await tracker.record_access(
        lineage_id=lineage_id,
        action="download",
        user_id=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )
    
    # Return compressed data directly
    if lineage.raw_inputs_compressed:
        # Create a file-like object from the compressed data
        file_obj = io.BytesIO(lineage.raw_inputs_compressed)
        
        return StreamingResponse(
            file_obj,
            media_type="application/gzip",
            headers={
                "Content-Disposition": f"attachment; filename=lineage_{lineage_id}_raw_inputs.json.gz",
                "Content-Length": str(len(lineage.raw_inputs_compressed)),
            },
        )
    else:
        # No data available
        return JSONResponse(
            status_code=204,
            content={"detail": "No raw inputs available for this lineage"},
        )