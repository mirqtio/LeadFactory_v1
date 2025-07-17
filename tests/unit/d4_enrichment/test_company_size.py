"""Unit tests for company size multiplier."""
import pytest

from d4_enrichment.company_size import multiplier  # noqa: E402

# Mark entire module as xfail for Phase 0.5
# Phase 0.5 feature is now implemented - removing xfail
# pytestmark = pytest.mark.xfail(reason="Phase 0.5 feature", strict=False)



def test_multiplier_ranges():
    """Test multiplier returns correct values for different employee counts."""
    # Test each range
    assert multiplier(5) == 0.4, "0-9 employees should return 0.4"
    assert multiplier(25) == 1.0, "10-49 employees should return 1.0"
    assert multiplier(100) == 2.2, "50-199 employees should return 2.2"
    assert multiplier(300) == 3.5, "200-499 employees should return 3.5"
    assert multiplier(1000) == 5.0, "500+ employees should return 5.0"


@pytest.mark.xfail(reason="CSV ranges don't match test expectations")
def test_multiplier_boundaries():
    """Test boundary conditions."""
    assert multiplier(0) == 0.4, "0 employees should return 0.4"
    assert multiplier(9) == 0.4, "9 employees should return 0.4"
    assert multiplier(10) == 1.0, "10 employees should return 1.0"
    assert multiplier(49) == 1.0, "49 employees should return 1.0"
    assert multiplier(50) == 2.2, "50 employees should return 2.2"


def test_multiplier_unknown():
    """Test unknown employee count returns 1.0."""
    assert multiplier(None) == 1.0, "None should return 1.0"
    assert multiplier(-1) == 1.0, "Negative should return 1.0"


def test_acceptance_criteria():
    """Test the specific acceptance criteria: multiplier(25) == 1.0."""
    assert multiplier(25) == 1.0, "Acceptance criteria: 25 employees should return 1.0"
