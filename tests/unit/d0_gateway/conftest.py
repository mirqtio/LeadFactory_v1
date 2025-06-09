"""
Shared test configuration for D0 Gateway tests
"""
import pytest
from prometheus_client import REGISTRY


@pytest.fixture(autouse=True)
def cleanup_prometheus_registry():
    """Clear Prometheus registry before and after each test"""
    # Clear before test
    collectors = list(REGISTRY._collector_to_names.keys())
    for collector in collectors:
        try:
            REGISTRY.unregister(collector)
        except KeyError:
            pass

    yield

    # Clear after test
    collectors = list(REGISTRY._collector_to_names.keys())
    for collector in collectors:
        try:
            REGISTRY.unregister(collector)
        except KeyError:
            pass
