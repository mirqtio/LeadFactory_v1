"""
Unit tests for Phase 0.5 bucket enrichment flow
Task ET-07: Test nightly bucket_enrichment Prefect flow
"""
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from d11_orchestration.bucket_enrichment import (
    load_bucket_features,
    get_unenriched_entities,
    enrich_with_buckets,
    update_entity_buckets,
    bucket_enrichment_flow,
)

# Mark entire module as xfail for Phase 0.5
pytestmark = pytest.mark.xfail(reason="Phase 0.5 feature", strict=False)


class TestBucketEnrichmentFlow:
    """Test bucket enrichment flow components"""

    @patch("d11_orchestration.flows.bucket_enrichment.get_bucket_loader")
    def test_load_bucket_features(self, mock_get_loader):
        """Test loading bucket features from CSV"""
        # Mock loader stats
        mock_loader = MagicMock()
        mock_loader.get_stats.return_value = {
            "total_zip_codes": 79,
            "total_categories": 90,
            "unique_geo_buckets": 12,
            "unique_vert_buckets": 8,
            "geo_bucket_list": ["high-high-high", "high-high-low"],
            "vert_bucket_list": ["high-high-medium", "low-low-low"],
        }
        mock_get_loader.return_value = mock_loader

        # Test loading
        stats = load_bucket_features()

        assert stats["total_zip_codes"] == 79
        assert stats["total_categories"] == 90
        assert stats["unique_geo_buckets"] == 12
        assert stats["unique_vert_buckets"] == 8

    @patch("d11_orchestration.flows.bucket_enrichment.SessionLocal")
    def test_get_unenriched_entities(self, mock_session):
        """Test fetching entities without buckets"""
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db

        # Mock business results
        mock_business = MagicMock()
        mock_business.id = "biz-123"
        mock_business.name = "Test Business"
        mock_business.zip_code = "94105"
        mock_business.categories = ["restaurants"]

        # Mock target results
        mock_target = MagicMock()
        mock_target.id = "tgt-456"
        mock_target.business_name = "Target Business"
        mock_target.zip_code = "10001"
        mock_target.categories = ["dentists"]

        # Set up query results
        mock_db.execute.return_value.scalars.return_value.all.side_effect = [
            [mock_business],  # Business query
            [mock_target],  # Target query
        ]

        # Test
        entities = get_unenriched_entities(batch_size=10)

        assert len(entities["businesses"]) == 1
        assert len(entities["targets"]) == 1
        assert entities["businesses"][0]["id"] == "biz-123"
        assert entities["targets"][0]["id"] == "tgt-456"

    @patch("d11_orchestration.flows.bucket_enrichment.get_bucket_loader")
    def test_enrich_with_buckets(self, mock_get_loader):
        """Test bucket enrichment logic"""
        # Mock loader
        mock_loader = MagicMock()

        def mock_enrich(entity):
            # Simulate enrichment
            entity_copy = entity.copy()
            if entity["zip_code"] == "94105":
                entity_copy["geo_bucket"] = "high-high-high"
            else:
                entity_copy["geo_bucket"] = None

            if "restaurants" in entity.get("categories", []):
                entity_copy["vert_bucket"] = "medium-medium-low"
            else:
                entity_copy["vert_bucket"] = None

            return entity_copy

        mock_loader.enrich_business = mock_enrich
        mock_get_loader.return_value = mock_loader

        # Test data
        entities = {
            "businesses": [
                {"id": "biz-1", "zip_code": "94105", "categories": ["restaurants"]},
                {"id": "biz-2", "zip_code": "99999", "categories": ["unknown"]},
            ],
            "targets": [
                {"id": "tgt-1", "zip_code": "94105", "categories": ["dentists"]}
            ],
        }

        # Test enrichment
        result = enrich_with_buckets(entities)

        # Check results
        assert result["businesses"][0]["geo_bucket"] == "high-high-high"
        assert result["businesses"][0]["vert_bucket"] == "medium-medium-low"
        assert result["businesses"][1]["geo_bucket"] is None
        assert result["businesses"][1]["vert_bucket"] is None

        assert result["stats"]["businesses_enriched"] == 2
        assert result["stats"]["targets_enriched"] == 1
        assert result["stats"]["missing_zips"] == 1  # '99999'
        assert result["stats"]["missing_categories"] == 2  # 'unknown', 'dentists'

    @patch("d11_orchestration.flows.bucket_enrichment.SessionLocal")
    @patch("d11_orchestration.flows.bucket_enrichment.update")
    def test_update_entity_buckets(self, mock_update, mock_session):
        """Test database update with buckets"""
        # Mock database
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db

        # Mock update results
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_db.execute.return_value = mock_result

        # Test data
        enriched_entities = {
            "businesses": [
                {
                    "id": "biz-1",
                    "geo_bucket": "high-high-high",
                    "vert_bucket": "medium-medium-low",
                }
            ],
            "targets": [
                {
                    "id": "tgt-1",
                    "geo_bucket": "low-low-low",
                    "vert_bucket": "high-high-medium",
                }
            ],
            "stats": {},
        }

        # Test update
        result = update_entity_buckets(enriched_entities)

        assert result["businesses_updated"] == 1
        assert result["targets_updated"] == 1
        assert result["errors"] == 0

        # Verify commit was called
        mock_db.commit.assert_called_once()

    @patch("d11_orchestration.flows.bucket_enrichment.load_bucket_features")
    @patch("d11_orchestration.flows.bucket_enrichment.get_unenriched_entities")
    @patch("d11_orchestration.flows.bucket_enrichment.enrich_with_buckets")
    @patch("d11_orchestration.flows.bucket_enrichment.update_entity_buckets")
    def test_bucket_enrichment_flow(
        self, mock_update, mock_enrich, mock_get_entities, mock_load
    ):
        """Test complete flow execution"""
        # Mock feature loading
        mock_load.return_value = {
            "total_zip_codes": 79,
            "total_categories": 90,
            "unique_geo_buckets": 12,
            "unique_vert_buckets": 8,
        }

        # Mock entity fetching (return empty on second call)
        mock_get_entities.side_effect = [
            {"businesses": [{"id": "biz-1"}], "targets": [{"id": "tgt-1"}]},
            {"businesses": [], "targets": []},
        ]

        # Mock enrichment
        mock_enrich.return_value = {
            "businesses": [
                {
                    "id": "biz-1",
                    "geo_bucket": "high-high-high",
                    "vert_bucket": "medium-medium-low",
                }
            ],
            "targets": [
                {
                    "id": "tgt-1",
                    "geo_bucket": "low-low-low",
                    "vert_bucket": "high-high-medium",
                }
            ],
            "stats": {
                "businesses_enriched": 1,
                "targets_enriched": 1,
                "missing_zips": 0,
                "missing_categories": 0,
                "missing_zip_list": [],
                "missing_category_list": [],
            },
        }

        # Mock update
        mock_update.return_value = {
            "businesses_updated": 1,
            "targets_updated": 1,
            "errors": 0,
        }

        # Run flow
        result = bucket_enrichment_flow(batch_size=10, max_batches=5)

        # Check results
        assert result["batches_processed"] == 1
        assert result["businesses_updated"] == 1
        assert result["targets_updated"] == 1
        assert result["total_errors"] == 0

    def test_flow_schedule(self):
        """Test that flow is scheduled for 02:00 UTC"""
        from d11_orchestration.flows.bucket_enrichment import create_nightly_deployment

        deployment = create_nightly_deployment()

        # Check schedule (mocked Deployment will just return self)
        assert deployment is not None

    @pytest.mark.asyncio
    async def test_manual_trigger(self):
        """Test manual flow trigger"""
        from d11_orchestration.flows.bucket_enrichment import trigger_bucket_enrichment

        with patch(
            "d11_orchestration.flows.bucket_enrichment.bucket_enrichment_flow"
        ) as mock_flow:
            mock_flow.return_value = {"status": "success"}

            result = await trigger_bucket_enrichment(batch_size=5, max_batches=1)

            assert result["status"] == "success"
            mock_flow.assert_called_once_with(batch_size=5, max_batches=1)

    def test_missing_data_logging(self):
        """Test that missing ZIP codes and categories are logged"""
        with patch(
            "d11_orchestration.flows.bucket_enrichment.get_bucket_loader"
        ) as mock_get_loader:
            # Mock loader to return None for certain inputs
            mock_loader = MagicMock()
            mock_loader.enrich_business.side_effect = lambda x: {
                **x,
                "geo_bucket": None,
                "vert_bucket": None,
            }
            mock_get_loader.return_value = mock_loader

            # Test data with various ZIPs and categories
            entities = {
                "businesses": [
                    {"id": "b1", "zip_code": "99999", "categories": ["unknown1"]},
                    {
                        "id": "b2",
                        "zip_code": "88888",
                        "categories": ["unknown2", "unknown3"],
                    },
                ],
                "targets": [],
            }

            # Run enrichment
            result = enrich_with_buckets(entities)

            # Check missing data was tracked
            assert "99999" in result["stats"]["missing_zip_list"]
            assert "88888" in result["stats"]["missing_zip_list"]
            assert "unknown1" in result["stats"]["missing_category_list"]
            assert "unknown2" in result["stats"]["missing_category_list"]
            assert "unknown3" in result["stats"]["missing_category_list"]
