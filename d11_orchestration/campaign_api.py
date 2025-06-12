"""
Campaign Management API
Implements missing campaign endpoints for orchestration
"""
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, text
from sqlalchemy.orm import Session

from database.session import get_db
from core.logging import get_logger
from d1_targeting.models import Campaign
from d1_targeting.types import CampaignStatus
from .schemas import (
    CampaignCreate,
    CampaignUpdate,
    CampaignResponse,
    CampaignListResponse
)

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/campaigns", tags=["campaigns"])


@router.post("", response_model=CampaignResponse, status_code=201)
def create_campaign(
    campaign_data: CampaignCreate,
    db: Session = Depends(get_db)
) -> CampaignResponse:
    """Create a new campaign"""
    try:
        # Create campaign
        campaign = Campaign(
            id=f"camp_{uuid4().hex[:12]}",
            name=campaign_data.name,
            description=getattr(campaign_data, 'description', ''),
            target_universe_id=getattr(campaign_data, 'target_universe_id', 'default_universe'),
            status=campaign_data.status or CampaignStatus.DRAFT,
            campaign_type=getattr(campaign_data, 'campaign_type', 'lead_generation'),
            created_at=datetime.utcnow()
        )
        
        db.add(campaign)
        db.commit()
        db.refresh(campaign)
        
        logger.info(f"Created campaign: {campaign.id}")
        
        return CampaignResponse(
            id=campaign.id,
            name=campaign.name,
            description=campaign.description,
            target_universe_id=campaign.target_universe_id,
            status=campaign.status,
            campaign_type=campaign.campaign_type,
            created_at=campaign.created_at,
            # Add optional fields that may not exist
            vertical=getattr(campaign, 'vertical', None),
            geo_targets=getattr(campaign, 'geo_targets', None),
            daily_quota=getattr(campaign, 'daily_quota', None)
        )
        
    except Exception as e:
        logger.error(f"Failed to create campaign: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=CampaignListResponse)
def list_campaigns(
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status: Optional[CampaignStatus] = None,
    db: Session = Depends(get_db)
) -> CampaignListResponse:
    """List campaigns with pagination"""
    try:
        # Build query
        query = select(Campaign)
        if status:
            query = query.where(Campaign.status == status)
        
        # Get total count
        count_query = select(func.count()).select_from(Campaign)
        if status:
            count_query = count_query.where(Campaign.status == status)
        
        total_result = db.execute(count_query)
        total = total_result.scalar() or 0
        
        # Get campaigns
        query = query.limit(limit).offset(offset).order_by(Campaign.created_at.desc())
        result = db.execute(query)
        campaigns = result.scalars().all()
        
        return CampaignListResponse(
            campaigns=[
                CampaignResponse(
                    id=c.id,
                    name=c.name,
                    description=c.description,
                    target_universe_id=c.target_universe_id,
                    status=c.status,
                    campaign_type=c.campaign_type,
                    created_at=c.created_at,
                    # Add optional fields that may not exist
                    vertical=getattr(c, 'vertical', None),
                    geo_targets=getattr(c, 'geo_targets', None),
                    daily_quota=getattr(c, 'daily_quota', None)
                )
                for c in campaigns
            ],
            total=total,
            limit=limit,
            offset=offset
        )
        
    except Exception as e:
        logger.error(f"Failed to list campaigns: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{campaign_id}", response_model=CampaignResponse)
def get_campaign(
    campaign_id: str,
    db: Session = Depends(get_db)
) -> CampaignResponse:
    """Get a specific campaign"""
    try:
        result = db.execute(
            select(Campaign).where(Campaign.id == campaign_id)
        )
        campaign = result.scalar_one_or_none()
        
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        return CampaignResponse(
            id=campaign.id,
            name=campaign.name,
            description=campaign.description,
            target_universe_id=campaign.target_universe_id,
            status=campaign.status,
            campaign_type=campaign.campaign_type,
            created_at=campaign.created_at,
            # Add optional fields that may not exist
            vertical=getattr(campaign, 'vertical', None),
            geo_targets=getattr(campaign, 'geo_targets', None),
            daily_quota=getattr(campaign, 'daily_quota', None)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get campaign: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{campaign_id}", response_model=CampaignResponse)
def update_campaign(
    campaign_id: str,
    campaign_update: CampaignUpdate,
    db: Session = Depends(get_db)
) -> CampaignResponse:
    """Update a campaign"""
    try:
        result = db.execute(
            select(Campaign).where(Campaign.id == campaign_id)
        )
        campaign = result.scalar_one_or_none()
        
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        # Update fields
        update_data = campaign_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(campaign, field, value)
        
        db.commit()
        db.refresh(campaign)
        
        logger.info(f"Updated campaign: {campaign.id}")
        
        return CampaignResponse(
            id=campaign.id,
            name=campaign.name,
            description=campaign.description,
            target_universe_id=campaign.target_universe_id,
            status=campaign.status,
            campaign_type=campaign.campaign_type,
            created_at=campaign.created_at,
            # Add optional fields that may not exist
            vertical=getattr(campaign, 'vertical', None),
            geo_targets=getattr(campaign, 'geo_targets', None),
            daily_quota=getattr(campaign, 'daily_quota', None)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update campaign: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{campaign_id}", status_code=204)
def delete_campaign(
    campaign_id: str,
    db: Session = Depends(get_db)
):
    """Delete a campaign"""
    try:
        result = db.execute(
            select(Campaign).where(Campaign.id == campaign_id)
        )
        campaign = result.scalar_one_or_none()
        
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        db.delete(campaign)
        db.commit()
        
        logger.info(f"Deleted campaign: {campaign_id}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete campaign: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))