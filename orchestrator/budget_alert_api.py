"""
P2-040 Budget Alert API Enhancement
Real-time budget monitoring API endpoints for dashboard integration
"""
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from account_management.models import AccountUser
from api.dependencies import get_current_user_dependency
from orchestrator.budget_monitor import BudgetStatus
from orchestrator.real_time_budget_alerts import (
    initialize_p2040_enhancements,
    real_time_alert_manager,
    threshold_integrator,
)
from orchestrator.unified_budget_system import (
    get_unified_budget_status,
    initialize_unified_p2040_system,
    trigger_unified_budget_check,
    unified_budget_system,
)

router = APIRouter(prefix="/api/v1/budget-alerts", tags=["Budget Monitoring"])


# Response Models
class BudgetStatusResponse(BaseModel):
    """Budget status response"""

    monitor_id: str
    status: str
    current_spend: float
    monthly_budget: float
    usage_percentage: float
    warning_threshold: float
    stop_threshold: float
    last_check: datetime = Field(default_factory=datetime.utcnow)


class BudgetSummaryResponse(BaseModel):
    """Complete budget summary"""

    monitors: List[BudgetStatusResponse]
    total_monitors: int
    alerts_active: int
    global_status: str
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class AlertHistoryResponse(BaseModel):
    """Alert history response"""

    alert_key: str
    last_sent: datetime
    cooldown_remaining_minutes: Optional[int] = None


# Request Models
class BudgetCheckRequest(BaseModel):
    """Manual budget check request"""

    monitor_ids: Optional[List[str]] = None
    current_spending: Optional[Dict[str, float]] = None


class ThresholdUpdateRequest(BaseModel):
    """Update budget thresholds"""

    monitor_id: str
    warning_threshold: Optional[float] = None
    stop_threshold: Optional[float] = None
    monthly_budget: Optional[float] = None


@router.post("/initialize", response_model=Dict[str, str])
async def initialize_budget_alerts(
    background_tasks: BackgroundTasks,
    current_user: AccountUser = Depends(get_current_user_dependency),
):
    """
    Initialize P2-040 unified budget monitoring system
    """
    try:
        # Initialize unified system in background
        background_tasks.add_task(initialize_unified_p2040_system)

        return {
            "status": "success",
            "message": "P2-040 unified budget monitoring system initialization started",
            "system_type": "unified_pm1_pm2",
            "monitors_registered": str(len(real_time_alert_manager.monitors)),
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initialize: {str(e)}")


@router.get("/status", response_model=BudgetSummaryResponse)
async def get_budget_status(
    current_user: AccountUser = Depends(get_current_user_dependency),
):
    """
    Get current status of all budget monitors
    """
    try:
        current_spending = await threshold_integrator.get_current_spending()
        monitors = []
        alerts_active = 0

        for monitor_id, monitor in real_time_alert_manager.monitors.items():
            spend = current_spending.get(monitor_id, 0.0)
            status = monitor.check_budget_status(spend)
            usage_pct = spend / float(monitor.monthly_budget_usd)

            if status != BudgetStatus.OK:
                alerts_active += 1

            monitors.append(
                BudgetStatusResponse(
                    monitor_id=monitor_id,
                    status=status.value,
                    current_spend=spend,
                    monthly_budget=float(monitor.monthly_budget_usd),
                    usage_percentage=usage_pct,
                    warning_threshold=monitor.warning_threshold,
                    stop_threshold=monitor.stop_threshold,
                )
            )

        # Determine global status
        global_status = "ok"
        if any(m.status == "stop" for m in monitors):
            global_status = "critical"
        elif any(m.status == "warning" for m in monitors):
            global_status = "warning"

        return BudgetSummaryResponse(
            monitors=monitors, total_monitors=len(monitors), alerts_active=alerts_active, global_status=global_status
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")


@router.post("/check", response_model=Dict[str, str])
async def manual_budget_check(
    request: BudgetCheckRequest,
    current_user: AccountUser = Depends(get_current_user_dependency),
):
    """
    Manually trigger budget check and alerts
    """
    try:
        # Get current spending if not provided
        spending = request.current_spending
        if not spending:
            spending = await threshold_integrator.get_current_spending()

        # Filter to specific monitors if requested
        if request.monitor_ids:
            spending = {k: v for k, v in spending.items() if k in request.monitor_ids}

        # Trigger checks
        violations = await real_time_alert_manager.check_all_budgets(spending)

        return {
            "status": "success",
            "message": f"Manual budget check completed",
            "monitors_checked": str(len(spending)),
            "alerts_sent": str(len(violations)),
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check budgets: {str(e)}")


@router.get("/alerts/history", response_model=List[AlertHistoryResponse])
async def get_alert_history(
    current_user: AccountUser = Depends(get_current_user_dependency),
):
    """
    Get alert history and cooldown status
    """
    try:
        history = []
        now = datetime.utcnow()

        for alert_key, last_sent in real_time_alert_manager.last_alerts.items():
            cooldown_remaining = None
            cooldown_period_min = real_time_alert_manager.alert_cooldown_minutes

            time_since = (now - last_sent).total_seconds() / 60
            if time_since < cooldown_period_min:
                cooldown_remaining = int(cooldown_period_min - time_since)

            history.append(
                AlertHistoryResponse(
                    alert_key=alert_key, last_sent=last_sent, cooldown_remaining_minutes=cooldown_remaining
                )
            )

        return history

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get alert history: {str(e)}")


@router.put("/thresholds", response_model=Dict[str, str])
async def update_thresholds(
    request: ThresholdUpdateRequest,
    current_user: AccountUser = Depends(get_current_user_dependency),
):
    """
    Update budget monitor thresholds
    """
    try:
        if request.monitor_id not in real_time_alert_manager.monitors:
            raise HTTPException(status_code=404, detail=f"Monitor {request.monitor_id} not found")

        monitor = real_time_alert_manager.monitors[request.monitor_id]

        # Update thresholds if provided
        if request.warning_threshold is not None:
            if not 0 < request.warning_threshold < 1:
                raise HTTPException(status_code=400, detail="Warning threshold must be between 0 and 1")
            monitor.warning_threshold = request.warning_threshold

        if request.stop_threshold is not None:
            if not 0 < request.stop_threshold <= 1:
                raise HTTPException(status_code=400, detail="Stop threshold must be between 0 and 1")
            monitor.stop_threshold = request.stop_threshold

        if request.monthly_budget is not None:
            if request.monthly_budget <= 0:
                raise HTTPException(status_code=400, detail="Monthly budget must be positive")
            from decimal import Decimal

            monitor.monthly_budget_usd = Decimal(str(request.monthly_budget))

        return {
            "status": "success",
            "message": f"Updated thresholds for monitor {request.monitor_id}",
            "timestamp": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update thresholds: {str(e)}")


@router.get("/health", response_model=Dict[str, str])
async def health_check():
    """
    Health check for budget alert system
    """
    try:
        # Check if system is initialized
        monitors_count = len(real_time_alert_manager.monitors)

        return {
            "status": "healthy" if monitors_count > 0 else "not_initialized",
            "monitors_registered": str(monitors_count),
            "alert_cooldown_minutes": str(real_time_alert_manager.alert_cooldown_minutes),
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        return {"status": "error", "error": str(e), "timestamp": datetime.utcnow().isoformat()}


# Unified system endpoints
@router.get("/unified/status", response_model=Dict[str, any])
async def get_unified_status(
    current_user: AccountUser = Depends(get_current_user_dependency),
):
    """
    Get unified P2-040 budget status from both PM-1 and PM-2 systems
    """
    try:
        status = await get_unified_budget_status()
        return status

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get unified status: {str(e)}")


@router.post("/unified/check", response_model=Dict[str, any])
async def trigger_unified_check(
    current_user: AccountUser = Depends(get_current_user_dependency),
):
    """
    Trigger coordinated budget check across both PM-1 and PM-2 systems
    """
    try:
        result = await trigger_unified_budget_check()
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to trigger unified check: {str(e)}")


@router.post("/unified/check-operation", response_model=Dict[str, any])
async def check_unified_operation(
    provider: str,
    estimated_cost: float,
    current_user: AccountUser = Depends(get_current_user_dependency),
):
    """
    Check operation budget using unified PM-1 and PM-2 systems
    """
    try:
        from orchestrator.unified_budget_system import check_unified_operation_budget

        result = await check_unified_operation_budget(provider, estimated_cost)
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check unified operation: {str(e)}")


# Integration endpoint for pre-operation budget checks
@router.post("/check-operation", response_model=Dict[str, bool])
async def check_operation_budget(
    provider: str,
    estimated_cost: float,
    current_user: AccountUser = Depends(get_current_user_dependency),
):
    """
    Check if operation should proceed based on budget status
    """
    try:
        from orchestrator.real_time_budget_alerts import check_budget_before_operation

        can_proceed = await check_budget_before_operation(provider, estimated_cost)

        return {
            "can_proceed": can_proceed,
            "provider": provider,
            "estimated_cost": estimated_cost,
            "checked_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check operation budget: {str(e)}")
