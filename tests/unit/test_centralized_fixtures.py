"""
Tests for centralized fixture system.

Verifies that all centralized fixtures work correctly and provide
proper test isolation.
"""
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from tests.fixtures import (
    APITestHelper,
    DatabaseSeeder,
    async_test_db,
    authenticated_client,
    mock_hunter_api,
    mock_llm_responses,
    seeded_db,
    test_client,
    test_db,
)


class TestDatabaseFixtures:
    """Test database fixture functionality."""

    def test_test_db_isolation(self, test_db):
        """Verify test_db provides isolated sessions."""
        assert isinstance(test_db, Session)

        # Create test data
        from d2_sourcing.models import Company

        company = Company(name="Test Isolation", domain="isolation.com")
        test_db.add(company)
        test_db.commit()

        # Verify data exists in this session
        result = test_db.query(Company).filter_by(name="Test Isolation").first()
        assert result is not None

    def test_test_db_rollback(self, test_db):
        """Verify data from previous test is not present."""
        from d2_sourcing.models import Company

        # This should not find the company from previous test
        result = test_db.query(Company).filter_by(name="Test Isolation").first()
        assert result is None

    async def test_async_db_fixture(self, async_test_db):
        """Test async database operations."""
        assert isinstance(async_test_db, AsyncSession)

        from d2_sourcing.models import Company

        # Create data
        company = Company(name="Async Test", domain="async.com")
        async_test_db.add(company)
        await async_test_db.commit()

        # Query data
        result = await async_test_db.execute(select(Company).where(Company.name == "Async Test"))
        found = result.scalar_one_or_none()
        assert found is not None
        assert found.domain == "async.com"

    def test_database_seeder(self, db_seeder):
        """Test database seeding utilities."""
        assert isinstance(db_seeder, DatabaseSeeder)

        # Seed companies
        companies = db_seeder.seed_companies(3)
        assert len(companies) == 3
        assert all(c.id is not None for c in companies)

        # Seed leads
        leads = db_seeder.seed_leads(5, [c.id for c in companies])
        assert len(leads) == 5
        assert all(lead.company_id is not None for lead in leads)

    def test_seeded_db_fixture(self, seeded_db):
        """Test pre-seeded database fixture."""
        assert "companies" in seeded_db
        assert "leads" in seeded_db
        assert "campaigns" in seeded_db
        assert "session" in seeded_db

        # Verify seeded data
        assert len(seeded_db["companies"]) == 5
        assert len(seeded_db["leads"]) == 10
        assert len(seeded_db["campaigns"]) == 3

        # Verify we can query the data
        from d2_sourcing.models import Company

        count = seeded_db["session"].query(Company).count()
        assert count == 5


class TestAPIFixtures:
    """Test API fixture functionality."""

    def test_test_client_fixture(self, test_client):
        """Test basic test client."""
        # Should be able to make requests
        response = test_client.get("/health")
        assert response.status_code in [200, 404]  # Depends on if health endpoint exists

    def test_auth_headers_fixture(self, auth_headers):
        """Test authentication headers generation."""
        assert "Authorization" in auth_headers
        assert auth_headers["Authorization"].startswith("Bearer ")

        # Token should be valid JWT
        token = auth_headers["Authorization"].split(" ")[1]
        assert len(token.split(".")) == 3  # JWT has 3 parts

    def test_authenticated_client(self, authenticated_client):
        """Test pre-authenticated client."""
        # Client should have auth headers set
        assert "Authorization" in authenticated_client.headers

    def test_api_helper(self, api_helper):
        """Test API helper utilities."""
        assert isinstance(api_helper, APITestHelper)

        # Test error assertion
        from unittest.mock import Mock

        mock_response = Mock(status_code=404, json=lambda: {"detail": "Not found"})
        api_helper.assert_error_response(mock_response, 404)

        # Test success assertion
        mock_response = Mock(status_code=200, json=lambda: {"status": "ok"})
        result = api_helper.assert_success_response(mock_response)
        assert result == {"status": "ok"}


class TestExternalServiceFixtures:
    """Test external service mock fixtures."""

    def test_mock_llm_responses(self, mock_llm_responses):
        """Test LLM mock functionality."""
        # Set custom response
        mock_llm_responses.set_response("test", "Test response")

        # Generate response
        response = mock_llm_responses.generate_sync("test prompt")
        assert response == "Test response"

        # Check call history
        assert mock_llm_responses.get_call_count() == 1
        mock_llm_responses.assert_called_with("test prompt")

    def test_mock_hunter_api(self, mock_hunter_api):
        """Test Hunter API mock."""
        # Use domain search
        result = mock_hunter_api.domain_search("example.com")

        assert "data" in result
        assert result["data"]["domain"] == "example.com"
        assert len(result["data"]["emails"]) > 0

        # Verify call was recorded
        assert len(mock_hunter_api.call_history) == 1
        assert mock_hunter_api.call_history[0][0] == "domain_search"
        assert mock_hunter_api.call_history[0][1] == "example.com"

    async def test_mock_openai_async(self, mock_openai):
        """Test OpenAI mock with async operations."""
        # The mock is already configured
        result = await mock_openai.chat.completions.create(
            model="gpt-3.5-turbo", messages=[{"role": "user", "content": "Hello"}]
        )

        assert result.choices[0].message.content is not None


class TestFixtureInteraction:
    """Test fixtures working together."""

    def test_db_and_api_fixtures(self, seeded_db, authenticated_client):
        """Test database and API fixtures together."""
        # We have seeded data
        companies = seeded_db["companies"]
        assert len(companies) > 0

        # And an authenticated client
        assert "Authorization" in authenticated_client.headers

        # They work independently
        from d2_sourcing.models import Company

        count = seeded_db["session"].query(Company).count()
        assert count == len(companies)

    def test_multiple_mocks(self, mock_llm_responses, mock_hunter_api):
        """Test multiple mock fixtures together."""
        # Both mocks work independently
        mock_llm_responses.set_response("test", "LLM response")
        llm_result = mock_llm_responses.generate_sync("test")
        assert llm_result == "LLM response"

        hunter_result = mock_hunter_api.domain_search("test.com")
        assert hunter_result["data"]["domain"] == "example.com"  # Default response

        # Each maintains its own state
        assert mock_llm_responses.get_call_count() == 1
        assert len(mock_hunter_api.call_history) == 1


class TestFixtureIsolation:
    """Verify fixtures provide proper test isolation."""

    def test_isolation_first(self, test_db):
        """First test - create data."""
        from d2_sourcing.models import Company

        company = Company(name="Isolation Test", domain="first.com")
        test_db.add(company)
        test_db.commit()

        count = test_db.query(Company).count()
        assert count == 1

    def test_isolation_second(self, test_db):
        """Second test - verify isolation from first test."""
        from d2_sourcing.models import Company

        # Should not see data from first test
        count = test_db.query(Company).count()
        assert count == 0

        # Create different data
        company = Company(name="Different Company", domain="second.com")
        test_db.add(company)
        test_db.commit()

        result = test_db.query(Company).filter_by(domain="first.com").first()
        assert result is None
