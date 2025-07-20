"""
Unit tests for P2-040 Budget Monitoring enhancements
Tests enhanced threshold tracking, alert system, and API cost monitoring integration
"""
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from d11_orchestration.cost_guardrails import (
    check_monthly_budget_threshold,
    get_budget_status_for_api,
    monthly_budget_monitor_flow,
    real_time_cost_check,
)


class TestP2040BudgetMonitoring:
    """Test P2-040 Budget Monitoring core functionality"""

    def test_check_monthly_budget_threshold_notice_level(self):
        """Test 70% notice threshold detection"""
        with patch("d11_orchestration.cost_guardrails.get_monthly_costs") as mock_costs, patch(
            "d11_orchestration.cost_guardrails.get_settings"
        ) as mock_settings:
            # Mock 70% usage - notice level
            mock_costs.return_value = Decimal("2100.0")  # 70% of 3000
            mock_settings.return_value.guardrail_global_monthly_limit = 3000.0

            is_over, percentage_used, alert_level, current_spend, monthly_limit = check_monthly_budget_threshold()

            assert is_over is True
            assert abs(percentage_used - 0.7) < 0.01  # 70%
            assert alert_level == "notice"
            assert current_spend == Decimal("2100.0")
            assert monthly_limit == Decimal("3000.0")

    def test_check_monthly_budget_threshold_warning_level(self):
        """Test 80% warning threshold detection"""
        with patch("d11_orchestration.cost_guardrails.get_monthly_costs") as mock_costs, patch(
            "d11_orchestration.cost_guardrails.get_settings"
        ) as mock_settings:
            # Mock 80% usage - warning level
            mock_costs.return_value = Decimal("2400.0")  # 80% of 3000
            mock_settings.return_value.guardrail_global_monthly_limit = 3000.0

            is_over, percentage_used, alert_level, current_spend, monthly_limit = check_monthly_budget_threshold()

            assert is_over is True
            assert abs(percentage_used - 0.8) < 0.01  # 80%
            assert alert_level == "warning"

    def test_check_monthly_budget_threshold_high_level(self):
        """Test 90% high threshold detection"""
        with patch("d11_orchestration.cost_guardrails.get_monthly_costs") as mock_costs, patch(
            "d11_orchestration.cost_guardrails.get_settings"
        ) as mock_settings:
            # Mock 90% usage - high level
            mock_costs.return_value = Decimal("2700.0")  # 90% of 3000
            mock_settings.return_value.guardrail_global_monthly_limit = 3000.0

            is_over, percentage_used, alert_level, current_spend, monthly_limit = check_monthly_budget_threshold()

            assert is_over is True
            assert abs(percentage_used - 0.9) < 0.01  # 90%
            assert alert_level == "high"

    def test_check_monthly_budget_threshold_critical_level(self):
        """Test 100%+ critical threshold detection"""
        with patch("d11_orchestration.cost_guardrails.get_monthly_costs") as mock_costs, patch(
            "d11_orchestration.cost_guardrails.get_settings"
        ) as mock_settings:
            # Mock 100%+ usage - critical level
            mock_costs.return_value = Decimal("3100.0")  # 103% of 3000
            mock_settings.return_value.guardrail_global_monthly_limit = 3000.0

            is_over, percentage_used, alert_level, current_spend, monthly_limit = check_monthly_budget_threshold()

            assert is_over is True
            assert percentage_used > 1.0  # Over 100%
            assert alert_level == "critical"

    def test_check_monthly_budget_threshold_ok_level(self):
        """Test under 70% OK level"""
        with patch("d11_orchestration.cost_guardrails.get_monthly_costs") as mock_costs, patch(
            "d11_orchestration.cost_guardrails.get_settings"
        ) as mock_settings:
            # Mock 60% usage - OK level
            mock_costs.return_value = Decimal("1800.0")  # 60% of 3000
            mock_settings.return_value.guardrail_global_monthly_limit = 3000.0

            is_over, percentage_used, alert_level, current_spend, monthly_limit = check_monthly_budget_threshold()

            assert is_over is False
            assert abs(percentage_used - 0.6) < 0.01  # 60%
            assert alert_level == "ok"

    def test_check_monthly_budget_threshold_zero_limit(self):
        """Test threshold checking with zero limit"""
        with patch("d11_orchestration.cost_guardrails.get_monthly_costs") as mock_costs, patch(
            "d11_orchestration.cost_guardrails.get_settings"
        ) as mock_settings:
            # Mock zero limit
            mock_costs.return_value = Decimal("100.0")
            mock_settings.return_value.guardrail_global_monthly_limit = 0.0

            is_over, percentage_used, alert_level, current_spend, monthly_limit = check_monthly_budget_threshold()

            assert percentage_used == 0.0
            assert alert_level == "ok"

    def test_real_time_cost_check_proceed(self):
        """Test real-time cost check allowing operation"""
        with patch("d11_orchestration.cost_guardrails.check_monthly_budget_threshold") as mock_threshold, patch(
            "d11_orchestration.cost_guardrails.get_run_logger"
        ) as mock_logger:
            # Mock 60% current usage, operation would bring to 65%
            mock_threshold.return_value = (False, 0.6, "ok", Decimal("1800.0"), Decimal("3000.0"))
            mock_logger.return_value = MagicMock()

            result = real_time_cost_check.fn(operation_cost=150.0, provider="openai")

            assert result["should_proceed"] is True
            assert result["recommendation"] == "proceed"
            assert result["operation_cost"] == 150.0
            assert result["current_percentage"] == 0.6
            assert abs(result["projected_percentage"] - 0.65) < 0.01  # 1950/3000

    def test_real_time_cost_check_proceed_with_monitoring(self):
        """Test real-time cost check with monitoring recommendation"""
        with patch("d11_orchestration.cost_guardrails.check_monthly_budget_threshold") as mock_threshold, patch(
            "d11_orchestration.cost_guardrails.get_run_logger"
        ) as mock_logger:
            # Mock 75% current usage, operation would bring to 85%
            mock_threshold.return_value = (True, 0.75, "notice", Decimal("2250.0"), Decimal("3000.0"))
            mock_logger.return_value = MagicMock()

            result = real_time_cost_check.fn(operation_cost=300.0, provider="dataaxle")

            assert result["should_proceed"] is True
            assert result["recommendation"] == "proceed_with_monitoring"
            assert abs(result["projected_percentage"] - 0.85) < 0.01  # 2550/3000

    def test_real_time_cost_check_proceed_with_caution(self):
        """Test real-time cost check with caution recommendation"""
        with patch("d11_orchestration.cost_guardrails.check_monthly_budget_threshold") as mock_threshold, patch(
            "d11_orchestration.cost_guardrails.get_run_logger"
        ) as mock_logger:
            # Mock 85% current usage, operation would bring to 92%
            mock_threshold.return_value = (True, 0.85, "warning", Decimal("2550.0"), Decimal("3000.0"))
            mock_logger.return_value = MagicMock()

            result = real_time_cost_check.fn(operation_cost=210.0, provider="hunter")

            assert result["should_proceed"] is True
            assert result["recommendation"] == "proceed_with_caution"
            assert abs(result["projected_percentage"] - 0.92) < 0.01  # 2760/3000

    def test_real_time_cost_check_block_high_risk(self):
        """Test real-time cost check blocking high risk operation"""
        with patch("d11_orchestration.cost_guardrails.check_monthly_budget_threshold") as mock_threshold, patch(
            "d11_orchestration.cost_guardrails.get_run_logger"
        ) as mock_logger:
            # Mock 90% current usage, operation would bring to 96%
            mock_threshold.return_value = (True, 0.9, "high", Decimal("2700.0"), Decimal("3000.0"))
            mock_logger.return_value = MagicMock()

            result = real_time_cost_check.fn(operation_cost=180.0, provider="openai")

            assert result["should_proceed"] is False
            assert result["recommendation"] == "block_high_risk"
            assert abs(result["projected_percentage"] - 0.96) < 0.01  # 2880/3000

    def test_real_time_cost_check_block_critical(self):
        """Test real-time cost check blocking critical operation"""
        with patch("d11_orchestration.cost_guardrails.check_monthly_budget_threshold") as mock_threshold, patch(
            "d11_orchestration.cost_guardrails.get_run_logger"
        ) as mock_logger:
            # Mock 95% current usage, operation would exceed 100%
            mock_threshold.return_value = (True, 0.95, "high", Decimal("2850.0"), Decimal("3000.0"))
            mock_logger.return_value = MagicMock()

            result = real_time_cost_check.fn(operation_cost=200.0, provider="dataaxle")

            assert result["should_proceed"] is False
            assert result["recommendation"] == "block_critical"
            assert abs(result["projected_percentage"] - 1.017) < 0.01  # 3050/3000

    def test_get_budget_status_for_api_healthy(self):
        """Test API budget status endpoint - healthy status"""
        with patch("d11_orchestration.cost_guardrails.check_monthly_budget_threshold") as mock_threshold:
            # Mock healthy budget status
            mock_threshold.return_value = (False, 0.6, "ok", Decimal("1800.0"), Decimal("3000.0"))

            status = get_budget_status_for_api()

            assert status["status"] == "healthy"
            assert status["current_spend"] == 1800.0
            assert status["monthly_limit"] == 3000.0
            assert status["percentage_used"] == 0.6
            assert status["alert_level"] == "ok"
            assert status["remaining_budget"] == 1200.0
            assert "thresholds" in status
            assert status["thresholds"]["notice"] == 0.7

    def test_get_budget_status_for_api_warning(self):
        """Test API budget status endpoint - warning status"""
        with patch("d11_orchestration.cost_guardrails.check_monthly_budget_threshold") as mock_threshold:
            # Mock warning budget status
            mock_threshold.return_value = (True, 0.8, "warning", Decimal("2400.0"), Decimal("3000.0"))

            status = get_budget_status_for_api()

            assert status["status"] == "warning"
            assert status["alert_level"] == "warning"
            assert status["remaining_budget"] == 600.0

    def test_get_budget_status_for_api_critical(self):
        """Test API budget status endpoint - critical status"""
        with patch("d11_orchestration.cost_guardrails.check_monthly_budget_threshold") as mock_threshold:
            # Mock critical budget status
            mock_threshold.return_value = (True, 1.05, "critical", Decimal("3150.0"), Decimal("3000.0"))

            status = get_budget_status_for_api()

            assert status["status"] == "critical"
            assert status["alert_level"] == "critical"
            assert status["remaining_budget"] == -150.0  # Over budget


class TestP2040BudgetMonitoringFlow:
    """Test P2-040 Monthly Budget Monitoring Flow"""

    def test_monthly_budget_monitor_flow_ok_status(self):
        """Test monthly budget monitoring flow with OK status"""
        with patch("d11_orchestration.cost_guardrails.check_monthly_budget_threshold") as mock_threshold, patch(
            "d11_orchestration.cost_guardrails.get_run_logger"
        ) as mock_logger, patch("d11_orchestration.cost_guardrails.PREFECT_AVAILABLE", False):
            # Mock OK status
            mock_threshold.return_value = (False, 0.6, "ok", Decimal("1800.0"), Decimal("3000.0"))
            mock_logger.return_value = MagicMock()

            result = monthly_budget_monitor_flow.fn()

            assert result["alert_level"] == "ok"
            assert result["is_over_threshold"] is False
            assert result["alert_sent"] is False
            assert result["current_spend"] == 1800.0
            assert result["percentage_used"] == 0.6

    def test_monthly_budget_monitor_flow_warning_status(self):
        """Test monthly budget monitoring flow with warning status and alert"""
        with patch("d11_orchestration.cost_guardrails.check_monthly_budget_threshold") as mock_threshold, patch(
            "d11_orchestration.cost_guardrails.get_run_logger"
        ) as mock_logger, patch("d11_orchestration.cost_guardrails.send_cost_alert") as mock_alert, patch(
            "d11_orchestration.cost_guardrails.PREFECT_AVAILABLE", False
        ), patch(
            "asyncio.get_event_loop"
        ) as mock_get_loop, patch(
            "asyncio.run"
        ) as mock_asyncio:
            # Mock warning status
            mock_threshold.return_value = (True, 0.8, "warning", Decimal("2400.0"), Decimal("3000.0"))
            mock_logger.return_value = MagicMock()

            # Mock the event loop path
            mock_loop = MagicMock()
            mock_get_loop.return_value = mock_loop
            mock_loop.run_until_complete.return_value = None
            mock_alert.return_value = None

            result = monthly_budget_monitor_flow.fn()

            assert result["alert_level"] == "warning"
            assert result["is_over_threshold"] is True
            assert result["alert_sent"] is True
            # Verify alert was sent via event loop
            mock_loop.run_until_complete.assert_called_once()

    def test_monthly_budget_monitor_flow_alert_failure(self):
        """Test monthly budget monitoring flow with alert failure"""
        with patch("d11_orchestration.cost_guardrails.check_monthly_budget_threshold") as mock_threshold, patch(
            "d11_orchestration.cost_guardrails.get_run_logger"
        ) as mock_logger, patch("d11_orchestration.cost_guardrails.send_cost_alert") as mock_alert, patch(
            "d11_orchestration.cost_guardrails.PREFECT_AVAILABLE", False
        ), patch(
            "asyncio.get_event_loop"
        ) as mock_get_loop, patch(
            "asyncio.run", side_effect=Exception("Alert failed")
        ):
            # Mock warning status
            mock_threshold.return_value = (True, 0.8, "warning", Decimal("2400.0"), Decimal("3000.0"))
            mock_logger.return_value = MagicMock()

            # Mock the event loop path to fail
            mock_loop = MagicMock()
            mock_get_loop.return_value = mock_loop
            mock_loop.run_until_complete.side_effect = Exception("Alert failed")

            result = monthly_budget_monitor_flow.fn()

            assert result["alert_level"] == "warning"
            assert result["is_over_threshold"] is True
            assert result["alert_sent"] is False  # Alert failed

    def test_monthly_budget_monitor_flow_with_prefect_artifact(self):
        """Test monthly budget monitoring flow with Prefect artifact creation"""
        with patch("d11_orchestration.cost_guardrails.check_monthly_budget_threshold") as mock_threshold, patch(
            "d11_orchestration.cost_guardrails.get_run_logger"
        ) as mock_logger, patch("d11_orchestration.cost_guardrails.PREFECT_AVAILABLE", True), patch(
            "d11_orchestration.cost_guardrails.create_markdown_artifact"
        ) as mock_artifact:
            # Mock notice status
            mock_threshold.return_value = (True, 0.75, "notice", Decimal("2250.0"), Decimal("3000.0"))
            mock_logger.return_value = MagicMock()

            result = monthly_budget_monitor_flow.fn()

            assert result["alert_level"] == "notice"
            # Verify artifact was created
            mock_artifact.assert_called_once()
            # Check artifact content includes status information
            artifact_call = mock_artifact.call_args
            assert "P2-040 Monthly Budget Monitoring" in artifact_call[1]["markdown"]
            assert "NOTICE" in artifact_call[1]["markdown"]
