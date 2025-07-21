"""
Comprehensive unit tests for guardrails.py - Cost guardrail system
Tests for models, guardrail manager, limit checking, and enforcement
"""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

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
    guardrail_manager,
)


class TestGuardrailModels:
    """Test Pydantic models"""

    def test_cost_limit_creation(self):
        """Test CostLimit model creation"""
        limit = CostLimit(
            name="test_limit",
            scope=LimitScope.PROVIDER,
            period=LimitPeriod.DAILY,
            limit_usd=Decimal("1000.0"),
            provider="dataaxle",
            campaign_id=123,
            operation="search",
            warning_threshold=0.8,
            critical_threshold=0.95,
            actions=[GuardrailAction.LOG, GuardrailAction.ALERT],
            circuit_breaker_enabled=True,
            circuit_breaker_failure_threshold=3,
            circuit_breaker_recovery_timeout=600,
        )

        assert limit.name == "test_limit"
        assert limit.scope == LimitScope.PROVIDER
        assert limit.period == LimitPeriod.DAILY
        assert limit.limit_usd == Decimal("1000.0")
        assert limit.provider == "dataaxle"
        assert limit.campaign_id == 123
        assert limit.operation == "search"
        assert limit.warning_threshold == 0.8
        assert limit.critical_threshold == 0.95
        assert GuardrailAction.LOG in limit.actions
        assert GuardrailAction.ALERT in limit.actions
        assert limit.circuit_breaker_enabled is True
        assert limit.circuit_breaker_failure_threshold == 3
        assert limit.circuit_breaker_recovery_timeout == 600
        assert limit.enabled is True
        assert isinstance(limit.created_at, datetime)
        assert isinstance(limit.updated_at, datetime)

    def test_cost_limit_validation_errors(self):
        """Test CostLimit validation errors"""
        # Test negative limit
        with pytest.raises(ValueError):
            CostLimit(
                name="test",
                scope=LimitScope.GLOBAL,
                period=LimitPeriod.DAILY,
                limit_usd=Decimal("-100.0"),
            )

        # Test critical threshold less than warning
        with pytest.raises(ValueError):
            CostLimit(
                name="test",
                scope=LimitScope.GLOBAL,
                period=LimitPeriod.DAILY,
                limit_usd=Decimal("1000.0"),
                warning_threshold=0.9,
                critical_threshold=0.8,  # Less than warning
            )

    def test_cost_limit_defaults(self):
        """Test CostLimit default values"""
        limit = CostLimit(
            name="test",
            scope=LimitScope.GLOBAL,
            period=LimitPeriod.DAILY,
            limit_usd=Decimal("1000.0"),
        )

        assert limit.warning_threshold == 0.8
        assert limit.critical_threshold == 0.95
        assert limit.actions == [GuardrailAction.LOG, GuardrailAction.ALERT]
        assert limit.circuit_breaker_enabled is False
        assert limit.circuit_breaker_failure_threshold == 5
        assert limit.circuit_breaker_recovery_timeout == 300
        assert limit.enabled is True

    def test_rate_limit_config_creation(self):
        """Test RateLimitConfig model creation"""
        rate_limit = RateLimitConfig(
            provider="openai",
            operation="chat_completion",
            requests_per_minute=60,
            burst_size=100,
            cost_per_minute=Decimal("50.0"),
            cost_burst_size=Decimal("75.0"),
            enabled=True,
        )

        assert rate_limit.provider == "openai"
        assert rate_limit.operation == "chat_completion"
        assert rate_limit.requests_per_minute == 60
        assert rate_limit.burst_size == 100
        assert rate_limit.cost_per_minute == Decimal("50.0")
        assert rate_limit.cost_burst_size == Decimal("75.0")
        assert rate_limit.enabled is True

    def test_rate_limit_config_defaults(self):
        """Test RateLimitConfig default values"""
        rate_limit = RateLimitConfig(
            provider="test",
            requests_per_minute=10,
            burst_size=20,
        )

        assert rate_limit.operation is None
        assert rate_limit.cost_per_minute is None
        assert rate_limit.cost_burst_size is None
        assert rate_limit.enabled is True

    def test_guardrail_status_creation(self):
        """Test GuardrailStatus model creation"""
        status = GuardrailStatus(
            limit_name="test_limit",
            current_spend=Decimal("800.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=0.8,
            status=AlertSeverity.WARNING,
            remaining_budget=Decimal("200.0"),
            period_start=datetime(2025, 1, 1),
            period_end=datetime(2025, 1, 2),
            is_blocked=False,
            circuit_breaker_open=False,
        )

        assert status.limit_name == "test_limit"
        assert status.current_spend == Decimal("800.0")
        assert status.limit_amount == Decimal("1000.0")
        assert status.percentage_used == 0.8
        assert status.status == AlertSeverity.WARNING
        assert status.remaining_budget == Decimal("200.0")
        assert status.is_blocked is False
        assert status.circuit_breaker_open is False
        assert status.is_over_limit is False  # Property test

    def test_guardrail_status_is_over_limit(self):
        """Test GuardrailStatus is_over_limit property"""
        # Under limit
        status = GuardrailStatus(
            limit_name="test",
            current_spend=Decimal("800.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=0.8,
            status=AlertSeverity.WARNING,
            remaining_budget=Decimal("200.0"),
            period_start=datetime.utcnow(),
            period_end=datetime.utcnow() + timedelta(days=1),
        )
        assert status.is_over_limit is False

        # Over limit
        status.percentage_used = 1.1
        assert status.is_over_limit is True

        # Exactly at limit
        status.percentage_used = 1.0
        assert status.is_over_limit is True

    def test_guardrail_violation_creation(self):
        """Test GuardrailViolation model creation"""
        violation = GuardrailViolation(
            limit_name="test_limit",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.CRITICAL,
            current_spend=Decimal("950.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=0.95,
            provider="dataaxle",
            campaign_id=123,
            operation="search",
            lead_id=456,
            action_taken=[GuardrailAction.ALERT, GuardrailAction.BLOCK],
            metadata={"test": "data"},
        )

        assert violation.limit_name == "test_limit"
        assert violation.scope == LimitScope.PROVIDER
        assert violation.severity == AlertSeverity.CRITICAL
        assert violation.current_spend == Decimal("950.0")
        assert violation.limit_amount == Decimal("1000.0")
        assert violation.percentage_used == 0.95
        assert violation.provider == "dataaxle"
        assert violation.campaign_id == 123
        assert violation.operation == "search"
        assert violation.lead_id == 456
        assert GuardrailAction.ALERT in violation.action_taken
        assert GuardrailAction.BLOCK in violation.action_taken
        assert violation.metadata == {"test": "data"}
        assert isinstance(violation.timestamp, datetime)

    def test_guardrail_violation_defaults(self):
        """Test GuardrailViolation default values"""
        violation = GuardrailViolation(
            limit_name="test",
            scope=LimitScope.GLOBAL,
            severity=AlertSeverity.WARNING,
            current_spend=Decimal("800.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=0.8,
            action_taken=[GuardrailAction.LOG],
        )

        assert violation.provider is None
        assert violation.campaign_id is None
        assert violation.operation is None
        assert violation.lead_id is None
        assert violation.metadata == {}

    def test_cost_estimate_creation(self):
        """Test CostEstimate model creation"""
        estimate = CostEstimate(
            provider="openai",
            operation="analyze",
            estimated_cost=Decimal("0.05"),
            confidence=0.9,
            based_on="token_estimate",
            metadata={"tokens": 1000},
        )

        assert estimate.provider == "openai"
        assert estimate.operation == "analyze"
        assert estimate.estimated_cost == Decimal("0.05")
        assert estimate.confidence == 0.9
        assert estimate.based_on == "token_estimate"
        assert estimate.metadata == {"tokens": 1000}

    def test_cost_estimate_defaults(self):
        """Test CostEstimate default values"""
        estimate = CostEstimate(
            provider="test",
            operation="test_op",
            estimated_cost=Decimal("1.0"),
        )

        assert estimate.confidence == 1.0
        assert estimate.based_on == "fixed"
        assert estimate.metadata == {}


class TestGuardrailManager:
    """Test GuardrailManager class"""

    def test_manager_initialization(self):
        """Test GuardrailManager initialization"""
        with patch("core.config.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                guardrail_global_daily_limit=1000.0,
                guardrail_global_monthly_limit=30000.0,
                guardrail_warning_threshold=0.8,
                guardrail_critical_threshold=0.95,
                guardrail_enable_circuit_breaker=True,
                guardrail_provider_daily_limits={"dataaxle": 500.0, "openai": 100.0},
            )

            manager = GuardrailManager()

            assert isinstance(manager._limits, dict)
            assert isinstance(manager._rate_limits, dict)
            assert isinstance(manager._circuit_breakers, dict)
            assert len(manager._limits) >= 5  # Should have default limits (at least global, provider, per-lead)

    def test_add_limit(self):
        """Test adding a cost limit"""
        manager = GuardrailManager()

        limit = CostLimit(
            name="test_add",
            scope=LimitScope.PROVIDER,
            period=LimitPeriod.DAILY,
            limit_usd=Decimal("500.0"),
            provider="test_provider",
        )

        with patch.object(manager.logger, "info") as mock_info:
            manager.add_limit(limit)

            assert "test_add" in manager._limits
            assert manager._limits["test_add"] == limit
            mock_info.assert_called_once()

    def test_remove_limit(self):
        """Test removing a cost limit"""
        manager = GuardrailManager()

        # Add a limit first
        limit = CostLimit(
            name="test_remove",
            scope=LimitScope.GLOBAL,
            period=LimitPeriod.DAILY,
            limit_usd=Decimal("1000.0"),
        )
        manager.add_limit(limit)

        # Remove it
        with patch.object(manager.logger, "info") as mock_info:
            manager.remove_limit("test_remove")

            assert "test_remove" not in manager._limits
            mock_info.assert_called_once()

        # Try to remove non-existent limit
        with patch.object(manager.logger, "info") as mock_info:
            manager.remove_limit("nonexistent")
            mock_info.assert_not_called()

    def test_add_rate_limit(self):
        """Test adding a rate limit"""
        manager = GuardrailManager()

        rate_limit = RateLimitConfig(
            provider="test_provider",
            operation="test_op",
            requests_per_minute=100,
            burst_size=150,
        )

        with patch.object(manager.logger, "info") as mock_info:
            manager.add_rate_limit(rate_limit)

            key = "test_provider:test_op"
            assert key in manager._rate_limits
            assert manager._rate_limits[key] == rate_limit
            mock_info.assert_called_once()

    def test_add_rate_limit_no_operation(self):
        """Test adding a rate limit without operation"""
        manager = GuardrailManager()

        rate_limit = RateLimitConfig(
            provider="test_provider",
            requests_per_minute=100,
            burst_size=150,
        )

        manager.add_rate_limit(rate_limit)

        key = "test_provider:*"
        assert key in manager._rate_limits

    def test_estimate_cost_fixed_costs(self):
        """Test cost estimation with fixed costs"""
        manager = GuardrailManager()

        # Test known fixed cost
        estimate = manager.estimate_cost("dataaxle", "match_business")
        assert estimate.provider == "dataaxle"
        assert estimate.operation == "match_business"
        assert estimate.estimated_cost == Decimal("0.10")
        assert estimate.confidence == 1.0
        assert estimate.based_on == "fixed"

        # Test unknown operation
        estimate = manager.estimate_cost("unknown", "unknown_op")
        assert estimate.estimated_cost == Decimal("0.00")
        assert estimate.confidence == 1.0
        assert estimate.based_on == "fixed"

    def test_estimate_cost_openai_tokens(self):
        """Test cost estimation for OpenAI with tokens"""
        manager = GuardrailManager()

        estimate = manager.estimate_cost("openai", "analyze", estimated_tokens=1000)
        assert estimate.provider == "openai"
        assert estimate.operation == "analyze"
        assert estimate.estimated_cost == Decimal("0.001")  # 1000 * 0.000001
        assert estimate.confidence == 0.9
        assert estimate.based_on == "token_estimate"
        assert estimate.metadata == {"estimated_tokens": 1000}

    def test_limit_applies_global(self):
        """Test _limit_applies for global scope"""
        manager = GuardrailManager()

        limit = CostLimit(
            name="global_test",
            scope=LimitScope.GLOBAL,
            period=LimitPeriod.DAILY,
            limit_usd=Decimal("1000.0"),
        )

        # Global limits apply to everything
        assert manager._limit_applies(limit, "any_provider", "any_op", None, None) is True
        assert manager._limit_applies(limit, "dataaxle", "search", 123, 456) is True

    def test_limit_applies_provider(self):
        """Test _limit_applies for provider scope"""
        manager = GuardrailManager()

        limit = CostLimit(
            name="provider_test",
            scope=LimitScope.PROVIDER,
            period=LimitPeriod.DAILY,
            limit_usd=Decimal("1000.0"),
            provider="dataaxle",
        )

        # Only applies to matching provider
        assert manager._limit_applies(limit, "dataaxle", "any_op", None, None) is True
        assert manager._limit_applies(limit, "openai", "any_op", None, None) is False

    def test_limit_applies_campaign(self):
        """Test _limit_applies for campaign scope"""
        manager = GuardrailManager()

        limit = CostLimit(
            name="campaign_test",
            scope=LimitScope.CAMPAIGN,
            period=LimitPeriod.DAILY,
            limit_usd=Decimal("1000.0"),
            campaign_id=123,
        )

        # Only applies to matching campaign
        assert manager._limit_applies(limit, "any_provider", "any_op", 123, None) is True
        assert manager._limit_applies(limit, "any_provider", "any_op", 456, None) is False

    def test_limit_applies_operation(self):
        """Test _limit_applies for operation scope"""
        manager = GuardrailManager()

        limit = CostLimit(
            name="operation_test",
            scope=LimitScope.OPERATION,
            period=LimitPeriod.DAILY,
            limit_usd=Decimal("1000.0"),
            operation="search",
        )

        # Only applies to matching operation
        assert manager._limit_applies(limit, "any_provider", "search", None, None) is True
        assert manager._limit_applies(limit, "any_provider", "analyze", None, None) is False

    def test_limit_applies_provider_operation(self):
        """Test _limit_applies for provider_operation scope"""
        manager = GuardrailManager()

        limit = CostLimit(
            name="provider_op_test",
            scope=LimitScope.PROVIDER_OPERATION,
            period=LimitPeriod.DAILY,
            limit_usd=Decimal("1000.0"),
            provider="dataaxle",
            operation="search",
        )

        # Only applies to matching provider AND operation
        assert manager._limit_applies(limit, "dataaxle", "search", None, None) is True
        assert manager._limit_applies(limit, "dataaxle", "analyze", None, None) is False
        assert manager._limit_applies(limit, "openai", "search", None, None) is False

    def test_limit_applies_per_lead(self):
        """Test _limit_applies for per_lead scope"""
        manager = GuardrailManager()

        limit = CostLimit(
            name="per_lead_test",
            scope=LimitScope.PER_LEAD,
            period=LimitPeriod.TOTAL,
            limit_usd=Decimal("2.50"),
        )

        # Only applies when lead_id is provided
        assert manager._limit_applies(limit, "any_provider", "any_op", None, 123) is True
        assert manager._limit_applies(limit, "any_provider", "any_op", None, None) is False

    def test_get_period_bounds_hourly(self):
        """Test _get_period_bounds for hourly period"""
        manager = GuardrailManager()

        with patch("d0_gateway.guardrails.datetime") as mock_datetime:
            mock_now = datetime(2025, 1, 15, 14, 30, 45)
            mock_datetime.utcnow.return_value = mock_now

            start, end = manager._get_period_bounds(LimitPeriod.HOURLY)

            assert start == datetime(2025, 1, 15, 14, 0, 0)
            assert end == datetime(2025, 1, 15, 15, 0, 0)

    def test_get_period_bounds_daily(self):
        """Test _get_period_bounds for daily period"""
        manager = GuardrailManager()

        with patch("d0_gateway.guardrails.datetime") as mock_datetime:
            mock_now = datetime(2025, 1, 15, 14, 30, 45)
            mock_datetime.utcnow.return_value = mock_now

            start, end = manager._get_period_bounds(LimitPeriod.DAILY)

            assert start == datetime(2025, 1, 15, 0, 0, 0)
            assert end == datetime(2025, 1, 16, 0, 0, 0)

    def test_get_period_bounds_weekly(self):
        """Test _get_period_bounds for weekly period"""
        manager = GuardrailManager()

        with patch("d0_gateway.guardrails.datetime") as mock_datetime:
            # Wednesday (weekday = 2)
            mock_now = datetime(2025, 1, 15, 14, 30, 45)
            mock_datetime.utcnow.return_value = mock_now

            start, end = manager._get_period_bounds(LimitPeriod.WEEKLY)

            # Should start on Monday (2 days earlier)
            assert start == datetime(2025, 1, 13, 0, 0, 0)
            assert end == datetime(2025, 1, 20, 0, 0, 0)

    def test_get_period_bounds_monthly(self):
        """Test _get_period_bounds for monthly period"""
        manager = GuardrailManager()

        with patch("d0_gateway.guardrails.datetime") as mock_datetime:
            mock_now = datetime(2025, 1, 15, 14, 30, 45)
            mock_datetime.utcnow.return_value = mock_now

            start, end = manager._get_period_bounds(LimitPeriod.MONTHLY)

            assert start == datetime(2025, 1, 1, 0, 0, 0)
            assert end == datetime(2025, 2, 1, 0, 0, 0)

    def test_get_period_bounds_monthly_december(self):
        """Test _get_period_bounds for monthly period in December"""
        manager = GuardrailManager()

        with patch("d0_gateway.guardrails.datetime") as mock_datetime:
            mock_now = datetime(2025, 12, 15, 14, 30, 45)
            mock_datetime.utcnow.return_value = mock_now

            start, end = manager._get_period_bounds(LimitPeriod.MONTHLY)

            assert start == datetime(2025, 12, 1, 0, 0, 0)
            assert end == datetime(2026, 1, 1, 0, 0, 0)

    def test_get_period_bounds_total(self):
        """Test _get_period_bounds for total period"""
        manager = GuardrailManager()

        start, end = manager._get_period_bounds(LimitPeriod.TOTAL)

        assert start == datetime(2020, 1, 1)
        assert end == datetime(2100, 1, 1)

    def test_is_circuit_open_no_breaker(self):
        """Test _is_circuit_open when no circuit breaker exists"""
        manager = GuardrailManager()

        assert manager._is_circuit_open("nonexistent") is False

    def test_is_circuit_open_closed_state(self):
        """Test _is_circuit_open when circuit is closed"""
        manager = GuardrailManager()

        manager._circuit_breakers["test"] = {
            "state": "closed",
            "failure_count": 0,
            "opened_at": None,
            "recovery_timeout": 300,
        }

        assert manager._is_circuit_open("test") is False

    def test_is_circuit_open_open_state(self):
        """Test _is_circuit_open when circuit is open"""
        manager = GuardrailManager()

        manager._circuit_breakers["test"] = {
            "state": "open",
            "failure_count": 5,
            "opened_at": datetime.utcnow() - timedelta(seconds=100),  # Recent
            "recovery_timeout": 300,
        }

        assert manager._is_circuit_open("test") is True

    def test_is_circuit_open_recovery_timeout(self):
        """Test _is_circuit_open when recovery timeout has passed"""
        manager = GuardrailManager()

        manager._circuit_breakers["test"] = {
            "state": "open",
            "failure_count": 5,
            "opened_at": datetime.utcnow() - timedelta(seconds=400),  # Old
            "recovery_timeout": 300,
        }

        # Should transition to half_open
        assert manager._is_circuit_open("test") is False
        assert manager._circuit_breakers["test"]["state"] == "half_open"
        assert manager._circuit_breakers["test"]["failure_count"] == 0

    def test_update_circuit_breaker_new(self):
        """Test _update_circuit_breaker creating new breaker that reaches threshold"""
        manager = GuardrailManager()

        with patch.object(manager.logger, "error") as mock_error:
            # Call multiple times to reach threshold
            manager._update_circuit_breaker("new_breaker", 3, 300)
            manager._update_circuit_breaker("new_breaker", 3, 300)
            manager._update_circuit_breaker("new_breaker", 3, 300)

            assert "new_breaker" in manager._circuit_breakers
            breaker = manager._circuit_breakers["new_breaker"]
            assert breaker["state"] == "open"
            assert breaker["failure_count"] == 3  # Reached threshold
            assert isinstance(breaker["opened_at"], datetime)
            assert breaker["recovery_timeout"] == 300
            mock_error.assert_called_once()

    def test_update_circuit_breaker_existing(self):
        """Test _update_circuit_breaker with existing breaker"""
        manager = GuardrailManager()

        # Create existing breaker
        manager._circuit_breakers["existing"] = {
            "state": "closed",
            "failure_count": 1,
            "opened_at": None,
            "recovery_timeout": 300,
        }

        with patch.object(manager.logger, "error") as mock_error:
            manager._update_circuit_breaker("existing", 3, 300)

            breaker = manager._circuit_breakers["existing"]
            assert breaker["failure_count"] == 2  # Incremented
            mock_error.assert_not_called()  # Not opened yet

    def test_update_circuit_breaker_threshold_reached(self):
        """Test _update_circuit_breaker when threshold is reached"""
        manager = GuardrailManager()

        # Create existing breaker near threshold
        manager._circuit_breakers["threshold"] = {
            "state": "closed",
            "failure_count": 2,
            "opened_at": None,
            "recovery_timeout": 300,
        }

        with patch.object(manager.logger, "error") as mock_error:
            manager._update_circuit_breaker("threshold", 3, 300)

            breaker = manager._circuit_breakers["threshold"]
            assert breaker["state"] == "open"
            assert breaker["failure_count"] == 3
            assert isinstance(breaker["opened_at"], datetime)
            mock_error.assert_called_once()

    def test_get_current_spend_daily_aggregate(self):
        """Test _get_current_spend using daily aggregates"""
        manager = GuardrailManager()

        limit = CostLimit(
            name="daily_test",
            scope=LimitScope.PROVIDER,
            period=LimitPeriod.DAILY,
            limit_usd=Decimal("1000.0"),
            provider="dataaxle",
        )

        mock_db = MagicMock()

        with (
            patch("d0_gateway.guardrails.get_db_sync") as mock_get_db,
            patch("d0_gateway.guardrails.datetime") as mock_datetime,
            patch.object(manager, "_get_daily_spend_from_aggregate", return_value=Decimal("500.0")) as mock_aggregate,
        ):
            mock_get_db.return_value.__enter__.return_value = mock_db
            mock_now = datetime(2025, 1, 15, 14, 30, 45)
            mock_datetime.utcnow.return_value = mock_now

            result = manager._get_current_spend(limit, "dataaxle", "search", None, None)

            assert result == Decimal("500.0")
            mock_aggregate.assert_called_once()

    def test_get_current_spend_raw_data(self):
        """Test _get_current_spend using raw data"""
        manager = GuardrailManager()

        limit = CostLimit(
            name="hourly_test",
            scope=LimitScope.PROVIDER,
            period=LimitPeriod.HOURLY,  # Forces raw data
            limit_usd=Decimal("100.0"),
            provider="dataaxle",
        )

        mock_db = MagicMock()

        with (
            patch("d0_gateway.guardrails.get_db_sync") as mock_get_db,
            patch.object(manager, "_get_spend_from_raw", return_value=Decimal("50.0")) as mock_raw,
        ):
            mock_get_db.return_value.__enter__.return_value = mock_db

            result = manager._get_current_spend(limit, "dataaxle", "search", None, None)

            assert result == Decimal("50.0")
            mock_raw.assert_called_once()

    def test_get_current_spend_per_lead(self):
        """Test _get_current_spend for per-lead limits"""
        manager = GuardrailManager()

        limit = CostLimit(
            name="per_lead_test",
            scope=LimitScope.PER_LEAD,
            period=LimitPeriod.DAILY,
            limit_usd=Decimal("2.50"),
        )

        mock_db = MagicMock()

        with (
            patch("d0_gateway.guardrails.get_db_sync") as mock_get_db,
            patch.object(manager, "_get_spend_from_raw", return_value=Decimal("1.50")) as mock_raw,
        ):
            mock_get_db.return_value.__enter__.return_value = mock_db

            result = manager._get_current_spend(limit, "dataaxle", "search", None, 123)

            assert result == Decimal("1.50")
            mock_raw.assert_called_once()

    def test_handle_violation_logging(self):
        """Test _handle_violation logging"""
        manager = GuardrailManager()

        violation = GuardrailViolation(
            limit_name="test_limit",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.WARNING,
            current_spend=Decimal("850.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=0.85,
            action_taken=[GuardrailAction.LOG],
        )

        limit = CostLimit(
            name="test_limit",
            scope=LimitScope.PROVIDER,
            period=LimitPeriod.DAILY,
            limit_usd=Decimal("1000.0"),
            circuit_breaker_enabled=False,
        )

        with (
            patch.object(manager.logger, "warning") as mock_warning,
            patch("d0_gateway.guardrail_alerts.send_cost_alert", new_callable=AsyncMock) as mock_send_alert,
        ):
            manager._handle_violation(violation, limit)

            mock_warning.assert_called_once()
            assert "Guardrail violation" in mock_warning.call_args[0][0]

    def test_handle_violation_circuit_breaker(self):
        """Test _handle_violation with circuit breaker"""
        manager = GuardrailManager()

        violation = GuardrailViolation(
            limit_name="circuit_test",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.EMERGENCY,
            current_spend=Decimal("1100.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=1.1,
            action_taken=[GuardrailAction.BLOCK],
        )

        limit = CostLimit(
            name="circuit_test",
            scope=LimitScope.PROVIDER,
            period=LimitPeriod.DAILY,
            limit_usd=Decimal("1000.0"),
            circuit_breaker_enabled=True,
            circuit_breaker_failure_threshold=3,
            circuit_breaker_recovery_timeout=300,
        )

        with (
            patch.object(manager, "_update_circuit_breaker") as mock_update,
            patch("d0_gateway.guardrail_alerts.send_cost_alert", new_callable=AsyncMock) as mock_send_alert,
        ):
            manager._handle_violation(violation, limit)

            mock_update.assert_called_once_with("circuit_test", 3, 300)

    def test_handle_violation_async_alert_running_loop(self):
        """Test _handle_violation with running async loop"""
        manager = GuardrailManager()

        violation = GuardrailViolation(
            limit_name="async_test",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.WARNING,
            current_spend=Decimal("800.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=0.8,
            action_taken=[GuardrailAction.ALERT],
        )

        limit = CostLimit(
            name="async_test",
            scope=LimitScope.PROVIDER,
            period=LimitPeriod.DAILY,
            limit_usd=Decimal("1000.0"),
            circuit_breaker_enabled=False,
        )

        with (
            patch("d0_gateway.guardrail_alerts.send_cost_alert", new_callable=AsyncMock) as mock_send_alert,
            patch("asyncio.get_event_loop") as mock_get_loop,
            patch("asyncio.create_task") as mock_create_task,
        ):
            mock_loop = MagicMock()
            mock_loop.is_running.return_value = True
            mock_get_loop.return_value = mock_loop

            manager._handle_violation(violation, limit)

            mock_create_task.assert_called_once()

    def test_handle_violation_async_alert_exception(self):
        """Test _handle_violation with async exception"""
        manager = GuardrailManager()

        violation = GuardrailViolation(
            limit_name="exception_test",
            scope=LimitScope.PROVIDER,
            severity=AlertSeverity.WARNING,
            current_spend=Decimal("800.0"),
            limit_amount=Decimal("1000.0"),
            percentage_used=0.8,
            action_taken=[GuardrailAction.ALERT],
        )

        limit = CostLimit(
            name="exception_test",
            scope=LimitScope.PROVIDER,
            period=LimitPeriod.DAILY,
            limit_usd=Decimal("1000.0"),
            circuit_breaker_enabled=False,
        )

        with (
            patch("d0_gateway.guardrail_alerts.send_cost_alert", new_callable=AsyncMock) as mock_send_alert,
            patch("asyncio.get_event_loop", side_effect=RuntimeError("No event loop")),
            patch.object(manager.logger, "warning") as mock_warning,
        ):
            manager._handle_violation(violation, limit)

            # Should have logged the fallback warning
            assert mock_warning.call_count >= 1
            fallback_calls = [call for call in mock_warning.call_args_list if "Could not send async alert" in str(call)]
            assert len(fallback_calls) == 1


class TestGuardrailManagerIntegration:
    """Integration tests for GuardrailManager"""

    def test_check_limits_basic(self):
        """Test check_limits basic functionality"""
        manager = GuardrailManager()

        # Add a test limit
        limit = CostLimit(
            name="integration_test",
            scope=LimitScope.PROVIDER,
            period=LimitPeriod.DAILY,
            limit_usd=Decimal("1000.0"),
            provider="dataaxle",
            warning_threshold=0.8,
            critical_threshold=0.95,
        )
        manager.add_limit(limit)

        with patch.object(manager, "_get_current_spend", return_value=Decimal("800.0")):
            statuses = manager.check_limits("dataaxle", "search", Decimal("50.0"))

            # Should find the matching limit
            matching_statuses = [s for s in statuses if s.limit_name == "integration_test"]
            assert len(matching_statuses) == 1

            status = matching_statuses[0]
            assert status.current_spend == Decimal("800.0")
            assert status.limit_amount == Decimal("1000.0")
            assert status.percentage_used == 0.85  # (800 + 50) / 1000
            assert status.status == AlertSeverity.WARNING  # > 0.8 threshold

    def test_check_limits_over_limit(self):
        """Test check_limits when over limit"""
        manager = GuardrailManager()

        limit = CostLimit(
            name="over_limit_test",
            scope=LimitScope.GLOBAL,
            period=LimitPeriod.DAILY,
            limit_usd=Decimal("1000.0"),
        )
        manager.add_limit(limit)

        with patch.object(manager, "_get_current_spend", return_value=Decimal("950.0")):
            statuses = manager.check_limits("any", "any", Decimal("100.0"))

            matching_statuses = [s for s in statuses if s.limit_name == "over_limit_test"]
            assert len(matching_statuses) == 1

            status = matching_statuses[0]
            assert status.percentage_used == 1.05  # (950 + 100) / 1000
            assert status.status == AlertSeverity.EMERGENCY  # >= 1.0

    def test_enforce_limits_allowed(self):
        """Test enforce_limits when operation is allowed"""
        manager = GuardrailManager()

        limit = CostLimit(
            name="enforce_allowed",
            scope=LimitScope.PROVIDER,
            period=LimitPeriod.DAILY,
            limit_usd=Decimal("1000.0"),
            provider="dataaxle",
            actions=[GuardrailAction.LOG],
        )
        manager.add_limit(limit)

        with patch.object(manager, "_get_current_spend", return_value=Decimal("500.0")):
            result = manager.enforce_limits("dataaxle", "search", Decimal("50.0"))

            assert result is True

    def test_enforce_limits_blocked(self):
        """Test enforce_limits when operation is blocked"""
        manager = GuardrailManager()

        limit = CostLimit(
            name="enforce_blocked",
            scope=LimitScope.PROVIDER,
            period=LimitPeriod.DAILY,
            limit_usd=Decimal("1000.0"),
            provider="dataaxle",
            actions=[GuardrailAction.BLOCK],
        )
        manager.add_limit(limit)

        with (
            patch.object(manager, "_get_current_spend", return_value=Decimal("950.0")),
            patch.object(manager, "_handle_violation") as mock_handle,
        ):
            result = manager.enforce_limits("dataaxle", "search", Decimal("100.0"))

            assert isinstance(result, GuardrailViolation)
            assert result.limit_name == "enforce_blocked"
            assert GuardrailAction.BLOCK in result.action_taken
            mock_handle.assert_called_once()

    def test_enforce_limits_circuit_breaker_blocked(self):
        """Test enforce_limits blocked by circuit breaker"""
        manager = GuardrailManager()

        limit = CostLimit(
            name="circuit_blocked",
            scope=LimitScope.PROVIDER,
            period=LimitPeriod.DAILY,
            limit_usd=Decimal("1000.0"),
            provider="dataaxle",
            circuit_breaker_enabled=True,
        )
        manager.add_limit(limit)

        # Set up open circuit breaker
        manager._circuit_breakers["circuit_blocked"] = {
            "state": "open",
            "failure_count": 5,
            "opened_at": datetime.utcnow() - timedelta(seconds=100),
            "recovery_timeout": 300,
        }

        with (
            patch.object(manager, "_get_current_spend", return_value=Decimal("500.0")),
            patch.object(manager, "_handle_violation") as mock_handle,
        ):
            result = manager.enforce_limits("dataaxle", "search", Decimal("50.0"))

            assert isinstance(result, GuardrailViolation)
            assert result.metadata["circuit_breaker_open"] is True
            mock_handle.assert_called_once()

    def test_enforce_limits_alert_only(self):
        """Test enforce_limits with alert-only violation"""
        # Create a fresh manager without default limits
        with patch("core.config.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                guardrail_global_daily_limit=10000.0,  # High limit to avoid triggering
                guardrail_global_monthly_limit=100000.0,  # High limit to avoid triggering
                guardrail_warning_threshold=0.99,  # High threshold to avoid triggering
                guardrail_critical_threshold=0.999,  # High threshold to avoid triggering
                guardrail_enable_circuit_breaker=False,
                guardrail_provider_daily_limits={},  # No provider limits
            )

            manager = GuardrailManager()

        limit = CostLimit(
            name="alert_only",
            scope=LimitScope.PROVIDER,
            period=LimitPeriod.DAILY,
            limit_usd=Decimal("1000.0"),
            provider="dataaxle",
            actions=[GuardrailAction.ALERT],
            warning_threshold=0.8,
        )
        manager.add_limit(limit)

        with (
            patch.object(manager, "_get_current_spend", return_value=Decimal("800.0")),
            patch.object(manager, "_handle_violation") as mock_handle,
            patch("d0_gateway.guardrail_alerts.send_cost_alert", new_callable=AsyncMock) as mock_send_alert,
        ):
            result = manager.enforce_limits("dataaxle", "search", Decimal("50.0"))

            # Should still return True but handle violation
            assert result is True
            mock_handle.assert_called_once()

            # Check the violation that was handled
            violation, limit_obj = mock_handle.call_args[0]
            assert violation.severity == AlertSeverity.WARNING
            assert GuardrailAction.ALERT in violation.action_taken


class TestSingletonInstance:
    """Test singleton guardrail_manager instance"""

    def test_singleton_instance(self):
        """Test that guardrail_manager is properly initialized"""
        assert guardrail_manager is not None
        assert isinstance(guardrail_manager, GuardrailManager)
