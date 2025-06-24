"""
Tests for bucket enrichment flow - Phase 0.5 Task ET-07
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from d11_orchestration.bucket_enrichment import (
    load_bucket_features,
    get_unenriched_businesses,
    enrich_business_buckets,
    update_business_buckets,
    bucket_enrichment_flow,
)


class TestBucketEnrichmentTasks:
    """Test individual tasks in the bucket enrichment flow"""

    @patch("d11_orchestration.bucket_enrichment.get_bucket_loader")
    def test_load_bucket_features(self, mock_get_loader):
        """Test loading bucket features"""
        # Mock loader with stats
        mock_loader = Mock()
        mock_loader.get_stats.return_value = {
            "total_zip_codes": 100,
            "total_categories": 50,
            "unique_geo_buckets": 10,
            "unique_vert_buckets": 8,
            "geo_bucket_list": ["high-high-high", "medium-medium-medium"],
            "vert_bucket_list": ["high-high-medium", "low-low-low"],
        }
        mock_get_loader.return_value = mock_loader

        # Run task
        stats = load_bucket_features()

        # Verify
        assert stats["total_zip_codes"] == 100
        assert stats["total_categories"] == 50
        assert stats["unique_geo_buckets"] == 10
        assert stats["unique_vert_buckets"] == 8

    @patch("d11_orchestration.bucket_enrichment.SessionLocal")
    def test_get_unenriched_businesses(self, mock_session):
        """Test fetching businesses without buckets"""
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db

        # Mock query results
        mock_leads = [
            Mock(
                id=1,
                business_name="Test Business 1",
                zip_code="94105",
                categories=["restaurants"],
            ),
            Mock(
                id=2,
                business_name="Test Business 2",
                zip_code="10001",
                categories=["dentists", "health"],
            ),
        ]

        mock_db.execute.return_value.scalars.return_value.all.return_value = mock_leads

        # Run task
        businesses = get_unenriched_businesses(batch_size=10)

        # Verify
        assert len(businesses) == 2
        assert businesses[0]["id"] == 1
        assert businesses[0]["zip_code"] == "94105"
        assert businesses[1]["categories"] == ["dentists", "health"]

    @patch("d11_orchestration.bucket_enrichment.get_bucket_loader")
    def test_enrich_business_buckets(self, mock_get_loader):
        """Test enriching businesses with buckets"""
        # Mock loader
        mock_loader = Mock()

        def mock_enrich(business):
            # Simulate enrichment
            business["geo_bucket"] = (
                "high-high-high" if business["zip_code"] == "94105" else None
            )
            business["vert_bucket"] = (
                "medium-medium-low" if "restaurants" in business["categories"] else None
            )
            return business

        mock_loader.enrich_business.side_effect = mock_enrich
        mock_get_loader.return_value = mock_loader

        # Test data
        businesses = [
            {
                "id": 1,
                "name": "Test Restaurant",
                "zip_code": "94105",
                "categories": ["restaurants"],
            },
            {
                "id": 2,
                "name": "Unknown Business",
                "zip_code": "00000",
                "categories": ["unknown"],
            },
        ]

        # Run task
        enriched = enrich_business_buckets(businesses)

        # Verify
        assert len(enriched) == 2
        assert enriched[0]["geo_bucket"] == "high-high-high"
        assert enriched[0]["vert_bucket"] == "medium-medium-low"
        assert enriched[1]["geo_bucket"] is None
        assert enriched[1]["vert_bucket"] is None

    @patch("d11_orchestration.bucket_enrichment.SessionLocal")
    @patch("d11_orchestration.bucket_enrichment.update")
    def test_update_business_buckets(self, mock_update, mock_session):
        """Test updating database with buckets"""
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db

        # Mock update results
        mock_result = Mock(rowcount=1)
        mock_db.execute.return_value = mock_result

        # Test data
        enriched_businesses = [
            {
                "id": 1,
                "geo_bucket": "high-high-high",
                "vert_bucket": "medium-medium-low",
            },
            {"id": 2, "geo_bucket": None, "vert_bucket": "low-low-low"},
        ]

        # Run task
        stats = update_business_buckets(enriched_businesses)

        # Verify
        assert stats["updated"] == 2  # Both updates succeed
        assert stats["errors"] == 0
        assert mock_db.commit.called

    @patch("d11_orchestration.bucket_enrichment.SessionLocal")
    @patch("d11_orchestration.bucket_enrichment.update")
    def test_update_business_buckets_with_error(self, mock_update, mock_session):
        """Test handling errors during update"""
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db

        # First update succeeds, second fails
        mock_db.execute.side_effect = [Mock(rowcount=1), Exception("Database error")]

        # Test data
        enriched_businesses = [
            {
                "id": 1,
                "geo_bucket": "high-high-high",
                "vert_bucket": "medium-medium-low",
            },
            {"id": 2, "geo_bucket": None, "vert_bucket": "low-low-low"},
        ]

        # Run task
        stats = update_business_buckets(enriched_businesses)

        # Verify
        assert stats["updated"] == 1
        assert stats["errors"] == 1


class TestBucketEnrichmentFlow:
    """Test the complete bucket enrichment flow"""

    @patch("d11_orchestration.bucket_enrichment.load_bucket_features")
    @patch("d11_orchestration.bucket_enrichment.get_unenriched_businesses")
    @patch("d11_orchestration.bucket_enrichment.enrich_business_buckets")
    @patch("d11_orchestration.bucket_enrichment.update_business_buckets")
    def test_bucket_enrichment_flow_success(
        self, mock_update, mock_enrich, mock_get_businesses, mock_load_features
    ):
        """Test successful flow execution"""
        # Mock feature loading
        mock_load_features.return_value = {
            "total_zip_codes": 100,
            "total_categories": 50,
        }

        # Mock getting businesses (return empty on second call)
        mock_get_businesses.side_effect = [
            [{"id": 1}, {"id": 2}],  # First batch
            [],  # No more businesses
        ]

        # Mock enrichment
        mock_enrich.return_value = [
            {
                "id": 1,
                "geo_bucket": "high-high-high",
                "vert_bucket": "medium-medium-low",
            },
            {"id": 2, "geo_bucket": "low-low-low", "vert_bucket": "high-high-medium"},
        ]

        # Mock update
        mock_update.return_value = {"updated": 2, "errors": 0}

        # Run flow
        result = bucket_enrichment_flow(batch_size=10, max_batches=5)

        # Verify
        assert result["batches_processed"] == 1
        assert result["total_updated"] == 2
        assert result["total_errors"] == 0
        assert "feature_stats" in result

    @patch("d11_orchestration.bucket_enrichment.load_bucket_features")
    @patch("d11_orchestration.bucket_enrichment.get_unenriched_businesses")
    def test_bucket_enrichment_flow_no_businesses(
        self, mock_get_businesses, mock_load_features
    ):
        """Test flow when no businesses need enrichment"""
        # Mock feature loading
        mock_load_features.return_value = {"total_zip_codes": 100}

        # No businesses to process
        mock_get_businesses.return_value = []

        # Run flow
        result = bucket_enrichment_flow(batch_size=10, max_batches=5)

        # Verify
        assert result["batches_processed"] == 0
        assert result["total_updated"] == 0
        assert result["total_errors"] == 0

    @patch("d11_orchestration.bucket_enrichment.load_bucket_features")
    @patch("d11_orchestration.bucket_enrichment.get_unenriched_businesses")
    @patch("d11_orchestration.bucket_enrichment.enrich_business_buckets")
    @patch("d11_orchestration.bucket_enrichment.update_business_buckets")
    def test_bucket_enrichment_flow_multiple_batches(
        self, mock_update, mock_enrich, mock_get_businesses, mock_load_features
    ):
        """Test flow with multiple batches"""
        # Mock feature loading
        mock_load_features.return_value = {"total_zip_codes": 100}

        # Mock getting businesses (3 batches then empty)
        mock_get_businesses.side_effect = [
            [{"id": 1}, {"id": 2}],  # Batch 1
            [{"id": 3}, {"id": 4}],  # Batch 2
            [{"id": 5}],  # Batch 3
            [],  # No more
        ]

        # Mock enrichment (just return input)
        mock_enrich.side_effect = lambda x: x

        # Mock updates
        mock_update.side_effect = [
            {"updated": 2, "errors": 0},
            {"updated": 2, "errors": 0},
            {"updated": 1, "errors": 0},
        ]

        # Run flow
        result = bucket_enrichment_flow(batch_size=2, max_batches=10)

        # Verify
        assert result["batches_processed"] == 3
        assert result["total_updated"] == 5
        assert result["total_errors"] == 0
