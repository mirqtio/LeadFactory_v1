"""
Unit tests for P2-040 budget monitoring task functions
Tests for task functions like get_daily_costs, check_budget_threshold, etc.
"""
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from d11_orchestration.cost_guardrails import (
    check_budget_threshold,
    create_profit_report,
    get_daily_costs,
    get_profit_metrics,
    pause_expensive_operations,
)


class TestBudgetTasks:
    """Test P2-040 budget monitoring task functions"""

    def test_get_daily_costs_with_data(self):
        """Test get_daily_costs task with mock database data"""
        mock_results = [
            MagicMock(provider="openai", total_cost=150.0),
            MagicMock(provider="dataaxle", total_cost=200.0),
            MagicMock(provider="hunter", total_cost=75.0),
        ]
        mock_total_result = MagicMock(total=425.0)

        with patch("d11_orchestration.cost_guardrails.SessionLocal") as mock_session_local, patch(
            "d11_orchestration.cost_guardrails.get_run_logger"
        ) as mock_logger:
            mock_db = MagicMock()
            mock_session_local.return_value.__enter__.return_value = mock_db
            mock_db.execute.return_value.fetchall.return_value = mock_results
            mock_db.execute.return_value.fetchone.return_value = mock_total_result
            mock_logger.return_value = MagicMock()

            result = get_daily_costs.fn()

            expected = {
                "openai": 150.0,
                "dataaxle": 200.0,
                "hunter": 75.0,
                "total": 425.0,
            }
            assert result == expected

    def test_get_daily_costs_no_data(self):
        """Test get_daily_costs task with no database data"""
        with patch("d11_orchestration.cost_guardrails.SessionLocal") as mock_session_local, patch(
            "d11_orchestration.cost_guardrails.get_run_logger"
        ) as mock_logger:
            mock_db = MagicMock()
            mock_session_local.return_value.__enter__.return_value = mock_db
            mock_db.execute.return_value.fetchall.return_value = []
            mock_db.execute.return_value.fetchone.return_value = MagicMock(total=0.0)
            mock_logger.return_value = MagicMock()

            result = get_daily_costs.fn()

            assert result["total"] == 0.0

    def test_check_budget_threshold_ok_status(self):
        """Test check_budget_threshold task with OK status"""
        daily_costs = {"total": 600.0, "openai": 300.0, "dataaxle": 300.0}
        daily_budget = 1000.0

        with patch("d11_orchestration.cost_guardrails.get_run_logger") as mock_logger:
            mock_logger.return_value = MagicMock()

            is_over, percentage_used, alert_level = check_budget_threshold.fn(daily_costs, daily_budget, 0.8)

            assert is_over is False
            assert percentage_used == 0.6  # 600/1000
            assert alert_level == "ok"

    def test_check_budget_threshold_warning_status(self):
        """Test check_budget_threshold task with warning status"""
        daily_costs = {"total": 850.0, "openai": 450.0, "dataaxle": 400.0}
        daily_budget = 1000.0

        with patch("d11_orchestration.cost_guardrails.get_run_logger") as mock_logger:
            mock_logger.return_value = MagicMock()

            is_over, percentage_used, alert_level = check_budget_threshold.fn(daily_costs, daily_budget, 0.8)

            assert is_over is True
            assert percentage_used == 0.85  # 850/1000
            assert alert_level == "warning"

    def test_check_budget_threshold_critical_status(self):
        """Test check_budget_threshold task with critical status"""
        daily_costs = {"total": 1100.0, "openai": 600.0, "dataaxle": 500.0}
        daily_budget = 1000.0

        with patch("d11_orchestration.cost_guardrails.get_run_logger") as mock_logger:
            mock_logger.return_value = MagicMock()

            is_over, percentage_used, alert_level = check_budget_threshold.fn(daily_costs, daily_budget, 0.8)

            assert is_over is True
            assert percentage_used == 1.1  # 1100/1000
            assert alert_level == "critical"

    def test_check_budget_threshold_zero_budget(self):
        """Test check_budget_threshold task with zero budget"""
        daily_costs = {"total": 100.0, "openai": 100.0}
        daily_budget = 0.0

        with patch("d11_orchestration.cost_guardrails.get_run_logger") as mock_logger:
            mock_logger.return_value = MagicMock()

            is_over, percentage_used, alert_level = check_budget_threshold.fn(daily_costs, daily_budget, 0.8)

            assert percentage_used == 0.0
            assert alert_level == "ok"

    def test_pause_expensive_operations(self):
        """Test pause_expensive_operations task"""
        providers_to_pause = ["openai", "dataaxle", "hunter"]

        with patch("d11_orchestration.cost_guardrails.get_run_logger") as mock_logger:
            mock_logger.return_value = MagicMock()

            result = pause_expensive_operations.fn(providers_to_pause)

            expected = {"openai": True, "dataaxle": True, "hunter": True}
            assert result == expected

    def test_get_profit_metrics_with_data(self):
        """Test get_profit_metrics task with mock database data"""
        mock_result = MagicMock(
            total_revenue=5000.0,
            total_cost=3000.0,
            total_profit=2000.0,
            avg_roi=0.67,
            avg_cpa=150.0,
            total_purchases=20,
        )

        with patch("d11_orchestration.cost_guardrails.SessionLocal") as mock_session_local, patch(
            "d11_orchestration.cost_guardrails.get_run_logger"
        ) as mock_logger:
            mock_db = MagicMock()
            mock_session_local.return_value.__enter__.return_value = mock_db
            mock_db.execute.return_value.fetchone.return_value = mock_result
            mock_logger.return_value = MagicMock()

            result = get_profit_metrics.fn(7)

            expected = {
                "total_revenue": 5000.0,
                "total_cost": 3000.0,
                "total_profit": 2000.0,
                "avg_roi": 0.67,
                "avg_cpa": 150.0,
                "total_purchases": 20,
            }
            assert result == expected

    def test_get_profit_metrics_no_data(self):
        """Test get_profit_metrics task with no database data"""
        with patch("d11_orchestration.cost_guardrails.SessionLocal") as mock_session_local, patch(
            "d11_orchestration.cost_guardrails.get_run_logger"
        ) as mock_logger:
            mock_db = MagicMock()
            mock_session_local.return_value.__enter__.return_value = mock_db
            mock_db.execute.return_value.fetchone.return_value = None
            mock_logger.return_value = MagicMock()

            result = get_profit_metrics.fn(7)

            expected = {
                "total_revenue": 0.0,
                "total_cost": 0.0,
                "total_profit": 0.0,
                "avg_roi": 0.0,
                "avg_cpa": 0.0,
                "total_purchases": 0,
            }
            assert result == expected

    def test_create_profit_report(self):
        """Test create_profit_report task"""
        metrics = {
            "total_revenue": 5000.0,
            "total_cost": 3000.0,
            "total_profit": 2000.0,
            "avg_roi": 0.67,
            "avg_cpa": 150.0,
            "total_purchases": 20,
        }

        bucket_performance = [
            {
                "geo_bucket": "US",
                "vert_bucket": "tech",
                "total_businesses": 100,
                "total_revenue_usd": 2000.0,
                "profit_usd": 800.0,
                "roi": 0.40,
            },
            {
                "geo_bucket": "EU",
                "vert_bucket": "finance",
                "total_businesses": 75,
                "total_revenue_usd": 1500.0,
                "profit_usd": 600.0,
                "roi": 0.40,
            },
        ]

        with patch("d11_orchestration.cost_guardrails.get_run_logger") as mock_logger:
            mock_logger.return_value = MagicMock()

            result = create_profit_report.fn(metrics, bucket_performance, 7)

            assert "# Profit Snapshot Report" in result
            assert "Last 7 days" in result
            assert "$5,000.00" in result  # Total revenue
            assert "$3,000.00" in result  # Total cost
            assert "$2,000.00" in result  # Total profit
            assert "US" in result  # Geo bucket
            assert "tech" in result  # Vert bucket
