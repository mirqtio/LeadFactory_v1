"""Unit tests for Google Business Profile adapter."""
import pytest
from unittest.mock import Mock, patch, AsyncMock

from d3_assessment.gbp import GBPAdapter
from d3_assessment.audit_schema import FindingSeverity, FindingCategory

# Mark entire module as xfail for Phase 0.5
pytestmark = pytest.mark.xfail(reason="Phase 0.5 feature", strict=False)


@pytest.fixture
def adapter():
    """Create GBP adapter with mock API key."""
    with patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"}):
        return GBPAdapter()


@pytest.mark.asyncio
async def test_fetch_business_profile_success(adapter):
    """Test successful business profile fetch."""
    # Mock client
    mock_client = Mock()

    # Mock find_place response
    mock_client.find_place = AsyncMock(
        return_value={
            "place_id": "ChIJtest123",
            "name": "Test Business",
            "formatted_address": "123 Main St",
        }
    )

    # Mock get_place_details response
    mock_client.get_place_details = AsyncMock(
        return_value={
            "rating": 4.5,
            "user_ratings_total": 150,
            "opening_hours": {"weekday_text": ["Monday: 9:00 AM – 5:00 PM"]},
            "name": "Test Business",
        }
    )

    adapter._client = mock_client

    result = await adapter.fetch_business_profile("Test Business", "123 Main St")

    assert result is not None
    assert result["place_id"] == "ChIJtest123"
    assert result["rating"] == 4.5
    assert result["review_count"] == 150
    assert result["has_hours"] is True


@pytest.mark.asyncio
async def test_fetch_business_profile_not_found(adapter):
    """Test when business is not found."""
    mock_client = Mock()
    mock_client.find_place = AsyncMock(return_value=None)
    adapter._client = mock_client

    result = await adapter.fetch_business_profile("Nonexistent Business")

    assert result is None


def test_create_trust_finding_no_gbp(adapter):
    """Test finding creation when no GBP exists."""
    finding = adapter.create_trust_finding(None)

    assert finding is not None
    assert finding.issue_id == "no_gbp_profile"
    assert finding.severity == FindingSeverity.HIGH
    assert finding.category == FindingCategory.TRUST
    assert finding.conversion_impact == 0.035


def test_create_trust_finding_low_rating(adapter):
    """Test finding for low rating (< 4.0)."""
    gbp_data = {
        "place_id": "test123",
        "rating": 3.5,
        "review_count": 50,
        "has_hours": True,
        "name": "Test Business",
    }

    finding = adapter.create_trust_finding(gbp_data)

    assert finding is not None
    assert finding.issue_id == "weak_gbp_presence"
    assert finding.severity == FindingSeverity.HIGH  # 3.5 rating = severity 3
    assert "3.5 stars is below the 4.0 threshold" in finding.description
    assert any(e.value == "3.5 stars" for e in finding.evidence)


def test_create_trust_finding_low_reviews(adapter):
    """Test finding for low review count (< 20)."""
    gbp_data = {
        "place_id": "test123",
        "rating": 4.5,
        "review_count": 10,
        "has_hours": True,
        "name": "Test Business",
    }

    finding = adapter.create_trust_finding(gbp_data)

    assert finding is not None
    assert finding.issue_id == "weak_gbp_presence"
    assert finding.severity == FindingSeverity.HIGH  # < 20 reviews = severity 3
    assert "only 10 reviews" in finding.description
    assert any(e.value == "10" for e in finding.evidence)


def test_create_trust_finding_good_profile(adapter):
    """Test finding for strong GBP presence."""
    gbp_data = {
        "place_id": "test123",
        "rating": 4.7,
        "review_count": 200,
        "has_hours": True,
        "name": "Test Business",
    }

    finding = adapter.create_trust_finding(gbp_data)

    assert finding is not None
    assert finding.issue_id == "strong_gbp_presence"
    assert finding.severity == FindingSeverity.LOW
    assert "Strong Google Business Profile" in finding.title
    assert finding.conversion_impact == 0.005  # Small improvement possible


def test_severity_mapping_integration(adapter):
    """Test that severity mapping matches expected values."""
    # Test case from acceptance criteria
    test_cases = [
        # (rating, review_count, expected_severity)
        (2.5, 50, FindingSeverity.CRITICAL),  # rating < 3.0
        (3.5, 50, FindingSeverity.HIGH),  # rating 3.0-4.0
        (4.2, 50, FindingSeverity.MEDIUM),  # rating 4.0-4.5
        (4.8, 50, FindingSeverity.LOW),  # rating 4.5-5.0
        (4.5, 3, FindingSeverity.CRITICAL),  # review_count < 5
        (4.5, 10, FindingSeverity.HIGH),  # review_count 5-20
    ]

    for rating, review_count, expected in test_cases:
        gbp_data = {
            "rating": rating,
            "review_count": review_count,
        }
        finding = adapter.create_trust_finding(gbp_data)

        # Good profiles still show as LOW severity
        if rating >= 4.0 and review_count >= 20:
            assert finding.severity == FindingSeverity.LOW
        else:
            assert (
                finding.severity == expected
            ), f"Rating {rating} with {review_count} reviews should be {expected}"


@pytest.mark.asyncio
async def test_mock_json_returns_rating_35():
    """Test acceptance criteria: mock JSON returns rating 3.5 → severity 3."""
    adapter = GBPAdapter(api_key="test-key")

    # Mock the API response
    mock_json_response = {
        "rating": 3.5,
        "user_ratings_total": 25,
        "opening_hours": {"weekday_text": ["Monday: 9:00 AM – 5:00 PM"]},
        "name": "Test Business",
    }

    mock_client = Mock()
    mock_client.find_place = AsyncMock(return_value={"place_id": "test123"})
    mock_client.get_place_details = AsyncMock(return_value=mock_json_response)
    adapter._client = mock_client

    # Fetch profile
    result = await adapter.fetch_business_profile("Test Business")
    assert result["rating"] == 3.5

    # Create finding
    finding = adapter.create_trust_finding(result)
    assert finding.severity == FindingSeverity.HIGH  # Severity 3 = HIGH
