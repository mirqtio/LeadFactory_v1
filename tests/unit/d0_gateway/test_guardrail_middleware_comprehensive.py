"""
Comprehensive unit tests for guardrail_middleware.py - Middleware and decorators for cost enforcement
Tests for RateLimiter, decorators, context managers, and utility functions
"""
import asyncio
import time
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from contextlib import contextmanager

from d0_gateway.guardrail_middleware import (
    GuardrailBlocked,
    GuardrailContext,
    GuardrailException,
    RateLimiter,
    RateLimitExceeded,
    check_budget_available,
    enforce_cost_guardrails,
    get_remaining_budget,
    rate_limiter,
)
from d0_gateway.guardrails import (
    AlertSeverity,
    GuardrailAction,
    GuardrailStatus,
    GuardrailViolation,
    LimitPeriod,
    LimitScope,
    RateLimitConfig,
)


@pytest.fixture(autouse=True)
def mock_db_session(monkeypatch, test_db):
    """Automatically mock all database sessions to use test SQLite fixture"""
    @contextmanager
    def mock_get_db_sync():
        yield test_db
    
    # Patch the database session function used by guardrails
    monkeypatch.setattr("d0_gateway.guardrails.get_db_sync", mock_get_db_sync)
    monkeypatch.setattr("database.session.get_db_sync", mock_get_db_sync)
    return test_db


class TestRateLimiter:
    """Test RateLimiter class functionality"""

    def setup_method(self):
        """Setup test fixtures"""
        self.rate_limiter = RateLimiter()

    def test_rate_limiter_initialization(self):
        """Test RateLimiter initialization"""
        limiter = RateLimiter()
        assert hasattr(limiter, "_buckets")
        assert isinstance(limiter._buckets, dict)

    def test_check_rate_limit_no_limit_configured(self):
        """Test rate limit check when no limit is configured"""
        with patch("d0_gateway.guardrail_middleware.guardrail_manager") as mock_manager:
            mock_manager._rate_limits = {}

            allowed, retry_after = self.rate_limiter.check_rate_limit("test_provider", "test_op")

            assert allowed is True
            assert retry_after is None

    def test_check_rate_limit_disabled_limit(self):
        """Test rate limit check when limit is disabled"""
        mock_rate_limit = Mock()
        mock_rate_limit.enabled = False

        with patch("d0_gateway.guardrail_middleware.guardrail_manager") as mock_manager:
            mock_manager._rate_limits = {"test_provider:test_op": mock_rate_limit}

            allowed, retry_after = self.rate_limiter.check_rate_limit("test_provider", "test_op")

            assert allowed is True
            assert retry_after is None

    def test_check_rate_limit_within_limits(self):
        """Test rate limit check when within limits"""
        mock_rate_limit = Mock()
        mock_rate_limit.enabled = True
        mock_rate_limit.requests_per_minute = 60
        mock_rate_limit.burst_size = 100
        mock_rate_limit.cost_per_minute = None

        with patch("d0_gateway.guardrail_middleware.guardrail_manager") as mock_manager:
            mock_manager._rate_limits = {"test_provider:test_op": mock_rate_limit}

            # First call should succeed (bucket starts with refill)
            allowed, retry_after = self.rate_limiter.check_rate_limit("test_provider", "test_op")

            assert allowed is True
            assert retry_after is None

    def test_check_rate_limit_request_rate_exceeded(self):
        """Test rate limit check when request rate is exceeded"""
        mock_rate_limit = Mock()
        mock_rate_limit.enabled = True
        mock_rate_limit.requests_per_minute = 1  # Very low limit
        mock_rate_limit.burst_size = 1
        mock_rate_limit.cost_per_minute = None

        with patch("d0_gateway.guardrail_middleware.guardrail_manager") as mock_manager:
            mock_manager._rate_limits = {"test_provider:test_op": mock_rate_limit}

            # Consume the token first
            self.rate_limiter.consume_tokens("test_provider", "test_op")

            # Second call should be rate limited
            allowed, retry_after = self.rate_limiter.check_rate_limit("test_provider", "test_op")

            assert allowed is False
            assert retry_after is not None
            assert retry_after > 0

    def test_check_rate_limit_cost_rate_exceeded(self):
        """Test rate limit check when cost rate is exceeded"""
        mock_rate_limit = Mock()
        mock_rate_limit.enabled = True
        mock_rate_limit.requests_per_minute = 60
        mock_rate_limit.burst_size = 100
        mock_rate_limit.cost_per_minute = 10.0
        mock_rate_limit.cost_burst_size = 20.0

        with patch("d0_gateway.guardrail_middleware.guardrail_manager") as mock_manager:
            mock_manager._rate_limits = {"test_provider:test_op": mock_rate_limit}

            # Large cost should exceed limit
            allowed, retry_after = self.rate_limiter.check_rate_limit("test_provider", "test_op", cost=Decimal("25.0"))

            assert allowed is False
            assert retry_after is not None
            assert retry_after > 0

    def test_check_rate_limit_with_cost_within_limits(self):
        """Test rate limit check with cost within limits"""
        mock_rate_limit = Mock()
        mock_rate_limit.enabled = True
        mock_rate_limit.requests_per_minute = 60
        mock_rate_limit.burst_size = 100
        mock_rate_limit.cost_per_minute = 100.0
        mock_rate_limit.cost_burst_size = 200.0

        with patch("d0_gateway.guardrail_middleware.guardrail_manager") as mock_manager:
            mock_manager._rate_limits = {"test_provider:test_op": mock_rate_limit}

            allowed, retry_after = self.rate_limiter.check_rate_limit("test_provider", "test_op", cost=Decimal("10.0"))

            assert allowed is True
            assert retry_after is None

    def test_check_rate_limit_default_cost_burst_size(self):
        """Test rate limit check with default cost burst size"""
        mock_rate_limit = Mock()
        mock_rate_limit.enabled = True
        mock_rate_limit.requests_per_minute = 60
        mock_rate_limit.burst_size = 100
        mock_rate_limit.cost_per_minute = 10.0
        mock_rate_limit.cost_burst_size = None  # Should default to 2x cost_per_minute

        with patch("d0_gateway.guardrail_middleware.guardrail_manager") as mock_manager:
            mock_manager._rate_limits = {"test_provider:test_op": mock_rate_limit}

            # Should use default burst size of 20.0 (2 * 10.0)
            allowed, retry_after = self.rate_limiter.check_rate_limit("test_provider", "test_op", cost=Decimal("15.0"))

            assert allowed is True

    def test_consume_tokens(self):
        """Test token consumption"""
        # Initialize bucket with tokens
        self.rate_limiter._buckets["test:op"] = {
            "tokens": 10,
            "last_refill": time.time(),
            "cost_tokens": Decimal("50.0"),
            "cost_last_refill": time.time(),
        }

        self.rate_limiter.consume_tokens("test", "op", Decimal("5.0"))

        bucket = self.rate_limiter._buckets["test:op"]
        assert bucket["tokens"] == 9
        assert bucket["cost_tokens"] == Decimal("45.0")

    def test_consume_tokens_no_cost(self):
        """Test token consumption without cost"""
        self.rate_limiter._buckets["test:op"] = {
            "tokens": 10,
            "last_refill": time.time(),
            "cost_tokens": Decimal("50.0"),
            "cost_last_refill": time.time(),
        }

        self.rate_limiter.consume_tokens("test", "op")

        bucket = self.rate_limiter._buckets["test:op"]
        assert bucket["tokens"] == 9
        assert bucket["cost_tokens"] == Decimal("50.0")  # Unchanged

    def test_rate_limiter_token_refill(self):
        """Test token bucket refill logic"""
        mock_rate_limit = Mock()
        mock_rate_limit.enabled = True
        mock_rate_limit.requests_per_minute = 60
        mock_rate_limit.burst_size = 100
        mock_rate_limit.cost_per_minute = None

        with patch("d0_gateway.guardrail_middleware.guardrail_manager") as mock_manager:
            mock_manager._rate_limits = {"test:op": mock_rate_limit}

            # Set up bucket with depleted tokens but old timestamp
            old_time = time.time() - 60  # 1 minute ago
            self.rate_limiter._buckets["test:op"] = {
                "tokens": 0,
                "last_refill": old_time,
                "cost_tokens": Decimal("0"),
                "cost_last_refill": old_time,
            }

            # Should refill tokens based on time passed
            allowed, retry_after = self.rate_limiter.check_rate_limit("test", "op")

            assert allowed is True
            bucket = self.rate_limiter._buckets["test:op"]
            assert bucket["tokens"] > 0


class TestEnforceCostGuardrailsDecorator:
    """Test enforce_cost_guardrails decorator"""

    def test_decorator_async_function_success(self, test_db):
        """Test decorator on async function with successful execution"""

        @enforce_cost_guardrails()
        async def test_async_method(self, operation="test_op"):
            return "success"

        # Mock client
        mock_client = Mock()
        mock_client.provider = "test_provider"

        with patch("d0_gateway.guardrail_middleware.rate_limiter") as mock_rate_limiter, patch(
            "d0_gateway.guardrail_middleware.guardrail_manager"
        ) as mock_manager:
            mock_rate_limiter.check_rate_limit.return_value = (True, None)
            mock_manager.enforce_limits.return_value = True
            mock_rate_limiter.consume_tokens.return_value = None

            async def run_test():
                result = await test_async_method(mock_client)
                return result

            result = asyncio.run(run_test())
            assert result == "success"

            # Verify enforce_limits was called with correct parameters
            call_args = mock_manager.enforce_limits.call_args
            assert call_args[1]["provider"] == "test_provider"
            assert call_args[1]["operation"] == "operation"  # Uses operation_field default

    def test_decorator_sync_function_success(self, test_db):
        """Test decorator on sync function with successful execution"""

        @enforce_cost_guardrails()
        def test_sync_method(self, operation="test_op"):
            return "success"

        # Mock client
        mock_client = Mock()
        mock_client.provider = "test_provider"

        with patch("d0_gateway.guardrail_middleware.rate_limiter") as mock_rate_limiter, patch(
            "d0_gateway.guardrail_middleware.guardrail_manager"
        ) as mock_manager:
            mock_rate_limiter.check_rate_limit.return_value = (True, None)
            mock_manager.enforce_limits.return_value = True
            mock_rate_limiter.consume_tokens.return_value = None

            result = test_sync_method(mock_client)
            assert result == "success"

    def test_decorator_no_provider_error(self, test_db):
        """Test decorator when no provider is found"""

        @enforce_cost_guardrails()
        async def test_method(self, operation="test_op"):
            return "success"

        mock_client = Mock()
        # No provider attribute or parameter

        with patch("d0_gateway.guardrail_middleware.logger") as mock_logger:

            async def run_test():
                result = await test_method(mock_client)
                return result

            result = asyncio.run(run_test())
            assert result == "success"
            mock_logger.error.assert_called_once()

    def test_decorator_rate_limit_exceeded(self, test_db):
        """Test decorator when rate limit is exceeded"""

        @enforce_cost_guardrails()
        async def test_method(self, operation="test_op"):
            return "success"

        mock_client = Mock()
        mock_client.provider = "test_provider"

        with patch("d0_gateway.guardrail_middleware.rate_limiter") as mock_rate_limiter:
            mock_rate_limiter.check_rate_limit.return_value = (False, 30.0)

            async def run_test():
                with pytest.raises(RateLimitExceeded) as exc_info:
                    await test_method(mock_client)
                return exc_info.value

            exc = asyncio.run(run_test())
            assert "Rate limit exceeded" in str(exc)
            assert "30.0 seconds" in str(exc)

    def test_decorator_guardrail_blocked(self, test_db):
        """Test decorator when guardrail blocks operation"""

        @enforce_cost_guardrails()
        async def test_method(self, operation="test_op"):
            return "success"

        mock_client = Mock()
        mock_client.provider = "test_provider"

        violation = GuardrailViolation(
            limit_name="test_limit",
            provider="test_provider",
            operation="test_op",
            scope="provider",
            severity=AlertSeverity.CRITICAL,
            current_spend=Decimal("1100.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=1.1,
            action_taken=[GuardrailAction.BLOCK],
        )

        with patch("d0_gateway.guardrail_middleware.rate_limiter") as mock_rate_limiter, patch(
            "d0_gateway.guardrail_middleware.guardrail_manager"
        ) as mock_manager:
            mock_rate_limiter.check_rate_limit.return_value = (True, None)
            mock_manager.enforce_limits.return_value = violation

            async def run_test():
                with pytest.raises(GuardrailBlocked) as exc_info:
                    await test_method(mock_client)
                return exc_info.value

            exc = asyncio.run(run_test())
            assert "Operation blocked by guardrail" in str(exc)
            assert "test_limit" in str(exc)

    @pytest.mark.asyncio
    async def test_decorator_guardrail_throttle(self, test_db):
        """Test decorator when guardrail throttles operation"""

        @enforce_cost_guardrails()
        async def test_method(self, operation="test_op"):
            return "success"

        mock_client = Mock()
        mock_client.provider = "test_provider"

        violation = GuardrailViolation(
            limit_name="test_limit",
            provider="test_provider",
            operation="test_op",
            scope="provider",
            severity=AlertSeverity.WARNING,
            current_spend=Decimal("900.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=0.9,
            action_taken=[GuardrailAction.THROTTLE],
        )

        with patch("d0_gateway.guardrail_middleware.rate_limiter") as mock_rate_limiter, patch(
            "d0_gateway.guardrail_middleware.guardrail_manager"
        ) as mock_manager, patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            mock_rate_limiter.check_rate_limit.return_value = (True, None)
            mock_manager.enforce_limits.return_value = violation
            mock_rate_limiter.consume_tokens.return_value = None

            result = await test_method(mock_client)
            assert result == "success"
            mock_sleep.assert_called_once()
            # Should throttle for 9 seconds (0.9 * 10)
            assert mock_sleep.call_args[0][0] == 9.0

    def test_decorator_sync_guardrail_throttle(self, test_db):
        """Test decorator sync version when guardrail throttles operation"""

        @enforce_cost_guardrails()
        def test_method(self, operation="test_op"):
            return "success"

        mock_client = Mock()
        mock_client.provider = "test_provider"

        violation = GuardrailViolation(
            limit_name="test_limit",
            provider="test_provider",
            operation="test_op",
            scope="provider",
            severity=AlertSeverity.WARNING,
            current_spend=Decimal("800.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=0.8,
            action_taken=[GuardrailAction.THROTTLE],
        )

        with patch("d0_gateway.guardrail_middleware.rate_limiter") as mock_rate_limiter, patch(
            "d0_gateway.guardrail_middleware.guardrail_manager"
        ) as mock_manager, patch("time.sleep") as mock_sleep:
            mock_rate_limiter.check_rate_limit.return_value = (True, None)
            mock_manager.enforce_limits.return_value = violation
            mock_rate_limiter.consume_tokens.return_value = None

            result = test_method(mock_client)
            assert result == "success"
            mock_sleep.assert_called_once_with(8.0)  # 0.8 * 10

    def test_decorator_cost_estimation_with_calculate_cost(self, test_db):
        """Test decorator cost estimation using client's calculate_cost method"""

        @enforce_cost_guardrails(estimate_cost=True)
        async def test_method(self, operation="test_op"):
            return "success"

        mock_client = Mock()
        mock_client.provider = "test_provider"
        mock_client.calculate_cost.return_value = 5.50

        with patch("d0_gateway.guardrail_middleware.rate_limiter") as mock_rate_limiter, patch(
            "d0_gateway.guardrail_middleware.guardrail_manager"
        ) as mock_manager:
            mock_rate_limiter.check_rate_limit.return_value = (True, None)
            mock_manager.enforce_limits.return_value = True
            mock_rate_limiter.consume_tokens.return_value = None

            async def run_test():
                result = await test_method(mock_client)
                return result

            result = asyncio.run(run_test())
            assert result == "success"
            mock_client.calculate_cost.assert_called_once_with("operation")
            # Verify cost estimation was passed to enforce_limits
            call_args = mock_manager.enforce_limits.call_args
            assert call_args[1]["estimated_cost"] == Decimal("5.50")

    def test_decorator_cost_estimation_with_guardrail_manager(self, test_db):
        """Test decorator cost estimation using guardrail manager"""

        @enforce_cost_guardrails(estimate_cost=True)
        async def test_method(self, operation="test_op"):
            return "success"

        mock_client = Mock(spec=["provider"])  # Only allow 'provider' attribute
        mock_client.provider = "test_provider"
        # No calculate_cost method by spec

        mock_estimate = Mock()
        mock_estimate.estimated_cost = Decimal("3.25")

        with patch("d0_gateway.guardrail_middleware.rate_limiter") as mock_rate_limiter, patch(
            "d0_gateway.guardrail_middleware.guardrail_manager"
        ) as mock_manager:
            mock_rate_limiter.check_rate_limit.return_value = (True, None)

            # Ensure the mock estimate_cost method is properly configured
            def mock_estimate_cost(*args, **kwargs):
                return mock_estimate

            mock_manager.estimate_cost.side_effect = mock_estimate_cost
            mock_manager.enforce_limits.return_value = True
            mock_rate_limiter.consume_tokens.return_value = None

            async def run_test():
                result = await test_method(mock_client)
                return result

            result = asyncio.run(run_test())
            assert result == "success"
            mock_manager.estimate_cost.assert_called_once()
            # Verify cost estimation was passed to enforce_limits
            call_args = mock_manager.enforce_limits.call_args
            assert call_args[1]["estimated_cost"] == Decimal("3.25")

    def test_decorator_cost_estimation_failure(self, test_db):
        """Test decorator handles cost estimation failures gracefully"""

        @enforce_cost_guardrails(estimate_cost=True)
        async def test_method(self, operation="test_op"):
            return "success"

        mock_client = Mock()
        mock_client.provider = "test_provider"
        mock_client.calculate_cost.side_effect = Exception("Cost calculation failed")

        with patch("d0_gateway.guardrail_middleware.rate_limiter") as mock_rate_limiter, patch(
            "d0_gateway.guardrail_middleware.guardrail_manager"
        ) as mock_manager, patch("d0_gateway.guardrail_middleware.logger") as mock_logger:
            mock_rate_limiter.check_rate_limit.return_value = (True, None)
            mock_manager.enforce_limits.return_value = True
            mock_rate_limiter.consume_tokens.return_value = None

            async def run_test():
                result = await test_method(mock_client)
                return result

            result = asyncio.run(run_test())
            assert result == "success"
            mock_logger.warning.assert_called_once()
            # Should use zero cost on estimation failure
            call_args = mock_manager.enforce_limits.call_args
            assert call_args[1]["estimated_cost"] == Decimal("0.00")

    @pytest.mark.asyncio
    async def test_decorator_circuit_breaker_update_on_failure(self, test_db):
        """Test decorator updates circuit breaker on fast failures"""

        @enforce_cost_guardrails()
        async def test_method(self, operation="test_op"):
            raise Exception("API call failed")

        mock_client = Mock()
        mock_client.provider = "test_provider"

        mock_limit = Mock()
        mock_limit.circuit_breaker_enabled = True
        mock_limit.provider = "test_provider"
        mock_limit.name = "test_limit"
        mock_limit.circuit_breaker_failure_threshold = 5
        mock_limit.circuit_breaker_recovery_timeout = 300

        with patch("d0_gateway.guardrail_middleware.rate_limiter") as mock_rate_limiter, patch(
            "d0_gateway.guardrail_middleware.guardrail_manager"
        ) as mock_manager, patch("time.time") as mock_time:
            mock_rate_limiter.check_rate_limit.return_value = (True, None)
            mock_manager.enforce_limits.return_value = True
            mock_rate_limiter.consume_tokens.return_value = None
            mock_manager._limits.values.return_value = [mock_limit]

            # Mock fast failure (< 1 second) - provide enough values for all time.time() calls
            mock_time.side_effect = [1000, 1000, 1000.5]  # 0.5 second elapsed

            with pytest.raises(Exception, match="API call failed"):
                await test_method(mock_client)

            # Verify circuit breaker was updated
            mock_manager._update_circuit_breaker.assert_called_once_with("test_limit", 5, 300)

    def test_decorator_custom_field_names(self, test_db):
        """Test decorator with custom field names"""

        @enforce_cost_guardrails(
            provider_field="custom_provider", operation_field="custom_operation", campaign_field="custom_campaign"
        )
        def test_method(self, custom_operation="test_op", custom_campaign=123):
            return "success"

        mock_client = Mock()
        mock_client.custom_provider = "custom_provider"

        with patch("d0_gateway.guardrail_middleware.rate_limiter") as mock_rate_limiter, patch(
            "d0_gateway.guardrail_middleware.guardrail_manager"
        ) as mock_manager:
            mock_rate_limiter.check_rate_limit.return_value = (True, None)
            mock_manager.enforce_limits.return_value = True
            mock_rate_limiter.consume_tokens.return_value = None

            result = test_method(mock_client, custom_campaign=123)
            assert result == "success"

            # Verify correct fields were used
            call_args = mock_manager.enforce_limits.call_args
            assert call_args[1]["provider"] == "custom_provider"
            assert call_args[1]["operation"] == "custom_operation"  # Uses field name as default
            assert call_args[1]["campaign_id"] == 123


class TestGuardrailContext:
    """Test GuardrailContext context manager"""

    def test_context_manager_bypass_guardrails(self, test_db):
        """Test context manager bypassing guardrails"""
        mock_limit1 = Mock()
        mock_limit1.enabled = True
        mock_limit1.provider = "test_provider"

        mock_limit2 = Mock()
        mock_limit2.enabled = True
        mock_limit2.provider = "other_provider"

        with patch("d0_gateway.guardrail_middleware.guardrail_manager") as mock_manager:
            mock_manager._limits = {"limit1": mock_limit1, "limit2": mock_limit2}

            with GuardrailContext(provider="test_provider", bypass_guardrails=True):
                # Only test_provider limits should be disabled
                assert mock_limit1.enabled is False
                assert mock_limit2.enabled is True

            # Should be restored after context
            assert mock_limit1.enabled is True
            assert mock_limit2.enabled is True

    def test_context_manager_bypass_all_guardrails(self, test_db):
        """Test context manager bypassing all guardrails"""
        mock_limit1 = Mock()
        mock_limit1.enabled = True
        mock_limit1.provider = "provider1"

        mock_limit2 = Mock()
        mock_limit2.enabled = True
        mock_limit2.provider = "provider2"

        with patch("d0_gateway.guardrail_middleware.guardrail_manager") as mock_manager:
            mock_manager._limits = {"limit1": mock_limit1, "limit2": mock_limit2}

            with GuardrailContext(bypass_guardrails=True):
                # All limits should be disabled
                assert mock_limit1.enabled is False
                assert mock_limit2.enabled is False

            # Should be restored after context
            assert mock_limit1.enabled is True
            assert mock_limit2.enabled is True

    def test_context_manager_temporary_limits(self, test_db):
        """Test context manager with temporary limit overrides"""
        mock_limit = Mock()
        mock_limit.limit_usd = Decimal("1000.0")

        with patch("d0_gateway.guardrail_middleware.guardrail_manager") as mock_manager:
            mock_manager._limits = {"test_limit": mock_limit}

            with GuardrailContext(temporary_limits={"test_limit": Decimal("2000.0")}):
                assert mock_limit.limit_usd == Decimal("2000.0")

            # Should be restored after context
            assert mock_limit.limit_usd == Decimal("1000.0")

    def test_context_manager_nonexistent_limit(self, test_db):
        """Test context manager with nonexistent limit name"""
        with patch("d0_gateway.guardrail_middleware.guardrail_manager") as mock_manager:
            mock_manager._limits = {}

            # Should not raise error even if limit doesn't exist
            with GuardrailContext(temporary_limits={"nonexistent_limit": Decimal("1000.0")}):
                pass

    def test_context_manager_exception_in_context(self, test_db):
        """Test context manager properly restores state even if exception occurs"""
        mock_limit = Mock()
        mock_limit.enabled = True
        mock_limit.provider = "test_provider"
        mock_limit.limit_usd = Decimal("1000.0")

        with patch("d0_gateway.guardrail_middleware.guardrail_manager") as mock_manager:
            mock_manager._limits = {"test_limit": mock_limit}

            try:
                with GuardrailContext(
                    provider="test_provider",
                    bypass_guardrails=True,
                    temporary_limits={"test_limit": Decimal("2000.0")},
                ):
                    raise ValueError("Test exception")
            except ValueError:
                pass

            # Should be restored even after exception
            assert mock_limit.enabled is True
            assert mock_limit.limit_usd == Decimal("1000.0")


class TestCustomExceptions:
    """Test custom exception classes"""

    def test_guardrail_exception_base(self):
        """Test GuardrailException base class"""
        exc = GuardrailException("Test message")
        assert str(exc) == "Test message"
        assert isinstance(exc, Exception)

    def test_guardrail_blocked_exception(self):
        """Test GuardrailBlocked exception"""
        exc = GuardrailBlocked("Operation blocked")
        assert str(exc) == "Operation blocked"
        assert isinstance(exc, GuardrailException)
        assert isinstance(exc, Exception)

    def test_rate_limit_exceeded_exception(self):
        """Test RateLimitExceeded exception"""
        exc = RateLimitExceeded("Rate limit exceeded")
        assert str(exc) == "Rate limit exceeded"
        assert isinstance(exc, GuardrailException)
        assert isinstance(exc, Exception)


class TestUtilityFunctions:
    """Test utility functions"""

    def test_check_budget_available_success(self, test_db):
        """Test check_budget_available when budget is available"""
        mock_status = Mock()
        mock_status.is_blocked = False
        mock_status.circuit_breaker_open = False

        with patch("d0_gateway.guardrail_middleware.guardrail_manager") as mock_manager:
            mock_manager.check_limits.return_value = [mock_status]

            result = check_budget_available("test_provider", "test_operation", 10.0, campaign_id=123)

            assert result is True
            mock_manager.check_limits.assert_called_once_with(
                provider="test_provider",
                operation="test_operation",
                estimated_cost=Decimal("10.0"),
                campaign_id=123,
            )

    def test_check_budget_available_blocked(self, test_db):
        """Test check_budget_available when budget is blocked"""
        mock_status = Mock()
        mock_status.is_blocked = True
        mock_status.circuit_breaker_open = False

        with patch("d0_gateway.guardrail_middleware.guardrail_manager") as mock_manager:
            mock_manager.check_limits.return_value = [mock_status]

            result = check_budget_available("test_provider", "test_operation", 10.0)

            assert result is False

    def test_check_budget_available_circuit_breaker_open(self, test_db):
        """Test check_budget_available when circuit breaker is open"""
        mock_status = Mock()
        mock_status.is_blocked = False
        mock_status.circuit_breaker_open = True

        with patch("d0_gateway.guardrail_middleware.guardrail_manager") as mock_manager:
            mock_manager.check_limits.return_value = [mock_status]

            result = check_budget_available("test_provider", "test_operation", 10.0)

            assert result is False

    def test_check_budget_available_decimal_input(self, test_db):
        """Test check_budget_available with Decimal input"""
        mock_status = Mock()
        mock_status.is_blocked = False
        mock_status.circuit_breaker_open = False

        with patch("d0_gateway.guardrail_middleware.guardrail_manager") as mock_manager:
            mock_manager.check_limits.return_value = [mock_status]

            result = check_budget_available("test_provider", "test_operation", Decimal("15.50"))

            assert result is True
            call_args = mock_manager.check_limits.call_args
            assert call_args[1]["estimated_cost"] == Decimal("15.50")

    def test_get_remaining_budget_provider_limits(self, test_db):
        """Test get_remaining_budget for provider limits"""
        mock_limit1 = Mock()
        mock_limit1.period.value = "daily"
        mock_limit1.scope.value = "provider"
        mock_limit1.provider = "provider1"
        mock_limit1.limit_usd = Decimal("1000.0")

        mock_limit2 = Mock()
        mock_limit2.period.value = "daily"
        mock_limit2.scope.value = "provider"
        mock_limit2.provider = "provider2"
        mock_limit2.limit_usd = Decimal("500.0")

        mock_limit3 = Mock()
        mock_limit3.period.value = "monthly"  # Different period
        mock_limit3.scope.value = "provider"
        mock_limit3.provider = "provider3"
        mock_limit3.limit_usd = Decimal("2000.0")

        with patch("d0_gateway.guardrail_middleware.guardrail_manager") as mock_manager:
            mock_manager._limits.values.return_value = [mock_limit1, mock_limit2, mock_limit3]
            mock_manager._get_current_spend.side_effect = [
                Decimal("600.0"),  # provider1 spent
                Decimal("200.0"),  # provider2 spent
            ]

            result = get_remaining_budget(period="daily")

            assert len(result) == 2
            assert result["provider1"] == Decimal("400.0")  # 1000 - 600
            assert result["provider2"] == Decimal("300.0")  # 500 - 200

    def test_get_remaining_budget_specific_provider(self, test_db):
        """Test get_remaining_budget for specific provider"""
        mock_limit1 = Mock()
        mock_limit1.period.value = "daily"
        mock_limit1.scope.value = "provider"
        mock_limit1.provider = "target_provider"
        mock_limit1.limit_usd = Decimal("1000.0")

        mock_limit2 = Mock()
        mock_limit2.period.value = "daily"
        mock_limit2.scope.value = "provider"
        mock_limit2.provider = "other_provider"
        mock_limit2.limit_usd = Decimal("500.0")

        with patch("d0_gateway.guardrail_middleware.guardrail_manager") as mock_manager:
            mock_manager._limits.values.return_value = [mock_limit1, mock_limit2]
            mock_manager._get_current_spend.return_value = Decimal("300.0")

            result = get_remaining_budget(provider="target_provider", period="daily")

            assert len(result) == 1
            assert result["target_provider"] == Decimal("700.0")  # 1000 - 300

    def test_get_remaining_budget_overspent(self, test_db):
        """Test get_remaining_budget when provider has overspent"""
        mock_limit = Mock()
        mock_limit.period.value = "daily"
        mock_limit.scope.value = "provider"
        mock_limit.provider = "overspent_provider"
        mock_limit.limit_usd = Decimal("100.0")

        with patch("d0_gateway.guardrail_middleware.guardrail_manager") as mock_manager:
            mock_manager._limits.values.return_value = [mock_limit]
            mock_manager._get_current_spend.return_value = Decimal("150.0")  # Over limit

            result = get_remaining_budget(provider="overspent_provider", period="daily")

            assert result["overspent_provider"] == Decimal("0")  # Should not go negative

    def test_get_remaining_budget_no_matching_limits(self, test_db):
        """Test get_remaining_budget when no limits match criteria"""
        mock_limit = Mock()
        mock_limit.period.value = "monthly"  # Different period
        mock_limit.scope.value = "provider"
        mock_limit.provider = "test_provider"

        with patch("d0_gateway.guardrail_middleware.guardrail_manager") as mock_manager:
            mock_manager._limits.values.return_value = [mock_limit]

            result = get_remaining_budget(period="daily")

            assert result == {}

    def test_get_remaining_budget_global_scope_excluded(self, test_db):
        """Test get_remaining_budget excludes global scope limits"""
        mock_limit = Mock()
        mock_limit.period.value = "daily"
        mock_limit.scope.value = "global"  # Global scope should be excluded
        mock_limit.provider = None

        with patch("d0_gateway.guardrail_middleware.guardrail_manager") as mock_manager:
            mock_manager._limits.values.return_value = [mock_limit]

            result = get_remaining_budget(period="daily")

            assert result == {}


class TestModuleGlobals:
    """Test module-level globals and imports"""

    def test_global_rate_limiter_instance(self):
        """Test that global rate_limiter instance exists"""
        from d0_gateway.guardrail_middleware import rate_limiter as global_limiter

        assert isinstance(global_limiter, RateLimiter)

    def test_rate_limiter_singleton_behavior(self):
        """Test that module always returns same rate limiter instance"""
        from d0_gateway.guardrail_middleware import rate_limiter as limiter1
        from d0_gateway.guardrail_middleware import rate_limiter as limiter2

        assert limiter1 is limiter2

    def test_logger_initialization(self):
        """Test that logger is properly initialized"""
        from d0_gateway.guardrail_middleware import logger

        assert logger is not None
        assert hasattr(logger, "info")
        assert hasattr(logger, "error")
        assert hasattr(logger, "warning")


class TestMiddlewareIntegration:
    """Integration tests for middleware components"""

    @pytest.mark.asyncio
    async def test_complete_middleware_workflow(self, test_db):
        """Test complete middleware workflow from decorator to execution"""

        @enforce_cost_guardrails(estimate_cost=True, record_cost=True)
        async def api_call(self, operation="search", campaign_id=123):
            return {"status": "success", "data": "test_result"}

        # Mock API client
        mock_client = Mock()
        mock_client.provider = "test_provider"
        mock_client.calculate_cost.return_value = 5.75
        mock_client.emit_cost = Mock()

        with patch("d0_gateway.guardrail_middleware.rate_limiter") as mock_rate_limiter, patch(
            "d0_gateway.guardrail_middleware.guardrail_manager"
        ) as mock_manager:
            # Setup successful path
            mock_rate_limiter.check_rate_limit.return_value = (True, None)
            mock_manager.enforce_limits.return_value = True
            mock_rate_limiter.consume_tokens.return_value = None

            result = await api_call(mock_client, campaign_id=123)

            assert result["status"] == "success"
            assert result["data"] == "test_result"

            # Verify all middleware steps were called
            mock_rate_limiter.check_rate_limit.assert_called_once()
            mock_client.calculate_cost.assert_called_once()
            mock_manager.enforce_limits.assert_called_once()
            mock_rate_limiter.consume_tokens.assert_called_once()

    def test_middleware_with_context_override(self, test_db):
        """Test middleware behavior with context override"""

        @enforce_cost_guardrails()
        def api_call(self, operation="search"):
            return "success"

        mock_client = Mock()
        mock_client.provider = "test_provider"

        mock_limit = Mock()
        mock_limit.enabled = True
        mock_limit.provider = "test_provider"

        with patch("d0_gateway.guardrail_middleware.guardrail_manager") as mock_manager:
            # Set up the mock to properly handle the _limits attribute iteration
            limits_dict = {"test_limit": mock_limit}
            mock_manager._limits = limits_dict

            # First call should check guardrails
            with patch("d0_gateway.guardrail_middleware.rate_limiter") as mock_rate_limiter:
                mock_rate_limiter.check_rate_limit.return_value = (True, None)
                mock_manager.enforce_limits.return_value = True

                # Call with context bypass
                with GuardrailContext(provider="test_provider", bypass_guardrails=True):
                    # Check that the limit was disabled within the context
                    assert (
                        mock_limit.enabled is False
                    ), f"Expected mock_limit.enabled to be False, got {mock_limit.enabled}"
                    result = api_call(mock_client)

                assert result == "success"

            # After context, guardrails should be restored
            assert mock_limit.enabled is True
