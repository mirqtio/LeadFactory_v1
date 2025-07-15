"""Smoke tests for generated value_curves.csv"""
from pathlib import Path

import pandas as pd

DATA_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "processed" / "value_curves.csv"
)


def test_file_exists():
    assert (
        DATA_PATH.exists()
    ), "value_curves.csv not found; run compute_value_curves.py first."


def test_row_count():
    df = pd.read_csv(DATA_PATH)
    assert len(df) >= 30000, "Expected at least 30k rows in value_curves.csv"


def test_sample_positive():
    df = pd.read_csv(DATA_PATH)
    sample = df[
        (df["naics3"] == 722)
        & (df["geo_bucket"] == "metro_nyc")
        & (df["score_bucket_low"] == 40)
    ]
    assert not sample.empty, "Sample row missing for naics3=722 metro_nyc bucket 40-59"
    assert sample["revenue_per_point_usd"].notna().all()
    assert (sample["revenue_per_point_usd"] > 0).all()
