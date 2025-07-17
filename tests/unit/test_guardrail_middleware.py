"""
Unit tests for cost guardrail middleware (P1-060)
"""
import asyncio
import time
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from d0_gateway.guardrail_middleware import (
    GuardrailBlocked,
    GuardrailContext,
    GuardrailException,
    RateLimiter,
    RateLimitExceeded,
    check_budget_available,
    enforce_cost_guardrails,
    get_remaining_budget,
)
from d0_gateway.guardrails import (
    CostLimit,
    GuardrailAction,
    GuardrailStatus,
    GuardrailViolation,
    LimitPeriod,
    LimitScope,
    RateLimitConfig,
)


class TestRateLimiter:
    """Test RateLimiter functionality"""

    def test_rate_limit_allows_within_limit(self):
        """Test that requests within rate limit are allowed"""
        limiter = RateLimiter()

        # Set up rate limit on the actual guardrail_manager
        from d0_gateway.guardrails import guardrail_manager

        original_limits = guardrail_manager._rate_limits.copy()
        try:
            guardrail_manager._rate_limits = {
                "openai:*": RateLimitConfig(provider="openai", requests_per_minute=60, burst_size=10, enabled=True)
            }

            # Initialize bucket with some tokens
            limiter._buckets["openai:*"]["tokens"] = 5
            limiter._buckets["openai:*"]["last_refill"] = time.time()

            # First request should be allowed
            allowed, retry_after = limiter.check_rate_limit("openai")
            assert allowed is True
            assert retry_after is None
        finally:
            # Restore original limits
            guardrail_manager._rate_limits = original_limits

    def test_rate_limit_blocks_over_limit(self):
        """Test that requests over rate limit are blocked"""
        limiter = RateLimiter()

        # Set up rate limit on the actual guardrail_manager
        from d0_gateway.guardrails import guardrail_manager

        original_limits = guardrail_manager._rate_limits.copy()
        try:
            guardrail_manager._rate_limits = {
                "openai:*": RateLimitConfig(
                    provider="openai", requests_per_minute=60, burst_size=1, enabled=True  # Very small burst
                )
            }

            # Consume all tokens
            limiter._buckets["openai:*"]["tokens"] = 0
            limiter._buckets["openai:*"]["last_refill"] = time.time()

            # Should be blocked
            allowed, retry_after = limiter.check_rate_limit("openai")
            assert allowed is False
            assert retry_after > 0
        finally:
            # Restore original limits
            guardrail_manager._rate_limits = original_limits

    def test_cost_rate_limit(self):
        """Test cost-based rate limiting"""
        limiter = RateLimiter()

        # Mock rate limit config with cost limits
        with patch("d0_gateway.guardrail_middleware.guardrail_manager") as mock_manager:
            mock_manager._rate_limits = {
                "openai:*": RateLimitConfig(
                    provider="openai",
                    requests_per_minute=60,
                    burst_size=10,
                    cost_per_minute=Decimal("1.00"),
                    cost_burst_size=Decimal("0.10"),
                    enabled=True,
                )
            }

            # Set up bucket with low cost tokens
            limiter._buckets["openai:*"]["cost_tokens"] = Decimal("0.05")
            limiter._buckets["openai:*"]["cost_last_refill"] = time.time()

            # Check with high cost operation
            allowed, retry_after = limiter.check_rate_limit("openai", cost=Decimal("0.10"))
            assert allowed is False
            assert retry_after > 0

    def test_consume_tokens(self):
        """Test token consumption"""
        limiter = RateLimiter()

        # Set up bucket
        limiter._buckets["openai:*"]["tokens"] = 5
        limiter._buckets["openai:*"]["cost_tokens"] = Decimal("1.00")

        # Consume tokens
        limiter.consume_tokens("openai", cost=Decimal("0.10"))

        assert limiter._buckets["openai:*"]["tokens"] == 4
        assert limiter._buckets["openai:*"]["cost_tokens"] == Decimal("0.90")


class TestEnforceCostGuardrails:
    """Test enforce_cost_guardrails decorator"""

    @pytest.mark.asyncio
    async def test_decorator_allows_operation(self):
        """Test decorator allows operation when within limits"""

        # Mock client class
        class MockClient:
            provider = "openai"

            def calculate_cost(self, operation, **kwargs):
                return Decimal("0.01")

            @enforce_cost_guardrails()
            async def test_method(self, operation="test"):
                return {"success": True}

        client = MockClient()

        with patch("d0_gateway.guardrail_middleware.guardrail_manager") as mock_manager:
            with patch("d0_gateway.guardrail_middleware.rate_limiter") as mock_rate_limiter:
                # Mock successful checks
                mock_rate_limiter.check_rate_limit.return_value = (True, None)
                mock_manager.enforce_limits.return_value = True

                result = await client.test_method()
                assert result == {"success": True}

                # Verify checks were made
                mock_rate_limiter.check_rate_limit.assert_called_once()
                mock_manager.enforce_limits.assert_called_once()

    @pytest.mark.asyncio
    async def test_decorator_blocks_operation(self):
        """Test decorator blocks operation when over limit"""

        # Mock client class
        class MockClient:
            provider = "openai"

            def calculate_cost(self, operation, **kwargs):
                return Decimal("10.00")

            @enforce_cost_guardrails()
            async def test_method(self, operation="test"):
                return {"success": True}

        client = MockClient()

        with patch("d0_gateway.guardrail_middleware.guardrail_manager") as mock_manager:
            with patch("d0_gateway.guardrail_middleware.rate_limiter") as mock_rate_limiter:
                # Mock rate limit OK but guardrail blocks
                mock_rate_limiter.check_rate_limit.return_value = (True, None)

                violation = GuardrailViolation(
                    limit_name="test_limit",
                    scope=LimitScope.GLOBAL,
                    severity="critical",
                    current_spend=Decimal("990.00"),
                    limit_amount=Decimal("1000.00"),
                    percentage_used=0.99,
                    action_taken=[GuardrailAction.BLOCK],
                )
                mock_manager.enforce_limits.return_value = violation

                with pytest.raises(GuardrailBlocked):
                    await client.test_method()

    @pytest.mark.asyncio
    async def test_decorator_handles_rate_limit(self):
        """Test decorator handles rate limit exceeded"""

        # Mock client class
        class MockClient:
            provider = "openai"

            @enforce_cost_guardrails()
            async def test_method(self, operation="test"):
                return {"success": True}

        client = MockClient()

        with patch("d0_gateway.guardrail_middleware.rate_limiter") as mock_rate_limiter:
            # Mock rate limit exceeded
            mock_rate_limiter.check_rate_limit.return_value = (False, 5.0)

            with pytest.raises(RateLimitExceeded) as exc_info:
                await client.test_method()

            assert "Retry after 5.0 seconds" in str(exc_info.value)

    def test_sync_decorator(self):
        """Test decorator works with sync methods"""

        # Mock client class
        class MockClient:
            provider = "dataaxle"

            def calculate_cost(self, operation, **kwargs):
                return Decimal("0.05")

            @enforce_cost_guardrails()
            def test_method(self, operation="match_business"):
                return {"success": True}

        client = MockClient()

        with patch("d0_gateway.guardrail_middleware.guardrail_manager") as mock_manager:
            with patch("d0_gateway.guardrail_middleware.rate_limiter") as mock_rate_limiter:
                # Mock successful checks
                mock_rate_limiter.check_rate_limit.return_value = (True, None)
                mock_manager.enforce_limits.return_value = True

                result = client.test_method()
                assert result == {"success": True}

    @pytest.mark.asyncio
    async def test_decorator_throttling(self):
        """Test decorator applies throttling"""

        # Mock client class
        class MockClient:
            provider = "openai"

            @enforce_cost_guardrails()
            async def test_method(self, operation="test"):
                return {"success": True}

        client = MockClient()

        with patch("d0_gateway.guardrail_middleware.guardrail_manager") as mock_manager:
            with patch("d0_gateway.guardrail_middleware.rate_limiter") as mock_rate_limiter:
                with patch("asyncio.sleep") as mock_sleep:
                    # Mock rate limit OK but guardrail throttles
                    mock_rate_limiter.check_rate_limit.return_value = (True, None)

                    violation = GuardrailViolation(
                        limit_name="test_limit",
                        scope=LimitScope.PROVIDER,
                        severity="warning",
                        current_spend=Decimal("80.00"),
                        limit_amount=Decimal("100.00"),
                        percentage_used=0.8,
                        action_taken=[GuardrailAction.THROTTLE],
                    )
                    mock_manager.enforce_limits.return_value = violation

                    result = await client.test_method()
                    assert result == {"success": True}

                    # Verify throttling delay was applied
                    mock_sleep.assert_called_once()
                    delay = mock_sleep.call_args[0][0]
                    assert 0 < delay <= 30  # Max 30s delay


class TestGuardrailContext:
    """Test GuardrailContext context manager"""

    def test_bypass_guardrails(self):
        """Test bypassing guardrails temporarily"""
        with patch("d0_gateway.guardrail_middleware.guardrail_manager") as mock_manager:
            # Set up mock limits
            limit1 = Mock(enabled=True, provider="openai")
            limit2 = Mock(enabled=True, provider="dataaxle")
            mock_manager._limits = {"limit1": limit1, "limit2": limit2}

            # Use context to bypass openai guardrails
            with GuardrailContext(provider="openai", bypass_guardrails=True):
                assert limit1.enabled is False
                assert limit2.enabled is True  # Not affected

            # Should be restored after context
            assert limit1.enabled is True
            assert limit2.enabled is True

    def test_temporary_limits(self):
        """Test applying temporary limit overrides"""
        with patch("d0_gateway.guardrail_middleware.guardrail_manager") as mock_manager:
            # Set up mock limit
            limit = Mock(limit_usd=Decimal("100.00"))
            mock_manager._limits = {"test_limit": limit}

            # Apply temporary limit
            with GuardrailContext(temporary_limits={"test_limit": Decimal("200.00")}):
                assert limit.limit_usd == Decimal("200.00")

            # Should be restored
            assert limit.limit_usd == Decimal("100.00")


class TestUtilityFunctions:
    """Test utility functions"""

    def test_check_budget_available(self):
        """Test check_budget_available function"""
        from datetime import datetime, timedelta

        with patch("d0_gateway.guardrail_middleware.guardrail_manager") as mock_manager:
            # Mock check_limits to return status
            status = GuardrailStatus(
                limit_name="test",
                current_spend=Decimal("50.00"),
                limit_amount=Decimal("100.00"),
                percentage_used=0.5,
                status="info",
                remaining_budget=Decimal("50.00"),
                period_start=datetime.utcnow(),
                period_end=datetime.utcnow() + timedelta(days=1),
                is_blocked=False,
                circuit_breaker_open=False,
            )
            mock_manager.check_limits.return_value = [status]

            # Should be available
            assert check_budget_available("openai", "test", Decimal("10.00")) is True

            # Test with blocked status
            status.is_blocked = True
            assert check_budget_available("openai", "test", Decimal("10.00")) is False

    def test_get_remaining_budget(self):
        """Test get_remaining_budget function"""
        with patch("d0_gateway.guardrail_middleware.guardrail_manager") as mock_manager:
            # Mock limits
            limit1 = Mock(
                scope=Mock(value="provider"), period=Mock(value="daily"), provider="openai", limit_usd=Decimal("100.00")
            )
            limit2 = Mock(
                scope=Mock(value="provider"),
                period=Mock(value="daily"),
                provider="dataaxle",
                limit_usd=Decimal("50.00"),
            )
            mock_manager._limits = {"openai_daily": limit1, "dataaxle_daily": limit2}

            # Mock get_current_spend
            def mock_get_spend(limit, provider, op, campaign):
                if provider == "openai":
                    return Decimal("30.00")
                return Decimal("10.00")

            mock_manager._get_current_spend = mock_get_spend

            # Get remaining budget
            remaining = get_remaining_budget(period="daily")

            assert remaining["openai"] == Decimal("70.00")  # 100 - 30
            assert remaining["dataaxle"] == Decimal("40.00")  # 50 - 10

    def test_get_remaining_budget_filtered(self):
        """Test get_remaining_budget with provider filter"""
        with patch("d0_gateway.guardrail_middleware.guardrail_manager") as mock_manager:
            # Mock limit
            limit = Mock(
                scope=Mock(value="provider"), period=Mock(value="daily"), provider="openai", limit_usd=Decimal("100.00")
            )
            mock_manager._limits = {"openai_daily": limit}
            mock_manager._get_current_spend.return_value = Decimal("25.00")

            # Get remaining budget for specific provider
            remaining = get_remaining_budget(provider="openai", period="daily")

            assert len(remaining) == 1
            assert remaining["openai"] == Decimal("75.00")
