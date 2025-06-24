"""
Test Helper Utilities

Reusable helpers for common test patterns to ensure consistency
and reduce boilerplate across the test suite.
"""

import asyncio
from contextlib import contextmanager
from typing import Any, Callable, Dict, Optional
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import FastAPI


def create_async_mock(return_value: Any) -> Callable:
    """
    Create an async mock function that returns the specified value.

    Usage:
        mock_gateway.some_method.side_effect = create_async_mock({"result": "data"})
    """

    async def mock_coro(*args, **kwargs):
        return return_value

    return mock_coro


def create_async_mock_error(exception: Exception) -> Callable:
    """
    Create an async mock function that raises the specified exception.

    Usage:
        mock_gateway.some_method.side_effect = create_async_mock_error(ValueError("Test error"))
    """

    async def mock_coro(*args, **kwargs):
        raise exception

    return mock_coro


@contextmanager
def override_fastapi_dependency(app: FastAPI, dependency: Callable, mock_value: Any):
    """
    Context manager to override a FastAPI dependency and clean up after.

    Usage:
        with override_fastapi_dependency(app, get_db, mock_db):
            response = client.get("/endpoint")
    """
    app.dependency_overrides[dependency] = lambda: mock_value
    try:
        yield mock_value
    finally:
        app.dependency_overrides.clear()


@contextmanager
def mock_env_vars(**env_vars):
    """
    Context manager to temporarily set environment variables.

    Usage:
        with mock_env_vars(API_KEY="test_key", ENV="test"):
            # Code that uses environment variables
    """
    with patch.dict("os.environ", env_vars):
        yield


def create_mock_gateway_facade():
    """
    Create a mock gateway facade with common methods pre-configured.
    """
    mock_gateway = Mock()

    # Common async methods
    async_methods = [
        "create_checkout_session_with_line_items",
        "get_checkout_session",
        "create_customer",
        "create_product",
        "create_price",
        "construct_webhook_event",
        "get_business_details",
        "search_businesses",
        "analyze_website",
        "get_pagespeed_insights",
        "send_email",
        "generate_text",
    ]

    for method_name in async_methods:
        setattr(mock_gateway, method_name, AsyncMock())

    return mock_gateway


def create_stripe_test_config():
    """
    Create a test Stripe configuration with all required environment variables.
    """
    return {
        "STRIPE_TEST_SECRET_KEY": "sk_test_mock_key",
        "STRIPE_TEST_PUBLISHABLE_KEY": "pk_test_mock_key",
        "STRIPE_TEST_WEBHOOK_SECRET": "whsec_test_mock_secret",
        "STRIPE_LIVE_SECRET_KEY": "sk_live_mock_key",
        "STRIPE_LIVE_PUBLISHABLE_KEY": "pk_live_mock_key",
        "STRIPE_LIVE_WEBHOOK_SECRET": "whsec_live_mock_secret",
    }


class AsyncContextManager:
    """
    Helper for testing async context managers.
    """

    def __init__(self, return_value=None):
        self.return_value = return_value

    async def __aenter__(self):
        return self.return_value

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


def run_async(coro):
    """
    Run an async coroutine in a test.

    Usage:
        result = run_async(async_function())
    """
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


@pytest.fixture
def mock_gateway():
    """
    Pytest fixture providing a mock gateway facade.
    """
    return create_mock_gateway_facade()


@pytest.fixture
def stripe_env_vars():
    """
    Pytest fixture providing Stripe environment variables.
    """
    with mock_env_vars(**create_stripe_test_config()):
        yield


@pytest.fixture
def async_return():
    """
    Pytest fixture providing the create_async_mock helper.
    """
    return create_async_mock


@pytest.fixture
def async_raise():
    """
    Pytest fixture providing the create_async_mock_error helper.
    """
    return create_async_mock_error


# Test data factories
def create_test_business(business_id: str = "test_biz_001", **kwargs) -> Dict[str, Any]:
    """Create a test business record with sensible defaults."""
    defaults = {
        "id": business_id,
        "business_name": "Test Business",
        "phone": "+1-555-123-4567",
        "address": "123 Test St, Test City, TS 12345",
        "city": "Test City",
        "state": "TS",
        "zip": "12345",
        "website": "https://testbusiness.com",
        "email": "contact@testbusiness.com",
    }
    defaults.update(kwargs)
    return defaults


def create_test_assessment_result(
    business_id: str = "test_biz_001", **kwargs
) -> Dict[str, Any]:
    """Create a test assessment result with sensible defaults."""
    defaults = {
        "business_id": business_id,
        "status": "completed",
        "overall_score": 75,
        "findings": [],
        "recommendations": [],
        "total_cost_usd": 0.05,
        "api_calls": 2,
    }
    defaults.update(kwargs)
    return defaults


def create_test_enrichment_result(
    business_id: str = "test_biz_001", **kwargs
) -> Dict[str, Any]:
    """Create a test enrichment result with sensible defaults."""
    defaults = {
        "business_id": business_id,
        "company_name": "Test Business",
        "match_confidence": "high",
        "match_score": 0.85,
        "source": "internal",
        "data_version": "test_v1",
        "enrichment_cost_usd": 0.01,
        "api_calls_used": 1,
        "processed_data": {},
    }
    defaults.update(kwargs)
    return defaults
