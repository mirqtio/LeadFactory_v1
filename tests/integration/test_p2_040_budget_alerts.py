"""
Integration tests for P2-040 Budget Alert Enhancement
"""
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

from orchestrator.budget_monitor import BudgetMonitor, BudgetStatus
from orchestrator.real_time_budget_alerts import RealTimeBudgetAlertManager


class TestP2040BudgetAlertIntegration:
    """Test P2-040 budget alert enhancement integration"""

    def test_budget_monitor_integration(self):
        """Test BudgetMonitor integration with alert system"""
        # Create budget monitor
        monitor = BudgetMonitor(monthly_budget_usd=1000.0, warning_threshold=0.8, stop_threshold=0.95)

        # Test different spending levels
        assert monitor.check_budget_status(500.0) == BudgetStatus.OK
        assert monitor.check_budget_status(850.0) == BudgetStatus.WARNING
        assert monitor.check_budget_status(980.0) == BudgetStatus.STOP

    def test_alert_manager_registration(self):
        """Test budget monitor registration in alert manager"""
        manager = RealTimeBudgetAlertManager()

        monitor = BudgetMonitor(monthly_budget_usd=500.0)
        manager.register_budget_monitor("test_provider", monitor)

        assert "test_provider" in manager.monitors
        assert manager.monitors["test_provider"] == monitor

    @pytest.mark.asyncio
    async def test_violation_creation(self):
        """Test GuardrailViolation creation from budget status"""
        manager = RealTimeBudgetAlertManager()
        monitor = BudgetMonitor(monthly_budget_usd=1000.0, warning_threshold=0.8, stop_threshold=0.95)

        # Test violation creation
        violation = manager._create_violation("test", monitor, 900.0, BudgetStatus.WARNING)

        assert violation.limit_name == "monthly_budget_test"
        assert violation.current_spend == Decimal("900.0")
        assert violation.limit_amount == Decimal("1000.0")
        assert violation.percentage_used == 0.9
        assert violation.provider == "test"

    @pytest.mark.asyncio
    async def test_alert_cooldown(self):
        """Test alert cooldown prevents spam"""
        manager = RealTimeBudgetAlertManager()
        manager.alert_cooldown_minutes = 1  # Short cooldown for testing

        monitor = BudgetMonitor(monthly_budget_usd=100.0, warning_threshold=0.8)
        manager.register_budget_monitor("test", monitor)

        # Mock the send_cost_alert function
        with patch("orchestrator.real_time_budget_alerts.send_cost_alert", new_callable=AsyncMock) as mock_alert:
            # First alert should be sent
            violation1 = await manager.check_budget_and_alert("test", 90.0)
            assert violation1 is not None
            mock_alert.assert_called_once()

            # Second alert immediately should be blocked by cooldown
            mock_alert.reset_mock()
            violation2 = await manager.check_budget_and_alert("test", 95.0)
            assert violation2 is None
            mock_alert.assert_not_called()

    @pytest.mark.asyncio
    async def test_multiple_budget_checks(self):
        """Test checking multiple budgets simultaneously"""
        manager = RealTimeBudgetAlertManager()

        # Register multiple monitors
        monitors = {
            "provider1": BudgetMonitor(monthly_budget_usd=1000.0, warning_threshold=0.8),
            "provider2": BudgetMonitor(monthly_budget_usd=500.0, warning_threshold=0.7),
            "provider3": BudgetMonitor(monthly_budget_usd=200.0, warning_threshold=0.9),
        }

        for monitor_id, monitor in monitors.items():
            manager.register_budget_monitor(monitor_id, monitor)

        # Test spending that triggers some alerts
        spending = {
            "provider1": 850.0,  # Should trigger warning (85% > 80%)
            "provider2": 300.0,  # Should be OK (60% < 70%)
            "provider3": 190.0,  # Should trigger warning (95% > 90%)
        }

        with patch("orchestrator.real_time_budget_alerts.send_cost_alert", new_callable=AsyncMock) as mock_alert:
            violations = await manager.check_all_budgets(spending)

            # Should have 2 violations (provider1 and provider3)
            assert len(violations) == 2
            assert mock_alert.call_count == 2

    def test_budget_api_health_check(self, client: TestClient):
        """Test budget alert API health check endpoint"""
        response = client.get("/api/v1/budget-alerts/health")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_threshold_integrator_setup(self):
        """Test BudgetThresholdIntegrator default setup"""
        from orchestrator.real_time_budget_alerts import BudgetThresholdIntegrator

        manager = RealTimeBudgetAlertManager()
        integrator = BudgetThresholdIntegrator(manager)

        # Setup default monitors
        integrator.setup_default_monitors()

        # Should have global + provider monitors
        assert len(manager.monitors) >= 6  # global + 5 providers
        assert "global" in manager.monitors
        assert "openai" in manager.monitors
        assert "dataaxle" in manager.monitors

    @pytest.mark.asyncio
    async def test_pre_operation_budget_check(self):
        """Test pre-operation budget checking"""
        from orchestrator.real_time_budget_alerts import check_budget_before_operation

        # Setup manager with test monitor
        manager = RealTimeBudgetAlertManager()
        monitor = BudgetMonitor(monthly_budget_usd=100.0, stop_threshold=0.9)
        manager.register_budget_monitor("test_provider", monitor)

        # Mock getting current spending
        with patch("orchestrator.real_time_budget_alerts.threshold_integrator.get_current_spending") as mock_spending:
            mock_spending.return_value = {"test_provider": 80.0}  # 80% of budget used

            # Operation that would exceed stop threshold should be blocked
            can_proceed = await check_budget_before_operation("test_provider", 15.0)  # Would be 95%
            assert can_proceed is False

            # Operation within limits should proceed
            can_proceed = await check_budget_before_operation("test_provider", 5.0)  # Would be 85%
            assert can_proceed is True
