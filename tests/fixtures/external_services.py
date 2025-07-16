"""
External service mock fixtures for testing.

Provides:
- Mock LLM provider responses
- Mock external API responses (Hunter, DataAxle, etc.)
- Stub server management utilities
- Rate limiting mocks
"""
import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, Mock

import pytest
import requests

from core.config import get_settings


# LLM Provider Mocks
@pytest.fixture
def mock_llm_responses():
    """
    Mock LLM provider responses for testing AI features.

    Returns a configurable mock that can simulate various LLM behaviors.
    """

    class MockLLMProvider:
        def __init__(self):
            self.responses = {
                "default": "This is a mock LLM response.",
                "analysis": "Based on the analysis, the lead score is 85.",
                "personalization": "Dear {{name}}, we noticed your interest in {{product}}.",
                "error": None,  # Will raise exception
            }
            self.call_history = []

        def set_response(self, key: str, response: str):
            """Set a specific response for a key."""
            self.responses[key] = response

        async def generate(self, prompt: str, model: str = "gpt-3.5-turbo", **kwargs) -> str:
            """Generate mock LLM response."""
            self.call_history.append({"prompt": prompt, "model": model, "kwargs": kwargs})

            # Check for specific response patterns
            if "analyze" in prompt.lower():
                return self.responses.get("analysis", self.responses["default"])
            elif "personalize" in prompt.lower():
                return self.responses.get("personalization", self.responses["default"])
            elif "error" in prompt.lower() and self.responses.get("error") is None:
                raise Exception("Mock LLM error")
            elif "test" in prompt.lower():
                return self.responses.get("test", self.responses["default"])

            return self.responses.get("default")

        def generate_sync(self, prompt: str, model: str = "gpt-3.5-turbo", **kwargs) -> str:
            """Synchronous version of generate."""
            import asyncio

            return asyncio.run(self.generate(prompt, model, **kwargs))

        def get_call_count(self) -> int:
            """Get number of calls made."""
            return len(self.call_history)

        def assert_called_with(self, prompt_contains: str):
            """Assert that LLM was called with prompt containing text."""
            for call in self.call_history:
                if prompt_contains in call["prompt"]:
                    return True
            raise AssertionError(f"LLM not called with prompt containing '{prompt_contains}'")

    return MockLLMProvider()


@pytest.fixture
def mock_openai(monkeypatch, mock_llm_responses):
    """Mock OpenAI API calls."""
    mock_client = Mock()
    mock_client.chat.completions.create = AsyncMock(
        return_value=Mock(choices=[Mock(message=Mock(content=mock_llm_responses.responses["default"]))])
    )

    monkeypatch.setattr("openai.AsyncOpenAI", lambda **kwargs: mock_client)
    monkeypatch.setattr("openai.OpenAI", lambda **kwargs: mock_client)

    return mock_client


# External API Mocks
@pytest.fixture
def mock_hunter_api(monkeypatch):
    """Mock Hunter.io API responses."""

    class MockHunterAPI:
        def __init__(self):
            self.responses = {
                "domain_search": {
                    "data": {
                        "domain": "example.com",
                        "emails": [
                            {
                                "value": "john@example.com",
                                "type": "personal",
                                "confidence": 95,
                                "first_name": "John",
                                "last_name": "Doe",
                                "position": "CEO",
                            }
                        ],
                        "organization": "Example Corp",
                    }
                },
                "email_finder": {
                    "data": {
                        "email": "john@example.com",
                        "score": 95,
                        "sources": [{"domain": "example.com", "uri": "https://example.com/about"}],
                    }
                },
                "email_verifier": {"data": {"result": "deliverable", "score": 98, "email": "john@example.com"}},
            }
            self.call_history = []

        def domain_search(self, domain: str, **kwargs) -> dict:
            """Mock domain search."""
            self.call_history.append(("domain_search", domain, kwargs))
            return self.responses["domain_search"]

        def email_finder(self, domain: str, first_name: str, last_name: str, **kwargs) -> dict:
            """Mock email finder."""
            self.call_history.append(("email_finder", domain, first_name, last_name, kwargs))
            return self.responses["email_finder"]

        def email_verifier(self, email: str, **kwargs) -> dict:
            """Mock email verifier."""
            self.call_history.append(("email_verifier", email, kwargs))
            return self.responses["email_verifier"]

    mock_api = MockHunterAPI()
    monkeypatch.setattr("d2_sourcing.providers.hunter.HunterAPI", lambda: mock_api)
    return mock_api


@pytest.fixture
def mock_dataaxle_api(monkeypatch):
    """Mock DataAxle API responses."""

    class MockDataAxleAPI:
        def __init__(self):
            self.responses = {
                "search": {
                    "results": [
                        {
                            "companyName": "Tech Corp",
                            "industry": "Technology",
                            "employeeCount": 150,
                            "annualRevenue": 25000000,
                            "address": {
                                "street": "123 Tech St",
                                "city": "San Francisco",
                                "state": "CA",
                                "zip": "94105",
                            },
                            "contacts": [{"name": "Jane Smith", "title": "CTO", "email": "jane@techcorp.com"}],
                        }
                    ],
                    "totalCount": 1,
                }
            }
            self.call_history = []

        def search_companies(self, filters: dict, **kwargs) -> dict:
            """Mock company search."""
            self.call_history.append(("search_companies", filters, kwargs))
            return self.responses["search"]

        def get_company_details(self, company_id: str) -> dict:
            """Mock company details retrieval."""
            self.call_history.append(("get_company_details", company_id))
            return self.responses["search"]["results"][0]

    mock_api = MockDataAxleAPI()
    monkeypatch.setattr("d2_sourcing.providers.dataaxle.DataAxleAPI", lambda: mock_api)
    return mock_api


# Stub Server Management
@pytest.fixture
def stub_server_url():
    """Get the stub server URL from settings."""
    settings = get_settings()
    return settings.stub_base_url


@pytest.fixture
def stub_client(stub_server_url):
    """
    Create a client for interacting with the stub server.

    Provides methods to configure stub responses dynamically.
    """

    class StubClient:
        def __init__(self, base_url: str):
            self.base_url = base_url

        def set_response(self, endpoint: str, response: dict, status_code: int = 200):
            """Configure stub server to return specific response."""
            requests.post(
                f"{self.base_url}/_stub/configure",
                json={"endpoint": endpoint, "response": response, "status_code": status_code},
            )

        def set_error(self, endpoint: str, error_message: str, status_code: int = 500):
            """Configure stub server to return error."""
            self.set_response(endpoint, {"error": error_message}, status_code)

        def reset(self):
            """Reset all stub configurations."""
            requests.post(f"{self.base_url}/_stub/reset")

        def get_call_history(self, endpoint: str) -> list:
            """Get call history for specific endpoint."""
            response = requests.get(f"{self.base_url}/_stub/history/{endpoint}")
            return response.json()

    return StubClient(stub_server_url)


# Rate Limiting Mocks
@pytest.fixture
def mock_rate_limits(monkeypatch):
    """
    Mock rate limiting for external services.

    Allows tests to simulate rate limit scenarios.
    """

    class MockRateLimiter:
        def __init__(self):
            self.limits = {
                "hunter": {"calls": 0, "limit": 100, "reset_at": None},
                "dataaxle": {"calls": 0, "limit": 1000, "reset_at": None},
                "openai": {"calls": 0, "limit": 60, "reset_at": None},
            }
            self.should_limit = {}

        def check_limit(self, service: str) -> bool:
            """Check if service is rate limited."""
            if service in self.should_limit:
                return self.should_limit[service]

            limit_info = self.limits.get(service, {})
            limit_info["calls"] += 1
            return limit_info["calls"] > limit_info.get("limit", float("inf"))

        def set_limited(self, service: str, limited: bool = True):
            """Manually set rate limit status."""
            self.should_limit[service] = limited

        def reset(self, service: str = None):
            """Reset rate limit counters."""
            if service:
                if service in self.limits:
                    self.limits[service]["calls"] = 0
                if service in self.should_limit:
                    del self.should_limit[service]
            else:
                for svc in self.limits:
                    self.limits[svc]["calls"] = 0
                self.should_limit.clear()

    limiter = MockRateLimiter()
    monkeypatch.setattr("core.rate_limiting.limiter", limiter)
    return limiter


# Mock External Service Responses
@pytest.fixture
def mock_all_external_services(mock_hunter_api, mock_dataaxle_api, mock_openai, mock_rate_limits):
    """
    Convenience fixture that mocks all external services.

    Returns:
        dict: Dictionary containing all mock services
    """
    return {
        "hunter": mock_hunter_api,
        "dataaxle": mock_dataaxle_api,
        "openai": mock_openai,
        "rate_limits": mock_rate_limits,
    }


# Email Service Mocks
@pytest.fixture
def mock_sendgrid(monkeypatch):
    """Mock SendGrid email service."""

    class MockSendGrid:
        def __init__(self):
            self.sent_emails = []
            self.should_fail = False

        def send(self, message: dict) -> dict:
            """Mock email sending."""
            if self.should_fail:
                raise Exception("SendGrid error")

            self.sent_emails.append(message)
            return {"message_id": f"mock_id_{len(self.sent_emails)}", "status": "sent"}

        def set_failing(self, failing: bool = True):
            """Set whether sends should fail."""
            self.should_fail = failing

        def get_sent_count(self) -> int:
            """Get number of emails sent."""
            return len(self.sent_emails)

        def assert_email_sent_to(self, email: str):
            """Assert email was sent to address."""
            for sent in self.sent_emails:
                if email in str(sent.get("to", [])):
                    return True
            raise AssertionError(f"No email sent to {email}")

    mock_sg = MockSendGrid()
    monkeypatch.setattr("d9_delivery.providers.sendgrid.client", mock_sg)
    return mock_sg


# Google Services Mocks
@pytest.fixture
def mock_google_services(monkeypatch):
    """Mock Google services (Places, PageSpeed, etc.)."""

    class MockGoogleServices:
        def __init__(self):
            self.places_responses = {
                "default": {
                    "result": {
                        "name": "Example Business",
                        "rating": 4.5,
                        "user_ratings_total": 123,
                        "reviews": [{"text": "Great service!", "rating": 5}],
                    }
                }
            }
            self.pagespeed_responses = {
                "default": {
                    "lighthouseResult": {
                        "categories": {
                            "performance": {"score": 0.85},
                            "accessibility": {"score": 0.92},
                            "seo": {"score": 0.88},
                        }
                    }
                }
            }

        def get_place_details(self, place_id: str) -> dict:
            """Mock Google Places details."""
            return self.places_responses.get(place_id, self.places_responses["default"])

        def get_pagespeed_insights(self, url: str) -> dict:
            """Mock PageSpeed Insights."""
            return self.pagespeed_responses.get(url, self.pagespeed_responses["default"])

    mock_google = MockGoogleServices()
    monkeypatch.setattr("d4_enrichment.providers.google_places.api", mock_google)
    monkeypatch.setattr("d4_enrichment.providers.pagespeed.api", mock_google)
    return mock_google


# Webhook Mocks
@pytest.fixture
def mock_webhook_server(monkeypatch):
    """Mock webhook endpoint for testing webhook deliveries."""

    class MockWebhookServer:
        def __init__(self):
            self.received_webhooks = []
            self.response_status = 200
            self.response_delay = 0

        def receive_webhook(self, url: str, data: dict, headers: dict = None):
            """Simulate receiving a webhook."""
            self.received_webhooks.append(
                {"url": url, "data": data, "headers": headers or {}, "timestamp": datetime.utcnow()}
            )

            if self.response_delay:
                import time

                time.sleep(self.response_delay)

            return self.response_status

        def set_response(self, status: int = 200, delay: float = 0):
            """Configure webhook response."""
            self.response_status = status
            self.response_delay = delay

        def assert_webhook_received(self, url_contains: str = None, data_contains: dict = None):
            """Assert webhook was received with specific criteria."""
            for webhook in self.received_webhooks:
                if url_contains and url_contains not in webhook["url"]:
                    continue
                if data_contains:
                    webhook_data = webhook["data"]
                    if all(webhook_data.get(k) == v for k, v in data_contains.items()):
                        return True
                else:
                    return True

            raise AssertionError(f"No webhook received matching criteria")

    server = MockWebhookServer()

    def mock_post(url, json=None, data=None, headers=None, **kwargs):
        response = Mock()
        response.status_code = server.receive_webhook(url, json or data, headers)
        response.json = lambda: {"status": "ok"}
        return response

    monkeypatch.setattr("requests.post", mock_post)
    return server
