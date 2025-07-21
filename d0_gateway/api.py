"""
Gateway API endpoints including cost tracking
"""

from fastapi import APIRouter

from .cost_api import router as cost_router
from .guardrail_api import router as guardrail_router

# Create main gateway router
router = APIRouter(prefix="/api/v1/gateway", tags=["gateway"])

# Include cost tracking endpoints
router.include_router(cost_router, prefix="/costs", tags=["costs"])

# Include guardrail endpoints
router.include_router(guardrail_router, tags=["guardrails"])


# Add gateway health endpoint
@router.get("/health")
async def gateway_health():
    """Check gateway service health"""
    return {
        "status": "healthy",
        "service": "d0_gateway",
    }
