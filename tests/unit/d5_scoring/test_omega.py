"""Unit tests for omega (online dependence) calculator."""
import pytest
from d5_scoring.omega import calculate_omega, evaluate_condition


def test_low_traffic_omega():
    """Test that low traffic returns omega 0.4."""
    omega = calculate_omega(visits_per_mil=2000)
    assert omega == 0.4, f"Expected 0.4 for low traffic, got {omega}"


def test_mixed_intent_omega():
    """Test mixed intent keywords returns omega 0.7."""
    omega = calculate_omega(
        visits_per_mil=5000,  # Above low traffic threshold
        commercial_kw_pct=30,  # Below 40%
    )
    assert omega == 0.7, f"Expected 0.7 for mixed intent, got {omega}"


def test_service_business_omega():
    """Test service business with low traffic."""
    omega = calculate_omega(vertical="plumbing", visits_per_mil=4000)
    assert omega == 0.5, f"Expected 0.5 for plumbing with low traffic, got {omega}"


def test_high_traffic_ecommerce():
    """Test high traffic e-commerce gets boost."""
    omega = calculate_omega(visits_per_mil=25000, commercial_kw_pct=70)
    assert omega == 1.2, f"Expected 1.2 for high traffic e-commerce, got {omega}"


def test_restaurant_with_delivery():
    """Test restaurant with online ordering."""
    omega = calculate_omega(vertical="restaurant", has_online_ordering=True)
    assert omega == 0.9, f"Expected 0.9 for restaurant with delivery, got {omega}"


def test_restaurant_without_delivery():
    """Test restaurant without online ordering."""
    omega = calculate_omega(vertical="restaurant", has_online_ordering=False)
    assert omega == 0.6, f"Expected 0.6 for restaurant without delivery, got {omega}"


def test_default_omega():
    """Test default omega when no rules match."""
    omega = calculate_omega(
        visits_per_mil=10000, commercial_kw_pct=50, vertical="other"
    )
    assert omega == 1.0, f"Expected 1.0 for default case, got {omega}"


def test_condition_evaluation():
    """Test condition evaluation logic."""
    # Simple comparison
    assert evaluate_condition("visits_per_mil < 3000", {"visits_per_mil": 2000})
    assert not evaluate_condition("visits_per_mil < 3000", {"visits_per_mil": 4000})

    # String comparison
    assert evaluate_condition("vertical == 'plumbing'", {"vertical": "plumbing"})

    # In operator
    assert evaluate_condition("vertical in ['plumbing', 'hvac']", {"vertical": "hvac"})

    # Boolean logic
    assert evaluate_condition(
        "visits_per_mil < 5000 and vertical == 'hvac'",
        {"visits_per_mil": 4000, "vertical": "hvac"},
    )


def test_missing_variables_use_defaults():
    """Test that missing variables use defaults."""
    # Should use default visits_per_mil=5000
    omega = calculate_omega(commercial_kw_pct=30)
    # 5000 > 3000, so low_traffic rule won't match
    # But commercial_kw_pct < 40, so mixed_intent matches
    assert omega == 0.7
