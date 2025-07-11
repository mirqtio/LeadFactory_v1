"""
Performance test configuration and fixtures - Task 085

Provides test environment setup and fixtures for performance testing.
"""

import tempfile
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database.base import Base
from database.session import get_db

# Import all models to ensure foreign key references are available
try:
    import database.models  # Main database models
    import d1_targeting.models  # D1 targeting models
    import d2_sourcing.models  # D2 sourcing models
    import d3_assessment.models  # D3 assessment models
    import d4_enrichment.models  # D4 enrichment models
    import d5_scoring.models  # D5 scoring models
    import d6_reports.models  # D6 reports models
    import d7_storefront.models  # D7 storefront models
    import d8_personalization.models  # D8 personalization models
    import d9_delivery.models  # D9 delivery models
    import d10_analytics.models  # D10 analytics models
    import d11_orchestration.models  # D11 orchestration models
except ImportError:
    # If imports fail, models will be registered when tests import them
    pass


@pytest.fixture(scope="function")
def test_db_session() -> Generator:
    """Create test database session for performance tests"""
    # Create in-memory SQLite database for each test
    engine = create_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        echo=False,  # Disable SQL echo for performance
    )

    # Create all tables
    Base.metadata.create_all(bind=engine)

    # Create session
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture(scope="function")
def mock_external_services():
    """Mock external services for performance testing"""
    with patch(
        "d0_gateway.providers.pagespeed.PageSpeedClient"
    ) as mock_pagespeed, patch(
        "d0_gateway.providers.openai.OpenAIClient"
    ) as mock_openai, patch(
        "d0_gateway.providers.sendgrid.SendGridClient"
    ) as mock_sendgrid:
        # Configure mock responses for consistent performance testing
        # Yelp removed from codebase

        mock_pagespeed.return_value.analyze_page.return_value = {
            "score": 85,
            "metrics": {"FCP": 1200, "LCP": 2500},
        }

        mock_openai.return_value.chat.return_value = {
            "choices": [{"message": {"content": "Personalized email content"}}]
        }

        mock_sendgrid.return_value.send_email.return_value = {
            "status_code": 202,
            "message_id": "test_message_id",
        }

        yield {
            # "yelp": mock_yelp,  # Yelp removed
            "pagespeed": mock_pagespeed,
            "openai": mock_openai,
            "sendgrid": mock_sendgrid,
        }


@pytest.fixture(scope="function")
def performance_monitor():
    """Fixture providing performance monitoring utilities"""

    class MockPerformanceMonitor:
        def __init__(self):
            self.metrics = {}

        def start_monitoring(self):
            pass

        def stop_monitoring(self):
            return {
                "cpu_usage": [10, 15, 20, 18, 12],
                "memory_usage": [100, 110, 115, 112, 105],
                "avg_cpu": 15.0,
                "avg_memory": 108.4,
                "peak_cpu": 20.0,
                "peak_memory": 115.0,
            }

    return MockPerformanceMonitor()
