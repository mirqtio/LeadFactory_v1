"""
Unit tests for cost guardrail system (P1-060)
"""
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, Mock, patch

import pytest

from d0_gateway.guardrails import (
    AlertSeverity,
    CostEstimate,
    CostLimit,
    GuardrailAction,
    GuardrailManager,
    GuardrailStatus,
    GuardrailViolation,
    LimitPeriod,
    LimitScope,
    RateLimitConfig,
)

# Mark entire module as unit test and critical - cost guardrails are essential for production
pytestmark = [pytest.mark.unit, pytest.mark.critical]


class TestCostLimit:
    """Test CostLimit model"""

    def test_create_cost_limit(self):
        """Test creating a cost limit"""
        limit = CostLimit(
            name="test_limit",
            scope=LimitScope.PROVIDER,
            period=LimitPeriod.DAILY,
            limit_usd=Decimal("100.00"),
            provider="openai",
            warning_threshold=0.8,
            critical_threshold=0.95,
        )

        assert limit.name == "test_limit"
        assert limit.scope == LimitScope.PROVIDER
        assert limit.period == LimitPeriod.DAILY
        assert limit.limit_usd == Decimal("100.00")
        assert limit.provider == "openai"
        assert limit.warning_threshold == 0.8
        assert limit.critical_threshold == 0.95
        assert limit.enabled is True

    def test_critical_threshold_validation(self):
        """Test that critical threshold must be >= warning threshold"""
        with pytest.raises(ValueError):
            CostLimit(
                name="invalid_limit",
                scope=LimitScope.GLOBAL,
                period=LimitPeriod.DAILY,
                limit_usd=Decimal("100.00"),
                warning_threshold=0.9,
                critical_threshold=0.8,  # Invalid: less than warning
            )


class TestGuardrailManager:
    """Test GuardrailManager functionality"""

    def test_default_limits_loaded(self):
        """Test that default limits are loaded on initialization"""
        manager = GuardrailManager()

        assert "global_daily" in manager._limits
        assert "openai_daily" in manager._limits
        assert "dataaxle_daily" in manager._limits
        assert "hunter_daily" in manager._limits

    def test_add_limit(self):
        """Test adding a new limit"""
        manager = GuardrailManager()

        limit = CostLimit(
            name="custom_limit",
            scope=LimitScope.CAMPAIGN,
            period=LimitPeriod.MONTHLY,
            limit_usd=Decimal("5000.00"),
            campaign_id=123,
        )

        manager.add_limit(limit)
        assert "custom_limit" in manager._limits
        assert manager._limits["custom_limit"] == limit

    def test_remove_limit(self):
        """Test removing a limit"""
        manager = GuardrailManager()

        # Add a limit first
        limit = CostLimit(
            name="temp_limit", scope=LimitScope.GLOBAL, period=LimitPeriod.DAILY, limit_usd=Decimal("100.00")
        )
        manager.add_limit(limit)

        # Remove it
        manager.remove_limit("temp_limit")
        assert "temp_limit" not in manager._limits

    def test_estimate_cost_fixed(self):
        """Test cost estimation for fixed-price operations"""
        manager = GuardrailManager()

        # Test known operation
        estimate = manager.estimate_cost("dataaxle", "match_business")
        assert estimate.provider == "dataaxle"
        assert estimate.operation == "match_business"
        assert estimate.estimated_cost == Decimal("0.10")
        assert estimate.confidence == 1.0
        assert estimate.based_on == "fixed"

        # Test unknown operation
        estimate = manager.estimate_cost("unknown", "unknown_op")
        assert estimate.estimated_cost == Decimal("0.00")

    def test_estimate_cost_openai(self):
        """Test cost estimation for OpenAI with tokens"""
        manager = GuardrailManager()

        estimate = manager.estimate_cost("openai", "analyze", estimated_tokens=1000)
        assert estimate.provider == "openai"
        assert estimate.operation == "analyze"
        assert estimate.estimated_cost == Decimal("0.001")
        assert estimate.confidence == 0.9
        assert estimate.based_on == "token_estimate"

    def test_limit_applies(self):
        """Test _limit_applies method"""
        manager = GuardrailManager()

        # Global limit applies to everything
        global_limit = CostLimit(
            name="global", scope=LimitScope.GLOBAL, period=LimitPeriod.DAILY, limit_usd=Decimal("1000.00")
        )
        assert manager._limit_applies(global_limit, "any", "any", None)

        # Provider limit
        provider_limit = CostLimit(
            name="provider",
            scope=LimitScope.PROVIDER,
            period=LimitPeriod.DAILY,
            limit_usd=Decimal("100.00"),
            provider="openai",
        )
        assert manager._limit_applies(provider_limit, "openai", "any", None)
        assert not manager._limit_applies(provider_limit, "dataaxle", "any", None)

        # Campaign limit
        campaign_limit = CostLimit(
            name="campaign",
            scope=LimitScope.CAMPAIGN,
            period=LimitPeriod.DAILY,
            limit_usd=Decimal("100.00"),
            campaign_id=123,
        )
        assert manager._limit_applies(campaign_limit, "any", "any", 123)
        assert not manager._limit_applies(campaign_limit, "any", "any", 456)

    @patch("d0_gateway.guardrails.get_db_sync")
    def test_get_current_spend(self, mock_get_db):
        """Test getting current spend from database"""
        manager = GuardrailManager()

        # Mock database session
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_db

        # Mock query result - need to mock the full chain
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = Decimal("50.00")

        limit = CostLimit(
            name="test",
            scope=LimitScope.PROVIDER,
            period=LimitPeriod.DAILY,
            limit_usd=Decimal("100.00"),
            provider="openai",
        )

        spend = manager._get_current_spend(limit, "openai", "test", None)
        assert spend == Decimal("50.00")

    def test_get_period_bounds(self):
        """Test period boundary calculation"""
        manager = GuardrailManager()

        # Test daily period
        start, end = manager._get_period_bounds(LimitPeriod.DAILY)
        assert start.date() == datetime.utcnow().date()
        assert end.date() == (datetime.utcnow() + timedelta(days=1)).date()
        assert start.hour == 0
        assert start.minute == 0

        # Test monthly period
        start, end = manager._get_period_bounds(LimitPeriod.MONTHLY)
        assert start.day == 1
        assert start.hour == 0

        # Test total period
        start, end = manager._get_period_bounds(LimitPeriod.TOTAL)
        assert start.year == 2020
        assert end.year == 2100

    @patch("d0_gateway.guardrails.get_db_sync")
    def test_check_limits(self, mock_get_db):
        """Test checking limits"""
        manager = GuardrailManager()

        # Mock database
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_db
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = Decimal("80.00")

        # Add a test limit
        limit = CostLimit(
            name="test_limit",
            scope=LimitScope.PROVIDER,
            period=LimitPeriod.DAILY,
            limit_usd=Decimal("100.00"),
            provider="openai",
            warning_threshold=0.8,
            critical_threshold=0.95,
        )
        manager.add_limit(limit)

        # Check limits
        statuses = manager.check_limits(provider="openai", operation="test", estimated_cost=Decimal("5.00"))

        assert len(statuses) >= 1
        status = next(s for s in statuses if s.limit_name == "test_limit")

        assert status.current_spend == Decimal("80.00")
        assert status.limit_amount == Decimal("100.00")
        assert status.percentage_used == 0.85  # (80+5)/100
        assert status.status == AlertSeverity.WARNING
        assert status.remaining_budget == Decimal("15.00")
        assert not status.is_blocked

    @patch("d0_gateway.guardrails.get_db_sync")
    def test_enforce_limits_allow(self, mock_get_db):
        """Test enforcing limits when operation is allowed"""
        manager = GuardrailManager()

        # Mock database - low spend
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_db
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = Decimal("20.00")

        result = manager.enforce_limits(provider="openai", operation="test", estimated_cost=Decimal("5.00"))

        assert result is True

    @patch("d0_gateway.guardrails.get_db_sync")
    def test_enforce_limits_block(self, mock_get_db):
        """Test enforcing limits when operation should be blocked"""
        manager = GuardrailManager()

        # Mock database - high spend
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_db
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = Decimal("995.00")

        # Add limit with BLOCK action
        limit = CostLimit(
            name="blocking_limit",
            scope=LimitScope.GLOBAL,
            period=LimitPeriod.DAILY,
            limit_usd=Decimal("1000.00"),
            actions=[GuardrailAction.LOG, GuardrailAction.ALERT, GuardrailAction.BLOCK],
        )
        manager.add_limit(limit)

        result = manager.enforce_limits(provider="openai", operation="test", estimated_cost=Decimal("10.00"))

        assert isinstance(result, GuardrailViolation)
        assert result.limit_name == "blocking_limit"
        assert GuardrailAction.BLOCK in result.action_taken
        assert result.percentage_used > 1.0

    def test_circuit_breaker_logic(self):
        """Test circuit breaker state management"""
        manager = GuardrailManager()

        # Initially no circuit breaker
        assert not manager._is_circuit_open("test_limit")

        # Update circuit breaker
        manager._update_circuit_breaker("test_limit", failure_threshold=3, recovery_timeout=60)
        assert manager._circuit_breakers["test_limit"]["failure_count"] == 1
        assert manager._circuit_breakers["test_limit"]["state"] == "closed"

        # Trigger more failures
        manager._update_circuit_breaker("test_limit", failure_threshold=3, recovery_timeout=60)
        manager._update_circuit_breaker("test_limit", failure_threshold=3, recovery_timeout=60)

        # Should now be open
        assert manager._circuit_breakers["test_limit"]["state"] == "open"
        assert manager._is_circuit_open("test_limit")

        # Test recovery timeout
        manager._circuit_breakers["test_limit"]["opened_at"] = datetime.utcnow() - timedelta(seconds=61)
        assert not manager._is_circuit_open("test_limit")  # Should be half-open now


class TestRateLimitConfig:
    """Test RateLimitConfig model"""

    def test_create_rate_limit(self):
        """Test creating a rate limit configuration"""
        rate_limit = RateLimitConfig(
            provider="openai",
            operation="chat",
            requests_per_minute=60,
            burst_size=10,
            cost_per_minute=Decimal("10.00"),
            cost_burst_size=Decimal("2.00"),
        )

        assert rate_limit.provider == "openai"
        assert rate_limit.operation == "chat"
        assert rate_limit.requests_per_minute == 60
        assert rate_limit.burst_size == 10
        assert rate_limit.cost_per_minute == Decimal("10.00")
        assert rate_limit.cost_burst_size == Decimal("2.00")
        assert rate_limit.enabled is True


class TestGuardrailStatus:
    """Test GuardrailStatus model"""

    def test_guardrail_status(self):
        """Test GuardrailStatus properties"""
        status = GuardrailStatus(
            limit_name="test_limit",
            current_spend=Decimal("90.00"),
            limit_amount=Decimal("100.00"),
            percentage_used=0.9,
            status=AlertSeverity.WARNING,
            remaining_budget=Decimal("10.00"),
            period_start=datetime.utcnow(),
            period_end=datetime.utcnow() + timedelta(days=1),
        )

        assert not status.is_over_limit

        # Test over limit
        status.percentage_used = 1.1
        assert status.is_over_limit


class TestGuardrailViolation:
    """Test GuardrailViolation model"""

    def test_create_violation(self):
        """Test creating a guardrail violation"""
        violation = GuardrailViolation(
            limit_name="test_limit",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.CRITICAL,
            current_spend=Decimal("95.00"),
            limit_amount=Decimal("100.00"),
            percentage_used=0.95,
            provider="openai",
            action_taken=[GuardrailAction.LOG, GuardrailAction.ALERT],
        )

        assert violation.limit_name == "test_limit"
        assert violation.scope == LimitScope.PROVIDER
        assert violation.severity == AlertSeverity.CRITICAL
        assert violation.current_spend == Decimal("95.00")
        assert violation.limit_amount == Decimal("100.00")
        assert violation.percentage_used == 0.95
        assert violation.provider == "openai"
        assert GuardrailAction.LOG in violation.action_taken
        assert GuardrailAction.ALERT in violation.action_taken
