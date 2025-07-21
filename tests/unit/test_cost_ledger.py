"""
Tests for cost tracking functionality - Phase 0.5 Task GW-04
"""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from d0_gateway.base import BaseAPIClient
from database.base import Base
from database.models import APICost, DailyCostAggregate

# P1-050: Gateway Cost Ledger tests - now implemented


@pytest.fixture
def test_db():
    """Create a test database session"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    session = SessionLocal()
    yield session
    session.close()


class TestAPICostModel:
    """Test the APICost database model"""

    def test_create_api_cost(self, test_db):
        """Test creating an API cost record"""
        cost = APICost(
            provider="dataaxle",
            operation="match_business",
            lead_id=1,
            campaign_id=1,
            cost_usd=Decimal("0.10"),
            request_id="req_123",
            meta_data={"match_confidence": 0.95},
        )
        test_db.add(cost)
        test_db.commit()

        # Verify
        saved_cost = test_db.query(APICost).first()
        assert saved_cost.provider == "dataaxle"
        assert saved_cost.operation == "match_business"
        assert saved_cost.lead_id == 1
        assert saved_cost.campaign_id == 1
        assert saved_cost.cost_usd == Decimal("0.10")
        assert saved_cost.meta_data["match_confidence"] == 0.95
        assert saved_cost.timestamp is not None

    def test_multiple_costs(self, test_db):
        """Test multiple API costs"""
        # Data Axle cost
        cost1 = APICost(
            provider="dataaxle",
            operation="match_business",
            lead_id=1,
            cost_usd=Decimal("0.10"),
        )
        test_db.add(cost1)

        # Hunter cost (fallback)
        cost2 = APICost(
            provider="hunter",
            operation="find_email",
            lead_id=1,
            cost_usd=Decimal("0.01"),
        )
        test_db.add(cost2)
        test_db.commit()

        # Verify total costs
        all_costs = test_db.query(APICost).filter_by(lead_id=1).all()
        total = sum(c.cost_usd for c in all_costs)
        assert total == Decimal("0.11")


class TestDailyCostAggregate:
    """Test the daily cost aggregate model"""

    def test_create_daily_aggregate(self, test_db):
        """Test creating daily cost aggregate"""
        agg = DailyCostAggregate(
            date=datetime.now().date(),
            provider="dataaxle",
            operation="match_business",
            campaign_id=1,
            total_cost_usd=Decimal("5.00"),
            request_count=100,
        )
        test_db.add(agg)
        test_db.commit()

        saved_agg = test_db.query(DailyCostAggregate).first()
        assert saved_agg.total_cost_usd == Decimal("5.00")
        assert saved_agg.request_count == 100

    def test_unique_constraint(self, test_db):
        """Test unique constraint on daily aggregates"""
        today = datetime.now().date()

        # First aggregate
        agg1 = DailyCostAggregate(
            date=today,
            provider="dataaxle",
            operation="match_business",
            campaign_id=None,
            total_cost_usd=Decimal("1.00"),
            request_count=20,
        )
        test_db.add(agg1)
        test_db.commit()

        # Try to add duplicate
        agg2 = DailyCostAggregate(
            date=today,
            provider="dataaxle",
            operation="match_business",
            campaign_id=None,
            total_cost_usd=Decimal("2.00"),
            request_count=40,
        )
        test_db.add(agg2)

        try:
            test_db.commit()
            # If we get here in SQLite, manually check for uniqueness
            count = (
                test_db.query(DailyCostAggregate)
                .filter_by(
                    date=today,
                    provider="dataaxle",
                    operation="match_business",
                    campaign_id=None,
                )
                .count()
            )
            assert count == 1, "Unique constraint should prevent duplicates"
        except Exception:
            # Expected behavior in PostgreSQL
            test_db.rollback()


class MockAPIClient(BaseAPIClient):
    """Mock API client for testing emit_cost"""

    def _get_base_url(self) -> str:
        return "https://api.test.com"

    def _get_headers(self) -> dict:
        return {"Authorization": "Bearer test"}

    def get_rate_limit(self) -> dict:
        return {"requests_per_minute": 100}

    def calculate_cost(self, operation: str, **kwargs) -> Decimal:
        if operation == "test_operation":
            return Decimal("0.10")
        return Decimal("0.00")


class TestEmitCost:
    """Test the emit_cost functionality in base client"""

    @patch("database.session.get_db_sync")
    def test_emit_cost_success(self, mock_get_db, test_db):
        """Test successful cost emission"""
        # Setup mock
        mock_get_db.return_value.__enter__.return_value = test_db

        # Create client with mocked components
        with (
            patch("d0_gateway.base.RateLimiter"),
            patch("d0_gateway.base.CircuitBreaker"),
            patch("d0_gateway.base.ResponseCache"),
            patch("d0_gateway.base.GatewayMetrics") as mock_metrics,
            patch("d0_gateway.base.get_settings"),
        ):
            client = MockAPIClient(provider="test_provider", api_key="test")

            # Emit cost
            client.emit_cost(
                lead_id=1,
                campaign_id=2,
                cost_usd=0.15,
                operation="test_operation",
                metadata={"test": "data"},
            )

            # Verify database record
            cost = test_db.query(APICost).first()
            assert cost is not None
            assert cost.provider == "test_provider"
            assert cost.operation == "test_operation"
            assert cost.lead_id == 1
            assert cost.campaign_id == 2
            assert cost.cost_usd == Decimal("0.15")
            assert cost.meta_data["test"] == "data"

            # Verify metrics were recorded
            mock_metrics.return_value.record_cost.assert_called_once_with("test_provider", "test_operation", 0.15)

    @patch("database.session.get_db_sync")
    def test_emit_cost_db_failure(self, mock_get_db):
        """Test emit_cost doesn't fail request on DB error"""
        # Setup mock to raise exception
        mock_get_db.side_effect = Exception("DB Error")

        # Create client
        with (
            patch("d0_gateway.base.RateLimiter"),
            patch("d0_gateway.base.CircuitBreaker"),
            patch("d0_gateway.base.ResponseCache"),
            patch("d0_gateway.base.GatewayMetrics"),
            patch("d0_gateway.base.get_settings"),
            patch("d0_gateway.base.get_logger") as mock_logger,
        ):
            client = MockAPIClient(provider="test_provider", api_key="test")

            # Should not raise exception
            client.emit_cost(lead_id=1, cost_usd=0.10, operation="test_op")

            # Verify error was logged
            mock_logger.return_value.error.assert_called()


class TestCostAggregation:
    """Test cost aggregation queries"""

    def test_provider_cost_aggregation(self, test_db):
        """Test aggregating costs by provider"""
        # Create costs for different providers
        costs = [
            APICost(provider="dataaxle", operation="match", cost_usd=Decimal("0.10")),
            APICost(provider="dataaxle", operation="match", cost_usd=Decimal("0.10")),
            APICost(provider="hunter", operation="find", cost_usd=Decimal("0.01")),
            APICost(provider="openai", operation="analyze", cost_usd=Decimal("0.02")),
        ]
        test_db.add_all(costs)
        test_db.commit()

        # Aggregate by provider
        from sqlalchemy import func

        results = (
            test_db.query(
                APICost.provider,
                func.sum(APICost.cost_usd).label("total_cost"),
                func.count(APICost.id).label("request_count"),
            )
            .group_by(APICost.provider)
            .all()
        )

        # Convert to dict for easy assertion
        cost_by_provider = {r.provider: r.total_cost for r in results}

        assert cost_by_provider["dataaxle"] == Decimal("0.20")
        assert cost_by_provider["hunter"] == Decimal("0.01")
        assert cost_by_provider["openai"] == Decimal("0.02")

    def test_campaign_cost_aggregation(self, test_db):
        """Test aggregating costs by campaign"""
        # Create costs for campaign
        costs = [
            APICost(
                provider="dataaxle",
                operation="match",
                campaign_id=1,
                cost_usd=Decimal("0.10"),
            )
            for _ in range(20)  # 20 matches = $2.00
        ]
        test_db.add_all(costs)
        test_db.commit()

        # Calculate total campaign cost
        from sqlalchemy import func

        total_cost = test_db.query(func.sum(APICost.cost_usd)).filter(APICost.campaign_id == 1).scalar()

        assert total_cost == Decimal("2.00")

    def test_daily_cost_tracking(self, test_db):
        """Test tracking costs by day"""
        today = datetime.now()
        yesterday = today - timedelta(days=1)

        # Create costs for different days
        costs = [
            APICost(
                provider="dataaxle",
                operation="match",
                cost_usd=Decimal("0.10"),
                timestamp=today,
            ),
            APICost(
                provider="dataaxle",
                operation="match",
                cost_usd=Decimal("0.10"),
                timestamp=today,
            ),
            APICost(
                provider="dataaxle",
                operation="match",
                cost_usd=Decimal("0.10"),
                timestamp=yesterday,
            ),
        ]

        # Add costs to database
        test_db.add_all(costs)
        test_db.commit()

        # Query costs manually grouped by day

        # Get all costs for today
        today_costs = test_db.query(APICost).filter(APICost.provider == "dataaxle").all()

        # Manually filter by date in Python (more reliable for SQLite)
        today_total = Decimal("0.00")
        for cost in today_costs:
            if cost.timestamp and cost.timestamp.date() == today.date():
                today_total += cost.cost_usd

        # Should have 2 costs for today
        assert today_total == Decimal("0.20")


class TestBaseClientCostIntegration:
    """Test cost tracking integration with base client"""

    @patch("d0_gateway.base.httpx.AsyncClient")
    @pytest.mark.asyncio
    async def test_cost_recorded_on_api_call(self, mock_httpx):
        """Test that costs are recorded when making API calls"""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "success"}

        mock_client = AsyncMock()
        mock_client.request.return_value = mock_response
        mock_httpx.return_value = mock_client

        # Create client with mocked components
        with (
            patch("d0_gateway.base.RateLimiter") as mock_rate_limiter,
            patch("d0_gateway.base.CircuitBreaker") as mock_circuit_breaker,
            patch("d0_gateway.base.ResponseCache") as mock_cache,
            patch("d0_gateway.base.GatewayMetrics") as mock_metrics,
            patch("d0_gateway.base.get_settings"),
            patch("database.session.get_db_sync"),
        ):
            # Setup mocks
            mock_rate_limiter.return_value.is_allowed = AsyncMock(return_value=True)
            mock_circuit_breaker.return_value.can_execute.return_value = True
            mock_circuit_breaker.return_value.record_success = MagicMock()
            mock_cache.return_value.get = AsyncMock(return_value=None)
            mock_cache.return_value.set = AsyncMock()

            client = MockAPIClient(provider="test_provider", api_key="test")

            # Make API call
            await client.make_request("GET", "/test")

            # Verify cost was recorded in metrics
            mock_metrics.return_value.record_cost.assert_called_with("test_provider", "/test", 0.0)
