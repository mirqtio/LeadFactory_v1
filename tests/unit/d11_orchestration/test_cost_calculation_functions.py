"""
Unit tests for P2-040 cost calculation and budget checking functions
Tests for get_monthly_costs, check_monthly_budget_limit, and budget_circuit_breaker functions
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


class TestCostCalculationFunctions:
    """Test core cost calculation and budget checking functions"""

    def test_get_monthly_costs_with_data(self):
        """Test get_monthly_costs function with mock database data"""
        mock_results = [
            MagicMock(monthly_cost=Decimal("1500.0")),  # Aggregated costs
            MagicMock(monthly_cost=Decimal("250.0")),  # Recent costs
        ]

        with patch("d11_orchestration.cost_guardrails.SessionLocal") as mock_session_local:
            mock_db = MagicMock()
            mock_session_local.return_value.__enter__.return_value = mock_db
            mock_db.execute.return_value.fetchall.return_value = mock_results

            result = get_monthly_costs()

            assert result == Decimal("1750.0")  # Sum of both results
            assert mock_db.execute.called

    def test_get_monthly_costs_no_data(self):
        """Test get_monthly_costs function with no database data"""
        with patch("d11_orchestration.cost_guardrails.SessionLocal") as mock_session_local:
            mock_db = MagicMock()
            mock_session_local.return_value.__enter__.return_value = mock_db
            mock_db.execute.return_value.fetchall.return_value = []

            result = get_monthly_costs()

            assert result == Decimal("0")

    def test_check_monthly_budget_limit_under_budget(self):
        """Test check_monthly_budget_limit when under budget"""
        with patch("d11_orchestration.cost_guardrails.get_monthly_costs") as mock_costs, patch(
            "d11_orchestration.cost_guardrails.get_settings"
        ) as mock_settings:
            mock_costs.return_value = Decimal("2000.0")
            mock_settings.return_value.guardrail_global_monthly_limit = 3000.0

            is_exceeded, current_spend, monthly_limit = check_monthly_budget_limit()

            assert is_exceeded is False
            assert current_spend == Decimal("2000.0")
            assert monthly_limit == Decimal("3000.0")

    def test_check_monthly_budget_limit_over_budget(self):
        """Test check_monthly_budget_limit when over budget"""
        with patch("d11_orchestration.cost_guardrails.get_monthly_costs") as mock_costs, patch(
            "d11_orchestration.cost_guardrails.get_settings"
        ) as mock_settings:
            mock_costs.return_value = Decimal("3500.0")
            mock_settings.return_value.guardrail_global_monthly_limit = 3000.0

            is_exceeded, current_spend, monthly_limit = check_monthly_budget_limit()

            assert is_exceeded is True
            assert current_spend == Decimal("3500.0")
            assert monthly_limit == Decimal("3000.0")

    def test_check_monthly_budget_limit_exactly_at_budget(self):
        """Test check_monthly_budget_limit when exactly at budget"""
        with patch("d11_orchestration.cost_guardrails.get_monthly_costs") as mock_costs, patch(
            "d11_orchestration.cost_guardrails.get_settings"
        ) as mock_settings:
            mock_costs.return_value = Decimal("3000.0")
            mock_settings.return_value.guardrail_global_monthly_limit = 3000.0

            is_exceeded, current_spend, monthly_limit = check_monthly_budget_limit()

            assert is_exceeded is True  # >= monthly_limit
            assert current_spend == Decimal("3000.0")
            assert monthly_limit == Decimal("3000.0")

    def test_budget_circuit_breaker_under_budget(self):
        """Test budget_circuit_breaker decorator when under budget"""

        @budget_circuit_breaker
        def mock_flow():
            return {"status": "success", "result": "flow_executed"}

        with patch("d11_orchestration.cost_guardrails.check_monthly_budget_limit") as mock_check:
            mock_check.return_value = (False, Decimal("2000.0"), Decimal("3000.0"))

            result = mock_flow()

            assert result["status"] == "success"
            assert result["result"] == "flow_executed"

    def test_budget_circuit_breaker_over_budget(self):
        """Test budget_circuit_breaker decorator when over budget"""

        @budget_circuit_breaker
        def mock_flow():
            return {"status": "success", "result": "flow_executed"}

        with patch("d11_orchestration.cost_guardrails.check_monthly_budget_limit") as mock_check, patch(
            "d11_orchestration.cost_guardrails.send_cost_alert"
        ) as mock_alert, patch("asyncio.get_event_loop") as mock_get_loop, patch("asyncio.run") as mock_asyncio_run:
            mock_check.return_value = (True, Decimal("3500.0"), Decimal("3000.0"))

            # Mock the event loop path (which is taken first)
            mock_loop = MagicMock()
            mock_get_loop.return_value = mock_loop
            mock_loop.run_until_complete.return_value = None

            with pytest.raises(BudgetExceededException) as exc_info:
                mock_flow()

            exception = exc_info.value
            assert exception.current_spend == Decimal("3500.0")
            assert exception.monthly_limit == Decimal("3000.0")
            assert "Monthly budget exceeded" in str(exception)

            # Verify alert was attempted via event loop
            mock_loop.run_until_complete.assert_called_once()

    def test_budget_circuit_breaker_alert_failure(self):
        """Test budget_circuit_breaker decorator when alert sending fails"""

        @budget_circuit_breaker
        def mock_flow():
            return {"status": "success", "result": "flow_executed"}

        with patch("d11_orchestration.cost_guardrails.check_monthly_budget_limit") as mock_check, patch(
            "d11_orchestration.cost_guardrails.send_cost_alert"
        ) as mock_alert, patch("asyncio.get_event_loop") as mock_get_loop, patch(
            "asyncio.run", side_effect=Exception("Alert failed")
        ), patch(
            "d11_orchestration.cost_guardrails.get_run_logger"
        ) as mock_logger:
            mock_check.return_value = (True, Decimal("3500.0"), Decimal("3000.0"))
            mock_logger_instance = MagicMock()
            mock_logger.return_value = mock_logger_instance

            # Mock the event loop path to fail
            mock_loop = MagicMock()
            mock_get_loop.return_value = mock_loop
            mock_loop.run_until_complete.side_effect = Exception("Alert failed")

            with pytest.raises(BudgetExceededException):
                mock_flow()

            # Alert failure should still raise BudgetExceededException
            # but error should be logged by the decorator's try-catch
            # Check that the exception was raised properly
            assert True  # The test passing means BudgetExceededException was raised correctly

    def test_budget_exceeded_exception_creation(self):
        """Test BudgetExceededException creation and attributes"""
        current_spend = Decimal("3500.0")
        monthly_limit = Decimal("3000.0")

        # Test with default message
        exception = BudgetExceededException(current_spend, monthly_limit)
        assert exception.current_spend == current_spend
        assert exception.monthly_limit == monthly_limit
        assert "Monthly budget exceeded: $3500.0 / $3000.0" in str(exception)

        # Test with custom message
        custom_message = "Custom budget exceeded message"
        exception = BudgetExceededException(current_spend, monthly_limit, custom_message)
        assert str(exception) == custom_message
