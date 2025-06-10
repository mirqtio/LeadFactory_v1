"""
Security test configuration and fixtures - Task 086

Provides test environment setup and fixtures for security and compliance testing.
"""

import tempfile
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database.base import Base

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
    """Create test database session for security tests"""
    # Create in-memory SQLite database for each test
    engine = create_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        echo=False,  # Disable SQL echo for security testing
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
def mock_security_services():
    """Mock security-related services for testing"""
    with patch("core.security.verify_token") as mock_verify, patch(
        "core.security.hash_email"
    ) as mock_hash, patch("core.security.encrypt_data") as mock_encrypt, patch(
        "d7_storefront.stripe_client.stripe"
    ) as mock_stripe:
        # Configure mock security responses
        mock_verify.return_value = {
            "valid": True,
            "user_id": "test_user_123",
            "role": "user",
            "permissions": ["read:own_data"],
        }

        mock_hash.return_value = "hashed_email_value"
        mock_encrypt.return_value = "encrypted_data_value"

        mock_stripe.Webhook.construct_event.return_value = {
            "type": "payment_intent.succeeded",
            "data": {"object": {"id": "pi_test_123"}},
        }

        yield {
            "verify_token": mock_verify,
            "hash_email": mock_hash,
            "encrypt_data": mock_encrypt,
            "stripe": mock_stripe,
        }
