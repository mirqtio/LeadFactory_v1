"""
Example of how to mark tests as slow for P0-009

This demonstrates the @pytest.mark.slow decorator usage
"""

import pytest
import time


@pytest.mark.slow
def test_slow_integration():
    """Example of a slow test that should be excluded from CI"""
    # Simulate slow operation
    time.sleep(5)

    # Some integration test logic
    result = perform_slow_operation()
    assert result == "success"


@pytest.mark.slow
@pytest.mark.integration
def test_slow_database_operation():
    """Example of a slow database test"""
    # This would normally connect to a real database
    # and perform time-consuming operations
    time.sleep(3)

    # Verify data
    assert True


def test_fast_unit_test():
    """Example of a fast test that runs in CI"""
    # Fast unit test - no slow marker
    result = 2 + 2
    assert result == 4


def perform_slow_operation():
    """Simulate a slow operation"""
    time.sleep(2)
    return "success"


# Usage in pytest.ini:
# [tool:pytest]
# markers =
#     slow: marks tests as slow (deselect with '-m "not slow"')
#
# Run without slow tests:
# pytest -m "not slow"
#
# Run only slow tests:
# pytest -m "slow"
