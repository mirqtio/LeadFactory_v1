"""
Cost enforcement middleware and decorators for P1-060 Cost guardrails
Implements pre-flight cost estimation, circuit breakers, and rate limiting
"""
import asyncio
import functools
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, Field

from core.config import get_settings
from core.exceptions import ExternalAPIError
from core.logging import get_logger
from d0_gateway.guardrails import CostEstimate, GuardrailAction, GuardrailViolation, guardrail_manager

logger = get_logger("gateway.cost_enforcement", domain="d0")


class OperationPriority(str, Enum):
    """Priority levels for operations"""

    CRITICAL = "critical"  # Must not be blocked (e.g., payment processing)
    HIGH = "high"  # Should rarely be blocked
    NORMAL = "normal"  # Standard operations
    LOW = "low"  # Can be aggressively rate limited


class TokenBucket:
    """
    Token bucket implementation for rate limiting
    Supports both request count and cost-based limiting
    """

    def __init__(
        self,
        capacity: int,
        refill_rate: float,
        cost_capacity: Optional[Decimal] = None,
        cost_refill_rate: Optional[Decimal] = None,
    ):
        self.capacity = capacity
        self.refill_rate = refill_rate  # tokens per second
        self.tokens = float(capacity)
        self.last_refill = time.time()

        # Cost-based rate limiting
        self.cost_capacity = cost_capacity
        self.cost_refill_rate = cost_refill_rate  # cost per second
        self.cost_tokens = float(cost_capacity) if cost_capacity else None
        self.cost_last_refill = time.time()

    def consume(self, tokens: int = 1, cost: Optional[Decimal] = None) -> Tuple[bool, Optional[float]]:
        """
        Try to consume tokens from the bucket

        Returns:
            Tuple of (success, retry_after_seconds)
        """
        now = time.time()

        # Refill request tokens
        time_passed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + time_passed * self.refill_rate)
        self.last_refill = now

        # Check request limit
        if self.tokens < tokens:
            retry_after = (tokens - self.tokens) / self.refill_rate
            return False, retry_after

        # Refill and check cost tokens if applicable
        if cost and self.cost_capacity and self.cost_refill_rate:
            cost_time_passed = now - self.cost_last_refill
            self.cost_tokens = min(
                float(self.cost_capacity),
                self.cost_tokens + cost_time_passed * float(self.cost_refill_rate),
            )
            self.cost_last_refill = now

            if self.cost_tokens < float(cost):
                retry_after = (float(cost) - self.cost_tokens) / float(self.cost_refill_rate)
                return False, retry_after

        # Consume tokens
        self.tokens -= tokens
        if cost and self.cost_tokens is not None:
            self.cost_tokens -= float(cost)

        return True, None


class SlidingWindowCounter:
    """
    Sliding window counter for tracking costs over time periods
    """

    def __init__(self, window_size: timedelta):
        self.window_size = window_size
        self.events: deque = deque()
        self._total = Decimal("0")

    def add(self, amount: Decimal, timestamp: Optional[datetime] = None):
        """Add an event to the window"""
        timestamp = timestamp or datetime.utcnow()
        self.events.append((timestamp, amount))
        self._total += amount
        self._cleanup()

    def get_total(self) -> Decimal:
        """Get total within the current window"""
        self._cleanup()
        return self._total

    def _cleanup(self):
        """Remove events outside the window"""
        cutoff = datetime.utcnow() - self.window_size
        while self.events and self.events[0][0] < cutoff:
            _, amount = self.events.popleft()
            self._total -= amount


class PreflightCostEstimator:
    """
    Estimates costs before API calls based on operation type and parameters
    """

    def __init__(self):
        self.settings = get_settings()
        self._cost_models = self._initialize_cost_models()

    def _initialize_cost_models(self) -> Dict[str, Dict[str, Any]]:
        """Initialize cost models for different providers and operations"""
        return {
            "openai": {
                "chat_completion": self._estimate_openai_cost,
                "embedding": lambda **kwargs: Decimal("0.0001") * kwargs.get("text_length", 1000) / 1000,
            },
            "dataaxle": {
                "match_business": lambda **kwargs: Decimal("0.05"),
                "enrich_business": lambda **kwargs: Decimal("0.10"),
            },
            "hunter": {
                "find_email": lambda **kwargs: Decimal("0.01"),
                "verify_email": lambda **kwargs: Decimal("0.005"),
            },
            "semrush": {
                "domain_overview": lambda **kwargs: Decimal("0.10"),
                "keyword_research": lambda **kwargs: Decimal("0.15"),
            },
            "screenshotone": {
                "capture": lambda **kwargs: Decimal("0.003"),
                "capture_full_page": lambda **kwargs: Decimal("0.005"),
            },
            "google_places": {
                "search": lambda **kwargs: Decimal("0.017"),  # $17 per 1000
                "details": lambda **kwargs: Decimal("0.017"),
            },
            "pagespeed": {
                "analyze": lambda **kwargs: Decimal("0.0"),  # Free API
            },
        }

    def estimate(self, provider: str, operation: str, **parameters) -> CostEstimate:
        """
        Estimate the cost of an operation

        Args:
            provider: API provider name
            operation: Operation to perform
            **parameters: Operation-specific parameters

        Returns:
            CostEstimate with estimated cost and confidence
        """
        # Check if we have a specific cost model
        if provider in self._cost_models and operation in self._cost_models[provider]:
            estimator = self._cost_models[provider][operation]
            try:
                estimated_cost = estimator(**parameters)
                confidence = 0.95
                based_on = "model"
            except Exception as e:
                logger.warning(f"Cost model failed for {provider}/{operation}: {e}")
                estimated_cost = self._get_fallback_estimate(provider, operation)
                confidence = 0.7
                based_on = "fallback"
        else:
            # Use guardrail manager's estimate as fallback
            estimate = guardrail_manager.estimate_cost(provider, operation, **parameters)
            return estimate

        return CostEstimate(
            provider=provider,
            operation=operation,
            estimated_cost=estimated_cost,
            confidence=confidence,
            based_on=based_on,
            metadata=parameters,
        )

    def _estimate_openai_cost(self, **kwargs) -> Decimal:
        """Estimate OpenAI API costs based on tokens"""
        model = kwargs.get("model", "gpt-3.5-turbo")
        estimated_tokens = kwargs.get("estimated_tokens", 1000)

        # Cost per 1K tokens (approximate)
        cost_per_1k = {
            "gpt-4": Decimal("0.03"),
            "gpt-4-turbo": Decimal("0.01"),
            "gpt-3.5-turbo": Decimal("0.0015"),
            "text-embedding-ada-002": Decimal("0.0001"),
        }

        base_rate = cost_per_1k.get(model, Decimal("0.002"))
        return base_rate * Decimal(estimated_tokens) / 1000

    def _get_fallback_estimate(self, provider: str, operation: str) -> Decimal:
        """Get a conservative fallback estimate"""
        # Conservative estimates when model fails
        fallback_costs = {
            "openai": Decimal("0.01"),
            "dataaxle": Decimal("0.10"),
            "hunter": Decimal("0.02"),
            "semrush": Decimal("0.20"),
            "screenshotone": Decimal("0.01"),
            "google_places": Decimal("0.02"),
        }
        return fallback_costs.get(provider, Decimal("0.05"))


class CostEnforcementMiddleware:
    """
    Main middleware class for cost enforcement
    Integrates rate limiting, cost tracking, and circuit breakers
    """

    def __init__(self):
        self.settings = get_settings()
        self.logger = logger
        self.estimator = PreflightCostEstimator()

        # Rate limiters per provider/operation
        self._rate_limiters: Dict[str, TokenBucket] = {}

        # Sliding window counters for cost tracking
        self._cost_windows: Dict[str, Dict[str, SlidingWindowCounter]] = defaultdict(dict)

        # Operation priorities
        self._operation_priorities: Dict[str, OperationPriority] = {}

        self._initialize_rate_limiters()

    def _initialize_rate_limiters(self):
        """Initialize rate limiters from configuration"""
        for key, config in guardrail_manager._rate_limits.items():
            if config.enabled:
                self._rate_limiters[key] = TokenBucket(
                    capacity=config.burst_size,
                    refill_rate=config.requests_per_minute / 60,
                    cost_capacity=config.cost_burst_size,
                    cost_refill_rate=config.cost_per_minute / 60 if config.cost_per_minute else None,
                )

    def set_operation_priority(self, provider: str, operation: str, priority: OperationPriority):
        """Set the priority for a specific operation"""
        key = f"{provider}:{operation}"
        self._operation_priorities[key] = priority
        logger.info(f"Set priority {priority.value} for {key}")

    async def check_and_enforce(
        self,
        provider: str,
        operation: str,
        estimated_cost: Optional[Decimal] = None,
        campaign_id: Optional[int] = None,
        priority: Optional[OperationPriority] = None,
        **kwargs,
    ) -> Union[bool, Dict[str, Any]]:
        """
        Check and enforce all cost controls

        Args:
            provider: API provider
            operation: Operation to perform
            estimated_cost: Pre-estimated cost (will estimate if not provided)
            campaign_id: Campaign ID if applicable
            priority: Operation priority (overrides configured priority)

        Returns:
            True if allowed, Dict with violation details if blocked
        """
        # Determine operation priority
        operation_key = f"{provider}:{operation}"
        priority = priority or self._operation_priorities.get(operation_key, OperationPriority.NORMAL)

        # Skip enforcement for critical operations
        if priority == OperationPriority.CRITICAL:
            logger.info(f"Skipping enforcement for critical operation: {operation_key}")
            return True

        # Estimate cost if not provided
        if estimated_cost is None:
            estimate = self.estimator.estimate(provider, operation, **kwargs)
            estimated_cost = estimate.estimated_cost

        # Check rate limits
        rate_limit_result = await self._check_rate_limits(provider, operation, estimated_cost, priority)
        if rate_limit_result is not True:
            return rate_limit_result

        # Check cost guardrails
        guardrail_result = guardrail_manager.enforce_limits(
            provider=provider, operation=operation, estimated_cost=estimated_cost, campaign_id=campaign_id, **kwargs
        )

        if isinstance(guardrail_result, GuardrailViolation):
            # Apply priority-based handling
            if priority == OperationPriority.HIGH and GuardrailAction.BLOCK in guardrail_result.action_taken:
                # Downgrade BLOCK to THROTTLE for high priority
                guardrail_result.action_taken = [
                    GuardrailAction.THROTTLE if action == GuardrailAction.BLOCK else action
                    for action in guardrail_result.action_taken
                ]

            return self._handle_violation(guardrail_result, priority)

        # Update sliding windows
        self._update_cost_tracking(provider, operation, estimated_cost)

        return True

    async def _check_rate_limits(
        self, provider: str, operation: str, cost: Decimal, priority: OperationPriority
    ) -> Union[bool, Dict[str, Any]]:
        """Check rate limits with priority-based enforcement"""
        # Check operation-specific limit first
        operation_key = f"{provider}:{operation}"
        if operation_key in self._rate_limiters:
            allowed, retry_after = self._rate_limiters[operation_key].consume(1, cost)
            if not allowed:
                return self._handle_rate_limit_exceeded(provider, operation, retry_after, priority)

        # Check provider-wide limit
        provider_key = f"{provider}:*"
        if provider_key in self._rate_limiters:
            allowed, retry_after = self._rate_limiters[provider_key].consume(1, cost)
            if not allowed:
                return self._handle_rate_limit_exceeded(provider, operation, retry_after, priority)

        return True

    def _handle_rate_limit_exceeded(
        self, provider: str, operation: str, retry_after: float, priority: OperationPriority
    ) -> Dict[str, Any]:
        """Handle rate limit exceeded with priority consideration"""
        if priority == OperationPriority.LOW:
            # Aggressive rate limiting for low priority
            retry_after *= 2

        return {
            "allowed": False,
            "reason": "rate_limit_exceeded",
            "provider": provider,
            "operation": operation,
            "retry_after": retry_after,
            "priority": priority.value,
        }

    def _handle_violation(self, violation: GuardrailViolation, priority: OperationPriority) -> Dict[str, Any]:
        """Handle guardrail violations based on priority"""
        blocked = GuardrailAction.BLOCK in violation.action_taken

        # Apply throttling for non-critical operations
        if GuardrailAction.THROTTLE in violation.action_taken:
            # Calculate delay based on usage and priority
            base_delay = violation.percentage_used * 10
            priority_multiplier = {
                OperationPriority.HIGH: 0.5,
                OperationPriority.NORMAL: 1.0,
                OperationPriority.LOW: 2.0,
            }
            delay = base_delay * priority_multiplier.get(priority, 1.0)

            if not blocked:
                # Just throttle, don't block
                logger.warning(
                    f"Throttling {violation.provider}/{violation.operation} "
                    f"for {delay:.1f}s (priority: {priority.value})"
                )
                time.sleep(min(delay, 30))  # Cap at 30 seconds
                return True

        return {
            "allowed": not blocked,
            "reason": "guardrail_violation",
            "violation": violation.dict(),
            "priority": priority.value,
        }

    def _update_cost_tracking(self, provider: str, operation: str, cost: Decimal):
        """Update sliding window cost trackers"""
        # Track by provider
        if provider not in self._cost_windows:
            self._cost_windows[provider] = {
                "hourly": SlidingWindowCounter(timedelta(hours=1)),
                "daily": SlidingWindowCounter(timedelta(days=1)),
            }

        for window in self._cost_windows[provider].values():
            window.add(cost)

        # Track by operation
        operation_key = f"{provider}:{operation}"
        if operation_key not in self._cost_windows:
            self._cost_windows[operation_key] = {
                "hourly": SlidingWindowCounter(timedelta(hours=1)),
            }

        self._cost_windows[operation_key]["hourly"].add(cost)

    def get_current_usage(self, provider: Optional[str] = None, operation: Optional[str] = None) -> Dict[str, Any]:
        """Get current usage statistics"""
        usage = {}

        if provider:
            if provider in self._cost_windows:
                usage[provider] = {
                    period: window.get_total() for period, window in self._cost_windows[provider].items()
                }

            if operation:
                key = f"{provider}:{operation}"
                if key in self._cost_windows:
                    usage[key] = {period: window.get_total() for period, window in self._cost_windows[key].items()}
        else:
            # Return all usage
            for key, windows in self._cost_windows.items():
                usage[key] = {period: window.get_total() for period, window in windows.items()}

        return usage


# Global middleware instance
cost_enforcement = CostEnforcementMiddleware()


# Decorators for easy integration
def enforce_cost_limits(
    priority: OperationPriority = OperationPriority.NORMAL,
    estimate_cost: bool = True,
    provider_attr: str = "provider",
    operation_param: str = "operation",
):
    """
    Decorator to enforce cost limits on methods

    Args:
        priority: Operation priority level
        estimate_cost: Whether to estimate costs
        provider_attr: Attribute name for provider
        operation_param: Parameter name for operation
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(self, *args, **kwargs):
            # Extract provider and operation
            provider = getattr(self, provider_attr, None)
            operation = kwargs.get(operation_param, func.__name__)

            if not provider:
                return await func(self, *args, **kwargs)

            # Skip enforcement in stub mode to avoid database calls
            settings = getattr(self, "settings", None)
            if settings and settings.use_stubs:
                return await func(self, *args, **kwargs)

            # Estimate cost if needed
            estimated_cost = None
            if estimate_cost and hasattr(self, "calculate_cost"):
                try:
                    estimated_cost = self.calculate_cost(operation, **kwargs)
                except Exception:
                    pass

            # Check enforcement
            result = await cost_enforcement.check_and_enforce(
                provider=provider,
                operation=operation,
                estimated_cost=estimated_cost,
                campaign_id=kwargs.get("campaign_id"),
                priority=priority,
                **kwargs,
            )

            if result is not True:
                raise ExternalAPIError(
                    provider=provider,
                    message=f"Operation blocked: {result.get('reason')}",
                    status_code=429,
                    response_body=result,
                )

            return await func(self, *args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(self, *args, **kwargs):
            # Sync version of the decorator
            provider = getattr(self, provider_attr, None)
            operation = kwargs.get(operation_param, func.__name__)

            if not provider:
                return func(self, *args, **kwargs)

            # Skip enforcement in stub mode to avoid database calls
            settings = getattr(self, "settings", None)
            if settings and settings.use_stubs:
                return func(self, *args, **kwargs)

            # Run async check in sync context
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(
                    cost_enforcement.check_and_enforce(
                        provider=provider,
                        operation=operation,
                        campaign_id=kwargs.get("campaign_id"),
                        priority=priority,
                        **kwargs,
                    )
                )
            finally:
                loop.close()

            if result is not True:
                raise ExternalAPIError(
                    provider=provider,
                    message=f"Operation blocked: {result.get('reason')}",
                    status_code=429,
                    response_body=result,
                )

            return func(self, *args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


# Convenience decorators for different priority levels
def critical_operation(func: Callable) -> Callable:
    """Decorator for critical operations that should never be blocked"""
    return enforce_cost_limits(priority=OperationPriority.CRITICAL)(func)


def non_critical_operation(func: Callable) -> Callable:
    """Decorator for non-critical operations that can be aggressively limited"""
    return enforce_cost_limits(priority=OperationPriority.LOW)(func)
