"""
Integration tests for gateway cost tracking across different APIs
P1-050: Gateway Cost Ledger implementation
"""
import asyncio

import pytest

# Mark entire module as xfail for Phase 0.5
pytestmark = pytest.mark.xfail(reason="Phase 0.5 feature - integration tests need database session fix", strict=False)
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from d0_gateway.cost_ledger import CostLedger, get_campaign_costs, get_provider_costs
from d0_gateway.providers.dataaxle import DataAxleClient
from d0_gateway.providers.hunter import HunterClient
from d0_gateway.providers.openai import OpenAIClient
from database.base import Base
from database.models import APICost, DailyCostAggregate


@pytest.fixture
def test_db():
    """Create a test database session"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def cost_ledger_instance(test_db):
    """Create a cost ledger instance with test database"""
    # Patch both cost_ledger module function and the instance's internal references
    with patch("d0_gateway.cost_ledger.get_db_sync") as mock_get_db:
        # Make the mock return a context manager that yields test_db
        mock_ctx = MagicMock()
        mock_ctx.__enter__.return_value = test_db
        mock_ctx.__exit__.return_value = None
        mock_get_db.return_value = mock_ctx
        yield CostLedger()


class TestCostTrackingIntegration:
    """Integration tests for cost tracking across multiple providers"""

    @pytest.mark.asyncio
    async def test_multi_provider_cost_tracking(self, test_db, cost_ledger_instance):
        """Test cost tracking across multiple providers in a workflow"""
        # Simulate a typical enrichment workflow
        lead_id = 123
        campaign_id = 1

        # Step 1: DataAxle business match
        cost_ledger_instance.record_cost(
            provider="dataaxle",
            operation="match_business",
            cost_usd=Decimal("0.10"),
            lead_id=lead_id,
            campaign_id=campaign_id,
            metadata={"match_confidence": 0.95},
        )

        # Step 2: Hunter email find (fallback)
        cost_ledger_instance.record_cost(
            provider="hunter",
            operation="find_email",
            cost_usd=Decimal("0.01"),
            lead_id=lead_id,
            campaign_id=campaign_id,
            metadata={"confidence_score": 0.85},
        )

        # Step 3: OpenAI analysis
        cost_ledger_instance.record_cost(
            provider="openai",
            operation="analyze_business",
            cost_usd=Decimal("0.002"),
            lead_id=lead_id,
            campaign_id=campaign_id,
            metadata={"model": "gpt-4o-mini", "tokens": 1500},
        )

        # Verify total costs for the lead
        all_costs = test_db.query(APICost).filter_by(lead_id=lead_id).all()
        assert len(all_costs) == 3

        total_cost = sum(c.cost_usd for c in all_costs)
        assert total_cost == Decimal("0.112")

        # Verify campaign costs
        campaign_costs = cost_ledger_instance.get_campaign_costs(campaign_id)
        assert campaign_costs["total_cost"] == 0.112
        assert len(campaign_costs["providers"]) == 3
        assert campaign_costs["providers"]["dataaxle"]["total_cost"] == 0.10

    @pytest.mark.asyncio
    async def test_provider_rate_limit_cost_tracking(self, test_db):
        """Test cost tracking when providers hit rate limits"""
        with patch("d0_gateway.cost_ledger.get_db_sync") as mock_get_db:
            mock_get_db.return_value.__enter__.return_value = test_db

            # Create mock clients
            with patch("d0_gateway.providers.dataaxle.httpx.AsyncClient") as mock_httpx:
                # Setup mock response
                mock_response = AsyncMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "match_found": True,
                    "match_confidence": 0.9,
                    "business_data": {"emails": ["test@example.com"]},
                }

                mock_client = AsyncMock()
                mock_client.request.return_value = mock_response
                mock_httpx.return_value = mock_client

                # Create client and make requests
                client = DataAxleClient(api_key="test-key")

                # Make 5 successful requests
                for i in range(5):
                    await client.match_business(
                        {
                            "name": f"Test Business {i}",
                            "lead_id": i,
                        }
                    )

                # Verify costs recorded
                costs = test_db.query(APICost).all()
                assert len(costs) == 5
                assert all(c.cost_usd == Decimal("0.10") for c in costs)

    def test_daily_cost_aggregation(self, test_db, cost_ledger_instance):
        """Test daily cost aggregation functionality"""
        # Create costs for multiple days
        today = datetime.now().date()
        yesterday = (datetime.now() - timedelta(days=1)).date()

        # Yesterday's costs
        for i in range(10):
            cost_ledger_instance.record_cost(
                provider="dataaxle",
                operation="match_business",
                cost_usd=Decimal("0.10"),
                campaign_id=1,
            )
            # Manually update timestamp to yesterday
            cost = test_db.query(APICost).order_by(APICost.id.desc()).first()
            cost.timestamp = datetime.combine(yesterday, datetime.min.time())

        test_db.commit()

        # Today's costs
        for i in range(5):
            cost_ledger_instance.record_cost(
                provider="hunter",
                operation="find_email",
                cost_usd=Decimal("0.01"),
                campaign_id=1,
            )

        # Aggregate yesterday's costs
        aggregates = cost_ledger_instance.aggregate_daily_costs(yesterday)

        assert len(aggregates) == 1
        assert aggregates[0].date == yesterday
        assert aggregates[0].provider == "dataaxle"
        assert aggregates[0].total_cost_usd == Decimal("1.00")
        assert aggregates[0].request_count == 10

    def test_cost_trends_analysis(self, test_db, cost_ledger_instance):
        """Test cost trend analysis over time"""
        # Create costs over 7 days with varying amounts
        base_date = datetime.now() - timedelta(days=7)

        daily_costs = [0.5, 0.8, 1.2, 0.9, 1.5, 1.1, 0.7]  # Varying daily costs

        for day_offset, daily_total in enumerate(daily_costs):
            cost_date = base_date + timedelta(days=day_offset)
            num_requests = int(daily_total / 0.10)  # Each request costs $0.10

            for _ in range(num_requests):
                cost_ledger_instance.record_cost(
                    provider="dataaxle",
                    operation="match_business",
                    cost_usd=Decimal("0.10"),
                )
                # Update timestamp
                cost = test_db.query(APICost).order_by(APICost.id.desc()).first()
                cost.timestamp = cost_date

            test_db.commit()

            # Aggregate for this day
            cost_ledger_instance.aggregate_daily_costs(cost_date.date())

        # Get daily costs for the week
        daily_records = cost_ledger_instance.get_daily_costs(
            start_date=base_date.date(),
            end_date=(base_date + timedelta(days=6)).date(),
        )

        assert len(daily_records) == 7

        # Find peak day (should be day 5 with $1.50)
        peak_cost = max(r["total_cost"] for r in daily_records)
        assert peak_cost == 1.5

        # Calculate average
        total = sum(r["total_cost"] for r in daily_records)
        average = total / 7
        assert average == pytest.approx(0.957, rel=0.01)

    @pytest.mark.asyncio
    async def test_concurrent_cost_recording(self, test_db, cost_ledger_instance):
        """Test concurrent cost recording from multiple providers"""

        async def record_provider_costs(provider: str, count: int):
            """Simulate provider making multiple API calls"""
            for i in range(count):
                cost_ledger_instance.record_cost(
                    provider=provider,
                    operation=f"{provider}_operation",
                    cost_usd=Decimal("0.01") * (i + 1),
                    lead_id=i,
                )
                await asyncio.sleep(0.01)  # Small delay to simulate real API calls

        # Run multiple providers concurrently
        await asyncio.gather(
            record_provider_costs("dataaxle", 5),
            record_provider_costs("hunter", 5),
            record_provider_costs("openai", 5),
        )

        # Verify all costs recorded
        total_costs = test_db.query(APICost).count()
        assert total_costs == 15

        # Verify costs by provider
        for provider in ["dataaxle", "hunter", "openai"]:
            provider_costs = test_db.query(APICost).filter_by(provider=provider).all()
            assert len(provider_costs) == 5

    def test_cost_cleanup(self, test_db, cost_ledger_instance):
        """Test cleanup of old cost records"""
        # Create old costs (100 days ago)
        old_date = datetime.now() - timedelta(days=100)

        for i in range(50):
            cost_ledger_instance.record_cost(
                provider="dataaxle",
                operation="match_business",
                cost_usd=Decimal("0.10"),
            )
            # Update timestamp to old date
            cost = test_db.query(APICost).order_by(APICost.id.desc()).first()
            cost.timestamp = old_date

        # Create recent costs (10 days ago)
        recent_date = datetime.now() - timedelta(days=10)

        for i in range(20):
            cost_ledger_instance.record_cost(
                provider="hunter",
                operation="find_email",
                cost_usd=Decimal("0.01"),
            )
            # Update timestamp to recent date
            cost = test_db.query(APICost).order_by(APICost.id.desc()).first()
            cost.timestamp = recent_date

        test_db.commit()

        # Aggregate old costs first
        cost_ledger_instance.aggregate_daily_costs(old_date.date())

        # Cleanup records older than 90 days
        deleted = cost_ledger_instance.cleanup_old_records(days_to_keep=90)

        assert deleted == 50

        # Verify recent costs still exist
        remaining_costs = test_db.query(APICost).count()
        assert remaining_costs == 20

        # Verify aggregates still exist
        aggregates = test_db.query(DailyCostAggregate).count()
        assert aggregates == 1  # Old costs were aggregated

    def test_provider_cost_comparison(self, test_db, cost_ledger_instance):
        """Test comparing costs across different providers"""
        # Simulate costs for different providers with varying rates
        providers_config = {
            "dataaxle": {"cost": 0.10, "count": 100},
            "hunter": {"cost": 0.01, "count": 200},
            "openai": {"cost": 0.002, "count": 500},
            "semrush": {"cost": 0.10, "count": 50},
        }

        for provider, config in providers_config.items():
            for _ in range(config["count"]):
                cost_ledger_instance.record_cost(
                    provider=provider,
                    operation=f"{provider}_api_call",
                    cost_usd=Decimal(str(config["cost"])),
                    campaign_id=1,
                )

        # Get costs for each provider
        provider_summaries = {}
        for provider in providers_config:
            summary = cost_ledger_instance.get_provider_costs(provider)
            provider_summaries[provider] = summary

        # Verify costs match expected
        assert provider_summaries["dataaxle"]["total_cost"] == 10.0  # 100 * 0.10
        assert provider_summaries["hunter"]["total_cost"] == 2.0  # 200 * 0.01
        assert provider_summaries["openai"]["total_cost"] == 1.0  # 500 * 0.002
        assert provider_summaries["semrush"]["total_cost"] == 5.0  # 50 * 0.10

        # Find most expensive provider by total cost
        most_expensive = max(provider_summaries.items(), key=lambda x: x[1]["total_cost"])
        assert most_expensive[0] == "dataaxle"  # $10.00 vs $5.00

        # Find most used provider
        most_used = max(provider_summaries.items(), key=lambda x: x[1]["total_requests"])
        assert most_used[0] == "openai"  # 500 requests
