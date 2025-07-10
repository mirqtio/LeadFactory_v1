"""
Root conftest.py for all tests
Provides common fixtures and configuration
"""
import pytest
from core.config import get_settings


@pytest.fixture(autouse=True)
def provider_stub():
    """
    Fixture to ensure stubs are always used in tests.
    This fixture runs automatically for all tests and fails loudly if stubs are disabled.
    """
    settings = get_settings()
    
    if not settings.use_stubs:
        pytest.fail(
            "CRITICAL: Tests must use stubs! USE_STUBS is False. "
            "Set USE_STUBS=true in environment or .env file."
        )
    
    # Verify stub configuration
    assert settings.stub_base_url, "Stub base URL must be configured"
    
    yield
    
    # Post-test verification could go here if needed


@pytest.fixture
def test_settings():
    """Provide test-specific settings"""
    settings = get_settings()
    # Ensure test environment
    assert settings.environment == "test"
    assert settings.use_stubs is True
    return settings