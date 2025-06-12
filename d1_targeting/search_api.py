"""
Target Search API
Implements business search functionality
"""
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from core.logging import get_logger
from d0_gateway.facade import get_gateway_facade

logger = get_logger(__name__)
router = APIRouter()


class TargetSearchRequest(BaseModel):
    """Request for target search"""
    location: str = Field(..., description="Location to search (city, state or address)")
    categories: List[str] = Field(..., description="Business categories to search")
    radius: int = Field(default=10000, ge=1000, le=40000, description="Search radius in meters")
    limit: int = Field(default=20, ge=1, le=50, description="Number of results")
    offset: int = Field(default=0, ge=0, description="Pagination offset")
    sort_by: str = Field(default="best_match", description="Sort order")


class BusinessResult(BaseModel):
    """Business search result"""
    id: str
    name: str
    url: Optional[str] = None
    phone: Optional[str] = None
    display_phone: Optional[str] = None
    review_count: int = 0
    rating: float = 0.0
    price: Optional[str] = None
    location: Dict[str, Any]
    coordinates: Dict[str, float]
    categories: List[Dict[str, str]]
    is_closed: bool = False
    distance: Optional[float] = None


class TargetSearchResponse(BaseModel):
    """Response for target search"""
    businesses: List[BusinessResult]
    total: int
    region: Optional[Dict[str, Any]] = None


@router.post("/search", response_model=TargetSearchResponse)
async def search_targets(request: TargetSearchRequest) -> TargetSearchResponse:
    """Search for business targets using Yelp API"""
    try:
        gateway = get_gateway_facade()
        
        # Convert categories list to comma-separated string
        categories_str = ",".join(request.categories) if request.categories else None
        
        # Call Yelp API
        result = await gateway.search_businesses(
            term=" ".join(request.categories) if request.categories else "business",
            location=request.location,
            categories=categories_str,
            limit=request.limit,
            offset=request.offset,
            sort_by=request.sort_by
        )
        
        # Convert Yelp results to our format
        businesses = []
        for biz in result.get("businesses", []):
            businesses.append(BusinessResult(
                id=biz.get("id"),
                name=biz.get("name"),
                url=biz.get("url"),
                phone=biz.get("phone"),
                display_phone=biz.get("display_phone"),
                review_count=biz.get("review_count", 0),
                rating=biz.get("rating", 0.0),
                price=biz.get("price"),
                location=biz.get("location", {}),
                coordinates=biz.get("coordinates", {}),
                categories=biz.get("categories", []),
                is_closed=biz.get("is_closed", False),
                distance=biz.get("distance")
            ))
        
        return TargetSearchResponse(
            businesses=businesses,
            total=result.get("total", 0),
            region=result.get("region")
        )
        
    except Exception as e:
        logger.error(f"Target search failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))