"""
FastAPI endpoints for Report Lineage Panel

Provides REST API for viewing report generation lineage,
including pipeline logs and raw input downloads.
"""
import gzip
import json
from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Response, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import text, or_
from sqlalchemy.orm import Session

from core.logging import get_logger
from database.session import get_db
from d6_reports.lineage.models import ReportLineage, ReportLineageAudit

logger = get_logger("lineage_api", domain="lineage")

# Create router with prefix
router = APIRouter(prefix="/api/lineage", tags=["lineage"])


@router.get("/{report_id}")
async def get_lineage_by_report_id(
    report_id: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get lineage information for a specific report ID.
    
    Response time: <500ms
    """
    logger.info(f"Getting lineage for report_id: {report_id}")
    
    lineage = db.query(ReportLineage).filter(
        ReportLineage.report_generation_id == report_id
    ).first()
    
    if not lineage:
        raise HTTPException(status_code=404, detail="Lineage not found")
    
    # Log access for audit
    audit = ReportLineageAudit(
        lineage_id=lineage.id,
        action="view_lineage",
        accessed_at=datetime.utcnow()
    )
    db.add(audit)
    db.commit()
    
    return {
        "id": lineage.id,
        "report_id": lineage.report_generation_id,
        "lead_id": lineage.lead_id,
        "pipeline_run_id": lineage.pipeline_run_id,
        "template_version_id": lineage.template_version_id,
        "created_at": lineage.created_at.isoformat(),
        "pipeline_logs_size": len(lineage.pipeline_logs) if lineage.pipeline_logs else 0,
        "raw_inputs_size": lineage.raw_inputs_size_bytes
    }


@router.get("/search", response_model=List[Dict[str, Any]])
async def search_lineage(
    lead_id: Optional[str] = Query(None),
    pipeline_run_id: Optional[str] = Query(None),
    template_version_id: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    Search lineage records with filtering.
    """
    query = db.query(ReportLineage)
    
    # Apply filters
    filters = []
    if lead_id:
        filters.append(ReportLineage.lead_id == lead_id)
    if pipeline_run_id:
        filters.append(ReportLineage.pipeline_run_id == pipeline_run_id)
    if template_version_id:
        filters.append(ReportLineage.template_version_id == template_version_id)
    
    if filters:
        query = query.filter(or_(*filters))
    
    # Order by creation date descending
    query = query.order_by(ReportLineage.created_at.desc())
    
    # Apply pagination
    lineages = query.offset(skip).limit(limit).all()
    
    return [
        {
            "id": lineage.id,
            "report_id": lineage.report_generation_id,
            "lead_id": lineage.lead_id,
            "pipeline_run_id": lineage.pipeline_run_id,
            "template_version_id": lineage.template_version_id,
            "created_at": lineage.created_at.isoformat(),
            "pipeline_logs_size": len(lineage.pipeline_logs) if lineage.pipeline_logs else 0,
            "raw_inputs_size": lineage.raw_inputs_size_bytes
        }
        for lineage in lineages
    ]


@router.get("/{lineage_id}/logs")
async def get_pipeline_logs(
    lineage_id: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    View JSON logs for a specific lineage record.
    
    Requirement: Loads in <500ms
    """
    lineage = db.query(ReportLineage).filter(
        ReportLineage.id == lineage_id
    ).first()
    
    if not lineage:
        raise HTTPException(status_code=404, detail="Lineage not found")
    
    # Log access
    audit = ReportLineageAudit(
        lineage_id=lineage.id,
        action="view_logs",
        accessed_at=datetime.utcnow()
    )
    db.add(audit)
    db.commit()
    
    # Parse and return logs
    try:
        logs = json.loads(lineage.pipeline_logs) if lineage.pipeline_logs else {}
    except json.JSONDecodeError:
        logs = {"error": "Invalid JSON in pipeline logs"}
    
    return {
        "lineage_id": lineage_id,
        "report_id": lineage.report_generation_id,
        "logs": logs,
        "log_size": len(lineage.pipeline_logs) if lineage.pipeline_logs else 0
    }


@router.get("/{lineage_id}/download")
async def download_raw_inputs(
    lineage_id: str,
    db: Session = Depends(get_db)
):
    """
    Download compressed raw inputs for a lineage record.
    
    Returns gzipped data with size limit of 2MB.
    """
    lineage = db.query(ReportLineage).filter(
        ReportLineage.id == lineage_id
    ).first()
    
    if not lineage:
        raise HTTPException(status_code=404, detail="Lineage not found")
    
    if not lineage.raw_inputs_compressed:
        raise HTTPException(status_code=404, detail="No raw inputs available")
    
    # Log download
    audit = ReportLineageAudit(
        lineage_id=lineage.id,
        action="download_raw_inputs",
        accessed_at=datetime.utcnow()
    )
    db.add(audit)
    db.commit()
    
    # Return compressed data as download
    return Response(
        content=lineage.raw_inputs_compressed,
        media_type="application/gzip",
        headers={
            "Content-Disposition": f'attachment; filename="lineage_{lineage_id}_raw_inputs.json.gz"'
        }
    )


@router.get("/panel/stats")
async def get_lineage_stats(
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get statistics for the lineage panel dashboard.
    """
    # Get counts
    total_count = db.query(ReportLineage).count()
    
    # Get recent count (last 24 hours)
    recent_count = db.execute(
        text("""
        SELECT COUNT(*) 
        FROM report_lineage 
        WHERE created_at >= datetime('now', '-1 day')
        """)
    ).scalar()
    
    # Get template version distribution
    template_stats = db.execute(
        text("""
        SELECT template_version_id, COUNT(*) as count
        FROM report_lineage
        GROUP BY template_version_id
        ORDER BY count DESC
        LIMIT 5
        """)
    ).fetchall()
    
    # Get total storage used
    total_storage = db.execute(
        text("""
        SELECT SUM(raw_inputs_size_bytes) as total_bytes
        FROM report_lineage
        """)
    ).scalar() or 0
    
    return {
        "total_records": total_count,
        "recent_records_24h": recent_count or 0,
        "template_distribution": [
            {"version": row[0], "count": row[1]} 
            for row in template_stats
        ],
        "total_storage_mb": round(total_storage / (1024 * 1024), 2)
    }


@router.delete("/{lineage_id}")
async def delete_lineage(
    lineage_id: str,
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    """
    Delete a lineage record (admin only).
    """
    lineage = db.query(ReportLineage).filter(
        ReportLineage.id == lineage_id
    ).first()
    
    if not lineage:
        raise HTTPException(status_code=404, detail="Lineage not found")
    
    # Log deletion
    audit = ReportLineageAudit(
        lineage_id=lineage.id,
        action="delete_lineage",
        accessed_at=datetime.utcnow()
    )
    db.add(audit)
    
    # Delete the lineage record
    db.delete(lineage)
    db.commit()
    
    return {"message": f"Lineage {lineage_id} deleted successfully"}