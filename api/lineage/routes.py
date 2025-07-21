"""
Lineage API routes
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from api.dependencies import get_current_user_optional, get_db
from d6_reports.lineage.compressor import decompress_lineage_data
from d6_reports.lineage.models import ReportLineage
from d6_reports.lineage.tracker import LineageTracker

from .schemas import LineageResponse, PanelStatsResponse

router = APIRouter(prefix="/api/lineage", tags=["lineage"])


@router.get("/search", response_model=list[LineageResponse])
def search_lineage(
    lead_id: str | None = Query(None, description="Filter by lead ID"),
    pipeline_run_id: str | None = Query(None, description="Filter by pipeline run ID"),
    template_version_id: str | None = Query(None, description="Filter by template version ID"),
    start_date: str | None = Query(None, description="Filter by start date (ISO format)"),
    end_date: str | None = Query(None, description="Filter by end date (ISO format)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
    db: Session = Depends(get_db),
):
    """
    Search lineage records by various criteria
    """
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
    results = tracker.search_lineage(
        lead_id=lead_id,
        pipeline_run_id=pipeline_run_id,
        template_version_id=template_version_id,
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
            pipeline_duration_seconds=lineage.pipeline_duration_seconds or 0,
            raw_inputs_size_bytes=lineage.raw_inputs_size_bytes or 0,
            compression_ratio=float(lineage.compression_ratio or 0),
            created_at=lineage.created_at,
            access_count=lineage.access_count or 0,
            last_accessed_at=lineage.last_accessed_at,
        )
        for lineage in results
    ]


@router.get("/{report_id}", response_model=LineageResponse)
def get_lineage_by_report(
    report_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: str | None = Depends(get_current_user_optional),
):
    """
    Retrieve lineage data for a specific report generation
    """
    tracker = LineageTracker(db)

    # Get lineage data
    lineage = tracker.get_lineage_by_report(report_id)
    if not lineage:
        raise HTTPException(status_code=404, detail="Lineage not found for this report")

    # Record access
    tracker.record_access(
        lineage_id=lineage.id,
        action="view_lineage",
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
        pipeline_duration_seconds=lineage.pipeline_duration_seconds or 0,
        raw_inputs_size_bytes=lineage.raw_inputs_size_bytes or 0,
        compression_ratio=float(lineage.compression_ratio or 0),
        created_at=lineage.created_at,
        access_count=lineage.access_count or 0,
        last_accessed_at=lineage.last_accessed_at,
    )


@router.get("/{lineage_id}/logs")
def view_lineage_logs(
    lineage_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: str | None = Depends(get_current_user_optional),
):
    """
    View JSON logs and raw inputs for a lineage record
    Loads in < 500ms as per requirement
    """
    # Get lineage record
    lineage = db.query(ReportLineage).filter(ReportLineage.id == lineage_id).first()
    if not lineage:
        raise HTTPException(status_code=404, detail="Lineage not found")

    # Record access
    tracker = LineageTracker(db)
    tracker.record_access(
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

    # Parse pipeline_logs if it's a string
    pipeline_logs = lineage.pipeline_logs
    if isinstance(pipeline_logs, str):
        import json

        pipeline_logs = json.loads(pipeline_logs)
    elif pipeline_logs is None:
        pipeline_logs = decompressed_data.get("pipeline_logs", {})

    # Create response with both new fields and compatibility fields
    response_data = {
        "lineage_id": lineage_id,
        "report_id": lineage.report_generation_id,
        "pipeline_logs": pipeline_logs,
        "logs": pipeline_logs,  # Compatibility
        "raw_inputs": decompressed_data.get("raw_inputs", decompressed_data.get("raw_inputs_sample", {})),
        "pipeline_start_time": lineage.pipeline_start_time,
        "pipeline_end_time": lineage.pipeline_end_time,
        "truncated": truncated,
        "log_size": len(str(pipeline_logs)) if pipeline_logs else 0,
    }

    return response_data


@router.get("/{lineage_id}/download")
def download_raw_inputs(
    lineage_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: str | None = Depends(get_current_user_optional),
):
    """
    Download compressed raw inputs (≤2MB with gzip)
    """
    import io

    # Get lineage record
    lineage = db.query(ReportLineage).filter(ReportLineage.id == lineage_id).first()
    if not lineage:
        raise HTTPException(status_code=404, detail="Lineage not found")

    # Record access
    tracker = LineageTracker(db)
    tracker.record_access(
        lineage_id=lineage_id,
        action="download_raw_inputs",
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
    # No data available
    raise HTTPException(status_code=404, detail="No raw inputs available for this lineage")


@router.get("/panel/stats", response_model=PanelStatsResponse)
def get_panel_stats(
    db: Session = Depends(get_db),
):
    """
    Get lineage panel statistics for dashboard
    """
    from sqlalchemy import func

    # Total records
    total_records = db.query(func.count(ReportLineage.id)).scalar() or 0

    # Recent records in last 24 hours
    yesterday = datetime.utcnow() - timedelta(days=1)
    recent_records_24h = (
        db.query(func.count(ReportLineage.id)).filter(ReportLineage.created_at >= yesterday).scalar() or 0
    )

    # Template distribution
    template_stats = (
        db.query(ReportLineage.template_version_id, func.count(ReportLineage.id).label("count"))
        .group_by(ReportLineage.template_version_id)
        .order_by(func.count(ReportLineage.id).desc())
        .all()
    )

    template_distribution = [
        {"version": stats[0], "count": stats[1]} for stats in template_stats if stats[0] is not None
    ]

    # Total storage in MB
    total_bytes = db.query(func.sum(ReportLineage.raw_inputs_size_bytes)).scalar() or 0
    total_storage_mb = round(total_bytes / (1024 * 1024), 2)

    return PanelStatsResponse(
        total_records=total_records,
        recent_records_24h=recent_records_24h,
        template_distribution=template_distribution,
        total_storage_mb=total_storage_mb,
    )


@router.delete("/{lineage_id}")
def delete_lineage(
    lineage_id: str,
    db: Session = Depends(get_db),
    current_user: str | None = Depends(get_current_user_optional),
):
    """
    Delete a lineage record
    """
    # Get lineage record
    lineage = db.query(ReportLineage).filter(ReportLineage.id == lineage_id).first()
    if not lineage:
        raise HTTPException(status_code=404, detail="Lineage not found")

    # Delete the lineage
    db.delete(lineage)
    db.commit()

    return {"message": f"Lineage {lineage_id} deleted successfully"}
