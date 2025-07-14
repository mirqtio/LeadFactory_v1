"""Unit tests for impact coefficients YAML."""
from pathlib import Path

import pytest
import yaml

# Mark entire module as xfail for Phase 0.5
pytestmark = pytest.mark.xfail(reason="Phase 0.5 feature - impact coefficients", strict=False)


def test_impact_coefficients_exist():
    """Test that impact_coefficients.yaml exists and has all required entries."""
    yaml_path = Path(__file__).parent.parent.parent / "config" / "impact_coefficients.yaml"

    assert yaml_path.exists(), "impact_coefficients.yaml should exist"

    with open(yaml_path, "r") as f:
        coefficients = yaml.safe_load(f)

    # Expected categories
    expected_categories = ["performance", "seo", "visual", "technical", "trust"]

    # Check all categories exist
    for category in expected_categories:
        assert category in coefficients, f"Category '{category}' should exist"

        # Check all severity levels exist for each category
        for severity in [1, 2, 3, 4]:
            assert severity in coefficients[category], f"Severity {severity} should exist for category '{category}'"

            # Check coefficient is a positive number
            beta = coefficients[category][severity]
            assert isinstance(beta, (int, float)), f"Coefficient for {category}[{severity}] should be numeric"
            assert beta > 0, f"Coefficient for {category}[{severity}] should be positive"


def test_coefficient_ordering():
    """Test that coefficients increase with severity."""
    yaml_path = Path(__file__).parent.parent.parent / "config" / "impact_coefficients.yaml"

    with open(yaml_path, "r") as f:
        coefficients = yaml.safe_load(f)

    for category, severities in coefficients.items():
        prev_beta = 0
        for severity in [1, 2, 3, 4]:
            beta = severities[severity]
            assert beta > prev_beta, f"Coefficients should increase with severity in {category}"
            prev_beta = beta


def test_performance_critical_value():
    """Test that performance critical matches Google/Soasta research."""
    yaml_path = Path(__file__).parent.parent.parent / "config" / "impact_coefficients.yaml"

    with open(yaml_path, "r") as f:
        coefficients = yaml.safe_load(f)

    # Performance severity 4 should be 0.0060 (3% / 5 as noted in comment)
    assert coefficients["performance"][4] == 0.0060, "Performance critical should match Google/Soasta 3% uplift"
