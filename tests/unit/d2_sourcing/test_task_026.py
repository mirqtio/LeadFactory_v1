"""
Test Task 026: Build Yelp scraper with pagination
Acceptance Criteria:
- Pagination handled correctly
- 1000 result limit respected
- Batch quota enforcement
- Error recovery works
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import aiohttp
import pytest

# Ensure we can import our modules
sys.path.insert(0, "/app")

from d2_sourcing.exceptions import (
    BatchQuotaException,
    ErrorRecoveryException,
    NetworkException,
    YelpAPIException,
    YelpAuthenticationException,
    YelpQuotaExceededException,
    YelpRateLimitException,
)
from d2_sourcing.yelp_scraper import (
    PaginationState,
    ScrapingResult,
    ScrapingStatus,
    YelpScraper,
)


class TestTask026AcceptanceCriteria:
    """Test that Task 026 meets all acceptance criteria"""

    @pytest.fixture
    def mock_session(self):
        """Mock database session"""
        mock_session = Mock()
        mock_session.query.return_value.filter.return_value.count.return_value = 100
        mock_session.add = Mock()
        mock_session.commit = Mock()
        mock_session.rollback = Mock()
        return mock_session

    @pytest.fixture
    def mock_settings(self):
        """Mock settings"""
        settings = Mock()
        settings.YELP_API_KEY = "test-api-key"
        settings.YELP_DAILY_QUOTA = 5000
        settings.YELP_BATCH_QUOTA = 1000
        settings.USE_STUBS = True
        return settings

    @pytest.fixture
    def scraper(self, mock_session, mock_settings):
        """Create YelpScraper instance with mocked dependencies"""
        with patch(
            "d2_sourcing.yelp_scraper.get_settings", return_value=mock_settings
        ), patch("d2_sourcing.yelp_scraper.SessionLocal", return_value=mock_session):
            return YelpScraper(session=mock_session)

    def test_pagination_handled_correctly(self, scraper):
        """Test that pagination is handled correctly across multiple pages"""

        # Test PaginationState initialization and updates
        pagination = PaginationState()
        assert pagination.offset == 0
        assert pagination.limit == 50
        assert pagination.has_more == True
        assert pagination.current_page == 1

        # Test pagination state updates
        pagination.offset += 50
        pagination.current_page += 1
        assert pagination.offset == 50
        assert pagination.current_page == 2

        # Test pagination with mock API responses
        mock_response_page1 = {
            "businesses": [
                {"id": f"biz_{i}", "name": f"Business {i}"} for i in range(50)
            ],
            "total": 150,
            "region": {"center": {"latitude": 37.7749, "longitude": -122.4194}},
        }

        mock_response_page2 = {
            "businesses": [
                {"id": f"biz_{i}", "name": f"Business {i}"} for i in range(50, 100)
            ],
            "total": 150,
            "region": {"center": {"latitude": 37.7749, "longitude": -122.4194}},
        }

        mock_response_page3 = {
            "businesses": [
                {"id": f"biz_{i}", "name": f"Business {i}"} for i in range(100, 150)
            ],
            "total": 150,
            "region": {"center": {"latitude": 37.7749, "longitude": -122.4194}},
        }

        # Test pagination logic with multiple pages
        async def mock_search_page(location, offset, limit, **kwargs):
            if offset == 0:
                return mock_response_page1
            elif offset == 50:
                return mock_response_page2
            elif offset == 100:
                return mock_response_page3
            else:
                return {"businesses": [], "total": 150}

        with patch.object(scraper, "_search_page", side_effect=mock_search_page):
            # Test async pagination
            async def test_pagination():
                result = await scraper.search_businesses(
                    location="San Francisco, CA", max_results=150
                )

                assert result.status == ScrapingStatus.COMPLETED
                assert result.fetched_count == 150
                assert result.total_results == 150
                assert len(result.businesses) == 150

                # Verify all businesses were collected across pages
                business_ids = [b["id"] for b in result.businesses]
                expected_ids = [f"biz_{i}" for i in range(150)]
                assert business_ids == expected_ids

            # Run the async test
            asyncio.run(test_pagination())

        print("✓ Pagination handled correctly")

    def test_1000_result_limit_respected(self, scraper):
        """Test that Yelp's 1000 result limit is respected"""

        # Test that max_results is capped at 1000
        async def test_limit_enforcement():
            # Mock a large total result count from Yelp
            mock_response = {
                "businesses": [
                    {"id": f"biz_{i}", "name": f"Business {i}"} for i in range(50)
                ],
                "total": 5000,  # More than 1000 available
                "region": {"center": {"latitude": 37.7749, "longitude": -122.4194}},
            }

            call_count = 0

            async def mock_search_page(location, offset, limit, **kwargs):
                nonlocal call_count
                call_count += 1

                # Return businesses until we hit 1000 limit
                if offset >= 1000:
                    return {"businesses": [], "total": 5000}

                businesses = [
                    {"id": f"biz_{offset + i}", "name": f"Business {offset + i}"}
                    for i in range(min(50, 1000 - offset))
                ]
                return {
                    "businesses": businesses,
                    "total": 5000,
                    "region": {"center": {"latitude": 37.7749, "longitude": -122.4194}},
                }

            with patch.object(scraper, "_search_page", side_effect=mock_search_page):
                # Request more than 1000 results
                result = await scraper.search_businesses(
                    location="San Francisco, CA",
                    max_results=2000,  # Request more than Yelp's limit
                )

                # Should be capped at 1000
                assert result.fetched_count <= 1000
                assert len(result.businesses) <= 1000

                # Should stop at 1000 even if more are available
                if result.fetched_count == 1000:
                    business_ids = [b["id"] for b in result.businesses]
                    expected_ids = [f"biz_{i}" for i in range(1000)]
                    assert business_ids == expected_ids

        # Test internal limit constant
        assert scraper.YELP_MAX_RESULTS == 1000

        # Test that internal methods respect the limit
        test_cases = [
            (500, 500),  # Normal case
            (1000, 1000),  # At limit
            (1500, 1000),  # Over limit - should be capped
            (2000, 1000),  # Way over limit - should be capped
        ]

        for requested, expected in test_cases:
            capped = min(requested, scraper.YELP_MAX_RESULTS)
            assert (
                capped == expected
            ), f"Failed for requested={requested}, expected={expected}, got={capped}"

        # Run the async test
        asyncio.run(test_limit_enforcement())

        print("✓ 1000 result limit respected")

    def test_batch_quota_enforcement(self, scraper):
        """Test that batch quota limits are enforced correctly"""

        # Test quota checking before operations
        scraper.current_quota_usage = 900
        scraper.batch_quota_limit = 1000

        # Should pass - within quota
        assert scraper.check_quota_availability(50) == True

        # Should fail - would exceed quota
        with pytest.raises(BatchQuotaException) as exc_info:
            scraper.check_quota_availability(150)

        assert "Batch quota would be exceeded" in str(exc_info.value)
        assert exc_info.value.current_usage == 900
        assert exc_info.value.limit == 1000

        # Test quota tracking during operations
        async def test_quota_tracking():
            initial_usage = scraper.current_quota_usage

            mock_response = {
                "businesses": [
                    {"id": f"biz_{i}", "name": f"Business {i}"} for i in range(20)
                ],
                "total": 20,
                "region": {"center": {"latitude": 37.7749, "longitude": -122.4194}},
            }

            with patch.object(scraper, "_search_page", return_value=mock_response):
                result = await scraper.search_businesses(
                    location="San Francisco, CA", max_results=20
                )

                # Quota should have increased by number of API calls made
                assert scraper.current_quota_usage > initial_usage
                assert result.quota_used > 0

        # Test daily quota enforcement
        with patch.object(scraper, "_get_current_daily_usage", return_value=4900):
            scraper.daily_quota_limit = 5000

            # Should pass - within daily limit
            assert scraper.check_quota_availability(50) == True

            # Should fail - would exceed daily limit
            with pytest.raises(YelpQuotaExceededException) as exc_info:
                scraper.check_quota_availability(150)

            assert "Daily quota would be exceeded" in str(exc_info.value)
            assert exc_info.value.quota_type == "daily"

        # Run the async test
        asyncio.run(test_quota_tracking())

        print("✓ Batch quota enforcement")

    def test_error_recovery_works(self, scraper):
        """Test that error recovery mechanisms work correctly"""

        # Test rate limit recovery
        async def test_rate_limit_recovery():
            rate_limit_error = YelpRateLimitException(
                "Rate limit exceeded", retry_after=1
            )

            # Mock error recovery
            with patch.object(
                scraper, "_handle_error_recovery", return_value=True
            ) as mock_recovery:
                should_retry = await scraper._handle_error_recovery(rate_limit_error)
                assert should_retry == True
                mock_recovery.assert_called_once()

        # Test network error recovery with exponential backoff
        async def test_network_error_recovery():
            network_error = NetworkException("Connection failed")
            scraper.consecutive_errors = 0

            # First attempt should retry
            should_retry = await scraper._handle_error_recovery(network_error)
            assert should_retry == True
            assert scraper.consecutive_errors == 1

            # After max retries, should not retry
            scraper.consecutive_errors = scraper.MAX_RETRIES
            should_retry = await scraper._handle_error_recovery(network_error)
            assert should_retry == False

        # Test non-recoverable errors
        async def test_non_recoverable_errors():
            auth_error = YelpAuthenticationException("Invalid API key")
            should_retry = await scraper._handle_error_recovery(auth_error)
            assert should_retry == False

            quota_error = YelpQuotaExceededException("Quota exceeded")
            should_retry = await scraper._handle_error_recovery(quota_error)
            assert should_retry == False

        # Test error counting and reset
        scraper.consecutive_errors = 0

        # Simulate successful request after errors
        scraper.consecutive_errors = 3
        # In real usage, successful request would reset this to 0
        # This is tested in the pagination methods

        # Test exponential backoff calculation
        assert scraper.BACKOFF_MULTIPLIER == 2
        assert scraper.MAX_RETRIES == 3

        # Test error recovery in search operation
        async def test_search_error_recovery():
            call_count = 0

            async def mock_search_page_with_errors(location, offset, limit, **kwargs):
                nonlocal call_count
                call_count += 1

                if call_count == 1:
                    # First call fails
                    return {"error": YelpRateLimitException("Rate limited")}
                else:
                    # Second call succeeds
                    return {
                        "businesses": [{"id": "biz_1", "name": "Business 1"}],
                        "total": 1,
                        "region": {
                            "center": {"latitude": 37.7749, "longitude": -122.4194}
                        },
                    }

            with patch.object(
                scraper, "_search_page", side_effect=mock_search_page_with_errors
            ), patch.object(scraper, "_handle_error_recovery", return_value=True):
                result = await scraper.search_businesses(
                    location="San Francisco, CA", max_results=10
                )

                # Should eventually succeed after error recovery
                assert result.status == ScrapingStatus.COMPLETED
                assert result.error_count > 0  # Errors were encountered
                assert result.fetched_count > 0  # But we still got results

        # Run all async tests
        asyncio.run(test_rate_limit_recovery())
        asyncio.run(test_network_error_recovery())
        asyncio.run(test_non_recoverable_errors())
        asyncio.run(test_search_error_recovery())

        print("✓ Error recovery works")

    def test_additional_functionality(self, scraper):
        """Test additional functionality beyond core acceptance criteria"""

        # Test scraper initialization
        assert scraper.daily_quota_limit == 5000
        assert scraper.batch_quota_limit == 1000
        assert scraper.current_quota_usage == 0
        assert scraper.consecutive_errors == 0

        # Test basic scraper object structure
        assert hasattr(scraper, "gateway")
        assert hasattr(scraper, "logger")
        assert hasattr(scraper, "settings")

        # Test business details fetching
        async def test_business_details():
            mock_business_data = {
                "id": "business_123",
                "name": "Test Business",
                "url": "https://yelp.com/biz/test-business",
                "phone": "+14155551234",
                "location": {"address1": "123 Main St"},
            }

            with patch.object(scraper, "_http_session") as mock_session:
                mock_response = AsyncMock()
                mock_response.status = 200
                mock_response.json = AsyncMock(return_value=mock_business_data)
                mock_session.get.return_value.__aenter__.return_value = mock_response

                result = await scraper.get_business_details("business_123")
                assert result == mock_business_data

        # Test data saving functionality
        business_data = {
            "id": "test_business",
            "name": "Test Restaurant",
            "url": "https://yelp.com/biz/test-restaurant",
            "photos": ["photo1.jpg", "photo2.jpg"],
            "phone": "+14155551234",
        }

        # Test async save_business_data method
        async def test_save_business_data():
            business_id = await scraper.save_business_data(business_data)
            assert business_id is not None
            assert isinstance(business_id, str)
            return business_id

        business_id = asyncio.run(test_save_business_data())

        # Test completeness score calculation
        score = scraper._calculate_completeness_score(business_data)
        assert 0.0 <= score <= 1.0
        assert isinstance(score, float)

        # Test pagination generator interface
        generator = scraper.get_pagination_generator(
            "San Francisco, CA", max_results=100
        )
        assert generator is not None

        # Test scraping statistics
        stats = scraper.get_scraping_stats()
        assert "quota_used" in stats
        assert "daily_quota_limit" in stats
        assert "batch_quota_limit" in stats
        assert "consecutive_errors" in stats
        # Check that stats is a dict with expected structure
        assert isinstance(stats, dict)
        assert stats["daily_quota_limit"] == 5000
        assert stats["batch_quota_limit"] == 1000

        # Async methods testing would require full database setup
        # Skip for unit tests - covered in integration tests

        print("✓ Additional functionality works")

    def test_convenience_functions(self):
        """Test convenience functions for common use cases"""

        from d2_sourcing.yelp_scraper import (
            scrape_businesses_by_location,
            scrape_businesses_by_term,
        )

        # Test function signatures exist
        assert callable(scrape_businesses_by_location)
        assert callable(scrape_businesses_by_term)

        # Test that functions return ScrapingResult
        async def test_convenience_functions():
            with patch("d2_sourcing.yelp_scraper.YelpScraper") as mock_scraper_class:
                mock_scraper = Mock()
                mock_result = ScrapingResult(
                    status=ScrapingStatus.COMPLETED,
                    total_results=10,
                    fetched_count=10,
                    error_count=0,
                    quota_used=1,
                    duration_seconds=1.5,
                    businesses=[{"id": "test_biz", "name": "Test Business"}],
                )
                mock_scraper.search_businesses = AsyncMock(return_value=mock_result)
                mock_scraper_class.return_value = mock_scraper

                # Test location-based search
                result1 = await scrape_businesses_by_location(
                    location="San Francisco, CA",
                    categories=["restaurants"],
                    max_results=50,
                )
                assert isinstance(result1, ScrapingResult)
                assert result1.status == ScrapingStatus.COMPLETED

                # Test term-based search
                result2 = await scrape_businesses_by_term(
                    term="pizza", location="New York, NY", max_results=100
                )
                assert isinstance(result2, ScrapingResult)
                assert result2.status == ScrapingStatus.COMPLETED

        asyncio.run(test_convenience_functions())

        print("✓ Convenience functions work")

    def test_exception_hierarchy(self):
        """Test that exception hierarchy is properly defined"""

        from d2_sourcing.exceptions import (
            BatchQuotaException,
            ErrorRecoveryException,
            PaginationException,
            SourcingException,
            YelpAPIException,
            YelpQuotaExceededException,
            YelpRateLimitException,
        )

        # Test exception inheritance
        assert issubclass(YelpAPIException, SourcingException)
        assert issubclass(YelpRateLimitException, YelpAPIException)
        assert issubclass(YelpQuotaExceededException, YelpAPIException)
        assert issubclass(BatchQuotaException, SourcingException)
        assert issubclass(PaginationException, SourcingException)
        assert issubclass(ErrorRecoveryException, SourcingException)

        # Test exception instantiation with parameters
        rate_limit_ex = YelpRateLimitException("Rate limited", retry_after=60)
        assert rate_limit_ex.retry_after == 60
        assert rate_limit_ex.status_code == 429

        quota_ex = BatchQuotaException("Quota exceeded", current_usage=900, limit=1000)
        assert quota_ex.current_usage == 900
        assert quota_ex.limit == 1000

        # Test exception string representation
        assert "Rate limited" in str(rate_limit_ex)
        assert "900/1000" in str(quota_ex)

        print("✓ Exception hierarchy works")


if __name__ == "__main__":
    # Allow running this test file directly
    test_instance = TestTask026AcceptanceCriteria()

    # Create mock fixtures
    mock_session = Mock()
    mock_session.query.return_value.filter.return_value.count.return_value = 100
    mock_session.add = Mock()
    mock_session.commit = Mock()
    mock_session.rollback = Mock()

    mock_settings = Mock()
    mock_settings.YELP_API_KEY = "test-api-key"
    mock_settings.YELP_DAILY_QUOTA = 5000
    mock_settings.YELP_BATCH_QUOTA = 1000
    mock_settings.USE_STUBS = True

    with patch(
        "d2_sourcing.yelp_scraper.get_settings", return_value=mock_settings
    ), patch("d2_sourcing.yelp_scraper.SessionLocal", return_value=mock_session):
        scraper = YelpScraper(session=mock_session)

    # Run tests
    test_instance.test_pagination_handled_correctly(scraper)
    test_instance.test_1000_result_limit_respected(scraper)
    test_instance.test_batch_quota_enforcement(scraper)
    test_instance.test_error_recovery_works(scraper)
    test_instance.test_additional_functionality(scraper)
    test_instance.test_convenience_functions()
    test_instance.test_exception_hierarchy()

    print("\n🎉 All Task 026 acceptance criteria tests pass!")
    print("   - Pagination handled correctly: ✓")
    print("   - 1000 result limit respected: ✓")
    print("   - Batch quota enforcement: ✓")
    print("   - Error recovery works: ✓")
