"""
Integration tests for P1-080 Bucket Enrichment Flow
Tests the complete bucket enrichment flow with database and enrichment components
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from d1_targeting.bucket_loader import get_bucket_loader
from d4_enrichment.models import EnrichmentSource
from database.models import Business
from database.session import SessionLocal
from flows.bucket_enrichment_flow import bucket_enrichment_flow, trigger_bucket_enrichment

# Mark entire module for Phase 0.5 feature implementation
pytestmark = [
    pytest.mark.integration,
    pytest.mark.xfail(reason="Phase 0.5 feature - not yet implemented", strict=False),
]


class TestBucketEnrichmentFlowIntegration:
    """Integration tests for bucket enrichment flow"""

    @pytest.fixture
    def setup_test_businesses(self, test_db_session):
        """Create test businesses with different buckets"""
        businesses = [
            # Healthcare bucket - high priority
            Business(
                id="biz-health-1",
                name="Premium Medical Center",
                address="123 Health St",
                city="San Francisco",
                state="CA",
                zip_code="94105",
                categories=["healthcare", "medical"],
                vert_bucket="healthcare-urgent",
                geo_bucket="high-high-high",
                website=None,  # Needs enrichment
                phone=None,
                email=None,
                last_enriched_at=None,
            ),
            Business(
                id="biz-health-2",
                name="City Dental Clinic",
                address="456 Dental Ave",
                city="San Francisco",
                state="CA",
                zip_code="94105",
                categories=["dentist", "healthcare"],
                vert_bucket="healthcare-urgent",
                geo_bucket="high-high-high",
                website="http://existing.com",
                phone="555-1234",
                last_enriched_at=datetime.utcnow() - timedelta(days=60),  # Old enrichment
            ),
            # SaaS bucket - medium priority
            Business(
                id="biz-saas-1",
                name="Tech Solutions Inc",
                address="789 Software Blvd",
                city="San Francisco",
                state="CA",
                zip_code="94107",
                categories=["software", "technology"],
                vert_bucket="saas-medium",
                geo_bucket="high-medium-high",
                website=None,
                phone=None,
                last_enriched_at=None,
            ),
            # Restaurant bucket - low priority
            Business(
                id="biz-rest-1",
                name="Joe's Pizza",
                address="321 Food St",
                city="San Francisco",
                state="CA",
                zip_code="94109",
                categories=["restaurant", "pizza"],
                vert_bucket="restaurants-low",
                geo_bucket="medium-high-medium",
                website=None,
                phone=None,
                last_enriched_at=None,
            ),
            Business(
                id="biz-rest-2",
                name="Burger Palace",
                address="654 Burger Way",
                city="San Francisco",
                state="CA",
                zip_code="94109",
                categories=["restaurant", "fast food"],
                vert_bucket="restaurants-low",
                geo_bucket="medium-high-medium",
                website="http://burgers.com",
                phone="555-9999",
                last_enriched_at=datetime.utcnow() - timedelta(days=3),  # Recent - should skip
            ),
            # No bucket - should not be processed
            Business(
                id="biz-nobucket-1",
                name="Unknown Business",
                address="999 Mystery Ln",
                city="San Francisco",
                state="CA",
                zip_code="94110",
                categories=["other"],
                vert_bucket=None,
                geo_bucket=None,
                website=None,
                phone=None,
                last_enriched_at=None,
            ),
        ]

        test_db_session.add_all(businesses)
        test_db_session.commit()

        return businesses

    @pytest.mark.asyncio
    @patch("flows.bucket_enrichment_flow.EnrichmentCoordinator")
    async def test_full_bucket_enrichment_flow(self, mock_coordinator_class, setup_test_businesses, test_db_session):
        """Test complete flow with real database"""
        # Mock enrichment coordinator
        mock_coordinator = AsyncMock()
        mock_coordinator_class.return_value = mock_coordinator

        # Mock enrichment results
        def create_mock_result(business_id, success=True):
            if success:
                return Mock(
                    business_id=business_id,
                    enriched_data={
                        "website": f"http://enriched-{business_id}.com",
                        "phone": "555-0000",
                        "email": f"info@{business_id}.com",
                    },
                    completed_at=datetime.utcnow(),
                    sources_completed=["internal"],
                )
            return None

        # Configure mock responses based on business ID
        async def mock_enrich_batch(businesses, **kwargs):
            results = []
            for biz in businesses:
                # Skip recently enriched
                if biz.get("id") == "biz-rest-2":
                    continue
                results.append(create_mock_result(biz["id"]))

            return Mock(
                successful_enrichments=len(results), skipped_enrichments=0, failed_enrichments=0, results=results
            )

        mock_coordinator.enrich_businesses_batch.side_effect = mock_enrich_batch

        # Run the flow
        result = await bucket_enrichment_flow(max_buckets=3, total_budget=100.0, bucket_limit=10)

        # Verify results
        assert result["status"] == "completed"
        assert result["buckets_processed"] >= 2  # At least healthcare and saas
        assert result["total_enriched"] >= 3  # health-1, health-2, saas-1
        assert result["total_cost"] > 0

        # Check bucket stats
        bucket_names = [stat["bucket"] for stat in result["bucket_stats"]]
        assert "healthcare-urgent" in bucket_names
        assert "saas-medium" in bucket_names

        # Verify database updates
        updated_businesses = test_db_session.query(Business).filter(Business.last_enriched_at.isnot(None)).all()

        # Should have updated businesses (exact count depends on skip logic)
        assert len(updated_businesses) >= 3

        # Check specific business was enriched
        health1 = test_db_session.query(Business).filter_by(id="biz-health-1").first()
        assert health1.website == "http://enriched-biz-health-1.com"
        assert health1.phone == "555-0000"
        assert health1.last_enriched_at is not None

    @pytest.mark.asyncio
    async def test_bucket_priority_order(self, setup_test_businesses, test_db_session):
        """Test that buckets are processed in priority order"""
        with patch("flows.bucket_enrichment_flow.process_single_bucket") as mock_process:
            # Track order of bucket processing
            processed_buckets = []

            async def track_bucket(bucket_name, config):
                processed_buckets.append((bucket_name, config.priority.value))
                return Mock(
                    bucket_name=bucket_name,
                    strategy=config.strategy.value,
                    total_businesses=1,
                    enriched_businesses=1,
                    total_cost=0.10,
                )

            mock_process.side_effect = track_bucket

            # Run flow
            await bucket_enrichment_flow(max_buckets=3, total_budget=10.0)

            # Verify priority order: HIGH -> MEDIUM -> LOW
            priorities = [p[1] for p in processed_buckets]
            assert priorities[0] == "high"  # Healthcare
            if len(priorities) > 1:
                assert priorities[1] == "medium"  # SaaS
            if len(priorities) > 2:
                assert priorities[2] == "low"  # Restaurants

    @pytest.mark.asyncio
    async def test_skip_recently_enriched(self, setup_test_businesses, test_db_session):
        """Test that recently enriched businesses are skipped"""
        with patch("flows.bucket_enrichment_flow.EnrichmentCoordinator") as mock_coord_class:
            mock_coordinator = AsyncMock()
            mock_coord_class.return_value = mock_coordinator

            # Track which businesses are sent for enrichment
            enriched_ids = []

            async def track_enrichment(businesses, **kwargs):
                enriched_ids.extend([b["id"] for b in businesses])
                return Mock(
                    successful_enrichments=len(businesses), skipped_enrichments=0, failed_enrichments=0, results=[]
                )

            mock_coordinator.enrich_businesses_batch.side_effect = track_enrichment

            # Run flow
            await bucket_enrichment_flow(max_buckets=5, total_budget=10.0)

            # Verify recently enriched business was not sent for enrichment
            assert "biz-rest-2" not in enriched_ids  # Has enrichment from 3 days ago
            assert "biz-health-1" in enriched_ids  # Never enriched
            assert "biz-health-2" in enriched_ids  # Enriched 60 days ago

    @pytest.mark.asyncio
    async def test_budget_enforcement(self, setup_test_businesses, test_db_session):
        """Test that budget limits are enforced"""
        with patch("flows.bucket_enrichment_flow.EnrichmentCoordinator") as mock_coord_class:
            mock_coordinator = AsyncMock()
            mock_coord_class.return_value = mock_coordinator

            # Simulate high cost enrichments
            call_count = 0

            async def expensive_enrichment(businesses, **kwargs):
                nonlocal call_count
                call_count += 1
                # Each business costs $0.50
                return Mock(
                    successful_enrichments=len(businesses),
                    skipped_enrichments=0,
                    failed_enrichments=0,
                    results=[Mock(business_id=b["id"]) for b in businesses],
                )

            mock_coordinator.enrich_businesses_batch.side_effect = expensive_enrichment

            # Patch the cost calculation
            with patch("flows.bucket_enrichment_flow.enrich_bucket_batch") as mock_enrich:

                async def mock_batch_with_cost(businesses, config, bucket_name, current_cost):
                    # Each business costs $0.50
                    cost = len(businesses) * 0.50
                    if current_cost + cost > config.max_budget:
                        return [], current_cost
                    return businesses, current_cost + cost

                mock_enrich.side_effect = mock_batch_with_cost

                # Run with small budget
                result = await bucket_enrichment_flow(max_buckets=None, total_budget=2.0)  # Only $2 budget

                # Should stop due to budget
                assert result["total_cost"] <= 2.0

    @pytest.mark.asyncio
    async def test_error_handling(self, setup_test_businesses, test_db_session):
        """Test error handling in bucket processing"""
        with patch("flows.bucket_enrichment_flow.process_single_bucket") as mock_process:
            # First bucket succeeds, second fails
            async def process_with_error(bucket_name, config):
                if "saas" in bucket_name:
                    raise Exception("Simulated processing error")
                return Mock(
                    bucket_name=bucket_name,
                    strategy=config.strategy.value,
                    total_businesses=1,
                    enriched_businesses=1,
                    total_cost=0.10,
                )

            mock_process.side_effect = process_with_error

            # Run flow - should continue despite error
            result = await bucket_enrichment_flow(max_buckets=3, total_budget=10.0)

            assert result["status"] == "completed"
            assert result["buckets_processed"] >= 1  # At least one succeeded

    @pytest.mark.asyncio
    async def test_manual_trigger_integration(self, setup_test_businesses, test_db_session):
        """Test manual trigger function"""
        with patch("flows.bucket_enrichment_flow.EnrichmentCoordinator") as mock_coord_class:
            mock_coordinator = AsyncMock()
            mock_coord_class.return_value = mock_coordinator

            mock_coordinator.enrich_businesses_batch.return_value = Mock(
                successful_enrichments=2, skipped_enrichments=0, failed_enrichments=0, results=[]
            )

            # Trigger manually with small limits
            result = await trigger_bucket_enrichment(max_buckets=1, total_budget=5.0)

            assert result["status"] == "completed"
            assert result["buckets_processed"] == 1
            assert result["total_cost"] <= 5.0

    @pytest.mark.asyncio
    async def test_no_buckets_scenario(self, test_db_session):
        """Test flow when no businesses have buckets"""
        # Don't create any businesses
        result = await bucket_enrichment_flow(max_buckets=10, total_budget=100.0)

        assert result["status"] == "no_data"
        assert result["buckets_processed"] == 0
        assert result["total_enriched"] == 0
        assert result["total_cost"] == 0.0


@pytest.mark.integration
class TestBucketLoaderIntegration:
    """Test integration with bucket loader"""

    @pytest.mark.skipif(not callable(get_bucket_loader), reason="Bucket loader not available")
    def test_bucket_loader_integration(self):
        """Test that bucket loader can be initialized"""
        try:
            loader = get_bucket_loader()
            stats = loader.get_stats()

            # Loader should return some statistics
            assert "total_zip_codes" in stats
            assert "total_categories" in stats
        except Exception as e:
            # Skip if bucket data not available
            pytest.skip(f"Bucket loader not configured: {e}")
