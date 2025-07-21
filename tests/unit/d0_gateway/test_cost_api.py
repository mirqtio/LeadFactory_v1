"""
Unit tests for d0_gateway.cost_api module
Tests cost tracking API endpoints and response models
"""

from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from d0_gateway.cost_api import (
    CampaignCostSummary,
    CostTrend,
    DailyCostRecord,
    OperationCost,
    ProviderCostSummary,
    cleanup_old_costs,
    get_campaign_costs,
    get_cost_trends,
    get_daily_costs,
    get_provider_costs,
    health_check,
    router,
    trigger_cost_aggregation,
)


class TestCostAPIModels:
    """Test Pydantic models for cost API"""

    def test_operation_cost_model(self):
        """Test OperationCost model creation"""
        cost = OperationCost(operation="search", cost=10.50, count=100, avg_cost=0.105)
        assert cost.operation == "search"
        assert cost.cost == 10.50
        assert cost.count == 100
        assert cost.avg_cost == 0.105

    def test_provider_cost_summary_model(self):
        """Test ProviderCostSummary model creation"""
        summary = ProviderCostSummary(
            provider="dataaxle",
            period={"start": "2025-01-01", "end": "2025-01-31"},
            total_cost=500.0,
            total_requests=1000,
            operations={"search": {"cost": 300.0, "count": 600}},
        )
        assert summary.provider == "dataaxle"
        assert summary.total_cost == 500.0
        assert summary.total_requests == 1000

    def test_campaign_cost_summary_model(self):
        """Test CampaignCostSummary model creation"""
        summary = CampaignCostSummary(
            campaign_id=123, total_cost=750.0, providers={"dataaxle": {"cost": 500.0}, "hunter": {"cost": 250.0}}
        )
        assert summary.campaign_id == 123
        assert summary.total_cost == 750.0

    def test_daily_cost_record_model(self):
        """Test DailyCostRecord model creation"""
        record = DailyCostRecord(
            date="2025-01-15",
            provider="openai",
            operation="completion",
            campaign_id=456,
            total_cost=25.0,
            request_count=50,
            avg_cost=0.50,
        )
        assert record.date == "2025-01-15"
        assert record.provider == "openai"
        assert record.total_cost == 25.0

    def test_cost_trend_model(self):
        """Test CostTrend model creation"""
        daily_record = DailyCostRecord(
            date="2025-01-15",
            provider="openai",
            operation="completion",
            campaign_id=123,
            total_cost=25.0,
            request_count=50,
            avg_cost=0.50,
        )

        trend = CostTrend(
            period={"start": "2025-01-01", "end": "2025-01-31"},
            daily_costs=[daily_record],
            total_cost=750.0,
            avg_daily_cost=25.0,
            peak_day="2025-01-15",
            peak_cost=100.0,
        )
        assert trend.total_cost == 750.0
        assert trend.avg_daily_cost == 25.0
        assert len(trend.daily_costs) == 1


class TestCostAPIEndpoints:
    """Test cost API endpoint functions"""

    @pytest.mark.asyncio
    @patch("d0_gateway.cost_api.cost_ledger")
    async def test_get_provider_costs_success(self, mock_ledger):
        """Test successful provider costs retrieval"""
        mock_user = {"user_id": 1, "username": "test"}
        mock_costs = {
            "provider": "dataaxle",
            "period": {"start": "2025-01-01", "end": "2025-01-31"},
            "total_cost": 500.0,
            "total_requests": 1000,
            "operations": {"search": {"cost": 300.0, "count": 600}},
        }
        mock_ledger.get_provider_costs.return_value = mock_costs

        result = await get_provider_costs("dataaxle", 30, mock_user)

        assert isinstance(result, ProviderCostSummary)
        assert result.provider == "dataaxle"
        assert result.total_cost == 500.0
        mock_ledger.get_provider_costs.assert_called_once()

    @pytest.mark.asyncio
    @patch("d0_gateway.cost_api.cost_ledger")
    async def test_get_provider_costs_error(self, mock_ledger):
        """Test provider costs retrieval with error"""
        mock_user = {"user_id": 1, "username": "test"}
        mock_ledger.get_provider_costs.side_effect = Exception("Database error")

        with pytest.raises(HTTPException) as exc_info:
            await get_provider_costs("dataaxle", 30, mock_user)

        assert exc_info.value.status_code == 500
        assert "Database error" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    @patch("d0_gateway.cost_api.cost_ledger")
    async def test_get_campaign_costs_success(self, mock_ledger):
        """Test successful campaign costs retrieval"""
        mock_user = {"user_id": 1, "username": "test"}
        mock_costs = {"campaign_id": 123, "total_cost": 750.0, "providers": {"dataaxle": {"cost": 500.0}}}
        mock_ledger.get_campaign_costs.return_value = mock_costs

        result = await get_campaign_costs(123, mock_user)

        assert isinstance(result, CampaignCostSummary)
        assert result.campaign_id == 123
        assert result.total_cost == 750.0

    @pytest.mark.asyncio
    @patch("d0_gateway.cost_api.cost_ledger")
    async def test_get_campaign_costs_error(self, mock_ledger):
        """Test campaign costs retrieval with error"""
        mock_user = {"user_id": 1, "username": "test"}
        mock_ledger.get_campaign_costs.side_effect = Exception("Database error")

        with pytest.raises(HTTPException) as exc_info:
            await get_campaign_costs(123, mock_user)

        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    @patch("d0_gateway.cost_api.cost_ledger")
    async def test_get_daily_costs_success(self, mock_ledger):
        """Test successful daily costs retrieval"""
        mock_user = {"user_id": 1, "username": "test"}
        mock_costs = [
            {
                "date": "2025-01-15",
                "provider": "openai",
                "operation": "completion",
                "campaign_id": 456,
                "total_cost": 25.0,
                "request_count": 50,
                "avg_cost": 0.50,
            }
        ]
        mock_ledger.get_daily_costs.return_value = mock_costs

        start_date = date(2025, 1, 1)
        result = await get_daily_costs(start_date, None, None, None, mock_user)

        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], DailyCostRecord)
        assert result[0].total_cost == 25.0

    @pytest.mark.asyncio
    @patch("d0_gateway.cost_api.cost_ledger")
    async def test_get_daily_costs_error(self, mock_ledger):
        """Test daily costs retrieval with error"""
        mock_user = {"user_id": 1, "username": "test"}
        mock_ledger.get_daily_costs.side_effect = Exception("Database error")

        start_date = date(2025, 1, 1)
        with pytest.raises(HTTPException) as exc_info:
            await get_daily_costs(start_date, None, None, None, mock_user)

        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    @patch("d0_gateway.cost_api.cost_ledger")
    @patch("d0_gateway.cost_api.datetime")
    @patch("d0_gateway.cost_api.date")
    async def test_get_cost_trends_success(self, mock_date, mock_datetime, mock_ledger):
        """Test successful cost trends retrieval"""
        mock_user = {"user_id": 1, "username": "test"}

        # Mock dates
        mock_now = datetime(2025, 1, 31, 12, 0)
        mock_datetime.now.return_value = mock_now
        mock_date.today.return_value = date(2025, 1, 31)

        mock_costs = [
            {
                "date": "2025-01-15",
                "provider": "openai",
                "operation": "completion",
                "campaign_id": 456,
                "total_cost": 25.0,
                "request_count": 50,
                "avg_cost": 0.50,
            },
            {
                "date": "2025-01-20",
                "provider": "dataaxle",
                "operation": "search",
                "campaign_id": 789,
                "total_cost": 50.0,
                "request_count": 100,
                "avg_cost": 0.50,
            },
        ]
        mock_ledger.get_daily_costs.return_value = mock_costs

        result = await get_cost_trends(30, None, mock_user)

        assert isinstance(result, CostTrend)
        assert result.total_cost == 75.0  # 25.0 + 50.0
        assert result.avg_daily_cost == 2.5  # 75.0 / 30
        assert len(result.daily_costs) == 2

    @pytest.mark.asyncio
    @patch("d0_gateway.cost_api.cost_ledger")
    async def test_get_cost_trends_error(self, mock_ledger):
        """Test cost trends retrieval with error"""
        mock_user = {"user_id": 1, "username": "test"}
        mock_ledger.get_daily_costs.side_effect = Exception("Database error")

        with pytest.raises(HTTPException) as exc_info:
            await get_cost_trends(30, None, mock_user)

        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    @patch("d0_gateway.cost_api.cost_ledger")
    async def test_trigger_cost_aggregation_success(self, mock_ledger):
        """Test successful cost aggregation trigger"""
        mock_user = {"user_id": 1, "username": "test"}

        # Mock aggregates with total_cost_usd attribute
        mock_aggregate1 = Mock()
        mock_aggregate1.total_cost_usd = 25.0
        mock_aggregate2 = Mock()
        mock_aggregate2.total_cost_usd = 50.0

        mock_aggregates = [mock_aggregate1, mock_aggregate2]
        mock_ledger.aggregate_daily_costs.return_value = mock_aggregates

        target_date = date(2025, 1, 15)
        result = await trigger_cost_aggregation(target_date, mock_user)

        assert result["status"] == "success"
        assert result["date"] == "2025-01-15"
        assert result["records_created"] == 2
        assert result["total_cost"] == 75.0

    @pytest.mark.asyncio
    @patch("d0_gateway.cost_api.cost_ledger")
    async def test_trigger_cost_aggregation_error(self, mock_ledger):
        """Test cost aggregation trigger with error"""
        mock_user = {"user_id": 1, "username": "test"}
        mock_ledger.aggregate_daily_costs.side_effect = Exception("Aggregation error")

        target_date = date(2025, 1, 15)
        with pytest.raises(HTTPException) as exc_info:
            await trigger_cost_aggregation(target_date, mock_user)

        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    @patch("d0_gateway.cost_api.cost_ledger")
    async def test_cleanup_old_costs_success(self, mock_ledger):
        """Test successful old costs cleanup"""
        mock_user = {"user_id": 1, "username": "test"}
        mock_ledger.cleanup_old_records.return_value = 150

        result = await cleanup_old_costs(90, mock_user)

        assert result["status"] == "success"
        assert result["deleted_count"] == 150
        assert result["days_kept"] == 90

    @pytest.mark.asyncio
    @patch("d0_gateway.cost_api.cost_ledger")
    async def test_cleanup_old_costs_error(self, mock_ledger):
        """Test old costs cleanup with error"""
        mock_user = {"user_id": 1, "username": "test"}
        mock_ledger.cleanup_old_records.side_effect = Exception("Cleanup error")

        with pytest.raises(HTTPException) as exc_info:
            await cleanup_old_costs(90, mock_user)

        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    @patch("d0_gateway.cost_api.datetime")
    async def test_health_check(self, mock_datetime):
        """Test health check endpoint"""
        mock_now = datetime(2025, 1, 15, 12, 0)
        mock_datetime.now.return_value = mock_now

        result = await health_check()

        assert result["status"] == "healthy"
        assert result["service"] == "gateway_cost_ledger"
        assert result["timestamp"] == "2025-01-15T12:00:00"


class TestCostAPIIntegration:
    """Test cost API router integration"""

    def test_router_configuration(self):
        """Test that router is properly configured"""
        assert "costs" in router.tags

    def test_router_endpoints_count(self):
        """Test that router has expected endpoints"""
        routes = [route for route in router.routes if hasattr(route, "path")]
        # Should have 7 endpoints: providers, campaigns, daily, trends, aggregate, cleanup, health
        assert len(routes) >= 7

    def test_router_has_provider_endpoint(self):
        """Test that router has provider costs endpoint"""
        provider_routes = [route for route in router.routes if hasattr(route, "path") and "/providers/" in route.path]
        assert len(provider_routes) == 1

    def test_router_has_campaign_endpoint(self):
        """Test that router has campaign costs endpoint"""
        campaign_routes = [route for route in router.routes if hasattr(route, "path") and "/campaigns/" in route.path]
        assert len(campaign_routes) == 1

    def test_router_has_daily_endpoint(self):
        """Test that router has daily costs endpoint"""
        daily_routes = [route for route in router.routes if hasattr(route, "path") and route.path == "/daily"]
        assert len(daily_routes) == 1

    def test_router_has_trends_endpoint(self):
        """Test that router has trends endpoint"""
        trends_routes = [route for route in router.routes if hasattr(route, "path") and route.path == "/trends"]
        assert len(trends_routes) == 1

    def test_router_has_aggregate_endpoint(self):
        """Test that router has aggregate endpoint"""
        aggregate_routes = [route for route in router.routes if hasattr(route, "path") and "/aggregate/" in route.path]
        assert len(aggregate_routes) == 1

    def test_router_has_cleanup_endpoint(self):
        """Test that router has cleanup endpoint"""
        cleanup_routes = [route for route in router.routes if hasattr(route, "path") and route.path == "/cleanup"]
        assert len(cleanup_routes) == 1

    def test_router_has_health_endpoint(self):
        """Test that router has health endpoint"""
        health_routes = [route for route in router.routes if hasattr(route, "path") and route.path == "/health"]
        assert len(health_routes) == 1
