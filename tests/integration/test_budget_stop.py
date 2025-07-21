"""
Integration tests for P2-040 Orchestration Budget Stop
Tests monthly spend circuit breaker functionality
"""

from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from d11_orchestration.cost_guardrails import (
    BudgetExceededException,
    budget_circuit_breaker,
    check_monthly_budget_limit,
    get_monthly_costs,
)


class TestBudgetCircuitBreaker:
    """Test P2-040 budget circuit breaker functionality"""

    def test_get_monthly_costs_calculation(self):
        """Test monthly cost calculation includes both aggregated and individual costs"""
        with patch("d11_orchestration.cost_guardrails.SessionLocal") as mock_session:
            # Mock database response
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db

            # Mock query results - simulating $1500 total spend
            mock_result = [
                MagicMock(monthly_cost=1200.0),  # Aggregated costs
                MagicMock(monthly_cost=300.0),  # Individual costs
            ]
            mock_db.execute.return_value.fetchall.return_value = mock_result

            monthly_cost = get_monthly_costs()

            assert monthly_cost == Decimal("1500.0")
            assert mock_db.execute.called

    def test_check_monthly_budget_limit_under_budget(self):
        """Test budget check when under monthly limit"""
        with (
            patch("d11_orchestration.cost_guardrails.get_monthly_costs") as mock_costs,
            patch("d11_orchestration.cost_guardrails.get_settings") as mock_settings,
        ):
            # Mock current spend under limit
            mock_costs.return_value = Decimal("2000.0")
            mock_settings.return_value.guardrail_global_monthly_limit = 3000.0

            is_exceeded, current_spend, monthly_limit = check_monthly_budget_limit()

            assert not is_exceeded
            assert current_spend == Decimal("2000.0")
            assert monthly_limit == Decimal("3000.0")

    def test_check_monthly_budget_limit_over_budget(self):
        """Test budget check when over monthly limit"""
        with (
            patch("d11_orchestration.cost_guardrails.get_monthly_costs") as mock_costs,
            patch("d11_orchestration.cost_guardrails.get_settings") as mock_settings,
        ):
            # Mock current spend over limit
            mock_costs.return_value = Decimal("3500.0")
            mock_settings.return_value.guardrail_global_monthly_limit = 3000.0

            is_exceeded, current_spend, monthly_limit = check_monthly_budget_limit()

            assert is_exceeded
            assert current_spend == Decimal("3500.0")
            assert monthly_limit == Decimal("3000.0")

    def test_budget_circuit_breaker_allows_execution_under_budget(self):
        """Test circuit breaker allows flow execution when under budget"""
        with patch("d11_orchestration.cost_guardrails.check_monthly_budget_limit") as mock_check:
            # Mock under budget
            mock_check.return_value = (False, Decimal("2000.0"), Decimal("3000.0"))

            @budget_circuit_breaker
            def test_flow():
                return "flow_executed"

            result = test_flow()
            assert result == "flow_executed"

    def test_budget_circuit_breaker_blocks_execution_over_budget(self):
        """Test circuit breaker blocks flow execution when over budget"""
        with (
            patch("d11_orchestration.cost_guardrails.check_monthly_budget_limit") as mock_check,
            patch("d11_orchestration.cost_guardrails.send_cost_alert") as mock_alert,
        ):
            # Mock over budget
            mock_check.return_value = (True, Decimal("3500.0"), Decimal("3000.0"))

            @budget_circuit_breaker
            def test_flow():
                return "flow_executed"

            with pytest.raises(BudgetExceededException) as exc_info:
                test_flow()

            # Verify exception details
            assert exc_info.value.current_spend == Decimal("3500.0")
            assert exc_info.value.monthly_limit == Decimal("3000.0")
            assert "Monthly budget exceeded" in str(exc_info.value)

            # Verify alert was sent
            mock_alert.assert_called_once()

    def test_budget_circuit_breaker_preserves_state_for_resume(self):
        """Test that budget stop preserves flow state for next month resume"""
        with (
            patch("d11_orchestration.cost_guardrails.check_monthly_budget_limit") as mock_check,
            patch("d11_orchestration.cost_guardrails.send_cost_alert") as mock_alert,
        ):
            # Mock over budget
            mock_check.return_value = (True, Decimal("3200.0"), Decimal("3000.0"))

            @budget_circuit_breaker
            def business_assessment_flow(business_id="test_123"):
                return f"assessed_{business_id}"

            with pytest.raises(BudgetExceededException):
                business_assessment_flow(business_id="test_business")

            # Verify alert contains state preservation info
            violation = mock_alert.call_args[0][0]  # First positional argument
            assert violation.metadata["action"] == "flow_blocked"
            assert violation.metadata["auto_resume"] == "next_month"
            assert violation.metadata["flow_name"] == "business_assessment_flow"

    def test_budget_exception_custom_message(self):
        """Test BudgetExceededException with custom message"""
        exception = BudgetExceededException(
            current_spend=Decimal("3500.0"), monthly_limit=Decimal("3000.0"), message="Custom budget message"
        )

        assert exception.current_spend == Decimal("3500.0")
        assert exception.monthly_limit == Decimal("3000.0")
        assert str(exception) == "Custom budget message"

    def test_budget_circuit_breaker_graceful_alert_failure(self):
        """Test circuit breaker handles alert sending failures gracefully"""
        with (
            patch("d11_orchestration.cost_guardrails.check_monthly_budget_limit") as mock_check,
            patch("d11_orchestration.cost_guardrails.send_cost_alert", side_effect=Exception("Alert failed")),
            patch("d11_orchestration.cost_guardrails.get_run_logger") as mock_logger,
        ):
            # Mock over budget
            mock_check.return_value = (True, Decimal("3500.0"), Decimal("3000.0"))
            mock_logger_instance = MagicMock()
            mock_logger.return_value = mock_logger_instance

            @budget_circuit_breaker
            def test_flow():
                return "should_not_execute"

            # Should still raise BudgetExceededException even if alert fails
            with pytest.raises(BudgetExceededException):
                test_flow()

            # Should log the alert failure
            mock_logger_instance.error.assert_called_with("Failed to send budget alert: Alert failed")


class TestBudgetStopIntegration:
    """Integration tests for budget stop with actual flows"""

    def test_flow_halt_verification(self):
        """Verify flows halt when budget exceeded - P2-040 acceptance criteria"""
        with patch("d11_orchestration.cost_guardrails.check_monthly_budget_limit") as mock_check:
            # Mock budget exceeded
            mock_check.return_value = (True, Decimal("3100.0"), Decimal("3000.0"))

            @budget_circuit_breaker
            def mock_prefect_flow():
                """Mock Prefect flow for testing"""
                return "flow_completed"

            # Verify flow transitions to Failed state
            with pytest.raises(BudgetExceededException) as exc_info:
                mock_prefect_flow()

            # Verify custom message format
            assert "Monthly budget exceeded: $3100.0 / $3000.0" in str(exc_info.value)

    def test_email_notifications_sent(self):
        """Test email notifications are sent when budget exceeded"""
        with (
            patch("d11_orchestration.cost_guardrails.check_monthly_budget_limit") as mock_check,
            patch("d11_orchestration.cost_guardrails.send_cost_alert") as mock_alert,
        ):
            mock_check.return_value = (True, Decimal("3050.0"), Decimal("3000.0"))

            @budget_circuit_breaker
            def test_flow():
                return "test"

            with pytest.raises(BudgetExceededException):
                test_flow()

            # Verify notification was sent with GuardrailViolation
            mock_alert.assert_called_once()
            violation = mock_alert.call_args[0][0]  # First positional argument
            assert violation.severity.value == "critical"
            assert "flow_blocked" in violation.metadata.get("action", "")

    def test_auto_resume_next_month_marker(self):
        """Test that flows are marked for auto-resume next month"""
        with (
            patch("d11_orchestration.cost_guardrails.check_monthly_budget_limit") as mock_check,
            patch("d11_orchestration.cost_guardrails.send_cost_alert") as mock_alert,
        ):
            mock_check.return_value = (True, Decimal("3001.0"), Decimal("3000.0"))

            @budget_circuit_breaker
            def monthly_report_flow():
                return "report_generated"

            with pytest.raises(BudgetExceededException):
                monthly_report_flow()

            # Verify auto-resume marker in alert metadata
            violation = mock_alert.call_args[0][0]  # First positional argument
            assert violation.metadata["auto_resume"] == "next_month"
            assert violation.metadata["flow_name"] == "monthly_report_flow"
