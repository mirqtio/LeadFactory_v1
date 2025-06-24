"""Unit tests for SEMrush adapter."""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
import responses

from d3_assessment.semrush import SEMrushAdapter


@pytest.fixture
def adapter():
    """Create SEMrush adapter with mock API key."""
    with patch.dict("os.environ", {"SEMRUSH_API_KEY": "test-key"}):
        return SEMrushAdapter()


@pytest.mark.asyncio
async def test_fetch_overview_returns_traffic_data(adapter):
    """Test fetch_overview returns visits and keyword data."""
    # Mock the client's get_domain_overview method
    mock_result = {
        "organic_traffic": 15000,
        "organic_keywords": 500,
        "paid_keywords": 50,
    }

    adapter.client.get_domain_overview = AsyncMock(return_value=mock_result)

    # Mock Redis quota check
    with patch("d3_assessment.semrush._get_redis_client"):
        result = await adapter.fetch_overview("example.com")

    assert result is not None
    assert result["visits"] == 15000
    assert result["organic_keywords"] == 500
    assert result["paid_keywords"] == 50
    assert "commercial_kw_pct" in result


@pytest.mark.asyncio
async def test_respects_monthly_cap(adapter):
    """Test that monthly quota cap is respected."""
    adapter.monthly_cap = 100

    # Mock Redis to return quota exceeded
    mock_redis = Mock()
    mock_redis.get.return_value = "100"  # At cap

    with patch("d3_assessment.semrush._get_redis_client", return_value=mock_redis):
        result = await adapter.fetch_overview("example.com")

    assert result is None  # Should not make API call


@pytest.mark.asyncio
async def test_cache_30_days(adapter):
    """Test that results are cached for 30 days."""
    mock_result = {
        "organic_traffic": 10000,
        "organic_keywords": 300,
        "paid_keywords": 30,
    }

    adapter.client.get_domain_overview = AsyncMock(return_value=mock_result)

    with patch("d3_assessment.semrush._get_redis_client"):
        # First call - should hit API
        result1 = await adapter.fetch_overview("cached.com")
        assert adapter.client.get_domain_overview.call_count == 1

        # Second call - should use cache
        result2 = await adapter.fetch_overview("cached.com")
        assert adapter.client.get_domain_overview.call_count == 1  # No additional call

        assert result1 == result2


def test_commercial_intent_estimation(adapter):
    """Test commercial intent percentage estimation."""
    # No paid keywords = low commercial intent
    assert (
        adapter._estimate_commercial_intent(
            {"organic_keywords": 100, "paid_keywords": 0}
        )
        == 20
    )

    # Equal paid/organic = medium-high commercial intent
    assert (
        adapter._estimate_commercial_intent(
            {"organic_keywords": 100, "paid_keywords": 100}
        )
        == 70
    )

    # Mostly paid = high commercial intent
    assert (
        adapter._estimate_commercial_intent(
            {"organic_keywords": 20, "paid_keywords": 180}
        )
        == 90
    )


def test_visits_per_mil_calculation(adapter):
    """Test visits per million revenue calculation."""
    # 10k visits, $2M revenue = 5k visits per $1M
    assert adapter.get_visits_per_mil(10000, 2_000_000) == 5000

    # 50k visits, $500k revenue = 100k visits per $1M
    assert adapter.get_visits_per_mil(50000, 500_000) == 100000

    # Zero revenue = default
    assert adapter.get_visits_per_mil(10000, 0) == 5000


@pytest.mark.asyncio
async def test_integration_with_responses():
    """Integration test using responses library to mock API."""
    # This test demonstrates how the adapter would work with actual HTTP calls
    # In practice, the SEMrushClient handles the HTTP layer

    adapter = SEMrushAdapter(api_key="test-key")

    # Mock successful API response
    mock_data = {
        "organic_traffic": 25000,
        "organic_keywords": 750,
        "paid_keywords": 150,
    }

    adapter.client.get_domain_overview = AsyncMock(return_value=mock_data)

    with patch("d3_assessment.semrush._get_redis_client"):
        result = await adapter.fetch_overview("test.com")

    assert isinstance(result["visits"], int)
    assert result["visits"] == 25000
    assert isinstance(result["commercial_kw_pct"], int)
    assert 0 <= result["commercial_kw_pct"] <= 100
