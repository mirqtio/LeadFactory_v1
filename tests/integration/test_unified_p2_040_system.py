"""
Integration tests for P2-040 Unified Budget Monitoring System
Tests the integration between PM-1's core monitoring and PM-2's alert enhancements
"""
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

from orchestrator.unified_budget_system import (
    PM1CoreIntegration,
    PM2AlertIntegration,
    UnifiedBudgetSystem,
    check_unified_operation_budget,
    get_unified_budget_status,
    initialize_unified_p2040_system,
    trigger_unified_budget_check,
    unified_budget_system,
)


class TestUnifiedP2040System:
    """Test P2-040 unified budget monitoring system"""

    @pytest.mark.asyncio
    async def test_unified_system_initialization(self):
        """Test unified system initialization"""
        system = UnifiedBudgetSystem()

        with patch("orchestrator.unified_budget_system.PM1CoreIntegration.initialize") as mock_pm1, patch(
            "orchestrator.unified_budget_system.PM2AlertIntegration.initialize"
        ) as mock_pm2:
            await system.initialize()

            assert system.is_initialized
            mock_pm1.assert_called_once()
            mock_pm2.assert_called_once()

    @pytest.mark.asyncio
    async def test_pm1_core_integration(self):
        """Test PM-1 core integration adapter"""
        pm1 = PM1CoreIntegration()

        await pm1.initialize()
        assert pm1.flows_initialized

        # Test budget configuration
        config = await pm1.get_budget_configuration()
        assert "monthly_limit" in config
        assert "provider_budgets" in config
        assert config["monthly_limit"] > 0

        # Test status retrieval
        status = await pm1.get_status()
        assert "system" in status
        assert status["system"] == "pm1_core"
        assert "current_spend" in status
        assert "monthly_limit" in status

    @pytest.mark.asyncio
    async def test_pm2_alert_integration(self):
        """Test PM-2 alert integration adapter"""
        pm2 = PM2AlertIntegration()

        with patch("orchestrator.unified_budget_system.initialize_p2040_enhancements") as mock_init:
            await pm2.initialize()
            mock_init.assert_called_once()

        # Test sync with PM-1 config
        pm1_config = {
            "monthly_limit": 3000.0,
            "warning_threshold": 0.8,
            "stop_threshold": 0.95,
            "provider_budgets": {"openai": 500.0, "dataaxle": 800.0},
        }

        # Mock monitors exist
        pm2.alert_manager.monitors = {"global": Mock(), "openai": Mock(), "dataaxle": Mock()}

        await pm2.sync_with_pm1_config(pm1_config)

        # Verify monitors were updated
        for monitor in pm2.alert_manager.monitors.values():
            assert hasattr(monitor, "monthly_budget_usd")

    @pytest.mark.asyncio
    async def test_unified_budget_status(self):
        """Test unified budget status retrieval"""
        # Mock both PM-1 and PM-2 status calls
        with patch.object(PM1CoreIntegration, "get_status") as mock_pm1_status, patch.object(
            PM2AlertIntegration, "get_status"
        ) as mock_pm2_status:
            mock_pm1_status.return_value = {
                "current_spend": 1500.0,
                "monthly_limit": 3000.0,
                "percentage_used": 0.5,
                "alert_level": "ok",
                "flows_active": True,
            }

            mock_pm2_status.return_value = {
                "monitors": [{"monitor_id": "global", "status": "ok", "current_spend": 1500.0}],
                "total_monitors": 1,
                "alerts_active": 0,
            }

            system = UnifiedBudgetSystem()
            system.is_initialized = True

            status = await system.check_unified_budget_status()

            assert status["system_status"] == "unified"
            assert "pm1_core_monitoring" in status
            assert "pm2_realtime_alerts" in status
            assert "global_budget" in status
            assert status["global_budget"]["current_spend"] == 1500.0

    @pytest.mark.asyncio
    async def test_unified_budget_check(self):
        """Test unified budget check coordination"""
        with patch.object(PM1CoreIntegration, "trigger_monthly_monitor") as mock_pm1_check, patch.object(
            PM2AlertIntegration, "trigger_realtime_check"
        ) as mock_pm2_check:
            mock_pm1_check.return_value = {"status": "success", "alert_sent": True}

            mock_pm2_check.return_value = {"status": "success", "alerts_sent": "2"}

            system = UnifiedBudgetSystem()
            system.is_initialized = True

            result = await system.trigger_unified_budget_check()

            assert "pm1_monitoring" in result
            assert "pm2_alerts" in result
            assert "coordination" in result
            assert result["coordination"]["alerts_sent"] == 3  # 1 + 2

    @pytest.mark.asyncio
    async def test_unified_operation_budget_check(self):
        """Test unified operation budget checking"""
        # Mock PM-1's real-time cost check
        with patch("orchestrator.unified_budget_system.real_time_cost_check") as mock_pm1_check, patch(
            "orchestrator.unified_budget_system.check_budget_before_operation"
        ) as mock_pm2_check:
            mock_pm1_check.return_value = {"should_proceed": True, "recommendation": "proceed"}

            mock_pm2_check.return_value = True

            result = await check_unified_operation_budget("openai", 50.0)

            assert result["unified_decision"] is True
            assert "pm1_analysis" in result
            assert "pm2_analysis" in result
            assert result["provider"] == "openai"
            assert result["estimated_cost"] == 50.0

    @pytest.mark.asyncio
    async def test_unified_operation_budget_check_blocked(self):
        """Test unified operation budget checking when blocked"""
        # Mock one system blocking the operation
        with patch("orchestrator.unified_budget_system.real_time_cost_check") as mock_pm1_check, patch(
            "orchestrator.unified_budget_system.check_budget_before_operation"
        ) as mock_pm2_check:
            mock_pm1_check.return_value = {"should_proceed": True, "recommendation": "proceed"}

            mock_pm2_check.return_value = False  # PM-2 blocks

            result = await check_unified_operation_budget("openai", 500.0)

            assert result["unified_decision"] is False  # Blocked by PM-2
            assert result["pm2_analysis"]["can_proceed"] is False

    @pytest.mark.asyncio
    async def test_global_unified_functions(self):
        """Test global unified system functions"""
        # Test initialization function
        with patch("orchestrator.unified_budget_system.unified_budget_system.initialize") as mock_init:
            await initialize_unified_p2040_system()
            mock_init.assert_called_once()

        # Test status function
        with patch(
            "orchestrator.unified_budget_system.unified_budget_system.check_unified_budget_status"
        ) as mock_status:
            mock_status.return_value = {"status": "test"}

            # Mock system as initialized
            unified_budget_system.is_initialized = True

            status = await get_unified_budget_status()
            assert status == {"status": "test"}

        # Test check function
        with patch(
            "orchestrator.unified_budget_system.unified_budget_system.trigger_unified_budget_check"
        ) as mock_check:
            mock_check.return_value = {"result": "test"}

            result = await trigger_unified_budget_check()
            assert result == {"result": "test"}

    def test_unified_api_endpoints(self, client: TestClient):
        """Test unified API endpoints"""
        # Test health check endpoint
        response = client.get("/api/v1/budget-alerts/health")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_error_handling_in_coordination(self):
        """Test error handling in unified system coordination"""
        system = UnifiedBudgetSystem()
        system.is_initialized = True

        # Mock PM-1 to raise exception
        with patch.object(PM1CoreIntegration, "trigger_monthly_monitor") as mock_pm1, patch.object(
            PM2AlertIntegration, "trigger_realtime_check"
        ) as mock_pm2:
            mock_pm1.side_effect = Exception("PM-1 error")
            mock_pm2.return_value = {"status": "success", "alerts_sent": "0"}

            result = await system.trigger_unified_budget_check()

            assert "error" in result["pm1_monitoring"]
            assert result["pm2_alerts"]["status"] == "success"
            assert result["coordination"]["overall_status"] == "error"

    @pytest.mark.asyncio
    async def test_budget_configuration_sync(self):
        """Test budget configuration synchronization between systems"""
        pm1 = PM1CoreIntegration()
        pm2 = PM2AlertIntegration()

        # Mock PM-2 monitors
        from decimal import Decimal
        from unittest.mock import Mock

        global_monitor = Mock()
        openai_monitor = Mock()
        pm2.alert_manager.monitors = {"global": global_monitor, "openai": openai_monitor}

        # Get PM-1 config and sync to PM-2
        pm1_config = await pm1.get_budget_configuration()
        await pm2.sync_with_pm1_config(pm1_config)

        # Verify sync occurred
        assert global_monitor.monthly_budget_usd == Decimal(str(pm1_config["monthly_limit"]))
        assert global_monitor.warning_threshold == pm1_config["warning_threshold"]
        assert openai_monitor.monthly_budget_usd == Decimal(str(pm1_config["provider_budgets"]["openai"]))

    @pytest.mark.asyncio
    async def test_system_status_aggregation(self):
        """Test proper aggregation of status from both systems"""
        system = UnifiedBudgetSystem()
        system.is_initialized = True

        # Create comprehensive status data
        pm1_status = {
            "current_spend": 2400.0,
            "monthly_limit": 3000.0,
            "percentage_used": 0.8,
            "alert_level": "warning",
            "flows_active": True,
            "circuit_breaker_active": False,
        }

        pm2_status = {
            "monitors": [
                {"monitor_id": "global", "status": "warning", "current_spend": 2400.0},
                {"monitor_id": "openai", "status": "ok", "current_spend": 400.0},
            ],
            "total_monitors": 2,
            "alerts_active": 1,
        }

        with patch.object(PM1CoreIntegration, "get_status", return_value=pm1_status), patch.object(
            PM2AlertIntegration, "get_status", return_value=pm2_status
        ):
            status = await system.check_unified_budget_status()

            # Verify unified status structure
            assert status["system_status"] == "unified"
            assert status["global_budget"]["current_spend"] == 2400.0
            assert status["global_budget"]["alert_level"] == "warning"
            assert status["alert_coordination"]["pm1_flows_active"] is True
            assert status["alert_coordination"]["pm2_monitors_active"] == 2
            assert status["alert_coordination"]["unified_alerting"] is True
