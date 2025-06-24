"""Impact calculator for revenue opportunity estimation."""
import yaml
from pathlib import Path
from typing import Dict, Tuple, Optional
from functools import lru_cache


@lru_cache(maxsize=1)
def _load_impact_coefficients() -> Dict[str, Dict[int, float]]:
    """Load impact coefficients from YAML."""
    yaml_path = Path(__file__).parent.parent / "config" / "impact_coefficients.yaml"
    with open(yaml_path, "r") as f:
        return yaml.safe_load(f)


@lru_cache(maxsize=1)
def _load_confidence_weights() -> Dict[str, float]:
    """Load confidence source weights from YAML."""
    yaml_path = Path(__file__).parent.parent / "config" / "confidence_sources.yaml"
    with open(yaml_path, "r") as f:
        data = yaml.safe_load(f)
        return {
            "sources": data["sources"],
            "category_modifiers": data["category_modifiers"],
            "default": data["default_confidence"],
        }


def calculate_impact(
    category: str,
    severity: int,
    baseline_revenue: float,
    source: Optional[str] = None,
    omega: float = 1.0,
) -> Tuple[float, float, float]:
    """
    Calculate revenue impact with confidence interval.

    Args:
        category: Finding category (performance, seo, visual, technical, trust)
        severity: Severity level (1-4)
        baseline_revenue: Annual revenue baseline
        source: Data source for confidence weighting
        omega: Online dependence scaler

    Returns:
        Tuple of (impact, low_range, high_range)
    """
    # Load coefficients
    coefficients = _load_impact_coefficients()
    confidence_data = _load_confidence_weights()

    # Get base coefficient
    beta = coefficients.get(category, {}).get(severity, 0.002)

    # Get confidence weight
    source_confidence = confidence_data["sources"].get(
        source, confidence_data["default"]
    )
    category_modifier = confidence_data["category_modifiers"].get(category, 1.0)

    # Combined confidence
    confidence = source_confidence * category_modifier

    # Calculate base impact
    base_impact = baseline_revenue * beta * omega

    # Calculate range based on confidence
    # Higher confidence = tighter range
    range_factor = 1.0 - confidence
    low_range = base_impact * (1 - range_factor * 0.3)  # ±30% at 0 confidence
    high_range = base_impact * (1 + range_factor * 0.3)

    return (base_impact, low_range, high_range)


def get_confidence_weight(source: str, category: str) -> float:
    """
    Get confidence weight for a specific source and category.

    Args:
        source: Data source name
        category: Finding category

    Returns:
        float: Confidence weight (0.0 - 1.0)
    """
    confidence_data = _load_confidence_weights()

    source_weight = confidence_data["sources"].get(source, confidence_data["default"])
    category_modifier = confidence_data["category_modifiers"].get(category, 1.0)

    return source_weight * category_modifier
