"""
Root conftest.py for all tests
Provides common fixtures and configuration
"""
import atexit
import os
import signal
import sys
import threading
import time

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
import requests
import uvicorn

from core.config import get_settings

# Import all centralized fixtures
from tests.fixtures import *  # noqa: F401,F403

# Import parallel safety plugin
from tests.parallel_safety import isolated_db, isolated_temp_dir

# Import port manager and synchronization utilities
from tests.test_port_manager import PortManager, get_dynamic_port, release_port
from tests.test_synchronization import SyncEvent, wait_for_condition


@pytest.fixture(scope="session", autouse=True)
def stub_server_session():
    """
    Start stub server once per test session if USE_STUBS is enabled.
    This ensures the stub server is available for all tests.
    """
    # Detect environment type with proper precedence
    is_docker_container = os.path.exists("/.dockerenv") or os.environ.get("DOCKER_ENV") == "true"
    is_ci = os.environ.get("CI") == "true"
    current_stub_url = os.environ.get("STUB_BASE_URL", "")
    has_external_stub = current_stub_url == "http://stub-server:5010"

    # Environment detection logic:
    # 1. If STUB_BASE_URL points to stub-server, we're in docker-compose (external stub)
    # 2. Otherwise, use localhost (single container or local development)

    if has_external_stub and is_docker_container:
        # Running in Docker Compose with external stub server - keep existing URL
        print(f"Using external stub server: {current_stub_url}")
    else:
        # Single container Docker, local development, or other CI - use localhost with dynamic port
        # We'll set this after allocating a port dynamically
        print(f"Will use localhost stub server with dynamic port (was: {current_stub_url})")

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
        response = requests.get(f"{settings.stub_base_url}/health", timeout=2)
        if response.status_code == 200:
            print(f"✅ Stub server already running at {settings.stub_base_url}")
            yield
            return  # Server already running locally
    except Exception as e:
        print(f"No existing stub server found: {e}")

    # Get a dynamic port for the stub server
    stub_port = get_dynamic_port(5011)  # Try 5011 first, but use any free port
    stub_url = f"http://localhost:{stub_port}"
    os.environ["STUB_BASE_URL"] = stub_url

    # Clear cache and update settings
    get_settings.cache_clear()
    settings = get_settings()

    # Start stub server in background thread for local testing
    print(f"Starting internal stub server at {stub_url}...")
    from stubs.server import app as stub_app

    # Event to signal server is ready
    server_ready = SyncEvent()
    server_thread = None
    server = None

    def run_server():
        nonlocal server
        try:
            config = uvicorn.Config(app=stub_app, host="127.0.0.1", port=stub_port, log_level="error", loop="asyncio")
            server = uvicorn.Server(config)

            # Signal that server is starting
            server_ready.set()

            # Run the server
            server.run()
        except Exception as e:
            print(f"Error starting stub server: {e}")
            server_ready.set()  # Signal even on error so tests don't hang

    server_thread = threading.Thread(target=run_server, daemon=False)
    server_thread.start()

    # Wait for server thread to start
    server_ready.wait(timeout=5.0)

    # Wait for local server to be ready using proper synchronization
    try:
        wait_for_condition(
            lambda: _check_server_health(stub_url),
            timeout=30.0,
            interval=0.5,
            message=f"Stub server not ready at {stub_url}",
        )
        print(f"✅ Internal stub server started successfully at {stub_url}")
    except TimeoutError as e:
        # Try to get more diagnostic info
        try:
            response = requests.get(f"{stub_url}/health", timeout=5)
            pytest.fail(f"Stub server returned status {response.status_code} at {stub_url}")
        except Exception as ex:
            pytest.fail(f"Internal stub server failed to start at {stub_url}. Error: {ex}")

    # Store cleanup info
    cleanup_info = {"port": stub_port, "server": server, "thread": server_thread, "url": stub_url}

    yield

    # Cleanup
    print(f"Stopping stub server at {stub_url}...")
    if server:
        server.should_exit = True

    # Give server time to shut down gracefully
    server_thread.join(timeout=5.0)

    # Release the port
    release_port(stub_port)
    print(f"Released port {stub_port}")


def _check_server_health(url: str) -> bool:
    """Check if server is healthy."""
    try:
        response = requests.get(f"{url}/health", timeout=2)
        return response.status_code == 200
    except Exception:
        return False


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
