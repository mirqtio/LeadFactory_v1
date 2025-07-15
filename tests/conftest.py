"""
Root conftest.py for all tests
Provides common fixtures and configuration
"""
import os
import threading
import time

import pytest
import requests
import uvicorn

from core.config import get_settings


@pytest.fixture(scope="session", autouse=True)
def stub_server_session():
    """
    Start stub server once per test session if USE_STUBS is enabled.
    This ensures the stub server is available for all tests.
    """
    # Detect environment type with proper precedence
    is_docker_container = os.path.exists("/.dockerenv") or os.environ.get("DOCKER_ENV") == "true"
    is_ci = os.environ.get("CI") == "true"
    has_external_stub = os.environ.get("STUB_BASE_URL") == "http://stub-server:5010"

    # Environment detection logic:
    # 1. If STUB_BASE_URL points to stub-server, we're in docker-compose (external stub)
    # 2. Otherwise, use localhost (single container or local development)

    if has_external_stub and is_docker_container:
        # Running in Docker Compose with external stub server - keep existing URL
        print(f"Using external stub server: {os.environ.get('STUB_BASE_URL')}")
    else:
        # Single container Docker, local development, or other CI - use localhost
        os.environ["STUB_BASE_URL"] = "http://localhost:5010"
        print("Using localhost stub server for single container or local environment")

    # Force USE_STUBS=true for all tests
    os.environ["USE_STUBS"] = "true"
    os.environ["ENVIRONMENT"] = "test"

    # Clear settings cache to ensure new environment variables are picked up
    get_settings.cache_clear()
    settings = get_settings()

    # Debug logging
    print(f"Environment detection - Docker: {is_docker_container}, CI: {is_ci}")
    print(f"STUB_BASE_URL set to: {os.environ.get('STUB_BASE_URL')}")
    print(f"Settings stub_base_url: {settings.stub_base_url}")

    if not settings.use_stubs:
        yield
        return

    # Determine if we should wait for external stub or start our own
    use_external_stub = has_external_stub and is_docker_container

    if use_external_stub:
        # Wait for external stub server to be ready (Docker Compose scenario)
        max_attempts = 30
        for attempt in range(max_attempts):
            try:
                response = requests.get(f"{settings.stub_base_url}/health", timeout=2)
                if response.status_code == 200:
                    print(f"✅ Connected to external stub server at {settings.stub_base_url}")
                    yield
                    return
            except Exception as e:
                if attempt == max_attempts - 1:
                    # On last attempt, provide more detail
                    import traceback

                    print(f"❌ Failed to connect to external stub server at {settings.stub_base_url}")
                    print(f"Error: {e}")
                    print(f"Traceback: {traceback.format_exc()}")
                elif attempt % 5 == 0:  # Log every 5th attempt
                    print(f"Attempt {attempt + 1}/{max_attempts}: Waiting for external stub server...")
            time.sleep(0.5)

        pytest.fail(f"External stub server not available at {settings.stub_base_url} after {max_attempts} attempts")

    # For local/single container environment, check if stub server is already running
    print(f"Checking if stub server is already running at {settings.stub_base_url}...")
    try:
        response = requests.get(f"{settings.stub_base_url}/health", timeout=1)
        if response.status_code == 200:
            print(f"✅ Stub server already running at {settings.stub_base_url}")
            yield
            return  # Server already running locally
    except Exception as e:
        print(f"No existing stub server found: {e}")

    # Start stub server in background thread for local testing
    print(f"Starting internal stub server at {settings.stub_base_url}...")
    from stubs.server import app as stub_app

    def run_server():
        uvicorn.run(stub_app, host="127.0.0.1", port=5010, log_level="error")

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Wait for local server to be ready
    max_attempts = 50
    for attempt in range(max_attempts):
        try:
            response = requests.get(f"{settings.stub_base_url}/health", timeout=1)
            if response.status_code == 200:
                print(f"✅ Internal stub server started successfully at {settings.stub_base_url}")
                break
        except Exception:
            pass
        time.sleep(0.1)
    else:
        pytest.fail(f"Internal stub server failed to start at {settings.stub_base_url}")

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

    # Clear cache to ensure environment changes are picked up
    get_settings.cache_clear()
    settings = get_settings()

    if not settings.use_stubs:
        pytest.fail(
            "CRITICAL: Tests must use stubs! USE_STUBS is False. " "Set USE_STUBS=true in environment or .env file."
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
    # Clear cache to ensure latest environment variables are used
    get_settings.cache_clear()
    settings = get_settings()
    # Ensure test environment
    assert settings.environment == "test"
    assert settings.use_stubs is True
    return settings
