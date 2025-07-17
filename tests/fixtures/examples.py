"""
Examples of using centralized fixtures in tests.

This file demonstrates best practices for using the centralized fixture system.
"""
import pytest

from tests.fixtures import (
    api_helper,
    async_test_db,
    authenticated_client,
    mock_hunter_api,
    mock_llm_responses,
    seeded_db,
    test_db,
)


class TestDatabaseFixtures:
    """Examples of database fixture usage."""

    def test_with_isolated_db(self, test_db):
        """Test with isolated database session."""
        from d2_sourcing.models import Company

        # Create test data
        company = Company(name="Test Corp", domain="testcorp.com")
        test_db.add(company)
        test_db.commit()

        # Query data
        result = test_db.query(Company).filter_by(name="Test Corp").first()
        assert result is not None
        assert result.domain == "testcorp.com"

        # Data is automatically rolled back after test

    def test_with_seeded_db(self, seeded_db):
        """Test with pre-seeded database."""
        # Access pre-created test data
        companies = seeded_db["companies"]
        leads = seeded_db["leads"]
        session = seeded_db["session"]

        assert len(companies) == 5
        assert len(leads) == 10

        # Use the seeded data in tests
        from d3_assessment.models import Lead

        lead_count = session.query(Lead).count()
        assert lead_count == 10

    async def test_async_database(self, async_test_db):
        """Test with async database session."""
        from sqlalchemy import select

        from d2_sourcing.models import Company

        # Create test data
        company = Company(name="Async Corp", domain="asynccorp.com")
        async_test_db.add(company)
        await async_test_db.commit()

        # Query with async
        result = await async_test_db.execute(select(Company).where(Company.name == "Async Corp"))
        company = result.scalar_one()
        assert company.domain == "asynccorp.com"


class TestAPIFixtures:
    """Examples of API testing fixtures."""

    def test_authenticated_request(self, authenticated_client):
        """Test with pre-authenticated client."""
        # Client already has auth headers set
        response = authenticated_client.get("/api/v1/me")
        assert response.status_code == 200
        assert "email" in response.json()

    def test_api_helper_utilities(self, test_client, api_helper):
        """Test using API helper utilities."""
        # Create user and login
        user_data = api_helper.create_user(email="newuser@example.com", password="secure123")
        assert "id" in user_data

        # Login and get token
        token = api_helper.login(email="newuser@example.com", password="secure123")
        assert token is not None

        # Test error response assertion
        response = test_client.get("/api/v1/nonexistent")
        api_helper.assert_error_response(response, 404)

    def test_paginated_endpoint(self, authenticated_client, api_helper):
        """Test paginated API response."""
        response = authenticated_client.get("/api/v1/leads?page=1&size=10")

        # Assert pagination structure
        data = api_helper.assert_paginated_response(response, expected_keys=["id", "email", "first_name", "last_name"])

        assert data["page"] == 1
        assert data["size"] == 10


class TestExternalServiceMocks:
    """Examples of external service mock usage."""

    def test_mock_llm_provider(self, mock_llm_responses):
        """Test with mocked LLM responses."""
        # Set custom response
        mock_llm_responses.set_response(
            "analysis", "The lead quality score is 92 based on company size and engagement."
        )

        # Use in your code
        response = mock_llm_responses.generate_sync("Please analyze this lead data...")
        assert "92" in response

        # Verify calls
        assert mock_llm_responses.get_call_count() == 1
        mock_llm_responses.assert_called_with("analyze")

    def test_mock_hunter_api(self, mock_hunter_api):
        """Test with mocked Hunter.io API."""
        # Default responses are already configured
        result = mock_hunter_api.domain_search("example.com")

        assert result["data"]["domain"] == "example.com"
        assert len(result["data"]["emails"]) > 0

        # Verify API was called
        assert len(mock_hunter_api.call_history) == 1
        assert mock_hunter_api.call_history[0][0] == "domain_search"

    def test_combined_mocks(self, mock_all_external_services):
        """Test with all external services mocked."""
        # Access individual mocks
        hunter = mock_all_external_services["hunter"]
        openai = mock_all_external_services["openai"]
        rate_limits = mock_all_external_services["rate_limits"]

        # Simulate rate limiting
        rate_limits.set_limited("hunter", True)
        assert rate_limits.check_limit("hunter") is True

        # Reset rate limits
        rate_limits.reset()
        assert rate_limits.check_limit("hunter") is False


class TestWebhookMocks:
    """Examples of webhook testing."""

    def test_webhook_delivery(self, mock_webhook_server):
        """Test webhook delivery and verification."""
        # Configure webhook response
        mock_webhook_server.set_response(status=200, delay=0.1)

        # Your code sends webhook (mocked requests.post)
        import requests

        response = requests.post("https://example.com/webhook", json={"event": "lead.created", "lead_id": "123"})

        assert response.status_code == 200

        # Verify webhook was received
        mock_webhook_server.assert_webhook_received(url_contains="webhook", data_contains={"event": "lead.created"})


class TestRateLimiting:
    """Examples of rate limiting fixtures."""

    def test_with_rate_limiting_disabled(self, disable_rate_limiting, test_client):
        """Test with rate limiting disabled."""
        # Make many requests without hitting limits
        for i in range(100):
            response = test_client.get(f"/api/v1/test?i={i}")
            assert response.status_code != 429

    def test_mock_rate_limiter(self, mock_rate_limiter, test_client):
        """Test with controlled rate limiting."""
        # Initially not limited
        response = test_client.get("/api/v1/test")
        assert response.status_code != 429

        # Enable rate limiting
        mock_rate_limiter.set_limited(True)

        # Now requests are limited
        response = test_client.get("/api/v1/test")
        assert response.status_code == 429


# Best Practices Summary:
#
# 1. Use test_db for sync database tests with automatic rollback
# 2. Use async_test_db for async database operations
# 3. Use seeded_db when you need pre-populated test data
# 4. Use authenticated_client for API tests requiring authentication
# 5. Use mock_llm_responses to control AI behavior in tests
# 6. Use mock_all_external_services for comprehensive external service mocking
# 7. Always verify mock calls to ensure your code is making expected requests
# 8. Use rate limiting fixtures to test both rate-limited and unlimited scenarios
