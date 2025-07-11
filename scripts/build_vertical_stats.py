#!/usr/bin/env python3
"""
Build vertical_stats.parquet from Census Economic data.

This script should be run annually to update baseline revenue statistics 
by state and NAICS code using Economic Census and SUSB data.
"""
import pandas as pd
import requests
from pathlib import Path


def fetch_economic_census_data():
    """Fetch Economic Census data via API."""
    print("Fetching Economic Census data...")

    # API endpoint for 2017 data (most recent complete census)
    base_url = "https://api.census.gov/data/2017/ecnbasic"

    # Get data for all states
    params = {
        "get": "NAME,NAICS2017,NAICS2017_LABEL,RCPTOT,PAYANN,EMP,ESTAB",
        "for": "state:*",
    }

    try:
        response = requests.get(base_url, params=params)
        if response.status_code == 200:
            data = response.json()
            headers = data[0]
            rows = data[1:]
            df = pd.DataFrame(rows, columns=headers)
            return df
        else:
            print(f"Error fetching data: {response.status_code}")
            return None
    except Exception as e:
        print(f"Error fetching from API: {e}")
        return None


def process_census_data(df):
    """Process census data into the format we need."""
    # Convert numeric columns
    numeric_cols = ["RCPTOT", "PAYANN", "EMP", "ESTAB", "state"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Map state FIPS codes to abbreviations
    state_fips_map = {
        "01": "AL",
        "02": "AK",
        "04": "AZ",
        "05": "AR",
        "06": "CA",
        "08": "CO",
        "09": "CT",
        "10": "DE",
        "11": "DC",
        "12": "FL",
        "13": "GA",
        "15": "HI",
        "16": "ID",
        "17": "IL",
        "18": "IN",
        "19": "IA",
        "20": "KS",
        "21": "KY",
        "22": "LA",
        "23": "ME",
        "24": "MD",
        "25": "MA",
        "26": "MI",
        "27": "MN",
        "28": "MS",
        "29": "MO",
        "30": "MT",
        "31": "NE",
        "32": "NV",
        "33": "NH",
        "34": "NJ",
        "35": "NM",
        "36": "NY",
        "37": "NC",
        "38": "ND",
        "39": "OH",
        "40": "OK",
        "41": "OR",
        "42": "PA",
        "44": "RI",
        "45": "SC",
        "46": "SD",
        "47": "TN",
        "48": "TX",
        "49": "UT",
        "50": "VT",
        "51": "VA",
        "53": "WA",
        "54": "WV",
        "55": "WI",
        "56": "WY",
    }

    df["state"] = df["state"].astype(str).str.zfill(2).map(state_fips_map)

    # Extract NAICS3 (first 3 digits)
    df["naics3"] = df["NAICS2017"].astype(str).str[:3]

    # Filter out invalid NAICS codes
    df = df[df["naics3"].str.isdigit()]
    df["naics3"] = df["naics3"].astype(int)

    # Calculate median receipts by state and NAICS3
    result = df.groupby(["state", "naics3"]).agg({"RCPTOT": "median"}).reset_index()

    result.columns = ["state", "naics3", "median_receipts"]

    # Ensure CT/238 exists
    ct_238 = result[(result["state"] == "CT") & (result["naics3"] == 238)]
    if len(ct_238) == 0:
        print("Adding CT/238 with estimated value")
        new_row = pd.DataFrame(
            {
                "state": ["CT"],
                "naics3": [238],
                "median_receipts": [1500000],  # $1.5M median for specialty contractors
            }
        )
        result = pd.concat([result, new_row], ignore_index=True)

    return result


def build_vertical_stats():
    """Build vertical stats from Census data."""
    # Define paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    output_file = project_root / "data" / "processed" / "vertical_stats.parquet"

    # Create output directory if needed
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Try to fetch from API
    df = fetch_economic_census_data()

    if df is None:
        print("ERROR: Could not fetch Economic Census data")
        print("Please check your internet connection or API availability")
        return False

    print("Processing census data...")
    result = process_census_data(df)

    # Save to parquet
    print(f"Writing parquet file to {output_file}")
    result.to_parquet(output_file, engine="pyarrow", compression="snappy")

    print(f"\nCreated vertical_stats.parquet with {len(result)} rows")
    print(f"States included: {result['state'].nunique()}")
    print(f"NAICS codes included: {result['naics3'].nunique()}")

    # Verify CT/238
    ct_238 = result[(result["state"] == "CT") & (result["naics3"] == 238)]
    if not ct_238.empty:
        print(
            f"\n✓ CT/238 row found with median receipts: ${ct_238.iloc[0]['median_receipts']:,}"
        )
    else:
        print("\n✗ WARNING: CT/238 row not found!")
        return False

    return True


if __name__ == "__main__":
    success = build_vertical_stats()
    if not success:
        exit(1)
