"""
Production Configuration API - P3-006 Mock Integration Replacement

API endpoints for assessing production readiness and managing the transition
from mock integrations to production APIs.
"""
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from account_management.models import AccountUser
from core.auth import get_current_user_dependency
from core.production_config import production_config_service

router = APIRouter(prefix="/api/v1/production", tags=["production"])


class IntegrationStatus(BaseModel):
    """Integration readiness status"""

    ready: bool
    enabled: bool
    has_api_key: bool
    service_name: str
    required_env_vars: List[str]
    cost_per_request: str


class ProductionReadinessResponse(BaseModel):
    """Production readiness assessment response"""

    current_status: Dict[str, Any]
    ready_integrations: List[str]
    needs_configuration: List[str]
    optional_integrations: List[str]
    critical_issues: List[str]
    warnings: List[str]
    recommendations: List[str]
    next_steps: List[str]


class IntegrationReadinessResponse(BaseModel):
    """Integration readiness response"""

    integrations: Dict[str, IntegrationStatus]


@router.get(
    "/readiness",
    response_model=ProductionReadinessResponse,
    summary="Production Readiness Assessment",
    description="Assess readiness for production deployment and API integration",
)
async def get_production_readiness(
    current_user: AccountUser = Depends(get_current_user_dependency),
) -> ProductionReadinessResponse:
    """
    Get comprehensive production readiness assessment

    Provides detailed analysis of:
    - API integration status
    - Configuration issues
    - Recommendations for production deployment
    """
    try:
        transition_plan = production_config_service.get_environment_transition_plan()

        return ProductionReadinessResponse(**transition_plan)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to assess production readiness: {str(e)}"
        )


@router.get(
    "/integrations",
    response_model=IntegrationReadinessResponse,
    summary="API Integration Status",
    description="Get detailed status of all API integrations",
)
async def get_integration_status(
    current_user: AccountUser = Depends(get_current_user_dependency),
) -> IntegrationReadinessResponse:
    """
    Get detailed status of all API integrations

    Shows which APIs are:
    - Ready for production use
    - Enabled but need configuration
    - Optional/disabled
    """
    try:
        integrations_raw = production_config_service.get_integration_readiness()

        # Convert to Pydantic models
        integrations = {name: IntegrationStatus(**status) for name, status in integrations_raw.items()}

        return IntegrationReadinessResponse(integrations=integrations)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to get integration status: {str(e)}"
        )


@router.get(
    "/recommendations",
    response_model=List[str],
    summary="Production Configuration Recommendations",
    description="Get actionable recommendations for production deployment",
)
async def get_production_recommendations(
    current_user: AccountUser = Depends(get_current_user_dependency),
) -> List[str]:
    """
    Get actionable recommendations for production deployment

    Returns prioritized list of configuration changes needed
    for successful production deployment.
    """
    try:
        return production_config_service.get_production_config_recommendations()

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to get recommendations: {str(e)}"
        )


@router.post(
    "/validate",
    summary="Validate Production Configuration",
    description="Validate current configuration for production readiness",
)
async def validate_production_config(
    current_user: AccountUser = Depends(get_current_user_dependency),
) -> Dict[str, Any]:
    """
    Validate current configuration for production readiness

    Performs comprehensive validation and returns:
    - Overall readiness status
    - Critical issues that must be fixed
    - Warnings and recommendations
    """
    try:
        is_ready, issues = production_config_service.validate_production_readiness()

        return {
            "production_ready": is_ready,
            "issues": issues,
            "summary": "Production ready" if is_ready else "Configuration issues found",
            "next_action": "Deploy to production" if is_ready else "Fix configuration issues",
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to validate production config: {str(e)}"
        )
