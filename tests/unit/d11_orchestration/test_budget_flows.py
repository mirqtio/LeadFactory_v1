"""
Unit tests for P2-040 budget monitoring flow functions
Tests for cost_guardrail_flow, profit_snapshot_flow, and deployment functions
"""

from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from d11_orchestration.cost_guardrails import (
    check_costs_now,
    cost_guardrail_flow,
    create_guardrail_deployment,
    create_monthly_budget_monitor_deployment,
    create_profit_snapshot_deployment,
    generate_profit_report_now,
    monitor_monthly_budget_now,
    profit_snapshot_flow,
)


class TestBudgetFlows:
    """Test P2-040 budget monitoring flow functions"""

    def test_cost_guardrail_flow_ok_status(self):
        """Test cost_guardrail_flow with OK status"""
        mock_daily_costs = {"total": 500.0, "openai": 250.0, "dataaxle": 250.0}

        with (
            patch("d11_orchestration.cost_guardrails.get_run_logger") as mock_logger,
            patch("d11_orchestration.cost_guardrails.get_settings") as mock_settings,
            patch("d11_orchestration.cost_guardrails.get_daily_costs") as mock_get_costs,
            patch("d11_orchestration.cost_guardrails.check_budget_threshold") as mock_check_budget,
            patch("d11_orchestration.cost_guardrails.PREFECT_AVAILABLE", False),
        ):
            mock_logger.return_value = MagicMock()
            mock_settings.return_value.cost_budget_usd = 1000.0
            mock_get_costs.return_value = mock_daily_costs
            mock_check_budget.return_value = (False, 0.5, "ok")

            result = cost_guardrail_flow.fn()

            assert result["daily_costs"] == mock_daily_costs
            assert result["budget_used_percentage"] == 0.5
            assert result["alert_level"] == "ok"
            assert result["paused_providers"] == {}
            assert "timestamp" in result

    def test_cost_guardrail_flow_critical_status(self):
        """Test cost_guardrail_flow with critical status and provider pausing"""
        mock_daily_costs = {"total": 1200.0, "openai": 600.0, "dataaxle": 600.0}
        mock_paused = {"openai": True, "dataaxle": True, "hunter": True}

        with (
            patch("d11_orchestration.cost_guardrails.get_run_logger") as mock_logger,
            patch("d11_orchestration.cost_guardrails.get_settings") as mock_settings,
            patch("d11_orchestration.cost_guardrails.get_daily_costs") as mock_get_costs,
            patch("d11_orchestration.cost_guardrails.check_budget_threshold") as mock_check_budget,
            patch("d11_orchestration.cost_guardrails.pause_expensive_operations") as mock_pause,
            patch("d11_orchestration.cost_guardrails.PREFECT_AVAILABLE", False),
        ):
            mock_logger.return_value = MagicMock()
            mock_settings.return_value.cost_budget_usd = 1000.0
            mock_get_costs.return_value = mock_daily_costs
            mock_check_budget.return_value = (True, 1.2, "critical")
            mock_pause.return_value = mock_paused

            result = cost_guardrail_flow.fn()

            assert result["daily_costs"] == mock_daily_costs
            assert result["budget_used_percentage"] == 1.2
            assert result["alert_level"] == "critical"
            assert result["paused_providers"] == mock_paused

    def test_cost_guardrail_flow_with_budget_override(self):
        """Test cost_guardrail_flow with daily budget override"""
        mock_daily_costs = {"total": 800.0, "openai": 400.0, "dataaxle": 400.0}

        with (
            patch("d11_orchestration.cost_guardrails.get_run_logger") as mock_logger,
            patch("d11_orchestration.cost_guardrails.get_settings") as mock_settings,
            patch("d11_orchestration.cost_guardrails.get_daily_costs") as mock_get_costs,
            patch("d11_orchestration.cost_guardrails.check_budget_threshold") as mock_check_budget,
            patch("d11_orchestration.cost_guardrails.PREFECT_AVAILABLE", False),
        ):
            mock_logger.return_value = MagicMock()
            mock_settings.return_value.cost_budget_usd = 1000.0
            mock_get_costs.return_value = mock_daily_costs
            mock_check_budget.return_value = (False, 0.4, "ok")  # 800/2000 = 0.4

            result = cost_guardrail_flow.fn(daily_budget_override=2000.0)

            assert result["budget_used_percentage"] == 0.4
            # Verify override budget was used
            mock_check_budget.assert_called_with(mock_daily_costs, 2000.0, 0.8)

    def test_profit_snapshot_flow_with_data(self):
        """Test profit_snapshot_flow with mock data"""
        mock_metrics = {
            "total_revenue": 5000.0,
            "total_cost": 3000.0,
            "total_profit": 2000.0,
            "avg_roi": 0.67,
            "avg_cpa": 150.0,
            "total_purchases": 20,
        }

        mock_bucket_data = [
            {
                "geo_bucket": "US",
                "vert_bucket": "tech",
                "total_businesses": 100,
                "total_revenue_usd": 2000.0,
                "profit_usd": 800.0,
                "roi": 0.40,
            }
        ]

        with (
            patch("d11_orchestration.cost_guardrails.get_run_logger") as mock_logger,
            patch("d11_orchestration.cost_guardrails.get_profit_metrics") as mock_get_metrics,
            patch("d11_orchestration.cost_guardrails.SessionLocal") as mock_session_local,
            patch("d11_orchestration.cost_guardrails.create_profit_report") as mock_create_report,
            patch("d11_orchestration.cost_guardrails.PREFECT_AVAILABLE", False),
        ):
            mock_logger.return_value = MagicMock()
            mock_get_metrics.return_value = mock_metrics
            mock_create_report.return_value = "Mock profit report"

            # Mock database query for bucket performance
            mock_db = MagicMock()
            mock_session_local.return_value.__enter__.return_value = mock_db
            mock_db.execute.return_value.fetchall.return_value = [
                MagicMock(
                    geo_bucket="US",
                    vert_bucket="tech",
                    total_businesses=100,
                    total_revenue_usd=2000.0,
                    profit_usd=800.0,
                    roi=0.40,
                )
            ]

            result = profit_snapshot_flow.fn(lookback_days=7, top_buckets_count=5)

            assert result["metrics"] == mock_metrics
            assert len(result["top_buckets"]) == 1
            assert result["top_buckets"][0]["geo_bucket"] == "US"
            assert result["report"] == "Mock profit report"
            assert result["period_days"] == 7
            assert "timestamp" in result

    def test_profit_snapshot_flow_no_data(self):
        """Test profit_snapshot_flow with no bucket data"""
        mock_metrics = {
            "total_revenue": 0.0,
            "total_cost": 0.0,
            "total_profit": 0.0,
            "avg_roi": 0.0,
            "avg_cpa": 0.0,
            "total_purchases": 0,
        }

        with (
            patch("d11_orchestration.cost_guardrails.get_run_logger") as mock_logger,
            patch("d11_orchestration.cost_guardrails.get_profit_metrics") as mock_get_metrics,
            patch("d11_orchestration.cost_guardrails.SessionLocal") as mock_session_local,
            patch("d11_orchestration.cost_guardrails.create_profit_report") as mock_create_report,
            patch("d11_orchestration.cost_guardrails.PREFECT_AVAILABLE", False),
        ):
            mock_logger.return_value = MagicMock()
            mock_get_metrics.return_value = mock_metrics
            mock_create_report.return_value = "Empty profit report"

            # Mock database query for bucket performance
            mock_db = MagicMock()
            mock_session_local.return_value.__enter__.return_value = mock_db
            mock_db.execute.return_value.fetchall.return_value = []

            result = profit_snapshot_flow.fn()

            assert result["metrics"] == mock_metrics
            assert result["top_buckets"] == []
            assert result["report"] == "Empty profit report"

    def test_check_costs_now(self):
        """Test check_costs_now async function"""
        mock_result = {"alert_level": "ok", "budget_used_percentage": 0.6}

        with patch("d11_orchestration.cost_guardrails.cost_guardrail_flow") as mock_flow:
            mock_flow.return_value = mock_result

            import asyncio

            result = asyncio.run(check_costs_now())

            assert result == mock_result

    def test_monitor_monthly_budget_now(self):
        """Test monitor_monthly_budget_now async function"""
        mock_result = {"alert_level": "warning", "percentage_used": 0.8}

        with patch("d11_orchestration.cost_guardrails.monthly_budget_monitor_flow") as mock_flow:
            mock_flow.return_value = mock_result

            import asyncio

            result = asyncio.run(monitor_monthly_budget_now())

            assert result == mock_result

    def test_generate_profit_report_now(self):
        """Test generate_profit_report_now async function"""
        mock_result = {"metrics": {"total_profit": 2000.0}, "period_days": 14}

        with patch("d11_orchestration.cost_guardrails.profit_snapshot_flow") as mock_flow:
            mock_flow.return_value = mock_result

            import asyncio

            result = asyncio.run(generate_profit_report_now(days=14))

            assert result == mock_result
            mock_flow.assert_called_with(lookback_days=14)

    def test_create_guardrail_deployment(self):
        """Test create_guardrail_deployment function"""
        with patch("d11_orchestration.cost_guardrails.Deployment") as mock_deployment:
            mock_deployment.build_from_flow.return_value = MagicMock()

            deployment = create_guardrail_deployment()

            assert deployment is not None
            mock_deployment.build_from_flow.assert_called_once()

    def test_create_profit_snapshot_deployment(self):
        """Test create_profit_snapshot_deployment function"""
        with patch("d11_orchestration.cost_guardrails.Deployment") as mock_deployment:
            mock_deployment.build_from_flow.return_value = MagicMock()

            deployment = create_profit_snapshot_deployment()

            assert deployment is not None
            mock_deployment.build_from_flow.assert_called_once()

    def test_create_monthly_budget_monitor_deployment(self):
        """Test create_monthly_budget_monitor_deployment function"""
        with patch("d11_orchestration.cost_guardrails.Deployment") as mock_deployment:
            mock_deployment.build_from_flow.return_value = MagicMock()

            deployment = create_monthly_budget_monitor_deployment()

            assert deployment is not None
            mock_deployment.build_from_flow.assert_called_once()
