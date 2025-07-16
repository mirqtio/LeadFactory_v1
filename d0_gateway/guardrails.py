"""
Cost guardrail models and configuration for P1-060
Provides configurable spending limits and enforcement mechanisms
"""
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field, validator
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from core.logging import get_logger
from database.models import APICost, DailyCostAggregate
from database.session import get_db_sync

logger = get_logger("gateway.guardrails", domain="d0")


class LimitScope(str, Enum):
    """Scope of cost limits"""

    GLOBAL = "global"
    PROVIDER = "provider"
    CAMPAIGN = "campaign"
    OPERATION = "operation"
    PROVIDER_OPERATION = "provider_operation"


class LimitPeriod(str, Enum):
    """Time period for cost limits"""

    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    TOTAL = "total"  # Lifetime limit


class AlertSeverity(str, Enum):
    """Alert severity levels"""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class GuardrailAction(str, Enum):
    """Actions to take when limits are exceeded"""

    LOG = "log"  # Just log the violation
    ALERT = "alert"  # Send alerts
    THROTTLE = "throttle"  # Slow down requests
    BLOCK = "block"  # Block further requests
    CIRCUIT_BREAK = "circuit_break"  # Open circuit breaker


class CostLimit(BaseModel):
    """Configuration for a single cost limit"""

    name: str = Field(..., description="Name of the limit")
    scope: LimitScope = Field(..., description="Scope of the limit")
    period: LimitPeriod = Field(..., description="Time period for the limit")
    limit_usd: Decimal = Field(..., gt=0, description="Limit amount in USD")

    # Scope-specific filters
    provider: Optional[str] = Field(None, description="Provider name for provider-scoped limits")
    campaign_id: Optional[int] = Field(None, description="Campaign ID for campaign-scoped limits")
    operation: Optional[str] = Field(None, description="Operation name for operation-scoped limits")

    # Thresholds and actions
    warning_threshold: float = Field(0.8, ge=0, le=1, description="Warning threshold (0-1)")
    critical_threshold: float = Field(0.95, ge=0, le=1, description="Critical threshold (0-1)")
    actions: List[GuardrailAction] = Field(
        default=[GuardrailAction.LOG, GuardrailAction.ALERT], description="Actions to take when limit is exceeded"
    )

    # Circuit breaker settings
    circuit_breaker_enabled: bool = Field(False, description="Enable circuit breaker")
    circuit_breaker_failure_threshold: int = Field(5, description="Failures before opening circuit")
    circuit_breaker_recovery_timeout: int = Field(300, description="Seconds before attempting recovery")

    # Metadata
    enabled: bool = Field(True, description="Whether this limit is active")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @validator("critical_threshold")
    def critical_must_be_higher_than_warning(cls, v, values):
        if "warning_threshold" in values and v < values["warning_threshold"]:
            raise ValueError("Critical threshold must be >= warning threshold")
        return v


class RateLimitConfig(BaseModel):
    """Configuration for rate limiting"""

    provider: str
    operation: Optional[str] = None

    # Token bucket settings
    requests_per_minute: int = Field(..., gt=0, description="Max requests per minute")
    burst_size: int = Field(..., gt=0, description="Max burst size")

    # Cost-based rate limiting
    cost_per_minute: Optional[Decimal] = Field(None, description="Max cost per minute")
    cost_burst_size: Optional[Decimal] = Field(None, description="Max cost burst")

    enabled: bool = Field(True, description="Whether this rate limit is active")


class GuardrailStatus(BaseModel):
    """Current status of a guardrail"""

    limit_name: str
    current_spend: Decimal
    limit_amount: Decimal
    percentage_used: float
    status: AlertSeverity
    remaining_budget: Decimal
    period_start: datetime
    period_end: datetime
    is_blocked: bool = False
    circuit_breaker_open: bool = False

    @property
    def is_over_limit(self) -> bool:
        return self.percentage_used >= 1.0


class GuardrailViolation(BaseModel):
    """Record of a guardrail violation"""

    timestamp: datetime = Field(default_factory=datetime.utcnow)
    limit_name: str
    scope: LimitScope
    severity: AlertSeverity
    current_spend: Decimal
    limit_amount: Decimal
    percentage_used: float
    provider: Optional[str] = None
    campaign_id: Optional[int] = None
    operation: Optional[str] = None
    action_taken: List[GuardrailAction]
    metadata: Dict = Field(default_factory=dict)


class CostEstimate(BaseModel):
    """Pre-flight cost estimate for an operation"""

    provider: str
    operation: str
    estimated_cost: Decimal
    confidence: float = Field(1.0, ge=0, le=1, description="Confidence in estimate (0-1)")
    based_on: str = Field("fixed", description="How estimate was calculated")
    metadata: Dict = Field(default_factory=dict)


class GuardrailManager:
    """
    Manages cost guardrails and enforcement
    """

    def __init__(self):
        self.logger = logger
        self._limits: Dict[str, CostLimit] = {}
        self._rate_limits: Dict[str, RateLimitConfig] = {}
        self._circuit_breakers: Dict[str, Dict] = {}
        self._load_default_limits()

    def _load_default_limits(self):
        """Load default guardrail configurations from settings"""
        from core.config import get_settings

        settings = get_settings()

        # Global daily limit
        self.add_limit(
            CostLimit(
                name="global_daily",
                scope=LimitScope.GLOBAL,
                period=LimitPeriod.DAILY,
                limit_usd=Decimal(str(settings.guardrail_global_daily_limit)),
                warning_threshold=settings.guardrail_warning_threshold,
                critical_threshold=settings.guardrail_critical_threshold,
                actions=[GuardrailAction.LOG, GuardrailAction.ALERT],
                circuit_breaker_enabled=settings.guardrail_enable_circuit_breaker,
            )
        )

        # Global monthly limit
        self.add_limit(
            CostLimit(
                name="global_monthly",
                scope=LimitScope.GLOBAL,
                period=LimitPeriod.MONTHLY,
                limit_usd=Decimal(str(settings.guardrail_global_monthly_limit)),
                warning_threshold=settings.guardrail_warning_threshold,
                critical_threshold=settings.guardrail_critical_threshold,
                actions=[GuardrailAction.LOG, GuardrailAction.ALERT, GuardrailAction.BLOCK],
                circuit_breaker_enabled=settings.guardrail_enable_circuit_breaker,
            )
        )

        # Provider-specific limits from settings
        for provider, limit in settings.guardrail_provider_daily_limits.items():
            self.add_limit(
                CostLimit(
                    name=f"{provider}_daily",
                    scope=LimitScope.PROVIDER,
                    period=LimitPeriod.DAILY,
                    provider=provider,
                    limit_usd=Decimal(str(limit)),
                    warning_threshold=settings.guardrail_warning_threshold,
                    critical_threshold=settings.guardrail_critical_threshold,
                    actions=[GuardrailAction.LOG, GuardrailAction.ALERT, GuardrailAction.THROTTLE],
                    circuit_breaker_enabled=settings.guardrail_enable_circuit_breaker,
                )
            )

    def add_limit(self, limit: CostLimit):
        """Add or update a cost limit"""
        self._limits[limit.name] = limit
        self.logger.info(f"Added cost limit: {limit.name} (${limit.limit_usd} {limit.period.value})")

    def remove_limit(self, name: str):
        """Remove a cost limit"""
        if name in self._limits:
            del self._limits[name]
            self.logger.info(f"Removed cost limit: {name}")

    def add_rate_limit(self, rate_limit: RateLimitConfig):
        """Add or update a rate limit"""
        key = f"{rate_limit.provider}:{rate_limit.operation or '*'}"
        self._rate_limits[key] = rate_limit
        self.logger.info(f"Added rate limit: {key} ({rate_limit.requests_per_minute} rpm)")

    def estimate_cost(self, provider: str, operation: str, **kwargs) -> CostEstimate:
        """
        Estimate the cost of an operation before execution

        Args:
            provider: API provider
            operation: Operation to perform
            **kwargs: Additional context for estimation

        Returns:
            Cost estimate
        """
        # Fixed costs per operation (can be made dynamic later)
        cost_map = {
            ("dataaxle", "match_business"): Decimal("0.05"),
            ("hunter", "find_email"): Decimal("0.01"),
            ("openai", "analyze"): Decimal("0.001"),  # Base cost, actual varies by tokens
            ("semrush", "domain_overview"): Decimal("0.10"),
            ("screenshotone", "capture"): Decimal("0.003"),
        }

        base_cost = cost_map.get((provider, operation), Decimal("0.00"))

        # Adjust for OpenAI based on estimated tokens
        if provider == "openai" and "estimated_tokens" in kwargs:
            tokens = kwargs["estimated_tokens"]
            base_cost = Decimal(str(tokens * 0.000001))  # Rough estimate

        return CostEstimate(
            provider=provider,
            operation=operation,
            estimated_cost=base_cost,
            confidence=0.9 if provider == "openai" else 1.0,
            based_on="token_estimate" if provider == "openai" else "fixed",
            metadata=kwargs,
        )

    def check_limits(
        self, provider: str, operation: str, estimated_cost: Decimal, campaign_id: Optional[int] = None, **kwargs
    ) -> List[GuardrailStatus]:
        """
        Check all applicable limits for an operation

        Args:
            provider: API provider
            operation: Operation to perform
            estimated_cost: Estimated cost of the operation
            campaign_id: Campaign ID if applicable

        Returns:
            List of guardrail statuses
        """
        statuses = []

        for limit in self._limits.values():
            if not limit.enabled:
                continue

            # Check if limit applies to this operation
            if not self._limit_applies(limit, provider, operation, campaign_id):
                continue

            # Get current spend for this limit
            current_spend = self._get_current_spend(limit, provider, operation, campaign_id)

            # Calculate status
            projected_spend = current_spend + estimated_cost
            percentage_used = float(projected_spend / limit.limit_usd)

            # Determine status level
            if percentage_used >= 1.0:
                status = AlertSeverity.EMERGENCY
            elif percentage_used >= limit.critical_threshold:
                status = AlertSeverity.CRITICAL
            elif percentage_used >= limit.warning_threshold:
                status = AlertSeverity.WARNING
            else:
                status = AlertSeverity.INFO

            # Get period bounds
            period_start, period_end = self._get_period_bounds(limit.period)

            # Check circuit breaker
            circuit_open = self._is_circuit_open(limit.name) if limit.circuit_breaker_enabled else False

            statuses.append(
                GuardrailStatus(
                    limit_name=limit.name,
                    current_spend=current_spend,
                    limit_amount=limit.limit_usd,
                    percentage_used=percentage_used,
                    status=status,
                    remaining_budget=max(Decimal("0"), limit.limit_usd - projected_spend),
                    period_start=period_start,
                    period_end=period_end,
                    is_blocked=GuardrailAction.BLOCK in limit.actions and percentage_used >= 1.0,
                    circuit_breaker_open=circuit_open,
                )
            )

        return statuses

    def enforce_limits(
        self, provider: str, operation: str, estimated_cost: Decimal, campaign_id: Optional[int] = None, **kwargs
    ) -> Union[bool, GuardrailViolation]:
        """
        Enforce cost limits, blocking if necessary

        Args:
            provider: API provider
            operation: Operation to perform
            estimated_cost: Estimated cost
            campaign_id: Campaign ID if applicable

        Returns:
            True if operation allowed, GuardrailViolation if blocked
        """
        statuses = self.check_limits(provider, operation, estimated_cost, campaign_id, **kwargs)

        for status in statuses:
            limit = self._limits[status.limit_name]

            # Check if we should block
            if status.is_blocked or status.circuit_breaker_open:
                violation = GuardrailViolation(
                    limit_name=status.limit_name,
                    scope=limit.scope,
                    severity=status.status,
                    current_spend=status.current_spend,
                    limit_amount=status.limit_amount,
                    percentage_used=status.percentage_used,
                    provider=provider,
                    campaign_id=campaign_id,
                    operation=operation,
                    action_taken=[GuardrailAction.BLOCK],
                    metadata={"circuit_breaker_open": status.circuit_breaker_open},
                )

                self._handle_violation(violation, limit)
                return violation

            # Check if we should alert
            if status.status in [AlertSeverity.WARNING, AlertSeverity.CRITICAL]:
                violation = GuardrailViolation(
                    limit_name=status.limit_name,
                    scope=limit.scope,
                    severity=status.status,
                    current_spend=status.current_spend,
                    limit_amount=status.limit_amount,
                    percentage_used=status.percentage_used,
                    provider=provider,
                    campaign_id=campaign_id,
                    operation=operation,
                    action_taken=limit.actions,
                    metadata={},
                )

                self._handle_violation(violation, limit)

        return True

    def _limit_applies(self, limit: CostLimit, provider: str, operation: str, campaign_id: Optional[int]) -> bool:
        """Check if a limit applies to the given operation"""
        if limit.scope == LimitScope.GLOBAL:
            return True
        elif limit.scope == LimitScope.PROVIDER:
            return limit.provider == provider
        elif limit.scope == LimitScope.CAMPAIGN:
            return limit.campaign_id == campaign_id
        elif limit.scope == LimitScope.OPERATION:
            return limit.operation == operation
        elif limit.scope == LimitScope.PROVIDER_OPERATION:
            return limit.provider == provider and limit.operation == operation
        return False

    def _get_current_spend(
        self, limit: CostLimit, provider: str, operation: str, campaign_id: Optional[int]
    ) -> Decimal:
        """Get current spend for a limit period"""
        period_start, period_end = self._get_period_bounds(limit.period)

        with get_db_sync() as db:
            # Use aggregated data for daily periods when possible
            if limit.period == LimitPeriod.DAILY and period_start.date() <= datetime.utcnow().date():
                return self._get_daily_spend_from_aggregate(
                    db, limit, provider, operation, campaign_id, period_start.date()
                )
            else:
                return self._get_spend_from_raw(db, limit, provider, operation, campaign_id, period_start, period_end)

    def _get_daily_spend_from_aggregate(
        self,
        db: Session,
        limit: CostLimit,
        provider: str,
        operation: str,
        campaign_id: Optional[int],
        date: datetime.date,
    ) -> Decimal:
        """Get spend from daily aggregates"""
        query = db.query(func.sum(DailyCostAggregate.total_cost_usd)).filter(DailyCostAggregate.date == date)

        if limit.scope == LimitScope.PROVIDER:
            query = query.filter(DailyCostAggregate.provider == provider)
        elif limit.scope == LimitScope.CAMPAIGN:
            query = query.filter(DailyCostAggregate.campaign_id == campaign_id)
        elif limit.scope == LimitScope.PROVIDER_OPERATION:
            query = query.filter(
                and_(DailyCostAggregate.provider == provider, DailyCostAggregate.operation == operation)
            )

        result = query.scalar()
        return result or Decimal("0.00")

    def _get_spend_from_raw(
        self,
        db: Session,
        limit: CostLimit,
        provider: str,
        operation: str,
        campaign_id: Optional[int],
        start: datetime,
        end: datetime,
    ) -> Decimal:
        """Get spend from raw cost records"""
        query = db.query(func.sum(APICost.cost_usd)).filter(and_(APICost.timestamp >= start, APICost.timestamp < end))

        if limit.scope == LimitScope.PROVIDER:
            query = query.filter(APICost.provider == provider)
        elif limit.scope == LimitScope.CAMPAIGN:
            query = query.filter(APICost.campaign_id == campaign_id)
        elif limit.scope == LimitScope.OPERATION:
            query = query.filter(APICost.operation == operation)
        elif limit.scope == LimitScope.PROVIDER_OPERATION:
            query = query.filter(and_(APICost.provider == provider, APICost.operation == operation))

        result = query.scalar()
        return result or Decimal("0.00")

    def _get_period_bounds(self, period: LimitPeriod) -> tuple[datetime, datetime]:
        """Get start and end times for a limit period"""
        now = datetime.utcnow()

        if period == LimitPeriod.HOURLY:
            start = now.replace(minute=0, second=0, microsecond=0)
            end = start + timedelta(hours=1)
        elif period == LimitPeriod.DAILY:
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
        elif period == LimitPeriod.WEEKLY:
            # Start of week (Monday)
            days_since_monday = now.weekday()
            start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days_since_monday)
            end = start + timedelta(days=7)
        elif period == LimitPeriod.MONTHLY:
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            # End of month
            if now.month == 12:
                end = start.replace(year=start.year + 1, month=1)
            else:
                end = start.replace(month=start.month + 1)
        else:  # TOTAL
            start = datetime(2020, 1, 1)  # Arbitrary old date
            end = datetime(2100, 1, 1)  # Far future

        return start, end

    def _is_circuit_open(self, limit_name: str) -> bool:
        """Check if circuit breaker is open for a limit"""
        if limit_name not in self._circuit_breakers:
            return False

        breaker = self._circuit_breakers[limit_name]
        if breaker["state"] == "open":
            # Check if recovery timeout has passed
            if datetime.utcnow() - breaker["opened_at"] > timedelta(seconds=breaker["recovery_timeout"]):
                breaker["state"] = "half_open"
                breaker["failure_count"] = 0
                return False
            return True
        return False

    def _handle_violation(self, violation: GuardrailViolation, limit: CostLimit):
        """Handle a guardrail violation"""
        # Log the violation
        self.logger.warning(
            f"Guardrail violation: {violation.limit_name} "
            f"({violation.percentage_used:.1%} of ${violation.limit_amount})"
        )

        # Update circuit breaker if enabled
        if limit.circuit_breaker_enabled and violation.severity == AlertSeverity.EMERGENCY:
            self._update_circuit_breaker(
                limit.name, limit.circuit_breaker_failure_threshold, limit.circuit_breaker_recovery_timeout
            )

        # TODO: Send alerts via configured channels (email, Slack, webhooks)
        # This will be implemented in the alert system module

    def _update_circuit_breaker(self, limit_name: str, failure_threshold: int, recovery_timeout: int):
        """Update circuit breaker state"""
        if limit_name not in self._circuit_breakers:
            self._circuit_breakers[limit_name] = {
                "state": "closed",
                "failure_count": 0,
                "opened_at": None,
                "recovery_timeout": recovery_timeout,
            }

        breaker = self._circuit_breakers[limit_name]
        breaker["failure_count"] += 1

        if breaker["failure_count"] >= failure_threshold:
            breaker["state"] = "open"
            breaker["opened_at"] = datetime.utcnow()
            self.logger.error(f"Circuit breaker opened for limit: {limit_name}")


# Singleton instance
guardrail_manager = GuardrailManager()
