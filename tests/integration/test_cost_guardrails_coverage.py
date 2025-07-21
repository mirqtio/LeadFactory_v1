"""
Comprehensive test coverage for P2-040 cost_guardrails module
Ensures ≥80% coverage for validation requirements
"""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from d11_orchestration.cost_guardrails import (
    check_budget_threshold,
    check_costs_now,
    cost_guardrail_flow,
    create_guardrail_deployment,
    create_profit_report,
    create_profit_snapshot_deployment,
    generate_profit_report_now,
    get_daily_costs,
    get_profit_metrics,
    pause_expensive_operations,
    profit_snapshot_flow,
)


class TestMockPrefectImports:
    """Test mock Prefect imports when Prefect unavailable"""

    def test_mock_imports_coverage(self):
        """Test mock Prefect imports coverage by simulating ImportError"""
        import importlib
        import sys

        # Force a temporary PREFECT_AVAILABLE=False state to test mock imports
        with patch.dict(
            sys.modules,
            {
                "prefect": None,
                "prefect.artifacts": None,
                "prefect.deployments": None,
                "prefect.logging": None,
                "prefect.server.schemas.schedules": None,
            },
        ):
            # Remove the module if already imported
            if "d11_orchestration.cost_guardrails" in sys.modules:
                del sys.modules["d11_orchestration.cost_guardrails"]

            # Mock the import to raise ImportError
            original_import = __builtins__["__import__"]

            def mock_import(name, *args, **kwargs):
                if name == "prefect" or name.startswith("prefect."):
                    raise ImportError(f"No module named '{name}'")
                return original_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=mock_import):
                # Import the module which should trigger mock imports
                import d11_orchestration.cost_guardrails as cg_module

                # Test that mock functions exist and work
                assert hasattr(cg_module, "flow")
                assert hasattr(cg_module, "task")
                assert hasattr(cg_module, "get_run_logger")
                assert hasattr(cg_module, "Deployment")
                assert hasattr(cg_module, "CronSchedule")
                assert hasattr(cg_module, "IntervalSchedule")
                assert hasattr(cg_module, "create_markdown_artifact")

                # Test mock decorators
                @cg_module.flow(retries=2, retry_delay_seconds=60)
                def test_flow():
                    return "test"

                @cg_module.task(retries=1, retry_delay_seconds=30)
                def test_task():
                    return "test"

                # Verify decorator attributes
                assert test_flow.retries == 2
                assert test_flow.retry_delay_seconds == 60
                assert test_task.retries == 1
                assert test_task.retry_delay_seconds == 30

                # Test mock classes and functions
                logger = cg_module.get_run_logger()
                assert logger is not None

                deployment = cg_module.Deployment.build_from_flow(flow=test_flow, name="test")
                assert deployment is not None

                cron_schedule = cg_module.CronSchedule("0 6 * * *")
                assert cron_schedule.cron == "0 6 * * *"

                interval_schedule = cg_module.IntervalSchedule(timedelta(hours=1))
                assert interval_schedule.interval == timedelta(hours=1)

                # Test artifact function (captures print output)
                cg_module.create_markdown_artifact("test markdown", "test-key")


class TestBudgetCircuitBreakerFunctions:
    """Test budget circuit breaker helper functions"""

    def test_get_monthly_costs_with_data(self):
        """Test get_monthly_costs function with database data"""
        with patch("d11_orchestration.cost_guardrails.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db

            # Mock monthly costs query results
            mock_results = [
                MagicMock(monthly_cost=1200.0),  # Aggregated costs
                MagicMock(monthly_cost=300.0),  # Individual costs
            ]
            mock_db.execute.return_value.fetchall.return_value = mock_results

            from d11_orchestration.cost_guardrails import get_monthly_costs

            result = get_monthly_costs()

            assert result == Decimal("1500.0")
            mock_db.execute.assert_called_once()

    def test_check_monthly_budget_limit_under_budget(self):
        """Test check_monthly_budget_limit when under budget"""
        with (
            patch("d11_orchestration.cost_guardrails.get_monthly_costs") as mock_costs,
            patch("d11_orchestration.cost_guardrails.get_settings") as mock_settings,
        ):
            mock_costs.return_value = Decimal("2000.0")
            mock_settings.return_value.guardrail_global_monthly_limit = 3000.0

            from d11_orchestration.cost_guardrails import check_monthly_budget_limit

            is_exceeded, current_spend, monthly_limit = check_monthly_budget_limit()

            assert not is_exceeded
            assert current_spend == Decimal("2000.0")
            assert monthly_limit == Decimal("3000.0")

    def test_check_monthly_budget_limit_over_budget(self):
        """Test check_monthly_budget_limit when over budget"""
        with (
            patch("d11_orchestration.cost_guardrails.get_monthly_costs") as mock_costs,
            patch("d11_orchestration.cost_guardrails.get_settings") as mock_settings,
        ):
            mock_costs.return_value = Decimal("3500.0")
            mock_settings.return_value.guardrail_global_monthly_limit = 3000.0

            from d11_orchestration.cost_guardrails import check_monthly_budget_limit

            is_exceeded, current_spend, monthly_limit = check_monthly_budget_limit()

            assert is_exceeded
            assert current_spend == Decimal("3500.0")
            assert monthly_limit == Decimal("3000.0")

    def test_budget_exception_initialization(self):
        """Test BudgetExceededException initialization"""
        from d11_orchestration.cost_guardrails import BudgetExceededException

        # Test with default message
        exc = BudgetExceededException(Decimal("3500.0"), Decimal("3000.0"))
        assert exc.current_spend == Decimal("3500.0")
        assert exc.monthly_limit == Decimal("3000.0")
        assert "Monthly budget exceeded: $3500.0 / $3000.0" in str(exc)

        # Test with custom message
        exc_custom = BudgetExceededException(Decimal("3500.0"), Decimal("3000.0"), "Custom message")
        assert str(exc_custom) == "Custom message"

    def test_budget_circuit_breaker_allows_execution(self):
        """Test budget circuit breaker allows execution when under budget"""
        with patch("d11_orchestration.cost_guardrails.check_monthly_budget_limit") as mock_check:
            mock_check.return_value = (False, Decimal("2000.0"), Decimal("3000.0"))

            from d11_orchestration.cost_guardrails import budget_circuit_breaker

            @budget_circuit_breaker
            def test_flow():
                return "flow_executed"

            result = test_flow()
            assert result == "flow_executed"
            mock_check.assert_called_once()

    def test_budget_circuit_breaker_blocks_execution(self):
        """Test budget circuit breaker blocks execution when over budget"""
        with (
            patch("d11_orchestration.cost_guardrails.check_monthly_budget_limit") as mock_check,
            patch("d11_orchestration.cost_guardrails.send_cost_alert") as mock_alert,
            patch("d11_orchestration.cost_guardrails.asyncio.run") as mock_asyncio,
        ):
            mock_check.return_value = (True, Decimal("3500.0"), Decimal("3000.0"))

            from d11_orchestration.cost_guardrails import BudgetExceededException, budget_circuit_breaker

            @budget_circuit_breaker
            def test_flow():
                return "should_not_execute"

            with pytest.raises(BudgetExceededException) as exc_info:
                test_flow()

            # Verify exception details
            assert exc_info.value.current_spend == Decimal("3500.0")
            assert exc_info.value.monthly_limit == Decimal("3000.0")

            # Verify alert was attempted (check if send_cost_alert was called)
            # Note: asyncio.run may not be called if event loop handling succeeds
            assert mock_alert.called or mock_asyncio.called

    def test_budget_circuit_breaker_alert_failure_handling(self):
        """Test budget circuit breaker handles alert failures gracefully"""
        with (
            patch("d11_orchestration.cost_guardrails.check_monthly_budget_limit") as mock_check,
            patch("d11_orchestration.cost_guardrails.send_cost_alert", side_effect=Exception("Alert failed")),
            patch("d11_orchestration.cost_guardrails.get_run_logger") as mock_logger,
            patch("d11_orchestration.cost_guardrails.PREFECT_AVAILABLE", True),
            patch("d11_orchestration.cost_guardrails.asyncio.run"),
        ):
            mock_check.return_value = (True, Decimal("3500.0"), Decimal("3000.0"))
            mock_logger_instance = MagicMock()
            mock_logger.return_value = mock_logger_instance

            from d11_orchestration.cost_guardrails import BudgetExceededException, budget_circuit_breaker

            @budget_circuit_breaker
            def test_flow():
                return "should_not_execute"

            # Should still raise BudgetExceededException even if alert fails
            with pytest.raises(BudgetExceededException):
                test_flow()

            # Should log the alert failure
            mock_logger_instance.error.assert_called_with("Failed to send budget alert: Alert failed")

    def test_budget_circuit_breaker_no_logger_when_prefect_unavailable(self):
        """Test budget circuit breaker when Prefect unavailable and alert fails"""
        with (
            patch("d11_orchestration.cost_guardrails.check_monthly_budget_limit") as mock_check,
            patch("d11_orchestration.cost_guardrails.send_cost_alert", side_effect=Exception("Alert failed")),
            patch("d11_orchestration.cost_guardrails.PREFECT_AVAILABLE", False),
            patch("d11_orchestration.cost_guardrails.asyncio.run"),
        ):
            mock_check.return_value = (True, Decimal("3500.0"), Decimal("3000.0"))

            from d11_orchestration.cost_guardrails import BudgetExceededException, budget_circuit_breaker

            @budget_circuit_breaker
            def test_flow():
                return "should_not_execute"

            # Should still raise BudgetExceededException even without logger
            with pytest.raises(BudgetExceededException):
                test_flow()

    def test_budget_circuit_breaker_asyncio_runtime_error(self):
        """Test budget circuit breaker handles asyncio RuntimeError"""
        with (
            patch("d11_orchestration.cost_guardrails.check_monthly_budget_limit") as mock_check,
            patch("d11_orchestration.cost_guardrails.send_cost_alert") as mock_alert,
            patch("d11_orchestration.cost_guardrails.asyncio.get_event_loop", side_effect=RuntimeError),
            patch("d11_orchestration.cost_guardrails.asyncio.run") as mock_asyncio_run,
        ):
            mock_check.return_value = (True, Decimal("3100.0"), Decimal("3000.0"))

            from d11_orchestration.cost_guardrails import BudgetExceededException, budget_circuit_breaker

            @budget_circuit_breaker
            def test_flow():
                return "should_not_execute"

            with pytest.raises(BudgetExceededException):
                test_flow()

            # Should fall back to asyncio.run when get_event_loop fails
            mock_asyncio_run.assert_called_once()

    def test_budget_circuit_breaker_successful_event_loop(self):
        """Test budget circuit breaker with successful event loop"""
        with (
            patch("d11_orchestration.cost_guardrails.check_monthly_budget_limit") as mock_check,
            patch("d11_orchestration.cost_guardrails.send_cost_alert") as mock_alert,
            patch("d11_orchestration.cost_guardrails.asyncio.get_event_loop") as mock_get_loop,
        ):
            mock_check.return_value = (True, Decimal("3200.0"), Decimal("3000.0"))
            mock_loop = MagicMock()
            mock_get_loop.return_value = mock_loop

            from d11_orchestration.cost_guardrails import BudgetExceededException, budget_circuit_breaker

            @budget_circuit_breaker
            def test_flow():
                return "should_not_execute"

            with pytest.raises(BudgetExceededException):
                test_flow()

            # Should use existing event loop
            mock_loop.run_until_complete.assert_called_once()

    def test_budget_circuit_breaker_guardrail_violation_creation(self):
        """Test budget circuit breaker creates proper GuardrailViolation"""
        with (
            patch("d11_orchestration.cost_guardrails.check_monthly_budget_limit") as mock_check,
            patch("d11_orchestration.cost_guardrails.send_cost_alert") as mock_alert,
            patch("d11_orchestration.cost_guardrails.asyncio.run"),
        ):
            mock_check.return_value = (True, Decimal("3400.0"), Decimal("3000.0"))

            from d11_orchestration.cost_guardrails import BudgetExceededException, budget_circuit_breaker

            @budget_circuit_breaker
            def business_flow(business_id="test123"):
                return f"processed_{business_id}"

            with pytest.raises(BudgetExceededException):
                business_flow(business_id="test_business")

            # Verify GuardrailViolation was created with correct data
            mock_alert.assert_called_once()
            violation = mock_alert.call_args[0][0]
            assert violation.limit_name == "monthly_budget_circuit_breaker"
            assert violation.current_spend == Decimal("3400.0")
            assert violation.limit_amount == Decimal("3000.0")
            assert violation.percentage_used == float(Decimal("3400.0") / Decimal("3000.0"))
            assert violation.metadata["flow_name"] == "business_flow"
            assert violation.metadata["action"] == "flow_blocked"
            assert violation.metadata["auto_resume"] == "next_month"


class TestDailyCostsFunctions:
    """Test daily costs and budget threshold functions"""

    def test_get_daily_costs_with_data(self):
        """Test get_daily_costs returns provider breakdown"""
        with (
            patch("d11_orchestration.cost_guardrails.SessionLocal") as mock_session,
            patch("d11_orchestration.cost_guardrails.get_run_logger") as mock_logger,
        ):
            # Mock database response
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db

            # Mock provider costs
            mock_results = [
                MagicMock(provider="openai", total_cost=50.0),
                MagicMock(provider="dataaxle", total_cost=100.0),
            ]
            mock_db.execute.return_value.fetchall.return_value = mock_results

            # Mock total cost
            mock_total = MagicMock(total=150.0)
            mock_db.execute.return_value.fetchone.return_value = mock_total

            result = get_daily_costs.fn()

            assert result["openai"] == 50.0
            assert result["dataaxle"] == 100.0
            assert result["total"] == 150.0
            mock_logger.return_value.info.assert_called_with("Daily costs: $150.00")

    def test_get_daily_costs_no_data(self):
        """Test get_daily_costs with empty database"""
        with (
            patch("d11_orchestration.cost_guardrails.SessionLocal") as mock_session,
            patch("d11_orchestration.cost_guardrails.get_run_logger"),
        ):
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db

            # Mock empty results
            mock_db.execute.return_value.fetchall.return_value = []
            mock_db.execute.return_value.fetchone.return_value = None

            result = get_daily_costs.fn()

            assert result["total"] == 0.0

    def test_check_budget_threshold_ok(self):
        """Test budget threshold check when under limit"""
        with patch("d11_orchestration.cost_guardrails.get_run_logger") as mock_logger:
            daily_costs = {"total": 50.0}
            daily_budget = 100.0

            is_over, percentage_used, alert_level = check_budget_threshold.fn(daily_costs, daily_budget)

            assert not is_over
            assert percentage_used == 0.5
            assert alert_level == "ok"
            mock_logger.return_value.info.assert_called_with("Budget OK: $50.00 / $100.00 (50.0%)")

    def test_check_budget_threshold_warning(self):
        """Test budget threshold warning level"""
        with patch("d11_orchestration.cost_guardrails.get_run_logger") as mock_logger:
            daily_costs = {"total": 85.0}
            daily_budget = 100.0

            is_over, percentage_used, alert_level = check_budget_threshold.fn(daily_costs, daily_budget, 0.8)

            assert is_over
            assert percentage_used == 0.85
            assert alert_level == "warning"
            mock_logger.return_value.warning.assert_called()

    def test_check_budget_threshold_critical(self):
        """Test budget threshold critical level"""
        with patch("d11_orchestration.cost_guardrails.get_run_logger") as mock_logger:
            daily_costs = {"total": 110.0}
            daily_budget = 100.0

            is_over, percentage_used, alert_level = check_budget_threshold.fn(daily_costs, daily_budget)

            assert is_over
            assert percentage_used == 1.1
            assert alert_level == "critical"
            mock_logger.return_value.error.assert_called()

    def test_pause_expensive_operations(self):
        """Test pausing expensive provider operations"""
        with patch("d11_orchestration.cost_guardrails.get_run_logger") as mock_logger:
            providers = ["openai", "dataaxle"]

            result = pause_expensive_operations.fn(providers)

            assert result["openai"] is True
            assert result["dataaxle"] is True
            assert mock_logger.return_value.warning.call_count == 2


class TestProfitMetricsFunctions:
    """Test profit metrics and reporting functions"""

    def test_get_profit_metrics_with_data(self):
        """Test profit metrics calculation"""
        with (
            patch("d11_orchestration.cost_guardrails.SessionLocal") as mock_session,
            patch("d11_orchestration.cost_guardrails.get_run_logger"),
        ):
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db

            # Mock profit data
            mock_result = MagicMock(
                total_revenue=1000.0,
                total_cost=600.0,
                total_profit=400.0,
                avg_roi=0.67,
                avg_cpa=50.0,
                total_purchases=20,
            )
            mock_db.execute.return_value.fetchone.return_value = mock_result

            result = get_profit_metrics.fn(7)

            assert result["total_revenue"] == 1000.0
            assert result["total_cost"] == 600.0
            assert result["total_profit"] == 400.0
            assert result["avg_roi"] == 0.67
            assert result["avg_cpa"] == 50.0
            assert result["total_purchases"] == 20

    def test_get_profit_metrics_no_data(self):
        """Test profit metrics with empty database"""
        with (
            patch("d11_orchestration.cost_guardrails.SessionLocal") as mock_session,
            patch("d11_orchestration.cost_guardrails.get_run_logger"),
        ):
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db
            mock_db.execute.return_value.fetchone.return_value = None

            result = get_profit_metrics.fn(7)

            assert result["total_revenue"] == 0.0
            assert result["total_cost"] == 0.0
            assert result["total_profit"] == 0.0

    def test_create_profit_report(self):
        """Test profit report generation"""
        with patch("d11_orchestration.cost_guardrails.get_run_logger"):
            metrics = {
                "total_revenue": 1000.0,
                "total_cost": 600.0,
                "total_profit": 400.0,
                "avg_roi": 0.67,
                "avg_cpa": 50.0,
                "total_purchases": 20,
            }
            bucket_performance = [
                {
                    "geo_bucket": "US",
                    "vert_bucket": "tech",
                    "total_businesses": 100,
                    "total_revenue_usd": 500.0,
                    "profit_usd": 200.0,
                    "roi": 0.4,
                }
            ]

            report = create_profit_report.fn(metrics, bucket_performance, 7)

            assert "Profit Snapshot Report" in report
            assert "$1,000.00" in report
            assert "$400.00" in report
            assert "67.0%" in report
            assert "US" in report
            assert "tech" in report


class TestFlowFunctions:
    """Test Prefect flow functions"""

    @patch("d11_orchestration.cost_guardrails.PREFECT_AVAILABLE", False)
    def test_cost_guardrail_flow_normal(self):
        """Test cost guardrail flow under normal conditions"""
        with (
            patch("d11_orchestration.cost_guardrails.get_settings") as mock_settings,
            patch("d11_orchestration.cost_guardrails.get_daily_costs") as mock_costs,
            patch("d11_orchestration.cost_guardrails.check_budget_threshold") as mock_threshold,
            patch("d11_orchestration.cost_guardrails.get_run_logger") as mock_logger,
            patch("d11_orchestration.cost_guardrails.create_markdown_artifact"),
        ):
            mock_settings.return_value.cost_budget_usd = 100.0
            mock_costs.return_value = {"total": 50.0}
            mock_threshold.return_value = (False, 0.5, "ok")
            mock_logger.return_value = MagicMock()

            from d11_orchestration.cost_guardrails import cost_guardrail_flow

            result = cost_guardrail_flow()

            assert result["alert_level"] == "ok"
            assert result["budget_used_percentage"] == 0.5
            assert result["paused_providers"] == {}

    @patch("d11_orchestration.cost_guardrails.PREFECT_AVAILABLE", False)
    def test_cost_guardrail_flow_critical(self):
        """Test cost guardrail flow in critical state"""
        with (
            patch("d11_orchestration.cost_guardrails.get_settings") as mock_settings,
            patch("d11_orchestration.cost_guardrails.get_daily_costs") as mock_costs,
            patch("d11_orchestration.cost_guardrails.check_budget_threshold") as mock_threshold,
            patch("d11_orchestration.cost_guardrails.pause_expensive_operations") as mock_pause,
            patch("d11_orchestration.cost_guardrails.get_run_logger") as mock_logger,
            patch("d11_orchestration.cost_guardrails.create_markdown_artifact"),
        ):
            mock_settings.return_value.cost_budget_usd = 100.0
            mock_costs.return_value = {"total": 110.0}
            mock_threshold.return_value = (True, 1.1, "critical")
            mock_pause.return_value = {"openai": True}
            mock_logger.return_value = MagicMock()

            from d11_orchestration.cost_guardrails import cost_guardrail_flow

            result = cost_guardrail_flow()

            assert result["alert_level"] == "critical"
            assert result["budget_used_percentage"] == 1.1
            assert result["paused_providers"] == {"openai": True}

    @patch("d11_orchestration.cost_guardrails.PREFECT_AVAILABLE", False)
    def test_profit_snapshot_flow(self):
        """Test profit snapshot flow"""
        with (
            patch("d11_orchestration.cost_guardrails.get_profit_metrics") as mock_metrics,
            patch("d11_orchestration.cost_guardrails.SessionLocal") as mock_session,
            patch("d11_orchestration.cost_guardrails.create_profit_report") as mock_report,
            patch("d11_orchestration.cost_guardrails.get_run_logger") as mock_logger,
            patch("d11_orchestration.cost_guardrails.create_markdown_artifact"),
        ):
            mock_metrics.return_value = {"total_profit": 400.0, "avg_roi": 0.67}
            mock_logger.return_value = MagicMock()

            # Mock database for bucket performance
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db
            mock_db.execute.return_value.fetchall.return_value = []

            mock_report.return_value = "Test Report"

            from d11_orchestration.cost_guardrails import profit_snapshot_flow

            result = profit_snapshot_flow(7, 5)

            assert result["metrics"]["total_profit"] == 400.0
            assert result["period_days"] == 7
            assert result["report"] == "Test Report"

    @patch("d11_orchestration.cost_guardrails.PREFECT_AVAILABLE", True)
    def test_cost_guardrail_flow_with_prefect_artifact(self):
        """Test cost guardrail flow with Prefect artifact creation"""
        with (
            patch("d11_orchestration.cost_guardrails.get_settings") as mock_settings,
            patch("d11_orchestration.cost_guardrails.get_daily_costs") as mock_costs,
            patch("d11_orchestration.cost_guardrails.check_budget_threshold") as mock_threshold,
            patch("d11_orchestration.cost_guardrails.get_run_logger") as mock_logger,
            patch("d11_orchestration.cost_guardrails.create_markdown_artifact") as mock_artifact,
        ):
            mock_settings.return_value.cost_budget_usd = 100.0
            mock_costs.return_value = {"total": 50.0, "openai": 30.0, "dataaxle": 20.0}
            mock_threshold.return_value = (False, 0.5, "ok")
            mock_logger.return_value = MagicMock()

            from d11_orchestration.cost_guardrails import cost_guardrail_flow

            result = cost_guardrail_flow()

            assert result["alert_level"] == "ok"
            mock_artifact.assert_called_once()

            # Verify artifact content
            call_args = mock_artifact.call_args
            assert "Cost Guardrail Alert" in call_args.kwargs["markdown"]
            assert "OK" in call_args.kwargs["markdown"]
            assert call_args.kwargs["key"] == "cost-guardrail-alert"

    @patch("d11_orchestration.cost_guardrails.PREFECT_AVAILABLE", True)
    def test_profit_snapshot_flow_with_prefect_artifact(self):
        """Test profit snapshot flow with Prefect artifact creation"""
        with (
            patch("d11_orchestration.cost_guardrails.get_profit_metrics") as mock_metrics,
            patch("d11_orchestration.cost_guardrails.SessionLocal") as mock_session,
            patch("d11_orchestration.cost_guardrails.create_profit_report") as mock_report,
            patch("d11_orchestration.cost_guardrails.get_run_logger") as mock_logger,
            patch("d11_orchestration.cost_guardrails.create_markdown_artifact") as mock_artifact,
        ):
            mock_metrics.return_value = {"total_profit": 400.0, "avg_roi": 0.67}
            mock_logger.return_value = MagicMock()

            # Mock database for bucket performance
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db
            mock_db.execute.return_value.fetchall.return_value = []

            mock_report.return_value = "Test Report"

            from d11_orchestration.cost_guardrails import profit_snapshot_flow

            result = profit_snapshot_flow(7, 5)

            assert result["metrics"]["total_profit"] == 400.0
            mock_artifact.assert_called_once_with(markdown="Test Report", key="profit-snapshot")


class TestDeploymentFunctions:
    """Test deployment configuration functions"""

    def test_create_guardrail_deployment(self):
        """Test guardrail deployment creation"""
        with patch("d11_orchestration.cost_guardrails.Deployment") as mock_deployment:
            deployment = create_guardrail_deployment()

            mock_deployment.build_from_flow.assert_called_once()
            assert deployment is not None

    def test_create_profit_snapshot_deployment(self):
        """Test profit snapshot deployment creation"""
        with patch("d11_orchestration.cost_guardrails.Deployment") as mock_deployment:
            deployment = create_profit_snapshot_deployment()

            mock_deployment.build_from_flow.assert_called_once()
            assert deployment is not None


class TestManualTriggers:
    """Test manual trigger functions"""

    @pytest.mark.asyncio
    async def test_check_costs_now(self):
        """Test manual cost check trigger"""
        with patch("d11_orchestration.cost_guardrails.cost_guardrail_flow") as mock_flow:
            mock_flow.return_value = {"alert_level": "ok"}

            result = await check_costs_now()

            assert result["alert_level"] == "ok"
            mock_flow.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_profit_report_now(self):
        """Test manual profit report generation"""
        with patch("d11_orchestration.cost_guardrails.profit_snapshot_flow") as mock_flow:
            mock_flow.return_value = {"metrics": {"total_profit": 400.0}}

            result = await generate_profit_report_now(7)

            assert result["metrics"]["total_profit"] == 400.0
            mock_flow.assert_called_once_with(lookback_days=7)
