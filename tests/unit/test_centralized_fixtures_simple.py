"""
Simple test to verify centralized fixtures work correctly.
"""

import pytest
from sqlalchemy.orm import Session

from tests.fixtures import mock_llm_responses, seeded_db, test_db


def test_basic_database_fixture(test_db):
    """Test basic database fixture functionality."""
    assert isinstance(test_db, Session)

    # Create test data
    from database.models import Business

    business = Business(name="Test Business", url="https://test.com", website="https://test.com")
    test_db.add(business)
    test_db.commit()

    # Query it back
    result = test_db.query(Business).filter_by(name="Test Business").first()
    assert result is not None
    assert result.url == "https://test.com"


def test_seeded_database(seeded_db):
    """Test pre-seeded database fixture."""
    # Check we have the expected data
    assert "businesses" in seeded_db
    assert "leads" in seeded_db
    assert "targets" in seeded_db

    # Verify counts
    assert len(seeded_db["businesses"]) == 5
    assert len(seeded_db["leads"]) == 10
    assert len(seeded_db["targets"]) == 3

    # Verify we can query
    from database.models import Lead

    session = seeded_db["session"]

    lead_count = session.query(Lead).count()
    assert lead_count == 10


def test_mock_llm_fixture(mock_llm_responses):
    """Test LLM mock fixture."""
    # Test default response
    result = mock_llm_responses.generate_sync("test prompt")
    assert result == "This is a mock LLM response."

    # Set a custom response
    mock_llm_responses.set_response("custom", "Custom mock response")

    # Now it should use the custom response for matching prompts
    mock_llm_responses.responses["default"] = "Custom mock response"
    result2 = mock_llm_responses.generate_sync("another test")
    assert result2 == "Custom mock response"

    # Verify call tracking
    assert mock_llm_responses.get_call_count() == 2
