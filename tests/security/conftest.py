"""
Security test configuration and fixtures - Task 086

Provides test environment setup and fixtures for security and compliance testing.
"""

from collections.abc import Generator
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database.base import Base

# Import all models to ensure foreign key references are available
try:
    import d1_targeting.models  # noqa: F401
    import d2_sourcing.models  # noqa: F401
    import d3_assessment.models  # noqa: F401
    import d4_enrichment.models  # noqa: F401
    import d5_scoring.models  # noqa: F401
    import d6_reports.models  # noqa: F401
    import d7_storefront.models  # noqa: F401
    import d8_personalization.models  # noqa: F401
    import d9_delivery.models  # noqa: F401
    import d10_analytics.models  # noqa: F401
    import d11_orchestration.models  # noqa: F401
    import database.models  # noqa: F401
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
    with (
        patch("core.security.verify_token") as mock_verify,
        patch("core.security.hash_email") as mock_hash,
        patch("core.security.encrypt_data") as mock_encrypt,
        patch("d7_storefront.stripe_client.stripe") as mock_stripe,
    ):
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
