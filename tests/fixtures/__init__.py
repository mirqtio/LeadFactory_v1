"""
Test Fixtures Package

Provides centralized fixtures for test isolation and setup:
- Database fixtures (test_db, async_test_db, seeded_db)
- API client fixtures (test_client, authenticated_client)
- External service mocks (mock_llm_responses, mock_hunter_api, etc.)
- Mock factories and utilities
"""

# Import API fixtures
from .api import (
    APITestHelper,
    MockResponse,
    admin_auth_headers,
    admin_client,
    api_context,
    api_helper,
    async_test_client,
    auth_headers,
    authenticated_client,
    disable_rate_limiting,
    mock_oauth_provider,
    mock_rate_limiter,
    mock_requests,
    test_client,
    websocket_client,
)

# Import database fixtures
from .database import (
    DatabaseSeeder,
    TestMigrationHelper,
    async_db_context,
    async_test_db,
    db_seeder,
    db_transaction,
    db_with_rollback,
    migration_helper,
    mock_production_db,
    seeded_db,
    test_db,
)

# Create alias for compatibility
mock_db_sessions = mock_production_db

# Import external service fixtures
from .external_services import (
    mock_all_external_services,
    mock_dataaxle_api,
    mock_google_services,
    mock_hunter_api,
    mock_llm_responses,
    mock_openai,
    mock_rate_limits,
    mock_sendgrid,
    mock_webhook_server,
    stub_client,
    stub_server_url,
)

# Import existing mock factories
from .google_places_mock import GooglePlacesMockFactory
from .mock_factory import MockFactory, ResponseBuilder
from .sendgrid_mock import SendGridMockFactory

__all__ = [
    # Database fixtures
    "test_db",
    "async_test_db",
    "db_with_rollback",
    "db_transaction",
    "db_seeder",
    "seeded_db",
    "migration_helper",
    "async_db_context",
    "mock_production_db",
    "mock_db_sessions",  # Alias for mock_production_db
    "DatabaseSeeder",
    "TestMigrationHelper",
    # API fixtures
    "test_client",
    "async_test_client",
    "auth_headers",
    "admin_auth_headers",
    "authenticated_client",
    "admin_client",
    "api_helper",
    "mock_requests",
    "api_context",
    "disable_rate_limiting",
    "mock_rate_limiter",
    "websocket_client",
    "mock_oauth_provider",
    "APITestHelper",
    "MockResponse",
    # External service fixtures
    "mock_llm_responses",
    "mock_openai",
    "mock_hunter_api",
    "mock_dataaxle_api",
    "stub_server_url",
    "stub_client",
    "mock_rate_limits",
    "mock_all_external_services",
    "mock_sendgrid",
    "mock_google_services",
    "mock_webhook_server",
    # Mock factories
    "MockFactory",
    "ResponseBuilder",
    "GooglePlacesMockFactory",
    "SendGridMockFactory",
]
