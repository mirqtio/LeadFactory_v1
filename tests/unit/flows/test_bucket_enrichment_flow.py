"""
Unit tests for P1-080 Bucket Enrichment Flow
Tests the flows/bucket_enrichment_flow.py implementation
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from flows.bucket_enrichment_flow import (
    BucketEnrichmentConfig,
    BucketPriority,
    BucketProcessingStats,
    BucketQueue,
    BucketStrategy,
    bucket_enrichment_flow,
    build_bucket_queue,
    enrich_bucket_batch,
    get_businesses_for_bucket,
    identify_bucket_segments,
    process_single_bucket,
    update_enriched_businesses,
)

# Mark entire module for Phase 0.5 feature implementation
pytestmark = pytest.mark.xfail(reason="Phase 0.5 feature - not yet implemented", strict=False)


class TestBucketQueue:
    """Test bucket queue prioritization"""

    def test_queue_priority_ordering(self):
        """Test that buckets are ordered by priority"""
        queue = BucketQueue()

        # Add buckets in random order
        queue.add_bucket(
            "restaurants",
            BucketEnrichmentConfig(
                strategy=BucketStrategy.RESTAURANTS,
                priority=BucketPriority.LOW,
                max_budget=100.0,
                enrichment_sources=[],
                batch_size=100,
                max_concurrent=5,
            ),
        )

        queue.add_bucket(
            "healthcare",
            BucketEnrichmentConfig(
                strategy=BucketStrategy.HEALTHCARE,
                priority=BucketPriority.HIGH,
                max_budget=1000.0,
                enrichment_sources=[],
                batch_size=50,
                max_concurrent=3,
            ),
        )

        queue.add_bucket(
            "saas",
            BucketEnrichmentConfig(
                strategy=BucketStrategy.SAAS,
                priority=BucketPriority.MEDIUM,
                max_budget=500.0,
                enrichment_sources=[],
                batch_size=100,
                max_concurrent=5,
            ),
        )

        # Check order - should be HIGH, MEDIUM, LOW
        bucket1 = queue.get_next()
        assert bucket1[0] == "healthcare"

        bucket2 = queue.get_next()
        assert bucket2[0] == "saas"

        bucket3 = queue.get_next()
        assert bucket3[0] == "restaurants"

        # No more buckets
        assert queue.get_next() is None


class TestBucketEnrichmentTasks:
    """Test individual tasks in the bucket enrichment flow"""

    @patch("flows.bucket_enrichment_flow.SessionLocal")
    def test_identify_bucket_segments(self, mock_session):
        """Test identifying unique bucket segments"""
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db

        # Mock query results
        mock_db.execute.return_value.all.return_value = [
            ("healthcare-urgent", 150),
            ("saas-medium", 100),
            ("restaurants-low", 50),
        ]

        # Test
        segments = identify_bucket_segments()

        assert len(segments) == 3
        assert segments[0] == ("healthcare-urgent", 150)
        assert segments[1] == ("saas-medium", 100)
        assert segments[2] == ("restaurants-low", 50)

    def test_build_bucket_queue(self):
        """Test building priority queue from segments"""
        segments = [
            ("healthcare-urgent", 150),
            ("software-saas", 100),
            ("restaurant-casual", 50),
            ("other-business", 25),
        ]

        queue = build_bucket_queue(segments)

        # Check queue has all buckets
        assert len(queue.buckets) == 4

        # Check priority order
        bucket1 = queue.get_next()
        assert "health" in bucket1[0].lower()
        assert bucket1[1].priority == BucketPriority.HIGH

        bucket2 = queue.get_next()
        assert "software" in bucket2[0].lower()
        assert bucket2[1].priority == BucketPriority.MEDIUM

    @patch("flows.bucket_enrichment_flow.SessionLocal")
    def test_get_businesses_for_bucket(self, mock_session):
        """Test fetching businesses for a specific bucket"""
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db

        # Mock businesses
        mock_business1 = Mock(
            id="biz-1",
            name="Test Healthcare",
            website="http://example.com",
            phone="555-1234",
            email="test@example.com",
            address="123 Main St",
            city="San Francisco",
            state="CA",
            zip_code="94105",
            categories=["healthcare"],
            vert_bucket="healthcare-urgent",
            geo_bucket="high-high-high",
        )

        mock_business2 = Mock(
            id="biz-2",
            name="Test Clinic",
            website=None,
            phone=None,
            email=None,
            address="456 Oak St",
            city="San Francisco",
            state="CA",
            zip_code="94105",
            categories=["medical"],
            vert_bucket="healthcare-urgent",
            geo_bucket="high-high-high",
        )

        mock_db.execute.return_value.scalars.return_value.all.return_value = [mock_business1, mock_business2]

        # Test
        config = BucketEnrichmentConfig(
            strategy=BucketStrategy.HEALTHCARE,
            priority=BucketPriority.HIGH,
            max_budget=1000.0,
            enrichment_sources=[],
            batch_size=10,
            max_concurrent=3,
            skip_recent_days=7,
        )

        businesses = get_businesses_for_bucket("healthcare-urgent", config)

        assert len(businesses) == 2
        assert businesses[0]["id"] == "biz-1"
        assert businesses[0]["name"] == "Test Healthcare"
        assert businesses[1]["id"] == "biz-2"
        assert businesses[1]["website"] is None

    @patch("flows.bucket_enrichment_flow.EnrichmentCoordinator")
    @pytest.mark.asyncio
    async def test_enrich_bucket_batch(self, mock_coordinator_class):
        """Test enriching a batch of businesses"""
        # Mock coordinator
        mock_coordinator = AsyncMock()
        mock_coordinator_class.return_value = mock_coordinator

        # Mock batch result
        mock_result1 = Mock(
            business_id="biz-1",
            enriched_data={"website": "http://updated.com", "phone": "555-5678"},
            completed_at=datetime.utcnow(),
            sources_completed=["internal", "hunter"],
        )

        mock_batch_result = Mock(
            successful_enrichments=1, skipped_enrichments=0, failed_enrichments=1, results=[mock_result1]
        )

        mock_coordinator.enrich_businesses_batch.return_value = mock_batch_result

        # Test data
        businesses = [
            {
                "id": "biz-1",
                "name": "Test Business",
                "website": None,
                "phone": None,
            },
            {
                "id": "biz-2",
                "name": "Failed Business",
                "website": None,
                "phone": None,
            },
        ]

        config = BucketEnrichmentConfig(
            strategy=BucketStrategy.HEALTHCARE,
            priority=BucketPriority.HIGH,
            max_budget=1000.0,
            enrichment_sources=[],
            batch_size=10,
            max_concurrent=3,
        )

        # Test enrichment
        enriched, new_cost = await enrich_bucket_batch(businesses, config, "healthcare-urgent", 0.0)

        assert len(enriched) == 1
        assert enriched[0]["id"] == "biz-1"
        assert enriched[0]["website"] == "http://updated.com"
        assert enriched[0]["phone"] == "555-5678"
        assert new_cost == 0.10  # 1 successful * $0.10

    @patch("flows.bucket_enrichment_flow.SessionLocal")
    def test_update_enriched_businesses(self, mock_session):
        """Test updating businesses with enrichment data"""
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db

        # Mock update results
        mock_result = Mock(rowcount=1)
        mock_db.execute.return_value = mock_result

        # Test data
        enriched_businesses = [
            {
                "id": "biz-1",
                "website": "http://enriched.com",
                "phone": "555-9999",
                "email": "new@example.com",
                "last_enriched_at": datetime.utcnow(),
            },
            {
                "id": "biz-2",
                "website": "http://another.com",
                "phone": "555-8888",
                "last_enriched_at": datetime.utcnow(),
            },
        ]

        # Test update
        count = update_enriched_businesses(enriched_businesses)

        assert count == 2
        assert mock_db.commit.called


class TestBucketProcessing:
    """Test bucket processing logic"""

    @patch("flows.bucket_enrichment_flow.get_businesses_for_bucket")
    @patch("flows.bucket_enrichment_flow.enrich_bucket_batch")
    @patch("flows.bucket_enrichment_flow.update_enriched_businesses")
    @pytest.mark.asyncio
    async def test_process_single_bucket(self, mock_update, mock_enrich, mock_get_businesses):
        """Test processing a single bucket"""
        # Mock getting businesses (2 batches then empty)
        mock_get_businesses.side_effect = [
            [{"id": "biz-1"}, {"id": "biz-2"}],  # First batch
            [{"id": "biz-3"}],  # Second batch
            [],  # No more
        ]

        # Mock enrichment
        mock_enrich.side_effect = [
            ([{"id": "biz-1"}, {"id": "biz-2"}], 0.20),  # 2 * $0.10
            ([{"id": "biz-3"}], 0.30),  # Total $0.30
        ]

        # Mock update
        mock_update.side_effect = [2, 1]

        # Test config
        config = BucketEnrichmentConfig(
            strategy=BucketStrategy.HEALTHCARE,
            priority=BucketPriority.HIGH,
            max_budget=10.0,
            enrichment_sources=[],
            batch_size=2,
            max_concurrent=3,
        )

        # Process bucket
        stats = await process_single_bucket("healthcare-urgent", config)

        assert stats.bucket_name == "healthcare-urgent"
        assert stats.total_businesses == 3
        assert stats.enriched_businesses == 3
        assert stats.total_cost == 0.30
        assert stats.success_rate == 100.0

    @patch("flows.bucket_enrichment_flow.get_businesses_for_bucket")
    @patch("flows.bucket_enrichment_flow.enrich_bucket_batch")
    @pytest.mark.asyncio
    async def test_process_bucket_budget_limit(self, mock_enrich, mock_get_businesses):
        """Test budget limit enforcement"""
        # Mock getting businesses
        mock_get_businesses.side_effect = [
            [{"id": f"biz-{i}"} for i in range(10)],  # First batch
            [{"id": f"biz-{i}"} for i in range(10, 20)],  # Second batch
        ]

        # Mock enrichment - second batch exceeds budget
        mock_enrich.side_effect = [
            ([{"id": f"biz-{i}"} for i in range(10)], 0.80),  # $0.80
            ([], 1.20),  # Would exceed $1.00 budget
        ]

        # Test config with $1.00 budget
        config = BucketEnrichmentConfig(
            strategy=BucketStrategy.RESTAURANTS,
            priority=BucketPriority.LOW,
            max_budget=1.0,
            enrichment_sources=[],
            batch_size=10,
            max_concurrent=5,
        )

        # Process bucket
        stats = await process_single_bucket("restaurants-low", config)

        assert stats.total_businesses == 10  # Only first batch
        assert stats.enriched_businesses == 10
        assert stats.total_cost == 0.80
        assert stats.total_cost < config.max_budget


class TestBucketEnrichmentFlow:
    """Test the complete bucket enrichment flow"""

    @patch("flows.bucket_enrichment_flow.identify_bucket_segments")
    @patch("flows.bucket_enrichment_flow.build_bucket_queue")
    @patch("flows.bucket_enrichment_flow.process_single_bucket")
    @pytest.mark.asyncio
    async def test_bucket_enrichment_flow_success(self, mock_process, mock_build_queue, mock_identify):
        """Test successful flow execution"""
        # Mock segments
        mock_identify.return_value = [
            ("healthcare-urgent", 100),
            ("saas-medium", 50),
        ]

        # Mock queue
        mock_queue = MagicMock()
        mock_queue.get_next.side_effect = [
            ("healthcare-urgent", MagicMock()),
            ("saas-medium", MagicMock()),
            None,  # End of queue
        ]
        mock_build_queue.return_value = mock_queue

        # Mock processing results
        stats1 = BucketProcessingStats(
            bucket_name="healthcare-urgent",
            strategy="healthcare",
            total_businesses=100,
            enriched_businesses=90,
            total_cost=9.0,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow() + timedelta(minutes=5),
        )

        stats2 = BucketProcessingStats(
            bucket_name="saas-medium",
            strategy="saas",
            total_businesses=50,
            enriched_businesses=45,
            total_cost=4.5,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow() + timedelta(minutes=3),
        )

        mock_process.side_effect = [stats1, stats2]

        # Run flow
        result = await bucket_enrichment_flow(max_buckets=None, total_budget=100.0)

        assert result["status"] == "completed"
        assert result["buckets_processed"] == 2
        assert result["total_businesses"] == 150
        assert result["total_enriched"] == 135
        assert result["total_cost"] == 13.5
        assert len(result["bucket_stats"]) == 2

    @patch("flows.bucket_enrichment_flow.identify_bucket_segments")
    @pytest.mark.asyncio
    async def test_bucket_enrichment_flow_no_data(self, mock_identify):
        """Test flow when no buckets found"""
        mock_identify.return_value = []

        result = await bucket_enrichment_flow()

        assert result["status"] == "no_data"
        assert result["buckets_processed"] == 0
        assert result["total_enriched"] == 0

    @patch("flows.bucket_enrichment_flow.identify_bucket_segments")
    @patch("flows.bucket_enrichment_flow.build_bucket_queue")
    @patch("flows.bucket_enrichment_flow.process_single_bucket")
    @pytest.mark.asyncio
    async def test_bucket_enrichment_flow_budget_limit(self, mock_process, mock_build_queue, mock_identify):
        """Test flow stops when total budget reached"""
        # Mock segments
        mock_identify.return_value = [
            ("healthcare-urgent", 100),
            ("saas-medium", 50),
            ("restaurants-low", 25),
        ]

        # Mock queue
        mock_queue = MagicMock()
        mock_queue.get_next.side_effect = [
            ("healthcare-urgent", MagicMock(max_budget=50.0)),
            ("saas-medium", MagicMock(max_budget=50.0)),
            ("restaurants-low", MagicMock(max_budget=50.0)),
        ]
        mock_build_queue.return_value = mock_queue

        # Mock processing - third bucket would exceed budget
        stats1 = BucketProcessingStats(
            bucket_name="healthcare-urgent",
            strategy="healthcare",
            total_businesses=100,
            enriched_businesses=90,
            total_cost=45.0,
        )

        stats2 = BucketProcessingStats(
            bucket_name="saas-medium", strategy="saas", total_businesses=50, enriched_businesses=45, total_cost=40.0
        )

        mock_process.side_effect = [stats1, stats2]

        # Run flow with $100 budget
        result = await bucket_enrichment_flow(max_buckets=None, total_budget=100.0)

        # Should only process 2 buckets due to budget
        assert result["buckets_processed"] == 2
        assert result["total_cost"] == 85.0
        assert result["total_cost"] < 100.0


class TestDeployment:
    """Test deployment configuration"""

    def test_create_nightly_deployment(self):
        """Test deployment creation"""
        from flows.bucket_enrichment_flow import create_nightly_deployment

        deployment = create_nightly_deployment()

        # Deployment object exists (mocked)
        assert deployment is not None

    @pytest.mark.asyncio
    async def test_manual_trigger(self):
        """Test manual trigger function"""
        from flows.bucket_enrichment_flow import trigger_bucket_enrichment

        with patch("flows.bucket_enrichment_flow.bucket_enrichment_flow") as mock_flow:
            mock_flow.return_value = {"status": "completed", "buckets_processed": 2}

            result = await trigger_bucket_enrichment(max_buckets=2, total_budget=50.0)

            assert result["status"] == "completed"
            assert result["buckets_processed"] == 2

            # Check flow was called with correct params
            mock_flow.assert_called_once_with(max_buckets=2, total_budget=50.0, bucket_limit=10)
