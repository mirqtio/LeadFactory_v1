"""Unit tests for impact calculator."""
import pytest
from d5_scoring.impact_calculator import calculate_impact, get_confidence_weight


def test_visual_finding_confidence():
    """Test that visual finding uses 0.6 confidence in range calculation."""
    # Visual source should have 0.6 confidence
    confidence = get_confidence_weight("visual", "visual")

    # visual source (0.6) * visual category modifier (0.8) = 0.48
    expected = 0.6 * 0.8
    assert abs(confidence - expected) < 0.01, f"Expected {expected}, got {confidence}"


def test_impact_calculation_basic():
    """Test basic impact calculation."""
    # Performance critical with $1M revenue
    impact, low, high = calculate_impact(
        category="performance",
        severity=4,
        baseline_revenue=1_000_000,
        source="pagespeed",
    )

    # Should be $1M * 0.006 = $6,000
    assert abs(impact - 6000) < 1

    # High confidence source should have tight range
    assert low > impact * 0.9
    assert high < impact * 1.1


def test_impact_with_low_confidence():
    """Test impact calculation with low confidence source."""
    impact, low, high = calculate_impact(
        category="visual",
        severity=3,
        baseline_revenue=1_000_000,
        source="manual",  # Low confidence source
    )

    # Wider range due to low confidence
    range_size = high - low
    assert range_size > impact * 0.3  # At least 30% range


def test_impact_with_omega_scaler():
    """Test impact calculation with omega scaler."""
    # Without omega
    impact1, _, _ = calculate_impact(
        category="seo", severity=3, baseline_revenue=1_000_000, omega=1.0
    )

    # With omega = 0.5 (low online dependence)
    impact2, _, _ = calculate_impact(
        category="seo", severity=3, baseline_revenue=1_000_000, omega=0.5
    )

    assert abs(impact2 - impact1 * 0.5) < 1


def test_unknown_source_uses_default():
    """Test unknown source uses default confidence."""
    confidence = get_confidence_weight("unknown_source", "performance")

    # Should use default (0.5)
    assert confidence == 0.5


def test_confidence_range_relationship():
    """Test that higher confidence produces tighter ranges."""
    # High confidence source
    _, low1, high1 = calculate_impact(
        category="performance",
        severity=3,
        baseline_revenue=1_000_000,
        source="pagespeed",  # 0.9 confidence
    )
    range1 = high1 - low1

    # Low confidence source
    _, low2, high2 = calculate_impact(
        category="performance",
        severity=3,
        baseline_revenue=1_000_000,
        source="manual",  # 0.5 confidence
    )
    range2 = high2 - low2

    # Lower confidence should have wider range
    assert range2 > range1
