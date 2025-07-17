"""
Unit tests for cost enforcement middleware
"""
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from d0_gateway.guardrails import CostLimit, GuardrailAction, GuardrailViolation, LimitPeriod, LimitScope
from d0_gateway.middleware.cost_enforcement import (
    CostEnforcementMiddleware,
    OperationPriority,
    PreflightCostEstimator,
    SlidingWindowCounter,
    TokenBucket,
    enforce_cost_limits,
)


class TestTokenBucket:
    """Test token bucket rate limiter"""

    def test_token_bucket_initialization(self):
        """Test token bucket initializes correctly"""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        assert bucket.capacity == 10
        assert bucket.refill_rate == 1.0
        assert bucket.tokens == 10.0

    def test_token_consumption(self):
        """Test consuming tokens from bucket"""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)

        # Should succeed with full bucket
        success, retry_after = bucket.consume(5)
        assert success is True
        assert retry_after is None
        assert bucket.tokens == 5.0

        # Should fail when not enough tokens
        success, retry_after = bucket.consume(6)
        assert success is False
        assert retry_after > 0

    def test_token_refill(self):
        """Test token refill mechanism"""
        bucket = TokenBucket(capacity=10, refill_rate=2.0)  # 2 tokens per second

        # Consume all tokens
        bucket.consume(10)
        assert bucket.tokens == 0.0

        # Mock time passage
        with patch("time.time") as mock_time:
            mock_time.return_value = bucket.last_refill + 2.5  # 2.5 seconds later

            # Should have refilled 5 tokens
            success, _ = bucket.consume(5)
            assert success is True
            assert bucket.tokens == 0.0  # 5 refilled, 5 consumed

    def test_cost_based_limiting(self):
        """Test cost-based token bucket"""
        bucket = TokenBucket(
            capacity=10, refill_rate=1.0, cost_capacity=Decimal("10.00"), cost_refill_rate=Decimal("1.00")
        )

        # Should succeed with cost within limit
        success, retry_after = bucket.consume(1, cost=Decimal("5.00"))
        assert success is True
        assert bucket.cost_tokens == 5.0

        # Should fail when cost exceeds remaining
        success, retry_after = bucket.consume(1, cost=Decimal("6.00"))
        assert success is False
        assert retry_after > 0


class TestSlidingWindowCounter:
    """Test sliding window counter for cost tracking"""

    def test_sliding_window_initialization(self):
        """Test sliding window initializes correctly"""
        window = SlidingWindowCounter(timedelta(hours=1))
        assert window.window_size == timedelta(hours=1)
        assert window.get_total() == Decimal("0")

    def test_adding_events(self):
        """Test adding events to window"""
        window = SlidingWindowCounter(timedelta(hours=1))

        window.add(Decimal("10.00"))
        window.add(Decimal("5.00"))

        assert window.get_total() == Decimal("15.00")

    def test_window_cleanup(self):
        """Test old events are removed from window"""
        window = SlidingWindowCounter(timedelta(hours=1))

        # Add event in the past
        old_time = datetime.utcnow() - timedelta(hours=2)
        window.add(Decimal("10.00"), old_time)

        # Add current event
        window.add(Decimal("5.00"))

        # Only current event should be counted
        assert window.get_total() == Decimal("5.00")


class TestPreflightCostEstimator:
    """Test pre-flight cost estimation"""

    def test_estimator_initialization(self):
        """Test estimator initializes with cost models"""
        estimator = PreflightCostEstimator()
        assert "openai" in estimator._cost_models
        assert "dataaxle" in estimator._cost_models

    def test_openai_cost_estimation(self):
        """Test OpenAI cost estimation"""
        estimator = PreflightCostEstimator()

        estimate = estimator.estimate("openai", "chat_completion", model="gpt-4", estimated_tokens=1000)

        assert estimate.provider == "openai"
        assert estimate.operation == "chat_completion"
        assert estimate.estimated_cost == Decimal("0.03")  # $0.03 per 1K tokens
        assert estimate.confidence == 0.95

    def test_fixed_cost_estimation(self):
        """Test fixed cost estimation"""
        estimator = PreflightCostEstimator()

        estimate = estimator.estimate("dataaxle", "match_business")

        assert estimate.provider == "dataaxle"
        assert estimate.operation == "match_business"
        assert estimate.estimated_cost == Decimal("0.05")
        assert estimate.confidence == 0.95

    def test_fallback_estimation(self):
        """Test fallback when model fails"""
        estimator = PreflightCostEstimator()

        # Mock the cost model to raise an exception
        original_func = estimator._cost_models["openai"]["chat_completion"]
        estimator._cost_models["openai"]["chat_completion"] = MagicMock(side_effect=Exception("Test error"))

        try:
            estimate = estimator.estimate("openai", "chat_completion")

            assert estimate.estimated_cost == Decimal("0.01")  # Fallback cost
            assert estimate.confidence == 0.7
            assert estimate.based_on == "fallback"
        finally:
            # Restore original function
            estimator._cost_models["openai"]["chat_completion"] = original_func


class TestCostEnforcementMiddleware:
    """Test main cost enforcement middleware"""

    @pytest.fixture
    def middleware(self):
        """Create middleware instance"""
        return CostEnforcementMiddleware()

    def test_middleware_initialization(self, middleware):
        """Test middleware initializes correctly"""
        assert middleware.estimator is not None
        assert isinstance(middleware._rate_limiters, dict)
        assert isinstance(middleware._cost_windows, dict)

    def test_set_operation_priority(self, middleware):
        """Test setting operation priorities"""
        middleware.set_operation_priority("openai", "analyze", OperationPriority.HIGH)

        assert middleware._operation_priorities["openai:analyze"] == OperationPriority.HIGH

    @pytest.mark.asyncio
    async def test_critical_operation_bypass(self, middleware):
        """Test critical operations bypass enforcement"""
        result = await middleware.check_and_enforce(
            provider="openai",
            operation="payment_process",
            estimated_cost=Decimal("100.00"),  # High cost
            priority=OperationPriority.CRITICAL,
        )

        assert result is True  # Should always pass for critical

    @pytest.mark.asyncio
    async def test_rate_limit_enforcement(self, middleware):
        """Test rate limit enforcement"""
        # Add a strict rate limiter
        middleware._rate_limiters["test:*"] = TokenBucket(capacity=1, refill_rate=0.1)  # Very slow refill

        # Mock the guardrail manager to avoid database calls
        with patch("d0_gateway.middleware.cost_enforcement.guardrail_manager") as mock_guardrail:
            mock_guardrail.enforce_limits.return_value = True

            # First request should succeed
            result = await middleware.check_and_enforce("test", "operation", Decimal("0.01"))
            assert result is True

            # Second request should be rate limited
            result = await middleware.check_and_enforce("test", "operation", Decimal("0.01"))
            assert result != True
            assert result["reason"] == "rate_limit_exceeded"
            assert result["retry_after"] > 0

    @pytest.mark.asyncio
    async def test_priority_based_rate_limiting(self, middleware):
        """Test priority affects rate limiting"""
        middleware._rate_limiters["test:*"] = TokenBucket(capacity=0, refill_rate=0.1)

        # Low priority should have longer retry
        result = await middleware.check_and_enforce(
            "test", "operation", Decimal("0.01"), priority=OperationPriority.LOW
        )
        low_retry = result["retry_after"]

        # High priority should have shorter retry
        result = await middleware.check_and_enforce(
            "test", "operation", Decimal("0.01"), priority=OperationPriority.HIGH
        )
        high_retry = result["retry_after"]

        assert low_retry > high_retry

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_guardrail_integration(self, middleware):
        """Test integration with guardrail manager"""
        with patch("d0_gateway.middleware.cost_enforcement.guardrail_manager.enforce_limits") as mock_enforce:
            # Mock a guardrail violation with BLOCK action to ensure dictionary response
            mock_violation = GuardrailViolation(
                limit_name="test_limit",
                scope=LimitScope.PROVIDER,
                severity="critical",
                current_spend=Decimal("90.00"),
                limit_amount=Decimal("100.00"),
                percentage_used=0.9,
                provider="test",
                operation="operation",
                action_taken=[GuardrailAction.THROTTLE, GuardrailAction.BLOCK],
            )
            mock_enforce.return_value = mock_violation

            result = await middleware.check_and_enforce("test", "operation", Decimal("15.00"))

            assert result != True
            assert result["reason"] == "guardrail_violation"
            assert "violation" in result

    def test_cost_tracking(self, middleware):
        """Test cost tracking with sliding windows"""
        middleware._update_cost_tracking("test", "operation", Decimal("10.00"))

        usage = middleware.get_current_usage("test")
        assert "test" in usage
        assert usage["test"]["hourly"] == Decimal("10.00")
        assert usage["test"]["daily"] == Decimal("10.00")


class TestEnforceCostLimitsDecorator:
    """Test the enforce_cost_limits decorator"""

    @pytest.mark.asyncio
    async def test_decorator_on_async_method(self):
        """Test decorator on async methods"""

        class TestClient:
            provider = "test"

            @enforce_cost_limits(priority=OperationPriority.NORMAL)
            async def test_method(self, operation="test_op"):
                return {"success": True}

            def calculate_cost(self, operation, **kwargs):
                return Decimal("0.01")

        client = TestClient()

        with patch("d0_gateway.middleware.cost_enforcement.cost_enforcement.check_and_enforce") as mock_check:
            mock_check.return_value = True

            result = await client.test_method()
            assert result == {"success": True}

            mock_check.assert_called_once()
            call_args = mock_check.call_args[1]
            assert call_args["provider"] == "test"
            assert call_args["operation"] == "test_method"
            assert call_args["priority"] == OperationPriority.NORMAL

    def test_decorator_on_sync_method(self):
        """Test decorator on sync methods"""

        class TestClient:
            provider = "test"

            @enforce_cost_limits(priority=OperationPriority.HIGH)
            def test_method(self, operation="test_op"):
                return {"success": True}

        client = TestClient()

        with patch("d0_gateway.middleware.cost_enforcement.cost_enforcement.check_and_enforce") as mock_check:
            # Return a simple boolean for sync methods
            mock_check.return_value = True

            result = client.test_method()
            assert result == {"success": True}

    @pytest.mark.asyncio
    async def test_decorator_blocks_on_failure(self):
        """Test decorator raises exception when enforcement fails"""
        from core.exceptions import ExternalAPIError

        class TestClient:
            provider = "test"

            @enforce_cost_limits()
            async def test_method(self):
                return {"success": True}

        client = TestClient()

        with patch("d0_gateway.middleware.cost_enforcement.cost_enforcement.check_and_enforce") as mock_check:
            mock_check.return_value = {"allowed": False, "reason": "rate_limit_exceeded", "retry_after": 60}

            with pytest.raises(ExternalAPIError) as exc_info:
                await client.test_method()

            assert "rate_limit_exceeded" in str(exc_info.value)
