"""
Cost guardrail middleware and decorators for P1-060
Provides automatic cost enforcement for API calls
"""
import asyncio
import functools
import time
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Callable, Dict, Optional, Tuple, Union

from core.logging import get_logger
from d0_gateway.guardrails import GuardrailAction, GuardrailViolation, guardrail_manager

logger = get_logger("gateway.guardrail_middleware", domain="d0")


class RateLimiter:
    """Token bucket rate limiter for API calls"""

    def __init__(self):
        self._buckets: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "tokens": 0,
                "last_refill": time.time(),
                "cost_tokens": Decimal("0"),
                "cost_last_refill": time.time(),
            }
        )

    def check_rate_limit(
        self, provider: str, operation: Optional[str] = None, cost: Optional[Decimal] = None
    ) -> Tuple[bool, Optional[float]]:
        """
        Check if request is within rate limits

        Args:
            provider: API provider
            operation: Specific operation
            cost: Estimated cost of operation

        Returns:
            Tuple of (allowed, retry_after_seconds)
        """
        key = f"{provider}:{operation or '*'}"
        rate_limit = guardrail_manager._rate_limits.get(key)

        if not rate_limit or not rate_limit.enabled:
            return True, None

        bucket = self._buckets[key]

        # Initialize bucket with full burst size on first access
        if bucket["tokens"] == 0 and bucket["last_refill"] == bucket.get("_initialized_at", bucket["last_refill"]):
            bucket["tokens"] = rate_limit.burst_size
            bucket["_initialized_at"] = bucket["last_refill"]

        now = time.time()

        # Check request rate limit
        time_passed = now - bucket["last_refill"]
        refill_amount = (time_passed / 60) * rate_limit.requests_per_minute
        bucket["tokens"] = min(rate_limit.burst_size, bucket["tokens"] + refill_amount)
        bucket["last_refill"] = now

        if bucket["tokens"] < 1:
            retry_after = (1 - bucket["tokens"]) * 60 / rate_limit.requests_per_minute
            return False, retry_after

        # Check cost rate limit if applicable
        if cost and rate_limit.cost_per_minute:
            # Initialize cost bucket with full burst size on first access
            if bucket["cost_tokens"] == Decimal("0") and bucket["cost_last_refill"] == bucket.get(
                "_cost_initialized_at", bucket["cost_last_refill"]
            ):
                bucket["cost_tokens"] = Decimal(str(rate_limit.cost_burst_size or rate_limit.cost_per_minute * 2))
                bucket["_cost_initialized_at"] = bucket["cost_last_refill"]

            cost_time_passed = now - bucket["cost_last_refill"]
            cost_refill = (cost_time_passed / 60) * rate_limit.cost_per_minute
            bucket["cost_tokens"] = min(
                Decimal(str(rate_limit.cost_burst_size or rate_limit.cost_per_minute * 2)),
                bucket["cost_tokens"] + Decimal(str(cost_refill)),
            )
            bucket["cost_last_refill"] = now

            if bucket["cost_tokens"] < cost:
                retry_after = float(
                    (cost - bucket["cost_tokens"]) * Decimal("60") / Decimal(str(rate_limit.cost_per_minute))
                )
                return False, retry_after

        return True, None

    def consume_tokens(self, provider: str, operation: Optional[str] = None, cost: Optional[Decimal] = None):
        """Consume tokens after successful rate limit check"""
        key = f"{provider}:{operation or '*'}"
        bucket = self._buckets[key]

        bucket["tokens"] -= 1
        if cost:
            bucket["cost_tokens"] -= cost


# Global rate limiter instance
rate_limiter = RateLimiter()


def enforce_cost_guardrails(
    estimate_cost: bool = True,
    record_cost: bool = True,
    provider_field: str = "provider",
    operation_field: str = "operation",
    campaign_field: str = "campaign_id",
):
    """
    Decorator to enforce cost guardrails on API client methods

    Args:
        estimate_cost: Whether to estimate cost before execution
        record_cost: Whether to record actual cost after execution
        provider_field: Name of provider parameter/attribute
        operation_field: Name of operation parameter/attribute
        campaign_field: Name of campaign_id parameter/attribute
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(self, *args, **kwargs):
            # Extract provider and operation
            provider = getattr(self, provider_field, None) or kwargs.get(provider_field)
            operation = kwargs.get(operation_field) or operation_field
            campaign_id = kwargs.get(campaign_field)

            if not provider:
                logger.error(f"No provider found for guardrail check in {func.__name__}")
                return await func(self, *args, **kwargs)

            # Check rate limits first
            allowed, retry_after = rate_limiter.check_rate_limit(provider, operation)
            if not allowed:
                raise RateLimitExceeded(
                    f"Rate limit exceeded for {provider}/{operation}. " f"Retry after {retry_after:.1f} seconds"
                )

            # Estimate cost if enabled
            if estimate_cost:
                try:
                    # Try to use the client's calculate_cost method if available
                    if hasattr(self, "calculate_cost"):
                        estimated_cost = Decimal(str(self.calculate_cost(operation, **kwargs)))
                    else:
                        estimate = guardrail_manager.estimate_cost(provider, operation, **kwargs)
                        estimated_cost = estimate.estimated_cost
                except Exception as e:
                    logger.warning(f"Failed to estimate cost: {e}")
                    estimated_cost = Decimal("0.00")
            else:
                estimated_cost = Decimal("0.00")

            # Check guardrails - extract campaign_id from kwargs to avoid duplication
            enforce_kwargs = {k: v for k, v in kwargs.items() if k != campaign_field}
            result = guardrail_manager.enforce_limits(
                provider=provider,
                operation=operation,
                estimated_cost=estimated_cost,
                campaign_id=campaign_id,
                **enforce_kwargs,
            )

            if isinstance(result, GuardrailViolation):
                if GuardrailAction.BLOCK in result.action_taken:
                    raise GuardrailBlocked(
                        f"Operation blocked by guardrail '{result.limit_name}': "
                        f"${result.current_spend:.2f} / ${result.limit_amount:.2f} "
                        f"({result.percentage_used:.1%})"
                    )
                elif GuardrailAction.THROTTLE in result.action_taken:
                    # Add delay for throttling
                    delay = min(30, result.percentage_used * 10)  # Max 30s delay
                    logger.warning(f"Throttling request for {delay:.1f}s due to guardrail")
                    await asyncio.sleep(delay)

            # Consume rate limit tokens
            rate_limiter.consume_tokens(provider, operation, estimated_cost)

            # Execute the function
            start_time = time.time()
            try:
                result = await func(self, *args, **kwargs)

                # Record actual cost if enabled
                if record_cost and hasattr(self, "emit_cost"):
                    # The actual cost recording is handled by the client's emit_cost method
                    pass

                return result

            except Exception as e:
                # Update circuit breaker on failures
                elapsed = time.time() - start_time
                if elapsed < 1.0:  # Fast failure indicates potential issue
                    for limit in guardrail_manager._limits.values():
                        if limit.circuit_breaker_enabled and limit.provider == provider:
                            guardrail_manager._update_circuit_breaker(
                                limit.name,
                                limit.circuit_breaker_failure_threshold,
                                limit.circuit_breaker_recovery_timeout,
                            )
                raise

        @functools.wraps(func)
        def sync_wrapper(self, *args, **kwargs):
            # Extract provider and operation
            provider = getattr(self, provider_field, None) or kwargs.get(provider_field)
            operation = kwargs.get(operation_field) or operation_field
            campaign_id = kwargs.get(campaign_field)

            if not provider:
                logger.error(f"No provider found for guardrail check in {func.__name__}")
                return func(self, *args, **kwargs)

            # Check rate limits first
            allowed, retry_after = rate_limiter.check_rate_limit(provider, operation)
            if not allowed:
                raise RateLimitExceeded(
                    f"Rate limit exceeded for {provider}/{operation}. " f"Retry after {retry_after:.1f} seconds"
                )

            # Estimate cost if enabled
            if estimate_cost:
                try:
                    # Try to use the client's calculate_cost method if available
                    if hasattr(self, "calculate_cost"):
                        estimated_cost = Decimal(str(self.calculate_cost(operation, **kwargs)))
                    else:
                        estimate = guardrail_manager.estimate_cost(provider, operation, **kwargs)
                        estimated_cost = estimate.estimated_cost
                except Exception as e:
                    logger.warning(f"Failed to estimate cost: {e}")
                    estimated_cost = Decimal("0.00")
            else:
                estimated_cost = Decimal("0.00")

            # Check guardrails - extract campaign_id from kwargs to avoid duplication
            enforce_kwargs = {k: v for k, v in kwargs.items() if k != campaign_field}
            result = guardrail_manager.enforce_limits(
                provider=provider,
                operation=operation,
                estimated_cost=estimated_cost,
                campaign_id=campaign_id,
                **enforce_kwargs,
            )

            if isinstance(result, GuardrailViolation):
                if GuardrailAction.BLOCK in result.action_taken:
                    raise GuardrailBlocked(
                        f"Operation blocked by guardrail '{result.limit_name}': "
                        f"${result.current_spend:.2f} / ${result.limit_amount:.2f} "
                        f"({result.percentage_used:.1%})"
                    )
                elif GuardrailAction.THROTTLE in result.action_taken:
                    # Add delay for throttling
                    delay = min(30, result.percentage_used * 10)  # Max 30s delay
                    logger.warning(f"Throttling request for {delay:.1f}s due to guardrail")
                    time.sleep(delay)

            # Consume rate limit tokens
            rate_limiter.consume_tokens(provider, operation, estimated_cost)

            # Execute the function
            start_time = time.time()
            try:
                result = func(self, *args, **kwargs)

                # Record actual cost if enabled
                if record_cost and hasattr(self, "emit_cost"):
                    # The actual cost recording is handled by the client's emit_cost method
                    pass

                return result

            except Exception as e:
                # Update circuit breaker on failures
                elapsed = time.time() - start_time
                if elapsed < 1.0:  # Fast failure indicates potential issue
                    for limit in guardrail_manager._limits.values():
                        if limit.circuit_breaker_enabled and limit.provider == provider:
                            guardrail_manager._update_circuit_breaker(
                                limit.name,
                                limit.circuit_breaker_failure_threshold,
                                limit.circuit_breaker_recovery_timeout,
                            )
                raise

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


class GuardrailContext:
    """Context manager for temporary guardrail overrides"""

    def __init__(
        self,
        provider: Optional[str] = None,
        bypass_guardrails: bool = False,
        temporary_limits: Optional[Dict[str, Decimal]] = None,
    ):
        self.provider = provider
        self.bypass_guardrails = bypass_guardrails
        self.temporary_limits = temporary_limits or {}
        self._original_limits = {}
        self._original_enabled = {}

    def __enter__(self):
        if self.bypass_guardrails:
            # Disable all limits temporarily
            for name, limit in guardrail_manager._limits.items():
                if self.provider and limit.provider != self.provider:
                    continue
                self._original_enabled[name] = limit.enabled
                limit.enabled = False

        # Apply temporary limit overrides
        for name, new_limit in self.temporary_limits.items():
            if name in guardrail_manager._limits:
                limit = guardrail_manager._limits[name]
                self._original_limits[name] = limit.limit_usd
                limit.limit_usd = new_limit

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore original enabled states
        for name, enabled in self._original_enabled.items():
            guardrail_manager._limits[name].enabled = enabled

        # Restore original limits
        for name, limit_usd in self._original_limits.items():
            guardrail_manager._limits[name].limit_usd = limit_usd


# Custom exceptions
class GuardrailException(Exception):
    """Base exception for guardrail violations"""

    pass


class GuardrailBlocked(GuardrailException):
    """Raised when an operation is blocked by guardrails"""

    pass


class RateLimitExceeded(GuardrailException):
    """Raised when rate limits are exceeded"""

    pass


# Utility functions
def check_budget_available(
    provider: str, operation: str, estimated_cost: Union[float, Decimal], campaign_id: Optional[int] = None
) -> bool:
    """
    Quick check if budget is available for an operation

    Args:
        provider: API provider
        operation: Operation to perform
        estimated_cost: Estimated cost
        campaign_id: Campaign ID if applicable

    Returns:
        True if budget is available
    """
    statuses = guardrail_manager.check_limits(
        provider=provider, operation=operation, estimated_cost=Decimal(str(estimated_cost)), campaign_id=campaign_id
    )

    for status in statuses:
        if status.is_blocked or status.circuit_breaker_open:
            return False

    return True


def get_remaining_budget(provider: Optional[str] = None, period: str = "daily") -> Dict[str, Decimal]:
    """
    Get remaining budget for providers

    Args:
        provider: Specific provider or None for all
        period: Time period (daily, monthly, etc.)

    Returns:
        Dict of provider -> remaining budget
    """
    remaining = {}

    for limit in guardrail_manager._limits.values():
        if period != limit.period.value:
            continue

        if provider and limit.provider != provider:
            continue

        if limit.scope.value == "provider" and limit.provider:
            current_spend = guardrail_manager._get_current_spend(limit, limit.provider, None, None)
            remaining[limit.provider] = max(Decimal("0"), limit.limit_usd - current_spend)

    return remaining
