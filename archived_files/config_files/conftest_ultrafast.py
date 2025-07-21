"""
Ultra-fast conftest for CI performance optimization.
Bypasses all expensive setup for maximum speed.
"""

import os

import pytest


# Disable stub server for ultra-fast tests
@pytest.fixture(scope="session", autouse=True)
def disable_stub_server():
    """Disable stub server startup for ultra-fast tests."""
    # Force minimal configuration
    os.environ["USE_STUBS"] = "false"
    os.environ["ENVIRONMENT"] = "test"
    os.environ["SKIP_STUB_SERVER"] = "true"
    yield


@pytest.fixture(autouse=True)
def minimal_provider_setup():
    """Minimal provider setup for ultra-fast tests."""
    # Disable all external providers
    os.environ["ENABLE_GBP"] = "false"
    os.environ["ENABLE_PAGESPEED"] = "false"
    os.environ["ENABLE_SENDGRID"] = "false"
    os.environ["ENABLE_OPENAI"] = "false"
    os.environ["ENABLE_DATAAXLE"] = "false"
    os.environ["ENABLE_HUNTER"] = "false"
    os.environ["ENABLE_SEMRUSH"] = "false"
    os.environ["ENABLE_SCREENSHOTONE"] = "false"
    yield


# Skip database setup for ultra-fast tests
@pytest.fixture(scope="session")
def database_url():
    """Mock database URL for ultra-fast tests."""
    return "sqlite:///:memory:"


# Minimal logging for speed
@pytest.fixture(autouse=True)
def suppress_logging():
    """Suppress logging for ultra-fast tests."""
    import logging

    logging.disable(logging.CRITICAL)
    yield
    logging.disable(logging.NOTSET)
