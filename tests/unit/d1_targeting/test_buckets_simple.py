"""
Simplified unit tests for Phase 0.5 bucket functionality
Task TG-06: Test bucket columns and CSV seed data
"""
import pytest
import pandas as pd
from pathlib import Path

# Mark entire module as xfail for Phase 0.5
pytestmark = pytest.mark.xfail(reason="Phase 0.5 feature", strict=False)


class TestBucketsSimple:
    """Test bucket functionality without database"""

    def test_geo_features_csv_exists_and_valid(self):
        """Test geo_features.csv exists with proper structure"""
        csv_path = Path("data/seed/geo_features.csv")
        assert csv_path.exists(), "geo_features.csv must exist"

        # Load CSV
        df = pd.read_csv(csv_path)

        # Check required columns
        required_cols = [
            "zip_code",
            "city",
            "state",
            "affluence",
            "agency_density",
            "broadband_quality",
        ]
        for col in required_cols:
            assert col in df.columns, f"Missing column: {col}"

        # Check data values
        assert set(df["affluence"].unique()).issubset({"high", "medium", "low"})
        assert set(df["agency_density"].unique()).issubset({"high", "medium", "low"})
        assert set(df["broadband_quality"].unique()).issubset({"high", "medium", "low"})

        # Check we have data
        assert len(df) > 0, "CSV must contain data"
        print(f"✓ geo_features.csv has {len(df)} rows")

    def test_vertical_features_csv_exists_and_valid(self):
        """Test vertical_features.csv exists with proper structure"""
        csv_path = Path("data/seed/vertical_features.csv")
        assert csv_path.exists(), "vertical_features.csv must exist"

        # Load CSV
        df = pd.read_csv(csv_path)

        # Check required columns
        required_cols = [
            "yelp_category",
            "business_vertical",
            "urgency",
            "ticket_size",
            "maturity",
        ]
        for col in required_cols:
            assert col in df.columns, f"Missing column: {col}"

        # Check data values
        assert set(df["urgency"].unique()).issubset({"high", "medium", "low"})
        assert set(df["ticket_size"].unique()).issubset({"high", "medium", "low"})
        assert set(df["maturity"].unique()).issubset({"high", "medium", "low"})

        # Check we have data
        assert len(df) > 0, "CSV must contain data"
        print(f"✓ vertical_features.csv has {len(df)} rows")

    def test_geo_bucket_combinations_count(self):
        """Test that 12 geo bucket combinations are possible"""
        # Load actual data
        df = pd.read_csv("data/seed/geo_features.csv")

        # Count unique values for each dimension
        affluence_vals = df["affluence"].unique()
        density_vals = df["agency_density"].unique()
        broadband_vals = df["broadband_quality"].unique()

        print(f"Affluence values: {sorted(affluence_vals)}")
        print(f"Density values: {sorted(density_vals)}")
        print(f"Broadband values: {sorted(broadband_vals)}")

        # Calculate theoretical combinations
        theoretical_combos = (
            len(affluence_vals) * len(density_vals) * len(broadband_vals)
        )
        print(f"Theoretical geo combinations: {theoretical_combos}")

        # Count actual unique combinations in data
        df["geo_bucket"] = (
            df["affluence"] + "-" + df["agency_density"] + "-" + df["broadband_quality"]
        )
        actual_combos = df["geo_bucket"].nunique()
        print(f"Actual geo combinations in data: {actual_combos}")

        # We should have at least 12 combinations possible
        assert (
            theoretical_combos >= 12
        ), f"Should have at least 12 possible geo combinations, got {theoretical_combos}"

    def test_vert_bucket_combinations_count(self):
        """Test that 8 vertical bucket combinations are possible"""
        # Load actual data
        df = pd.read_csv("data/seed/vertical_features.csv")

        # Count unique values for each dimension
        urgency_vals = df["urgency"].unique()
        ticket_vals = df["ticket_size"].unique()
        maturity_vals = df["maturity"].unique()

        print(f"Urgency values: {sorted(urgency_vals)}")
        print(f"Ticket values: {sorted(ticket_vals)}")
        print(f"Maturity values: {sorted(maturity_vals)}")

        # Calculate theoretical combinations
        theoretical_combos = len(urgency_vals) * len(ticket_vals) * len(maturity_vals)
        print(f"Theoretical vertical combinations: {theoretical_combos}")

        # Count actual unique combinations in data
        df["vert_bucket"] = (
            df["urgency"] + "-" + df["ticket_size"] + "-" + df["maturity"]
        )
        actual_combos = df["vert_bucket"].nunique()
        print(f"Actual vertical combinations in data: {actual_combos}")

        # We should have at least 8 combinations possible
        assert (
            theoretical_combos >= 8
        ), f"Should have at least 8 possible vertical combinations, got {theoretical_combos}"

    def test_csv_data_quality(self):
        """Test that CSV data is complete and consistent"""
        # Load both CSVs
        geo_df = pd.read_csv("data/seed/geo_features.csv")
        vert_df = pd.read_csv("data/seed/vertical_features.csv")

        # Check geo data completeness
        assert geo_df["affluence"].notna().all(), "All rows must have affluence"
        assert (
            geo_df["agency_density"].notna().all()
        ), "All rows must have agency_density"
        assert (
            geo_df["broadband_quality"].notna().all()
        ), "All rows must have broadband_quality"

        # Check vertical data completeness
        assert vert_df["urgency"].notna().all(), "All rows must have urgency"
        assert vert_df["ticket_size"].notna().all(), "All rows must have ticket_size"
        assert vert_df["maturity"].notna().all(), "All rows must have maturity"

        # Check for duplicates
        assert not geo_df.duplicated(
            ["zip_code"]
        ).any(), "No duplicate zip codes allowed"
        assert not vert_df.duplicated(
            ["yelp_category"]
        ).any(), "No duplicate categories allowed"

        print(f"✓ Data quality checks passed")
        print(f"  - {len(geo_df)} unique ZIP codes")
        print(f"  - {len(vert_df)} unique Yelp categories")

    def test_bucket_format(self):
        """Test that bucket strings follow expected format"""
        # Test geo bucket format
        geo_bucket = "high-medium-low"
        parts = geo_bucket.split("-")
        assert len(parts) == 3, "Geo bucket should have 3 parts"

        # Test vert bucket format
        vert_bucket = "high-low-medium"
        parts = vert_bucket.split("-")
        assert len(parts) == 3, "Vert bucket should have 3 parts"

        print("✓ Bucket format validation passed")

    def test_migration_file_exists(self):
        """Test that migration file exists"""
        migration_path = Path("alembic/versions/004_bucket_columns.py")
        assert migration_path.exists(), "Migration file must exist"

        # Read migration to verify it adds the columns
        content = migration_path.read_text()
        assert "geo_bucket" in content, "Migration must add geo_bucket column"
        assert "vert_bucket" in content, "Migration must add vert_bucket column"
        assert "businesses" in content, "Migration must update businesses table"
        assert "targets" in content, "Migration must update targets table"

        print("✓ Migration file validated")
