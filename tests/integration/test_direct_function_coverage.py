"""
Direct function testing to achieve 80% coverage for cost_guardrails
Tests specific function code directly without Prefect flows
"""
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest


def test_cost_guardrail_flow_function_direct():
    """Test cost_guardrail_flow function with mocked dependencies to achieve coverage"""
    # Import and call the actual function with all dependencies mocked
    with patch('d11_orchestration.cost_guardrails.get_run_logger') as mock_logger, \
         patch('d11_orchestration.cost_guardrails.get_settings') as mock_settings, \
         patch('d11_orchestration.cost_guardrails.get_daily_costs') as mock_get_costs, \
         patch('d11_orchestration.cost_guardrails.check_budget_threshold') as mock_threshold, \
         patch('d11_orchestration.cost_guardrails.pause_expensive_operations') as mock_pause, \
         patch('d11_orchestration.cost_guardrails.create_markdown_artifact') as mock_artifact:
        
        # Mock all function calls
        mock_logger.return_value = MagicMock()
        mock_settings.return_value.cost_budget_usd = 100.0
        mock_get_costs.return_value = {"total": 85.0, "openai": 50.0}
        mock_threshold.return_value = (True, 0.85, "warning")
        mock_pause.return_value = {}
        
        # Import the actual flow function
        from d11_orchestration.cost_guardrails import cost_guardrail_flow
        
        # Call the function - this will execute the flow body and get coverage
        result = cost_guardrail_flow(daily_budget_override=100.0, warning_threshold=0.8)
        
        # Verify the result has expected structure
        assert "daily_costs" in result
        assert "budget_used_percentage" in result
        assert "alert_level" in result
        assert "paused_providers" in result
        assert "timestamp" in result
        
        # Verify all mocked functions were called
        mock_logger.assert_called()
        mock_settings.assert_called()
        mock_get_costs.assert_called()
        mock_threshold.assert_called()


def test_profit_snapshot_flow_function_direct():
    """Test profit_snapshot_flow function with mocked dependencies to achieve coverage"""
    with patch('d11_orchestration.cost_guardrails.get_run_logger') as mock_logger, \
         patch('d11_orchestration.cost_guardrails.get_profit_metrics') as mock_metrics, \
         patch('d11_orchestration.cost_guardrails.SessionLocal') as mock_session, \
         patch('d11_orchestration.cost_guardrails.create_profit_report') as mock_report, \
         patch('d11_orchestration.cost_guardrails.create_markdown_artifact') as mock_artifact:
        
        # Mock all dependencies
        mock_logger.return_value = MagicMock()
        mock_metrics.return_value = {"total_profit": 300.0, "avg_roi": 0.5}
        
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db
        mock_db.execute.return_value.fetchall.return_value = []
        
        mock_report.return_value = "Test report content"
        
        # Import the actual flow function
        from d11_orchestration.cost_guardrails import profit_snapshot_flow
        
        # Call the function - this will execute the flow body and get coverage
        result = profit_snapshot_flow(lookback_days=5, top_buckets_count=3)
        
        # Verify the result has expected structure
        assert "metrics" in result
        assert "top_buckets" in result
        assert "report" in result
        assert "period_days" in result
        assert "timestamp" in result
        assert result["period_days"] == 5
        
        # Verify all mocked functions were called
        mock_logger.assert_called()
        mock_metrics.assert_called_with(5)
        mock_report.assert_called()


def test_manual_trigger_functions():
    """Test manual trigger functions for additional coverage"""
    with patch('d11_orchestration.cost_guardrails.cost_guardrail_flow') as mock_flow:
        mock_flow.return_value = {"alert_level": "ok"}
        
        # Import and test manual trigger
        from d11_orchestration.cost_guardrails import check_costs_now
        
        # Use asyncio to test async function
        import asyncio
        
        async def test_async():
            result = await check_costs_now()
            assert result["alert_level"] == "ok"
            mock_flow.assert_called_once()
        
        asyncio.run(test_async())
        
    # Test profit report manual trigger
    with patch('d11_orchestration.cost_guardrails.profit_snapshot_flow') as mock_profit:
        mock_profit.return_value = {"metrics": {"total_profit": 200.0}}
        
        from d11_orchestration.cost_guardrails import generate_profit_report_now
        
        async def test_profit_async():
            result = await generate_profit_report_now(days=3)
            assert result["metrics"]["total_profit"] == 200.0
            mock_profit.assert_called_once_with(lookback_days=3)
        
        asyncio.run(test_profit_async())