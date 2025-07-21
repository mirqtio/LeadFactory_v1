"""
Cost tracking API endpoints for gateway cost ledger
P1-050: Gateway Cost Ledger implementation
"""

from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from core.auth import get_current_user
from core.logging import get_logger
from d0_gateway.cost_ledger import cost_ledger

logger = get_logger("gateway.cost_api", domain="d0")

# Create router
router = APIRouter(tags=["costs"])


# Response models
class OperationCost(BaseModel):
    """Cost breakdown for a single operation"""

    operation: str
    cost: float
    count: int
    avg_cost: float


class ProviderCostSummary(BaseModel):
    """Cost summary for a provider"""

    provider: str
    period: dict[str, str]
    total_cost: float
    total_requests: int
    operations: dict[str, dict[str, float]]


class CampaignCostSummary(BaseModel):
    """Cost summary for a campaign"""

    campaign_id: int
    total_cost: float
    providers: dict[str, dict]


class DailyCostRecord(BaseModel):
    """Daily cost aggregate record"""

    date: str
    provider: str
    operation: str | None
    campaign_id: int | None
    total_cost: float
    request_count: int
    avg_cost: float


class CostTrend(BaseModel):
    """Cost trend over time"""

    period: dict[str, str]
    daily_costs: list[DailyCostRecord]
    total_cost: float
    avg_daily_cost: float
    peak_day: str | None
    peak_cost: float | None


# API endpoints
@router.get("/providers/{provider}", response_model=ProviderCostSummary)
async def get_provider_costs(
    provider: str,
    days: int = Query(30, ge=1, le=365, description="Number of days to look back"),
    current_user: dict = Depends(get_current_user),
) -> ProviderCostSummary:
    """
    Get cost summary for a specific provider

    Args:
        provider: Provider name (e.g., 'dataaxle', 'hunter')
        days: Number of days to look back (default: 30)

    Returns:
        Cost summary with breakdown by operation
    """
    try:
        start_date = datetime.now() - timedelta(days=days)
        costs = cost_ledger.get_provider_costs(provider, start_date=start_date)
        return ProviderCostSummary(**costs)
    except Exception as e:
        logger.error(f"Failed to get provider costs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/campaigns/{campaign_id}", response_model=CampaignCostSummary)
async def get_campaign_costs(
    campaign_id: int,
    current_user: dict = Depends(get_current_user),
) -> CampaignCostSummary:
    """
    Get total costs for a specific campaign

    Args:
        campaign_id: Campaign ID

    Returns:
        Cost breakdown by provider and operation
    """
    try:
        costs = cost_ledger.get_campaign_costs(campaign_id)
        return CampaignCostSummary(**costs)
    except Exception as e:
        logger.error(f"Failed to get campaign costs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/daily", response_model=list[DailyCostRecord])
async def get_daily_costs(
    start_date: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: date | None = Query(None, description="End date (YYYY-MM-DD)"),
    provider: str | None = Query(None, description="Filter by provider"),
    campaign_id: int | None = Query(None, description="Filter by campaign"),
    current_user: dict = Depends(get_current_user),
) -> list[DailyCostRecord]:
    """
    Get daily cost aggregates with optional filtering

    Args:
        start_date: Start date
        end_date: End date (default: today)
        provider: Filter by provider
        campaign_id: Filter by campaign

    Returns:
        List of daily cost records
    """
    try:
        costs = cost_ledger.get_daily_costs(
            start_date=start_date,
            end_date=end_date,
            provider=provider,
            campaign_id=campaign_id,
        )
        return [DailyCostRecord(**c) for c in costs]
    except Exception as e:
        logger.error(f"Failed to get daily costs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trends", response_model=CostTrend)
async def get_cost_trends(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    provider: str | None = Query(None, description="Filter by provider"),
    current_user: dict = Depends(get_current_user),
) -> CostTrend:
    """
    Get cost trends over time

    Args:
        days: Number of days to analyze
        provider: Filter by provider (optional)

    Returns:
        Cost trend analysis with daily breakdown
    """
    try:
        start_date = (datetime.now() - timedelta(days=days)).date()
        end_date = date.today()

        # Get daily costs
        daily_costs = cost_ledger.get_daily_costs(
            start_date=start_date,
            end_date=end_date,
            provider=provider,
        )

        # Calculate trends
        total_cost = sum(d["total_cost"] for d in daily_costs)
        avg_daily_cost = total_cost / days if days > 0 else 0

        # Find peak day
        peak_day = None
        peak_cost = 0.0
        if daily_costs:
            # Group by date to find daily totals
            daily_totals = {}
            for record in daily_costs:
                day = record["date"]
                if day not in daily_totals:
                    daily_totals[day] = 0.0
                daily_totals[day] += record["total_cost"]

            # Find peak
            for day, cost in daily_totals.items():
                if cost > peak_cost:
                    peak_day = day
                    peak_cost = cost

        return CostTrend(
            period={
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            daily_costs=[DailyCostRecord(**c) for c in daily_costs],
            total_cost=total_cost,
            avg_daily_cost=avg_daily_cost,
            peak_day=peak_day,
            peak_cost=peak_cost,
        )
    except Exception as e:
        logger.error(f"Failed to get cost trends: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/aggregate/{target_date}")
async def trigger_cost_aggregation(
    target_date: date,
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Manually trigger cost aggregation for a specific date

    Args:
        target_date: Date to aggregate costs for

    Returns:
        Aggregation result summary
    """
    try:
        aggregates = cost_ledger.aggregate_daily_costs(target_date)

        return {
            "status": "success",
            "date": target_date.isoformat(),
            "records_created": len(aggregates),
            "total_cost": float(sum(a.total_cost_usd for a in aggregates)),
        }
    except Exception as e:
        logger.error(f"Failed to aggregate costs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/cleanup")
async def cleanup_old_costs(
    days_to_keep: int = Query(90, ge=30, le=365, description="Days of records to keep"),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Clean up old cost records (keeps aggregates)

    Args:
        days_to_keep: Number of days of records to keep

    Returns:
        Cleanup result summary
    """
    try:
        deleted_count = cost_ledger.cleanup_old_records(days_to_keep)

        return {
            "status": "success",
            "deleted_count": deleted_count,
            "days_kept": days_to_keep,
        }
    except Exception as e:
        logger.error(f"Failed to cleanup costs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Health check
@router.get("/health")
async def health_check() -> dict[str, str]:
    """Check if cost tracking service is healthy"""
    return {
        "status": "healthy",
        "service": "gateway_cost_ledger",
        "timestamp": datetime.now().isoformat(),
    }
