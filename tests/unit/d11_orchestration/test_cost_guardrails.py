"""
Tests for cost guardrail flows - Phase 0.5 Task OR-09
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from d11_orchestration.cost_guardrails import (
    get_daily_costs,
    check_budget_threshold,
    pause_expensive_operations,
    get_profit_metrics,
    create_profit_report,
    cost_guardrail_flow,
    profit_snapshot_flow,
)

# Mark entire module as xfail for Phase 0.5
pytestmark = pytest.mark.xfail(reason="Phase 0.5 feature", strict=False)


class TestCostGuardrailTasks:
    """Test individual tasks in cost guardrail flows"""

    @patch("d11_orchestration.cost_guardrails.SessionLocal")
    def test_get_daily_costs(self, mock_session):
        """Test getting daily costs by provider"""
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db

        # Mock query results
        mock_results = [
            Mock(provider="openai", total_cost=25.50),
            Mock(provider="dataaxle", total_cost=15.25),
            Mock(provider="sendgrid", total_cost=5.00),
        ]
        mock_total = Mock(total=45.75)

        mock_db.execute.return_value.fetchall.return_value = mock_results
        mock_db.execute.return_value.fetchone.return_value = mock_total

        # Run task
        costs = get_daily_costs()

        # Verify
        assert costs["openai"] == 25.50
        assert costs["dataaxle"] == 15.25
        assert costs["sendgrid"] == 5.00
        assert costs["total"] == 45.75

    def test_check_budget_threshold_ok(self):
        """Test budget check when under threshold"""
        daily_costs = {"total": 500.0}
        daily_budget = 1000.0

        is_over, percentage, alert_level = check_budget_threshold(
            daily_costs, daily_budget, warning_threshold=0.8
        )

        assert not is_over
        assert percentage == 0.5  # 50%
        assert alert_level == "ok"

    def test_check_budget_threshold_warning(self):
        """Test budget check when approaching limit"""
        daily_costs = {"total": 850.0}
        daily_budget = 1000.0

        is_over, percentage, alert_level = check_budget_threshold(
            daily_costs, daily_budget, warning_threshold=0.8
        )

        assert is_over
        assert percentage == 0.85  # 85%
        assert alert_level == "warning"

    def test_check_budget_threshold_critical(self):
        """Test budget check when over limit"""
        daily_costs = {"total": 1200.0}
        daily_budget = 1000.0

        is_over, percentage, alert_level = check_budget_threshold(
            daily_costs, daily_budget, warning_threshold=0.8
        )

        assert is_over
        assert percentage == 1.2  # 120%
        assert alert_level == "critical"

    def test_pause_expensive_operations(self):
        """Test pausing expensive provider operations"""
        providers = ["openai", "dataaxle", "hunter"]

        paused = pause_expensive_operations(providers)

        assert paused["openai"] is True
        assert paused["dataaxle"] is True
        assert paused["hunter"] is True
        assert len(paused) == 3

    @patch("d11_orchestration.cost_guardrails.SessionLocal")
    def test_get_profit_metrics(self, mock_session):
        """Test getting profit metrics"""
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db

        # Mock query result
        mock_result = Mock(
            total_revenue=5000.0,
            total_cost=3000.0,
            total_profit=2000.0,
            avg_roi=0.67,
            avg_cpa=50.0,
            total_purchases=60,
        )

        mock_db.execute.return_value.fetchone.return_value = mock_result

        # Run task
        metrics = get_profit_metrics(lookback_days=7)

        # Verify
        assert metrics["total_revenue"] == 5000.0
        assert metrics["total_cost"] == 3000.0
        assert metrics["total_profit"] == 2000.0
        assert metrics["avg_roi"] == 0.67
        assert metrics["avg_cpa"] == 50.0
        assert metrics["total_purchases"] == 60

    def test_create_profit_report(self):
        """Test creating profit report markdown"""
        metrics = {
            "total_revenue": 5000.0,
            "total_cost": 3000.0,
            "total_profit": 2000.0,
            "avg_roi": 0.67,
            "avg_cpa": 50.0,
            "total_purchases": 60,
        }

        bucket_performance = [
            {
                "geo_bucket": "high-high-high",
                "vert_bucket": "high-high-medium",
                "total_businesses": 100,
                "total_revenue_usd": 2000.0,
                "profit_usd": 1000.0,
                "roi": 1.0,
            },
            {
                "geo_bucket": "medium-medium-medium",
                "vert_bucket": "medium-medium-low",
                "total_businesses": 150,
                "total_revenue_usd": 1500.0,
                "profit_usd": 500.0,
                "roi": 0.5,
            },
        ]

        report = create_profit_report(metrics, bucket_performance, period_days=7)

        # Verify report contains key information
        assert "# Profit Snapshot Report" in report
        assert "Last 7 days" in report
        assert "$5,000.00" in report  # Revenue
        assert "$2,000.00" in report  # Profit
        assert "67.0%" in report  # ROI
        assert "high-high-high" in report
        assert "high-high-medium" in report


class TestCostGuardrailFlows:
    """Test complete cost guardrail flows"""

    @patch("d11_orchestration.cost_guardrails.get_settings")
    @patch("d11_orchestration.cost_guardrails.get_daily_costs")
    @patch("d11_orchestration.cost_guardrails.check_budget_threshold")
    @patch("d11_orchestration.cost_guardrails.pause_expensive_operations")
    def test_cost_guardrail_flow_under_budget(
        self, mock_pause, mock_check, mock_get_costs, mock_settings
    ):
        """Test cost guardrail flow when under budget"""
        # Mock settings
        mock_settings.return_value.cost_budget_usd = 1000.0

        # Mock tasks
        mock_get_costs.return_value = {"total": 500.0, "openai": 300.0}
        mock_check.return_value = (False, 0.5, "ok")

        # Run flow
        result = cost_guardrail_flow()

        # Verify
        assert result["alert_level"] == "ok"
        assert result["budget_used_percentage"] == 0.5
        assert result["paused_providers"] == {}
        assert not mock_pause.called

    @patch("d11_orchestration.cost_guardrails.get_settings")
    @patch("d11_orchestration.cost_guardrails.get_daily_costs")
    @patch("d11_orchestration.cost_guardrails.check_budget_threshold")
    @patch("d11_orchestration.cost_guardrails.pause_expensive_operations")
    def test_cost_guardrail_flow_over_budget(
        self, mock_pause, mock_check, mock_get_costs, mock_settings
    ):
        """Test cost guardrail flow when over budget"""
        # Mock settings
        mock_settings.return_value.cost_budget_usd = 1000.0

        # Mock tasks
        mock_get_costs.return_value = {"total": 1200.0, "openai": 800.0}
        mock_check.return_value = (True, 1.2, "critical")
        mock_pause.return_value = {"openai": True, "dataaxle": True}

        # Run flow
        result = cost_guardrail_flow(expensive_providers=["openai", "dataaxle"])

        # Verify
        assert result["alert_level"] == "critical"
        assert result["budget_used_percentage"] == 1.2
        assert result["paused_providers"] == {"openai": True, "dataaxle": True}
        mock_pause.assert_called_once_with(["openai", "dataaxle"])

    @patch("d11_orchestration.cost_guardrails.get_profit_metrics")
    @patch("d11_orchestration.cost_guardrails.SessionLocal")
    @patch("d11_orchestration.cost_guardrails.create_profit_report")
    def test_profit_snapshot_flow(
        self, mock_create_report, mock_session, mock_get_metrics
    ):
        """Test profit snapshot flow"""
        # Mock profit metrics
        mock_get_metrics.return_value = {
            "total_revenue": 5000.0,
            "total_cost": 3000.0,
            "total_profit": 2000.0,
            "avg_roi": 0.67,
            "avg_cpa": 50.0,
            "total_purchases": 60,
        }

        # Mock bucket performance query
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db

        mock_buckets = [
            Mock(
                geo_bucket="high-high-high",
                vert_bucket="high-high-medium",
                total_businesses=100,
                total_revenue_usd=2000.0,
                profit_usd=1000.0,
                roi=1.0,
            )
        ]

        mock_db.execute.return_value.fetchall.return_value = mock_buckets

        # Mock report creation
        mock_create_report.return_value = "# Test Report"

        # Run flow
        result = profit_snapshot_flow(lookback_days=7)

        # Verify
        assert result["metrics"]["total_profit"] == 2000.0
        assert result["metrics"]["avg_roi"] == 0.67
        assert len(result["top_buckets"]) == 1
        assert result["top_buckets"][0]["geo_bucket"] == "high-high-high"
        assert result["period_days"] == 7
        assert result["report"] == "# Test Report"
