"""Company size utility functions for enrichment."""

from functools import lru_cache
from pathlib import Path

import pandas as pd


@lru_cache(maxsize=1)
def _load_size_multipliers():
    """Load size multipliers from CSV file."""
    csv_path = Path(__file__).parent.parent / "config" / "size_multipliers.csv"
    df = pd.read_csv(csv_path)

    # Parse employee ranges
    multipliers = []
    for _, row in df.iterrows():
        emp_range = row["employees"]
        multiplier = row["multiplier"]

        if "-" in emp_range:
            min_emp, max_emp = emp_range.split("-")
            min_emp = int(min_emp)
            max_emp = int(max_emp) if max_emp.isdigit() else float("inf")
        elif "+" in emp_range:
            min_emp = int(emp_range.replace("+", ""))
            max_emp = float("inf")
        else:
            # Single value
            min_emp = max_emp = int(emp_range)

        multipliers.append((min_emp, max_emp, multiplier))

    return multipliers


def multiplier(emp_count: int) -> float:
    """
    Get size multiplier based on employee count.

    Args:
        emp_count: Number of employees (use -1 or None for unknown)

    Returns:
        float: Multiplier value (1.0 if employee count unknown)
    """
    # Return 1.0 for unknown employee counts
    if emp_count is None or emp_count < 0:
        return 1.0

    # Load multipliers
    size_ranges = _load_size_multipliers()

    # Find matching range
    for min_emp, max_emp, mult in size_ranges:
        if min_emp <= emp_count <= max_emp:
            return float(mult)

    # Default to 1.0 if no range matches
    return 1.0
