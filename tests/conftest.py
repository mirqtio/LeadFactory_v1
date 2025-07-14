"""
Root conftest.py for all tests
Provides common fixtures and configuration
"""
import pytest
import threading
import time
import requests
import uvicorn
from core.config import get_settings


@pytest.fixture(scope="session", autouse=True)
def stub_server_session():
    """
    Start stub server once per test session if USE_STUBS is enabled.
    This ensures the stub server is available for all tests.
    """
    settings = get_settings()
    
    if not settings.use_stubs:
        yield
        return
    
    # Check if stub server is already running
    try:
        response = requests.get(f"{settings.stub_base_url}/health", timeout=1)
        if response.status_code == 200:
            yield
            return  # Server already running
    except:
        pass
    
    # Start stub server in background thread
    from stubs.server import app as stub_app
    
    def run_server():
        uvicorn.run(stub_app, host="127.0.0.1", port=5010, log_level="error")
    
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    # Wait for server to be ready
    max_attempts = 30
    for attempt in range(max_attempts):
        try:
            response = requests.get(f"{settings.stub_base_url}/health", timeout=1)
            if response.status_code == 200:
                break
        except:
            pass
        time.sleep(0.1)
    else:
        pytest.fail(f"Stub server failed to start at {settings.stub_base_url}")
    
    yield


@pytest.fixture(autouse=True)
def provider_stub(monkeypatch):
    """
    Fixture to ensure stubs are always used in tests.
    This fixture runs automatically for all tests and fails loudly if stubs are disabled.
    """
    # Force USE_STUBS=true for all tests
    monkeypatch.setenv("USE_STUBS", "true")
    monkeypatch.setenv("ENVIRONMENT", "test")
    
    settings = get_settings()
    
    if not settings.use_stubs:
        pytest.fail(
            "CRITICAL: Tests must use stubs! USE_STUBS is False. "
            "Set USE_STUBS=true in environment or .env file."
        )
    
    # Verify stub configuration
    assert settings.stub_base_url, "Stub base URL must be configured"
    
    # Verify all provider flags are auto-disabled
    assert settings.enable_gbp is False, "GBP should be disabled when using stubs"
    assert settings.enable_pagespeed is False, "PageSpeed should be disabled when using stubs"
    assert settings.enable_sendgrid is False, "SendGrid should be disabled when using stubs"
    assert settings.enable_openai is False, "OpenAI should be disabled when using stubs"
    
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