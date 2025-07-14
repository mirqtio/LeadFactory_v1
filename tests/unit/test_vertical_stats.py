"""Unit tests for vertical_stats.parquet processing."""
import pytest

# Mark entire module as slow for CI optimization
pytestmark = pytest.mark.slow
from pathlib import Path

import pandas as pd


def test_vertical_stats_parquet_exists():
    """Test that vertical_stats.parquet exists and contains expected data."""
    parquet_path = Path(__file__).parent.parent.parent / "data" / "processed" / "vertical_stats.parquet"

    if not parquet_path.exists():
        pytest.skip("vertical_stats.parquet not yet generated - run scripts/build_vertical_stats.py")

    # Load parquet
    df = pd.read_parquet(parquet_path)

    # Basic checks
    assert not df.empty, "Parquet file should not be empty"
    assert "state" in df.columns, "Should have state column"
    assert "naics3" in df.columns, "Should have naics3 column"
    assert "median_receipts" in df.columns, "Should have median_receipts column"

    # Check data types
    assert df["state"].dtype == "object"
    assert pd.api.types.is_numeric_dtype(df["naics3"])
    assert pd.api.types.is_numeric_dtype(df["median_receipts"])

    # Check for CT/238 row
    ct_238 = df[(df["state"] == "CT") & (df["naics3"] == 238)]
    assert len(ct_238) > 0, "Should contain CT/238 row"
    assert ct_238.iloc[0]["median_receipts"] > 0, "CT/238 should have positive median receipts"
