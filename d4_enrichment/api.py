"""
Enrichment API endpoints
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from database.session import get_db
from sqlalchemy.orm import Session

from .coordinator import EnrichmentCoordinator, EnrichmentPriority
from .models import EnrichmentSource

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/v1/enrichment", tags=["enrichment"])

# Global coordinator instance
coordinator = EnrichmentCoordinator()


class EnrichmentRequest(BaseModel):
    """Request model for enrichment"""
    
    business_id: str = Field(..., description="Business ID to enrich")
    business_data: Dict = Field(..., description="Business data (name, address, etc)")
    sources: Optional[List[str]] = Field(
        default=None, 
        description="Enrichment sources to use (internal, data_axle, hunter_io)"
    )
    priority: Optional[str] = Field(
        default="medium",
        description="Priority level (low, medium, high, critical)"
    )
    skip_if_recent: Optional[bool] = Field(
        default=True,
        description="Skip if recently enriched"
    )


class EnrichmentResponse(BaseModel):
    """Response model for enrichment"""
    
    business_id: str
    status: str
    sources_attempted: List[str]
    successful_source: Optional[str] = None
    enrichment_data: Optional[Dict] = None
    confidence_score: Optional[float] = None
    timestamp: datetime


@router.post("/enrich", response_model=EnrichmentResponse)
async def enrich_business(
    request: EnrichmentRequest,
    db: Session = Depends(get_db)
) -> EnrichmentResponse:
    """
    Enrich a single business with data from multiple sources
    """
    try:
        # Convert source strings to EnrichmentSource enum
        if request.sources:
            sources = []
            for source in request.sources:
                try:
                    sources.append(EnrichmentSource(source))
                except ValueError:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid source: {source}. Valid sources: {[s.value for s in EnrichmentSource]}"
                    )
        else:
            # Default to all available sources
            sources = list(coordinator.enrichers.keys())
        
        # Convert priority
        try:
            priority = EnrichmentPriority(request.priority)
        except ValueError:
            priority = EnrichmentPriority.MEDIUM
        
        # Run enrichment
        result = await coordinator.batch_enrich_businesses(
            businesses=[request.business_data],
            sources=sources,
            skip_existing=request.skip_if_recent,
            priority=priority.value
        )
        
        # Extract result for single business
        if result.results and result.results[0]:
            enrichment = result.results[0]
            
            return EnrichmentResponse(
                business_id=request.business_id,
                status="success",
                sources_attempted=[s.value for s in sources],
                successful_source=enrichment.source,
                enrichment_data={
                    "email": enrichment.email,
                    "phone": enrichment.phone,
                    "website": enrichment.website,
                    "company_name": enrichment.company_name,
                    "address": enrichment.headquarters_address,
                    "city": enrichment.headquarters_city,
                    "state": enrichment.headquarters_state,
                    "employee_count": enrichment.employee_size_range,
                    "annual_revenue": enrichment.annual_revenue_range,
                    "industry": enrichment.industry_classification,
                    "tags": enrichment.tags,
                    "logo_url": enrichment.logo_url,
                    "linkedin_url": enrichment.linkedin_company_url,
                    "facebook_url": enrichment.facebook_url,
                    "twitter_handle": enrichment.twitter_handle
                },
                confidence_score=enrichment.match_score,
                timestamp=datetime.utcnow()
            )
        else:
            # No enrichment found
            return EnrichmentResponse(
                business_id=request.business_id,
                status="no_match",
                sources_attempted=[s.value for s in sources],
                successful_source=None,
                enrichment_data=None,
                confidence_score=0.0,
                timestamp=datetime.utcnow()
            )
            
    except Exception as e:
        logger.error(f"Enrichment failed for {request.business_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Enrichment failed: {str(e)}"
        )


@router.post("/batch", response_model=Dict)
async def batch_enrich(
    businesses: List[EnrichmentRequest],
    db: Session = Depends(get_db)
) -> Dict:
    """
    Enrich multiple businesses in batch
    """
    try:
        # Prepare business data
        business_list = []
        for req in businesses:
            business_list.append({
                "id": req.business_id,
                **req.business_data
            })
        
        # Use first request's settings for batch
        sources = []
        if businesses[0].sources:
            for source in businesses[0].sources:
                try:
                    sources.append(EnrichmentSource(source))
                except ValueError:
                    continue
        else:
            sources = list(coordinator.enrichers.keys())
        
        # Run batch enrichment
        result = await coordinator.batch_enrich_businesses(
            businesses=business_list,
            sources=sources,
            skip_existing=businesses[0].skip_if_recent,
            priority=businesses[0].priority
        )
        
        return {
            "total_businesses": result.total_processed,
            "successful": result.successful_enrichments,
            "failed": result.failed_enrichments,
            "skipped": result.skipped_enrichments,
            "execution_time_seconds": result.execution_time_seconds,
            "request_id": result.request_id
        }
        
    except Exception as e:
        logger.error(f"Batch enrichment failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Batch enrichment failed: {str(e)}"
        )


@router.get("/sources")
async def get_available_sources():
    """Get list of available enrichment sources"""
    return {
        "sources": [
            {
                "id": source.value,
                "name": source.name,
                "available": source in coordinator.enrichers
            }
            for source in EnrichmentSource
        ]
    }


@router.get("/health")
async def health_check():
    """Health check for enrichment service"""
    return {
        "status": "healthy",
        "enrichers_loaded": len(coordinator.enrichers),
        "sources": list(coordinator.enrichers.keys())
    }