"""
Shared test configuration for D0 Gateway tests
"""

import pytest
from prometheus_client import REGISTRY
from sqlalchemy import create_engine

from database.models import Base


@pytest.fixture(scope="function")
def test_engine():
    """Create test database engine and tables for each test"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


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
