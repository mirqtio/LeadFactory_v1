"""
Integration tests for cost guardrail system (P1-060)
"""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from d0_gateway.guardrail_middleware import GuardrailBlocked, RateLimitExceeded
from d0_gateway.guardrails import CostLimit, GuardrailAction, LimitPeriod, LimitScope, guardrail_manager
from database.models import APICost, DailyCostAggregate
from database.session import SessionLocal


@pytest.fixture
def setup_test_data(db_session):
    """Set up test cost data"""
    # Add some API costs
    costs = [
        APICost(provider="openai", operation="chat", cost_usd=Decimal("5.00"), timestamp=datetime.utcnow()),
        APICost(provider="openai", operation="embedding", cost_usd=Decimal("2.00"), timestamp=datetime.utcnow()),
        APICost(provider="dataaxle", operation="match_business", cost_usd=Decimal("0.10"), timestamp=datetime.utcnow()),
    ]

    for cost in costs:
        db_session.add(cost)

    # Add daily aggregates
    today = datetime.utcnow().date()
    aggregates = [
        DailyCostAggregate(
            date=today, provider="openai", operation="chat", total_cost_usd=Decimal("50.00"), request_count=100
        ),
        DailyCostAggregate(
            date=today,
            provider="dataaxle",
            operation="match_business",
            total_cost_usd=Decimal("25.00"),
            request_count=500,
        ),
    ]

    for agg in aggregates:
        db_session.add(agg)

    db_session.commit()


class TestGuardrailAPIIntegration:
    """Test guardrail API endpoints"""

    def test_get_guardrail_status(self, client: TestClient, setup_test_data):
        """Test getting guardrail status"""
        response = client.get("/api/v1/gateway/guardrails/status")
        assert response.status_code == 200

        data = response.json()
        assert "limits" in data
        assert "total_limits" in data
        assert "limits_exceeded" in data
        assert "timestamp" in data

    def test_list_limits(self, client: TestClient):
        """Test listing configured limits"""
        response = client.get("/api/v1/gateway/guardrails/limits")
        assert response.status_code == 200

        limits = response.json()
        assert isinstance(limits, list)

        # Should have default limits
        limit_names = [limit["name"] for limit in limits]
        assert "global_daily" in limit_names
        assert "openai_daily" in limit_names

    def test_create_limit(self, client: TestClient):
        """Test creating a new limit"""
        limit_data = {
            "name": "test_campaign_limit",
            "scope": "campaign",
            "period": "monthly",
            "limit_usd": 5000.0,
            "campaign_id": 123,
            "warning_threshold": 0.75,
            "critical_threshold": 0.9,
        }

        response = client.post("/api/v1/gateway/guardrails/limits", json=limit_data)
        assert response.status_code == 200

        created = response.json()
        assert created["name"] == "test_campaign_limit"
        assert created["limit_usd"] == 5000.0
        assert created["campaign_id"] == 123

    def test_update_limit(self, client: TestClient):
        """Test updating an existing limit"""
        # First create a limit
        client.post(
            "/api/v1/gateway/guardrails/limits",
            json={"name": "update_test", "scope": "global", "period": "daily", "limit_usd": 100.0},
        )

        # Update it
        update_data = {"limit_usd": 200.0, "warning_threshold": 0.7}

        response = client.put("/api/v1/gateway/guardrails/limits/update_test", json=update_data)
        assert response.status_code == 200

        updated = response.json()
        assert updated["limit_usd"] == 200.0
        assert updated["warning_threshold"] == 0.7

    def test_delete_limit(self, client: TestClient):
        """Test deleting a limit"""
        # First create a limit
        client.post(
            "/api/v1/gateway/guardrails/limits",
            json={"name": "delete_test", "scope": "global", "period": "daily", "limit_usd": 100.0},
        )

        # Delete it
        response = client.delete("/api/v1/gateway/guardrails/limits/delete_test")
        assert response.status_code == 200

        # Verify it's gone
        response = client.get("/api/v1/gateway/guardrails/limits")
        limit_names = [limit["name"] for limit in response.json()]
        assert "delete_test" not in limit_names

    def test_get_budget_summary(self, client: TestClient, setup_test_data):
        """Test getting budget summary"""
        response = client.get("/api/v1/gateway/guardrails/budget?period=daily")
        assert response.status_code == 200

        data = response.json()
        assert "providers" in data
        assert "total_remaining" in data
        assert "total_limit" in data
        assert "total_spent" in data

    def test_configure_alerts(self, client: TestClient):
        """Test configuring alerts"""
        alert_config = {
            "channel": "webhook",
            "webhook_url": "https://example.com/alerts",
            "min_severity": "warning",
            "enabled": True,
        }

        response = client.post("/api/v1/gateway/guardrails/alerts/configure", json=alert_config)
        assert response.status_code == 200
        assert "webhook configured successfully" in response.json()["message"]


class TestGuardrailEnforcement:
    """Test guardrail enforcement in API calls"""

    @pytest.mark.asyncio
    async def test_guardrail_blocks_over_limit(self, db_session):
        """Test that guardrails block operations when over limit"""
        # Create a very low limit
        test_limit = CostLimit(
            name="test_low_limit",
            scope=LimitScope.PROVIDER,
            period=LimitPeriod.DAILY,
            limit_usd=Decimal("0.01"),  # Very low limit
            provider="openai",
            actions=[GuardrailAction.BLOCK],
        )
        guardrail_manager.add_limit(test_limit)

        # Mock high current spend
        with patch.object(guardrail_manager, "_get_current_spend") as mock_spend:
            mock_spend.return_value = Decimal("100.00")

            # Try to enforce limits
            result = guardrail_manager.enforce_limits(
                provider="openai", operation="chat", estimated_cost=Decimal("5.00")
            )

            assert hasattr(result, "limit_name")
            assert result.limit_name == "test_low_limit"
            assert GuardrailAction.BLOCK in result.action_taken

        # Clean up
        guardrail_manager.remove_limit("test_low_limit")

    @pytest.mark.asyncio
    async def test_guardrail_allows_under_limit(self, db_session):
        """Test that guardrails allow operations when under limit"""
        # Mock low current spend
        with patch.object(guardrail_manager, "_get_current_spend") as mock_spend:
            mock_spend.return_value = Decimal("10.00")

            # Try to enforce limits
            result = guardrail_manager.enforce_limits(
                provider="openai", operation="chat", estimated_cost=Decimal("1.00")
            )

            assert result is True

    @pytest.mark.asyncio
    async def test_rate_limiting(self):
        """Test rate limiting functionality"""
        from d0_gateway.guardrail_middleware import rate_limiter

        # Add a strict rate limit
        from d0_gateway.guardrails import RateLimitConfig

        rate_config = RateLimitConfig(provider="test_provider", requests_per_minute=1, burst_size=1)
        guardrail_manager.add_rate_limit(rate_config)

        # First request should succeed
        allowed, retry_after = rate_limiter.check_rate_limit("test_provider")
        assert allowed is True

        # Consume the token
        rate_limiter.consume_tokens("test_provider")

        # Second request should be rate limited
        allowed, retry_after = rate_limiter.check_rate_limit("test_provider")
        assert allowed is False
        assert retry_after > 0


class TestCostLedgerIntegration:
    """Test integration with cost ledger"""

    def test_daily_aggregate_query(self, db_session, setup_test_data):
        """Test querying daily cost aggregates"""
        today = datetime.utcnow().date()

        # Query aggregates
        result = db_session.execute(
            text(
                """
                SELECT provider, SUM(total_cost_usd) as total
                FROM agg_daily_cost
                WHERE date = :date
                GROUP BY provider
            """
            ),
            {"date": today},
        ).fetchall()

        costs_by_provider = {row.provider: float(row.total) for row in result}
        assert costs_by_provider["openai"] == 50.0
        assert costs_by_provider["dataaxle"] == 25.0

    def test_cost_recording_triggers_guardrails(self, db_session):
        """Test that recording costs triggers guardrail checks"""
        from d0_gateway.cost_ledger import cost_ledger

        # Record a cost
        cost_record = cost_ledger.record_cost(
            provider="openai", operation="chat", cost_usd=Decimal("5.00"), lead_id=123
        )

        assert cost_record.id is not None
        assert cost_record.provider == "openai"
        assert cost_record.cost_usd == Decimal("5.00")


class TestCircuitBreaker:
    """Test circuit breaker functionality"""

    def test_circuit_breaker_opens_on_failures(self):
        """Test that circuit breaker opens after multiple failures"""
        # Create limit with circuit breaker
        cb_limit = CostLimit(
            name="cb_test",
            scope=LimitScope.PROVIDER,
            period=LimitPeriod.DAILY,
            limit_usd=Decimal("100.00"),
            provider="test_provider",
            circuit_breaker_enabled=True,
            circuit_breaker_failure_threshold=3,
            circuit_breaker_recovery_timeout=60,
        )
        guardrail_manager.add_limit(cb_limit)

        # Simulate failures
        for _ in range(3):
            guardrail_manager._update_circuit_breaker("cb_test", failure_threshold=3, recovery_timeout=60)

        # Circuit should be open
        assert guardrail_manager._is_circuit_open("cb_test")

        # Clean up
        guardrail_manager.remove_limit("cb_test")
        del guardrail_manager._circuit_breakers["cb_test"]

    def test_circuit_breaker_recovery(self):
        """Test circuit breaker recovery after timeout"""
        # Set up open circuit breaker
        guardrail_manager._circuit_breakers["test_cb"] = {
            "state": "open",
            "failure_count": 3,
            "opened_at": datetime.utcnow() - timedelta(seconds=61),
            "recovery_timeout": 60,
        }

        # Should not be open anymore (moved to half-open)
        assert not guardrail_manager._is_circuit_open("test_cb")

        # Clean up
        del guardrail_manager._circuit_breakers["test_cb"]


class TestAlertIntegration:
    """Test alert system integration"""

    @pytest.mark.asyncio
    async def test_violation_triggers_alert(self):
        """Test that violations trigger alerts"""
        from d0_gateway.guardrail_alerts import alert_manager

        # Mock alert sending
        with patch.object(alert_manager, "_send_log_alert") as mock_log:
            # Create a violation that triggers alerts
            with patch.object(guardrail_manager, "_get_current_spend") as mock_spend:
                mock_spend.return_value = Decimal("950.00")

                # This should trigger a violation
                result = guardrail_manager.enforce_limits(
                    provider="openai", operation="chat", estimated_cost=Decimal("100.00")
                )

                # Verify violation was created
                assert hasattr(result, "severity")

                # Send alert for the violation
                await alert_manager.send_alert(result)

                # Verify alert was sent
                mock_log.assert_called_once()
