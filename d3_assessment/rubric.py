"""Severity rubric mapper for audit findings."""

# Define severity mappings for specific metrics
SEVERITY_MAPPINGS = {
    "performance": {
        "page_load_time": [
            (10.0, float("inf"), 4),  # > 10s = Critical
            (5.0, 10.0, 3),  # 5-10s = High
            (3.0, 5.0, 2),  # 3-5s = Medium
            (0, 3.0, 1),  # < 3s = Low
        ],
        "mobile_score": [
            (0, 30, 4),  # < 30 = Critical
            (30, 50, 3),  # 30-50 = High
            (50, 70, 2),  # 50-70 = Medium
            (70, 100, 1),  # 70-100 = Low
        ],
        "blocking_resources_size": [
            (2048, float("inf"), 4),  # > 2MB = Critical
            (1024, 2048, 3),  # 1-2MB = High
            (512, 1024, 2),  # 512KB-1MB = Medium
            (0, 512, 1),  # < 512KB = Low
        ],
    },
    "seo": {
        "missing_title": lambda v: 4 if v else 1,
        "missing_h1": lambda v: 3 if v else 1,
        "missing_meta_description": lambda v: 2 if v else 1,
        "robots_blocked": lambda v: 4 if v else 1,
    },
    "visual": {
        "cta_below_fold": lambda v: 3 if v else 1,
        "mobile_responsive": lambda v: 3 if not v else 1,
        "color_contrast_ratio": [
            (0, 3.0, 4),  # < 3:1 = Critical
            (3.0, 4.5, 3),  # 3-4.5:1 = High
            (4.5, 7.0, 2),  # 4.5-7:1 = Medium
            (7.0, float("inf"), 1),  # > 7:1 = Low
        ],
    },
    "technical": {
        "ssl_valid": lambda v: 3 if not v else 1,
        "console_errors": [
            (10, float("inf"), 4),  # > 10 errors = Critical
            (5, 10, 3),  # 5-10 errors = High
            (1, 5, 2),  # 1-5 errors = Medium
            (0, 1, 1),  # 0-1 errors = Low
        ],
    },
    "trust": {
        "review_count": [
            (0, 5, 4),  # < 5 reviews = Critical
            (5, 20, 3),  # 5-20 reviews = High
            (20, 50, 2),  # 20-50 reviews = Medium
            (50, float("inf"), 1),  # > 50 reviews = Low
        ],
        "rating": [
            (0, 3.0, 4),  # < 3.0 = Critical
            (3.0, 4.0, 3),  # 3.0-4.0 = High
            (4.0, 4.5, 2),  # 4.0-4.5 = Medium
            (4.5, 5.0, 1),  # 4.5-5.0 = Low
        ],
    },
}


def map_severity(category: str, raw_metric: dict) -> int:
    """
    Map raw metrics to severity level (1-4) based on category and rubric.

    Args:
        category: Category of the finding (performance, seo, visual, technical, trust)
        raw_metric: Dictionary containing metric name and value

    Returns:
        int: Severity level 1-4 (1=Low, 4=Critical)
    """
    category = category.lower()

    # Default to medium severity if category unknown
    if category not in SEVERITY_MAPPINGS:
        return 2

    category_mappings = SEVERITY_MAPPINGS[category]

    # Extract metric name and value from raw_metric
    metric_name = raw_metric.get("name", "").lower().replace(" ", "_")
    metric_value = raw_metric.get("value")

    # Check if we have a specific mapping for this metric
    if metric_name in category_mappings:
        mapping = category_mappings[metric_name]

        # Handle function-based mappings
        if callable(mapping):
            return mapping(metric_value)

        # Handle range-based mappings
        if isinstance(mapping, list):
            for min_val, max_val, severity in mapping:
                if min_val <= metric_value <= max_val:
                    return severity

    # Special case handling for common patterns
    if category == "visual" and "cta_below_fold" in str(raw_metric):
        return 3

    if category == "trust":
        if "review_count" in raw_metric and raw_metric.get("review_count", 100) < 20:
            return 3
        if "rating" in raw_metric and raw_metric.get("rating", 5.0) < 4.0:
            return 3

    # Default severity by category if no specific mapping found
    default_severities = {
        "performance": 2,
        "seo": 2,
        "visual": 2,
        "technical": 2,
        "trust": 2,
    }

    return default_severities.get(category, 2)
