"""
API testing fixtures for FastAPI applications.

Provides:
- Test client fixtures with authentication
- Request/response mocking utilities
- API endpoint testing helpers
- OAuth and JWT token management
"""
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import jwt
import pytest

# Import will be added when auth module is available
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient

from core.config import get_settings


@pytest.fixture
def test_client() -> TestClient:
    """
    Create a FastAPI test client for API testing.

    Returns:
        TestClient: FastAPI test client instance
    """
    from main import app

    return TestClient(app)


@pytest.fixture
async def async_test_client() -> AsyncClient:
    """
    Create an async FastAPI test client for async API testing.

    Returns:
        AsyncClient: Async HTTP client for testing
    """
    from main import app

    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
def auth_headers() -> Dict[str, str]:
    """
    Generate authentication headers with a valid JWT token.

    Returns:
        dict: Headers with Authorization bearer token
    """
    settings = get_settings()
    token_data = {
        "sub": "test_user@example.com",
        "exp": datetime.utcnow() + timedelta(hours=1),
        "iat": datetime.utcnow(),
        "scope": "user",
    }
    token = jwt.encode(token_data, settings.secret_key, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_auth_headers() -> Dict[str, str]:
    """
    Generate admin authentication headers with elevated permissions.

    Returns:
        dict: Headers with admin Authorization bearer token
    """
    settings = get_settings()
    token_data = {
        "sub": "admin@example.com",
        "exp": datetime.utcnow() + timedelta(hours=1),
        "iat": datetime.utcnow(),
        "scope": "admin",
        "permissions": ["read", "write", "delete", "admin"],
    }
    token = jwt.encode(token_data, settings.secret_key, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def authenticated_client(test_client: TestClient, auth_headers: Dict[str, str]) -> TestClient:
    """
    Create an authenticated test client with user credentials.

    Args:
        test_client: Base test client
        auth_headers: Authentication headers

    Returns:
        TestClient: Authenticated test client
    """
    test_client.headers.update(auth_headers)
    return test_client


@pytest.fixture
def admin_client(test_client: TestClient, admin_auth_headers: Dict[str, str]) -> TestClient:
    """
    Create an authenticated test client with admin credentials.

    Args:
        test_client: Base test client
        admin_auth_headers: Admin authentication headers

    Returns:
        TestClient: Admin authenticated test client
    """
    test_client.headers.update(admin_auth_headers)
    return test_client


class APITestHelper:
    """Helper class for common API testing operations."""

    def __init__(self, client: TestClient):
        self.client = client

    def create_user(self, email: str = "test@example.com", password: str = "testpass123") -> dict:
        """Create a test user via API."""
        response = self.client.post("/api/v1/auth/register", json={"email": email, "password": password})
        response.raise_for_status()
        return response.json()

    def login(self, email: str = "test@example.com", password: str = "testpass123") -> str:
        """Login and return access token."""
        response = self.client.post("/api/v1/auth/login", data={"username": email, "password": password})
        response.raise_for_status()
        return response.json()["access_token"]

    def assert_error_response(self, response, status_code: int, error_type: Optional[str] = None):
        """Assert that response is an error with expected status and type."""
        assert response.status_code == status_code
        data = response.json()
        assert "detail" in data or "error" in data
        if error_type:
            assert error_type in str(data.get("detail", data.get("error", "")))

    def assert_success_response(self, response, status_code: int = 200):
        """Assert that response is successful."""
        assert response.status_code == status_code
        return response.json()

    def assert_paginated_response(self, response, expected_keys: list = None):
        """Assert that response has pagination structure."""
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "size" in data
        assert "pages" in data

        if expected_keys:
            for item in data["items"]:
                for key in expected_keys:
                    assert key in item

        return data


@pytest.fixture
def api_helper(test_client: TestClient) -> APITestHelper:
    """
    Provide API testing helper utilities.

    Returns:
        APITestHelper: Helper instance for API testing
    """
    return APITestHelper(test_client)


class MockResponse:
    """Mock HTTP response for testing."""

    def __init__(self, json_data: dict, status_code: int = 200, headers: dict = None):
        self.json_data = json_data
        self.status_code = status_code
        self.headers = headers or {}
        self.text = str(json_data)

    def json(self):
        return self.json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


@pytest.fixture
def mock_requests(monkeypatch):
    """
    Mock requests library for external API calls.

    Usage:
        def test_external_api(mock_requests):
            mock_requests.get("https://api.example.com/data", {"result": "success"})
            # Your test code
    """

    class MockRequests:
        def __init__(self):
            self.mocks = {}

        def get(self, url: str, response_data: dict, status_code: int = 200):
            """Mock GET request."""
            self.mocks[("GET", url)] = MockResponse(response_data, status_code)

        def post(self, url: str, response_data: dict, status_code: int = 200):
            """Mock POST request."""
            self.mocks[("POST", url)] = MockResponse(response_data, status_code)

        def _mock_request(self, method: str, url: str, **kwargs):
            """Internal mock request handler."""
            key = (method.upper(), url)
            if key in self.mocks:
                return self.mocks[key]
            raise Exception(f"No mock found for {method} {url}")

    mock = MockRequests()

    # Patch requests library
    monkeypatch.setattr("requests.get", lambda url, **kwargs: mock._mock_request("GET", url, **kwargs))
    monkeypatch.setattr("requests.post", lambda url, **kwargs: mock._mock_request("POST", url, **kwargs))
    monkeypatch.setattr("requests.put", lambda url, **kwargs: mock._mock_request("PUT", url, **kwargs))
    monkeypatch.setattr("requests.delete", lambda url, **kwargs: mock._mock_request("DELETE", url, **kwargs))

    return mock


@pytest.fixture
def api_context():
    """
    Provide context for API testing with common test data.

    Returns:
        dict: Common test data for API tests
    """
    return {
        "test_user": {"email": "test@example.com", "password": "testpass123", "name": "Test User"},
        "test_company": {"name": "Test Company", "domain": "testcompany.com", "industry": "Technology"},
        "test_lead": {"email": "lead@example.com", "first_name": "John", "last_name": "Doe", "company": "Test Company"},
    }


# Rate limiting test utilities
@pytest.fixture
def disable_rate_limiting(monkeypatch):
    """Disable rate limiting for tests."""
    monkeypatch.setenv("ENABLE_RATE_LIMITING", "false")
    get_settings.cache_clear()


@pytest.fixture
def mock_rate_limiter(monkeypatch):
    """Mock rate limiter to control rate limiting in tests."""

    class MockRateLimiter:
        def __init__(self):
            self.calls = []
            self.should_limit = False

        def check_rate_limit(self, key: str) -> bool:
            """Check if request should be rate limited."""
            self.calls.append(key)
            return self.should_limit

        def set_limited(self, limited: bool = True):
            """Set whether requests should be limited."""
            self.should_limit = limited

    limiter = MockRateLimiter()
    monkeypatch.setattr("api.middleware.rate_limiter", limiter)
    return limiter


# WebSocket testing fixtures
@pytest.fixture
def websocket_client(test_client: TestClient):
    """
    Create a WebSocket test client.

    Usage:
        def test_websocket(websocket_client):
            with websocket_client.websocket_connect("/ws") as websocket:
                websocket.send_json({"type": "ping"})
                data = websocket.receive_json()
                assert data["type"] == "pong"
    """
    return test_client


# OAuth testing fixtures
@pytest.fixture
def mock_oauth_provider(monkeypatch):
    """Mock OAuth provider for testing OAuth flows."""

    class MockOAuthProvider:
        def __init__(self):
            self.users = {"test_user": {"id": "123", "email": "oauth@example.com", "name": "OAuth User"}}

        def exchange_code(self, code: str) -> dict:
            """Exchange authorization code for tokens."""
            if code == "valid_code":
                return {"access_token": "mock_access_token", "refresh_token": "mock_refresh_token", "expires_in": 3600}
            raise Exception("Invalid code")

        def get_user_info(self, access_token: str) -> dict:
            """Get user info from access token."""
            if access_token == "mock_access_token":
                return self.users["test_user"]
            raise Exception("Invalid token")

    provider = MockOAuthProvider()
    monkeypatch.setattr("auth.oauth.provider", provider)
    return provider
