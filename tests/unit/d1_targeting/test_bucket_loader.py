"""
Tests for bucket feature loader - Phase 0.5 Task TG-06
"""
import tempfile
from pathlib import Path

import pytest

from d1_targeting.bucket_loader import BucketFeatureLoader


class TestBucketFeatureLoader:
    """Test bucket feature loading and assignment"""

    @pytest.fixture
    def temp_seed_dir(self):
        """Create temporary seed directory with test data"""
        with tempfile.TemporaryDirectory() as tmpdir:
            seed_dir = Path(tmpdir)

            # Create test geo features
            geo_csv = seed_dir / "geo_features.csv"
            geo_csv.write_text(
                """zip_code,city,state,affluence,agency_density,broadband_quality
94105,San Francisco,CA,high,high,high
94107,San Francisco,CA,high,high,high
10001,New York,NY,high,high,high
60601,Chicago,IL,high,high,high
85001,Phoenix,AZ,medium,medium,medium
"""
            )

            # Create test vertical features
            vert_csv = seed_dir / "vertical_features.csv"
            vert_csv.write_text(
                """yelp_category,business_vertical,urgency,ticket_size,maturity
dentists,dental,high,high,medium
lawyers,legal,high,high,high
restaurants,restaurant,medium,medium,low
plumbing,home_services,high,medium,medium
gyms,fitness,low,medium,low
"""
            )

            yield seed_dir

    def test_load_features(self, temp_seed_dir):
        """Test loading features from CSV files"""
        loader = BucketFeatureLoader(seed_dir=temp_seed_dir)

        # Check geo features loaded
        assert len(loader.geo_features) == 5
        assert "94105" in loader.geo_features
        assert loader.geo_features["94105"]["affluence"] == "high"

        # Check vertical features loaded
        assert len(loader.vertical_features) == 5
        assert "dentists" in loader.vertical_features
        assert loader.vertical_features["dentists"]["urgency"] == "high"

    def test_get_geo_bucket(self, temp_seed_dir):
        """Test geo bucket generation"""
        loader = BucketFeatureLoader(seed_dir=temp_seed_dir)

        # Test existing ZIP
        bucket = loader.get_geo_bucket("94105")
        assert bucket == "high-high-high"

        bucket = loader.get_geo_bucket("85001")
        assert bucket == "medium-medium-medium"

        # Test non-existent ZIP
        bucket = loader.get_geo_bucket("00000")
        assert bucket is None

    def test_get_vertical_bucket(self, temp_seed_dir):
        """Test vertical bucket generation"""
        loader = BucketFeatureLoader(seed_dir=temp_seed_dir)

        # Test single category
        bucket = loader.get_vertical_bucket(["dentists"])
        assert bucket == "high-high-medium"

        # Test multiple categories (uses first match)
        bucket = loader.get_vertical_bucket(["unknown", "restaurants", "dentists"])
        assert bucket == "medium-medium-low"

        # Test no match
        bucket = loader.get_vertical_bucket(["unknown", "notfound"])
        assert bucket is None

    def test_get_business_buckets(self, temp_seed_dir):
        """Test getting both buckets for a business"""
        loader = BucketFeatureLoader(seed_dir=temp_seed_dir)

        geo_bucket, vert_bucket = loader.get_business_buckets("94105", ["lawyers"])

        assert geo_bucket == "high-high-high"
        assert vert_bucket == "high-high-high"

    def test_enrich_business(self, temp_seed_dir):
        """Test enriching business with bucket data"""
        loader = BucketFeatureLoader(seed_dir=temp_seed_dir)

        business = {
            "name": "Test Dental",
            "zip_code": "94105",
            "categories": ["dentists", "cosmeticdentists"],
        }

        enriched = loader.enrich_business(business)

        assert enriched["geo_bucket"] == "high-high-high"
        assert enriched["vert_bucket"] == "high-high-medium"

        # Original data preserved
        assert enriched["name"] == "Test Dental"

    def test_enrich_business_missing_data(self, temp_seed_dir):
        """Test enriching business with missing bucket data"""
        loader = BucketFeatureLoader(seed_dir=temp_seed_dir)

        business = {
            "name": "Unknown Business",
            "zip_code": "00000",  # Not in data
            "categories": ["unknown"],  # Not in data
        }

        enriched = loader.enrich_business(business)

        assert enriched["geo_bucket"] is None
        assert enriched["vert_bucket"] is None

    def test_get_stats(self, temp_seed_dir):
        """Test getting statistics"""
        loader = BucketFeatureLoader(seed_dir=temp_seed_dir)

        stats = loader.get_stats()

        assert stats["total_zip_codes"] == 5
        assert stats["total_categories"] == 5
        assert (
            stats["unique_geo_buckets"] == 2
        )  # high-high-high and medium-medium-medium
        assert stats["unique_vert_buckets"] == 5  # All different in test data

        assert "high-high-high" in stats["geo_bucket_list"]
        assert "medium-medium-medium" in stats["geo_bucket_list"]

    def test_singleton_loader(self, temp_seed_dir):
        """Test singleton pattern for default loader"""
        from d1_targeting.bucket_loader import get_bucket_loader

        # Can't test with temp dir for singleton, but can verify it returns same instance
        loader1 = get_bucket_loader()
        loader2 = get_bucket_loader()

        assert loader1 is loader2

    def test_handle_string_categories(self, temp_seed_dir):
        """Test handling categories as string instead of list"""
        loader = BucketFeatureLoader(seed_dir=temp_seed_dir)

        business = {
            "zip_code": "94105",
            "categories": "dentists",  # String instead of list
        }

        enriched = loader.enrich_business(business)
        assert enriched["vert_bucket"] == "high-high-medium"
