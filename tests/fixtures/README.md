# Centralized Test Fixtures

This package provides a comprehensive set of reusable fixtures for testing the LeadFactory application. The fixtures are designed to reduce test boilerplate and ensure consistent test isolation.

## Overview

The centralized fixture system provides:

- **Database Fixtures**: Isolated test databases with automatic rollback
- **API Fixtures**: Pre-configured test clients with authentication
- **External Service Mocks**: Mocked responses for all external APIs
- **Utility Fixtures**: Helpers for common testing patterns

## Quick Start

### Basic Database Test

```python
def test_create_company(test_db):
    """Test with isolated database."""
    from d2_sourcing.models import Company
    
    company = Company(name="Test Corp", domain="test.com")
    test_db.add(company)
    test_db.commit()
    
    # Data is automatically rolled back after test
```

### API Test with Authentication

```python
def test_protected_endpoint(authenticated_client):
    """Test with pre-authenticated client."""
    response = authenticated_client.get("/api/v1/leads")
    assert response.status_code == 200
```

### Mocking External Services

```python
def test_with_mocked_llm(mock_llm_responses):
    """Test with controlled LLM responses."""
    mock_llm_responses.set_response("analysis", "Lead score: 85")
    
    # Your code that uses LLM
    result = analyze_lead(lead_data)
    assert result.score == 85
```

## Available Fixtures

### Database Fixtures (`database.py`)

| Fixture | Scope | Description |
|---------|-------|-------------|
| `test_db` | function | Isolated SQLite database session with rollback |
| `async_test_db` | function | Async database session for async operations |
| `db_with_rollback` | function | Explicit rollback capability |
| `db_transaction` | function | Database session within transaction context |
| `db_seeder` | function | Utility for seeding test data |
| `seeded_db` | function | Pre-populated database with sample data |
| `migration_helper` | function | Utilities for testing migrations |

### API Fixtures (`api.py`)

| Fixture | Scope | Description |
|---------|-------|-------------|
| `test_client` | function | FastAPI test client |
| `async_test_client` | function | Async HTTP client for async tests |
| `auth_headers` | function | JWT authentication headers |
| `admin_auth_headers` | function | Admin authentication headers |
| `authenticated_client` | function | Test client with user auth |
| `admin_client` | function | Test client with admin auth |
| `api_helper` | function | API testing utility methods |
| `mock_requests` | function | Mock external HTTP requests |
| `disable_rate_limiting` | function | Disable rate limits for tests |

### External Service Fixtures (`external_services.py`)

| Fixture | Scope | Description |
|---------|-------|-------------|
| `mock_llm_responses` | function | Mock LLM/AI responses |
| `mock_openai` | function | Mock OpenAI API |
| `mock_hunter_api` | function | Mock Hunter.io API |
| `mock_dataaxle_api` | function | Mock DataAxle API |
| `mock_sendgrid` | function | Mock SendGrid email service |
| `mock_google_services` | function | Mock Google APIs |
| `stub_client` | function | Client for stub server interaction |
| `mock_rate_limits` | function | Control rate limiting behavior |
| `mock_webhook_server` | function | Mock webhook endpoints |

## Usage Patterns

### 1. Testing with Seeded Data

```python
def test_with_sample_data(seeded_db):
    """Use pre-populated test data."""
    companies = seeded_db["companies"]  # 5 companies
    leads = seeded_db["leads"]          # 10 leads
    campaigns = seeded_db["campaigns"]  # 3 campaigns
    session = seeded_db["session"]      # Database session
    
    # Test with the seeded data
    from d3_assessment.models import Lead
    high_score_leads = session.query(Lead).filter(Lead.score > 75).all()
    assert len(high_score_leads) > 0
```

### 2. Testing External API Integrations

```python
def test_hunter_integration(mock_hunter_api):
    """Test Hunter.io integration with mocked responses."""
    # Custom response
    mock_hunter_api.responses["domain_search"] = {
        "data": {
            "emails": [
                {"value": "ceo@company.com", "confidence": 99}
            ]
        }
    }
    
    # Test your integration
    from d2_sourcing.services import find_company_emails
    emails = find_company_emails("company.com")
    
    assert "ceo@company.com" in emails
    assert len(mock_hunter_api.call_history) == 1
```

### 3. Testing Async Operations

```python
async def test_async_lead_processing(async_test_db):
    """Test async database operations."""
    from d3_assessment.services import process_lead_async
    
    lead_id = await process_lead_async(
        email="test@example.com",
        session=async_test_db
    )
    
    # Verify in database
    from sqlalchemy import select
    from d3_assessment.models import Lead
    
    result = await async_test_db.execute(
        select(Lead).where(Lead.id == lead_id)
    )
    lead = result.scalar_one()
    assert lead.email == "test@example.com"
```

### 4. Testing with All Mocks

```python
def test_full_integration(mock_all_external_services, seeded_db, authenticated_client):
    """Test with all external services mocked."""
    # Configure mocks
    mock_all_external_services["hunter"].responses["email_verifier"] = {
        "data": {"result": "deliverable", "score": 95}
    }
    mock_all_external_services["openai"].chat.completions.create.return_value = Mock(
        choices=[Mock(message=Mock(content="High quality lead"))]
    )
    
    # Make API request
    response = authenticated_client.post(
        "/api/v1/leads/enrich",
        json={"lead_id": seeded_db["leads"][0].id}
    )
    
    assert response.status_code == 200
    assert response.json()["enrichment_score"] > 90
```

## Best Practices

1. **Use Function Scope**: Most fixtures use function scope for complete isolation
2. **Prefer Centralized Fixtures**: Use these instead of creating custom fixtures
3. **Mock External Services**: Always mock external APIs in unit tests
4. **Verify Mock Calls**: Check that your code called mocks as expected
5. **Use Seeded Data**: For integration tests, use `seeded_db` for consistency
6. **Clean Up**: Fixtures automatically clean up, no manual cleanup needed

## Migration Guide

If you're updating existing tests to use centralized fixtures:

1. Remove local fixture definitions
2. Import from `tests.fixtures`
3. Update fixture names if needed
4. Remove manual cleanup code

### Before:
```python
@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    # ... setup code ...
    yield session
    session.close()  # Manual cleanup
```

### After:
```python
from tests.fixtures import test_db

def test_something(test_db):
    # Use test_db directly, no cleanup needed
```

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure `tests.fixtures` is in the Python path
2. **Fixture Not Found**: Check fixture is imported in `__init__.py`
3. **Database Errors**: Models might not be registered - check `model_imports.py`
4. **Mock Not Working**: Ensure you're using the fixture, not creating your own mock

### Debug Tips

- Use `pytest -v` to see which fixtures are being used
- Check fixture scope if seeing unexpected behavior
- Use `mock.call_history` to debug mock usage
- Enable SQL echo with `test_db.bind.echo = True` for SQL debugging

## Contributing

When adding new fixtures:

1. Add to appropriate module (`database.py`, `api.py`, or `external_services.py`)
2. Export in `__init__.py`
3. Add documentation here
4. Include usage example in `examples.py`