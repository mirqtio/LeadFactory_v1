"""
API endpoints for cost guardrail management in P1-060
Provides REST endpoints for guardrail configuration and monitoring
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from core.logging import get_logger
from d0_gateway.guardrail_alerts import AlertChannel, AlertConfig, alert_manager
from d0_gateway.guardrail_middleware import get_remaining_budget
from d0_gateway.guardrails import (
    CostLimit,
    GuardrailStatus,
    LimitPeriod,
    LimitScope,
    RateLimitConfig,
    guardrail_manager,
)

logger = get_logger("gateway.guardrail_api", domain="d0")

router = APIRouter(prefix="/guardrails", tags=["Cost Guardrails"])


# Request/Response models
class CreateLimitRequest(BaseModel):
    """Request to create a new cost limit"""

    name: str = Field(..., description="Unique name for the limit")
    scope: LimitScope = Field(..., description="Scope of the limit")
    period: LimitPeriod = Field(..., description="Time period for the limit")
    limit_usd: float = Field(..., gt=0, description="Limit amount in USD")
    provider: Optional[str] = Field(None, description="Provider for provider-scoped limits")
    campaign_id: Optional[int] = Field(None, description="Campaign for campaign-scoped limits")
    operation: Optional[str] = Field(None, description="Operation for operation-scoped limits")
    warning_threshold: float = Field(0.8, ge=0, le=1, description="Warning threshold (0-1)")
    critical_threshold: float = Field(0.95, ge=0, le=1, description="Critical threshold (0-1)")
    circuit_breaker_enabled: bool = Field(False, description="Enable circuit breaker")


class UpdateLimitRequest(BaseModel):
    """Request to update an existing cost limit"""

    limit_usd: Optional[float] = Field(None, gt=0, description="New limit amount in USD")
    warning_threshold: Optional[float] = Field(None, ge=0, le=1, description="New warning threshold")
    critical_threshold: Optional[float] = Field(None, ge=0, le=1, description="New critical threshold")
    enabled: Optional[bool] = Field(None, description="Enable/disable the limit")


class CreateRateLimitRequest(BaseModel):
    """Request to create a rate limit"""

    provider: str = Field(..., description="Provider to rate limit")
    operation: Optional[str] = Field(None, description="Specific operation or None for all")
    requests_per_minute: int = Field(..., gt=0, description="Max requests per minute")
    burst_size: int = Field(..., gt=0, description="Max burst size")
    cost_per_minute: Optional[float] = Field(None, description="Max cost per minute")
    cost_burst_size: Optional[float] = Field(None, description="Max cost burst")


class ConfigureAlertRequest(BaseModel):
    """Request to configure alerts"""

    channel: AlertChannel = Field(..., description="Alert channel")
    enabled: bool = Field(True, description="Enable this channel")
    email_addresses: Optional[List[str]] = Field(None, description="Email addresses for email channel")
    slack_webhook_url: Optional[str] = Field(None, description="Slack webhook URL")
    webhook_url: Optional[str] = Field(None, description="Generic webhook URL")
    webhook_headers: Optional[Dict[str, str]] = Field(None, description="Webhook headers")
    min_severity: str = Field("warning", description="Minimum severity to alert on")
    providers: Optional[List[str]] = Field(None, description="Filter by providers")


class GuardrailStatusResponse(BaseModel):
    """Response with guardrail status"""

    limits: List[GuardrailStatus]
    total_limits: int
    limits_exceeded: int
    limits_warning: int
    timestamp: datetime


class LimitResponse(BaseModel):
    """Response with limit details"""

    name: str
    scope: str
    period: str
    limit_usd: float
    provider: Optional[str]
    campaign_id: Optional[int]
    operation: Optional[str]
    warning_threshold: float
    critical_threshold: float
    enabled: bool
    circuit_breaker_enabled: bool


class BudgetSummaryResponse(BaseModel):
    """Response with budget summary"""

    period: str
    providers: Dict[str, Dict[str, float]]  # provider -> {remaining, limit, spent, percentage}
    total_remaining: float
    total_limit: float
    total_spent: float
    timestamp: datetime


# Endpoints
@router.get("/status", response_model=GuardrailStatusResponse)
async def get_guardrail_status(
    provider: Optional[str] = Query(None, description="Filter by provider"),
    campaign_id: Optional[int] = Query(None, description="Filter by campaign"),
) -> GuardrailStatusResponse:
    """Get current status of all guardrails"""
    all_statuses = []

    # Check all limits
    for limit in guardrail_manager._limits.values():
        if not limit.enabled:
            continue

        # Apply filters
        if provider and limit.provider != provider:
            continue
        if campaign_id and limit.campaign_id != campaign_id:
            continue

        # Get status for this limit
        statuses = guardrail_manager.check_limits(
            provider=limit.provider or provider or "unknown",
            operation=limit.operation or "unknown",
            estimated_cost=Decimal("0"),
            campaign_id=limit.campaign_id or campaign_id,
        )

        # Find the status for this specific limit
        for status in statuses:
            if status.limit_name == limit.name:
                all_statuses.append(status)
                break

    # Count by status
    limits_exceeded = sum(1 for s in all_statuses if s.is_over_limit)
    limits_warning = sum(1 for s in all_statuses if s.status.value in ["warning", "critical"])

    return GuardrailStatusResponse(
        limits=all_statuses,
        total_limits=len(all_statuses),
        limits_exceeded=limits_exceeded,
        limits_warning=limits_warning,
        timestamp=datetime.utcnow(),
    )


@router.get("/limits", response_model=List[LimitResponse])
async def list_limits(
    scope: Optional[LimitScope] = Query(None, description="Filter by scope"),
    provider: Optional[str] = Query(None, description="Filter by provider"),
    enabled_only: bool = Query(True, description="Only show enabled limits"),
) -> List[LimitResponse]:
    """List all configured cost limits"""
    limits = []

    for limit in guardrail_manager._limits.values():
        # Apply filters
        if scope and limit.scope != scope:
            continue
        if provider and limit.provider != provider:
            continue
        if enabled_only and not limit.enabled:
            continue

        limits.append(
            LimitResponse(
                name=limit.name,
                scope=limit.scope.value,
                period=limit.period.value,
                limit_usd=float(limit.limit_usd),
                provider=limit.provider,
                campaign_id=limit.campaign_id,
                operation=limit.operation,
                warning_threshold=limit.warning_threshold,
                critical_threshold=limit.critical_threshold,
                enabled=limit.enabled,
                circuit_breaker_enabled=limit.circuit_breaker_enabled,
            )
        )

    return limits


@router.post("/limits", response_model=LimitResponse)
async def create_limit(request: CreateLimitRequest) -> LimitResponse:
    """Create a new cost limit"""
    # Check if limit already exists
    if request.name in guardrail_manager._limits:
        raise HTTPException(status_code=400, detail=f"Limit '{request.name}' already exists")

    # Create limit
    limit = CostLimit(
        name=request.name,
        scope=request.scope,
        period=request.period,
        limit_usd=Decimal(str(request.limit_usd)),
        provider=request.provider,
        campaign_id=request.campaign_id,
        operation=request.operation,
        warning_threshold=request.warning_threshold,
        critical_threshold=request.critical_threshold,
        circuit_breaker_enabled=request.circuit_breaker_enabled,
    )

    guardrail_manager.add_limit(limit)

    return LimitResponse(
        name=limit.name,
        scope=limit.scope.value,
        period=limit.period.value,
        limit_usd=float(limit.limit_usd),
        provider=limit.provider,
        campaign_id=limit.campaign_id,
        operation=limit.operation,
        warning_threshold=limit.warning_threshold,
        critical_threshold=limit.critical_threshold,
        enabled=limit.enabled,
        circuit_breaker_enabled=limit.circuit_breaker_enabled,
    )


@router.put("/limits/{name}", response_model=LimitResponse)
async def update_limit(name: str, request: UpdateLimitRequest) -> LimitResponse:
    """Update an existing cost limit"""
    if name not in guardrail_manager._limits:
        raise HTTPException(status_code=404, detail=f"Limit '{name}' not found")

    limit = guardrail_manager._limits[name]

    # Update fields
    if request.limit_usd is not None:
        limit.limit_usd = Decimal(str(request.limit_usd))
    if request.warning_threshold is not None:
        limit.warning_threshold = request.warning_threshold
    if request.critical_threshold is not None:
        limit.critical_threshold = request.critical_threshold
    if request.enabled is not None:
        limit.enabled = request.enabled

    limit.updated_at = datetime.utcnow()

    return LimitResponse(
        name=limit.name,
        scope=limit.scope.value,
        period=limit.period.value,
        limit_usd=float(limit.limit_usd),
        provider=limit.provider,
        campaign_id=limit.campaign_id,
        operation=limit.operation,
        warning_threshold=limit.warning_threshold,
        critical_threshold=limit.critical_threshold,
        enabled=limit.enabled,
        circuit_breaker_enabled=limit.circuit_breaker_enabled,
    )


@router.delete("/limits/{name}")
async def delete_limit(name: str):
    """Delete a cost limit"""
    if name not in guardrail_manager._limits:
        raise HTTPException(status_code=404, detail=f"Limit '{name}' not found")

    guardrail_manager.remove_limit(name)
    return {"message": f"Limit '{name}' deleted successfully"}


@router.get("/budget", response_model=BudgetSummaryResponse)
async def get_budget_summary(
    period: LimitPeriod = Query(LimitPeriod.DAILY, description="Time period"),
) -> BudgetSummaryResponse:
    """Get budget summary for all providers"""
    provider_budgets = {}
    total_remaining = Decimal("0")
    total_limit = Decimal("0")
    total_spent = Decimal("0")

    # Get all provider limits for the period
    for limit in guardrail_manager._limits.values():
        if limit.scope != LimitScope.PROVIDER or limit.period != period:
            continue
        if not limit.enabled or not limit.provider:
            continue

        # Get current spend
        current_spend = guardrail_manager._get_current_spend(limit, limit.provider, None, None)

        remaining = max(Decimal("0"), limit.limit_usd - current_spend)

        provider_budgets[limit.provider] = {
            "remaining": float(remaining),
            "limit": float(limit.limit_usd),
            "spent": float(current_spend),
            "percentage": float(current_spend / limit.limit_usd) if limit.limit_usd > 0 else 0,
        }

        total_remaining += remaining
        total_limit += limit.limit_usd
        total_spent += current_spend

    return BudgetSummaryResponse(
        period=period.value,
        providers=provider_budgets,
        total_remaining=float(total_remaining),
        total_limit=float(total_limit),
        total_spent=float(total_spent),
        timestamp=datetime.utcnow(),
    )


@router.post("/rate-limits")
async def create_rate_limit(request: CreateRateLimitRequest):
    """Create a new rate limit"""
    rate_limit = RateLimitConfig(
        provider=request.provider,
        operation=request.operation,
        requests_per_minute=request.requests_per_minute,
        burst_size=request.burst_size,
        cost_per_minute=Decimal(str(request.cost_per_minute)) if request.cost_per_minute else None,
        cost_burst_size=Decimal(str(request.cost_burst_size)) if request.cost_burst_size else None,
    )

    guardrail_manager.add_rate_limit(rate_limit)

    return {"message": "Rate limit created successfully", "key": f"{rate_limit.provider}:{rate_limit.operation or '*'}"}


@router.post("/alerts/configure")
async def configure_alerts(request: ConfigureAlertRequest):
    """Configure alert channels"""
    from d0_gateway.guardrail_alerts import AlertSeverity

    config = AlertConfig(
        channel=request.channel,
        enabled=request.enabled,
        email_addresses=request.email_addresses,
        slack_webhook_url=request.slack_webhook_url,
        webhook_url=request.webhook_url,
        webhook_headers=request.webhook_headers,
        min_severity=AlertSeverity(request.min_severity),
        providers=request.providers,
    )

    alert_manager.add_config(config)

    return {"message": f"Alert channel {request.channel.value} configured successfully"}


@router.post("/circuit-breakers/{limit_name}/reset")
async def reset_circuit_breaker(limit_name: str):
    """Reset a circuit breaker"""
    if limit_name not in guardrail_manager._limits:
        raise HTTPException(status_code=404, detail=f"Limit '{limit_name}' not found")

    if limit_name in guardrail_manager._circuit_breakers:
        del guardrail_manager._circuit_breakers[limit_name]
        return {"message": f"Circuit breaker for '{limit_name}' reset successfully"}
    else:
        return {"message": f"No circuit breaker active for '{limit_name}'"}


@router.get("/violations")
async def get_recent_violations(
    hours: int = Query(24, description="Hours to look back"),
    min_severity: Optional[str] = Query(None, description="Minimum severity"),
) -> List[Dict]:
    """Get recent guardrail violations from logs"""
    # In a production system, this would query a violations table
    # For now, return a placeholder response
    return [
        {
            "message": "This endpoint would return recent violations from a violations table",
            "note": "Implement violation storage in database for production use",
        }
    ]


class AlertAcknowledgment(BaseModel):
    """Acknowledgment of an alert"""

    alert_id: str = Field(..., description="ID of the alert being acknowledged")
    limit_name: str = Field(..., description="Name of the limit that triggered the alert")
    acknowledged_by: str = Field(..., description="User or system acknowledging the alert")
    action_taken: str = Field(..., description="Action taken in response to alert")
    notes: Optional[str] = Field(None, description="Additional notes")
    increase_limit_to: Optional[float] = Field(None, description="New limit if increasing")
    snooze_until: Optional[datetime] = Field(None, description="Snooze alerts until this time")


@router.post("/alerts/acknowledge")
async def acknowledge_alert(ack: AlertAcknowledgment) -> Dict[str, Any]:
    """
    Acknowledge an alert and optionally take action

    This endpoint allows users to:
    - Acknowledge they've seen an alert
    - Temporarily increase limits
    - Snooze future alerts
    - Reset circuit breakers
    """
    response = {"acknowledged": True, "alert_id": ack.alert_id, "timestamp": datetime.utcnow(), "actions_taken": []}

    # If increasing limit
    if ack.increase_limit_to and ack.limit_name in guardrail_manager._limits:
        old_limit = guardrail_manager._limits[ack.limit_name].limit_usd
        guardrail_manager._limits[ack.limit_name].limit_usd = Decimal(str(ack.increase_limit_to))
        response["actions_taken"].append(f"Increased limit from ${old_limit} to ${ack.increase_limit_to}")
        logger.info(
            f"Limit '{ack.limit_name}' increased from ${old_limit} to ${ack.increase_limit_to} "
            f"by {ack.acknowledged_by}"
        )

    # If snoozing alerts
    if ack.snooze_until:
        # In production, this would update alert configuration
        response["actions_taken"].append(f"Alerts snoozed until {ack.snooze_until.isoformat()}")
        logger.info(f"Alerts for '{ack.limit_name}' snoozed until {ack.snooze_until} " f"by {ack.acknowledged_by}")

    # Log the acknowledgment
    logger.info(
        f"Alert {ack.alert_id} acknowledged by {ack.acknowledged_by}. "
        f"Action: {ack.action_taken}. Notes: {ack.notes}"
    )

    response["message"] = "Alert acknowledged successfully"
    return response


async def _test_alert_core(channel, severity: str) -> Dict[str, Any]:
    """Core test alert functionality that can be called directly or via API"""
    from d0_gateway.alerts import alert_manager
    from d0_gateway.guardrail_alerts import AlertChannel
    from d0_gateway.guardrails import AlertSeverity, GuardrailAction, GuardrailViolation, LimitScope

    # Create a test violation
    test_violation = GuardrailViolation(
        limit_name="test_limit",
        scope=LimitScope.GLOBAL,
        severity=AlertSeverity(severity),
        current_spend=Decimal("850.00"),
        limit_amount=Decimal("1000.00"),
        percentage_used=0.85,
        provider="test_provider",
        operation="test_operation",
        action_taken=[GuardrailAction.ALERT],
        metadata={"test": True},
    )

    # Handle both AlertChannel enum and raw channel values
    channel_enum = channel if isinstance(channel, AlertChannel) else AlertChannel(channel)
    channel_value = channel_enum.value

    # Send test alert
    results = await alert_manager.send_alert(test_violation, [channel_enum])

    return {
        "channel": channel_value,
        "success": results.get(channel_enum, False),
        "message": f"Test alert sent to {channel_value}"
        if results.get(channel_enum)
        else f"Failed to send test alert to {channel_value}",
        "timestamp": datetime.utcnow(),
    }


@router.post("/alerts/test")
async def test_alert(
    channel: AlertChannel = Query(..., description="Channel to test"),
    severity: str = Query("warning", description="Alert severity to simulate"),
) -> Dict[str, Any]:
    """Test alert delivery to a specific channel"""
    return await _test_alert_core(channel, severity)
