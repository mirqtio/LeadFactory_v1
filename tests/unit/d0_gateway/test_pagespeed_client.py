"""
Test PageSpeed API client implementation
"""
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch

import pytest

from d0_gateway.providers.pagespeed import PageSpeedClient

# Mark entire module as slow for CI optimization
pytestmark = pytest.mark.slow


class TestPageSpeedClient:
    @pytest.fixture
    def pagespeed_client(self):
        """Create PageSpeed client for testing"""
        return PageSpeedClient()

    def test_url_analysis_works_initialization(self, pagespeed_client):
        """Test that URL analysis client is properly initialized"""
        # Should inherit from BaseAPIClient
        assert hasattr(pagespeed_client, "provider")
        assert pagespeed_client.provider == "pagespeed"

        # Should have rate limiter, circuit breaker, cache
        assert hasattr(pagespeed_client, "rate_limiter")
        assert hasattr(pagespeed_client, "circuit_breaker")
        assert hasattr(pagespeed_client, "cache")

        # Should have proper base URL
        assert pagespeed_client._get_base_url() == "https://www.googleapis.com"

        # Should have proper headers
        headers = pagespeed_client._get_headers()
        assert headers["Content-Type"] == "application/json"

    def test_25k_day_limit_enforced_config(self, pagespeed_client):
        """Test that 25k/day limit is enforced through configuration"""
        rate_limit = pagespeed_client.get_rate_limit()

        # Should have 25000 daily limit as per PageSpeed API
        assert rate_limit["daily_limit"] == 25000
        assert rate_limit["burst_limit"] == 50  # Reasonable burst limit
        assert rate_limit["window_seconds"] == 1

        # Should track daily usage
        assert "daily_used" in rate_limit

    @pytest.mark.asyncio
    async def test_url_analysis_works_basic(self, pagespeed_client):
        """Test basic URL analysis functionality"""
        # Mock PageSpeed API response
        mock_response = {
            "analysisUTCTimestamp": "2023-01-01T00:00:00.000Z",
            "id": "https://example.com/",
            "lighthouseResult": {
                "requestedUrl": "https://example.com/",
                "finalUrl": "https://example.com/",
                "categories": {
                    "performance": {"score": 0.85, "title": "Performance"},
                    "accessibility": {"score": 0.92, "title": "Accessibility"},
                },
                "audits": {
                    "largest-contentful-paint": {
                        "score": 0.8,
                        "numericValue": 2500,
                        "displayValue": "2.5 s",
                    }
                },
            },
            "loadingExperience": {
                "metrics": {
                    "LARGEST_CONTENTFUL_PAINT_MS": {
                        "percentile": 2500,
                        "category": "AVERAGE",
                    }
                }
            },
        }

        pagespeed_client.make_request = AsyncMock(return_value=mock_response)

        # Test basic URL analysis
        result = await pagespeed_client.analyze_url("https://example.com")

        # Verify API call was made correctly
        pagespeed_client.make_request.assert_called_once_with(
            "GET",
            "/pagespeedonline/v5/runPagespeed",
            params={
                "url": "https://example.com",
                "strategy": "mobile",  # Default strategy
                "key": pagespeed_client.api_key,
                "category": "performance,accessibility,best-practices,seo",  # Default categories
            },
        )

        # Verify response structure
        assert "analysisUTCTimestamp" in result
        assert "lighthouseResult" in result
        assert result["id"] == "https://example.com/"

    @pytest.mark.asyncio
    async def test_mobile_desktop_strategies(self, pagespeed_client):
        """Test mobile and desktop analysis strategies"""
        mock_response = {"lighthouseResult": {"categories": {}}}
        pagespeed_client.make_request = AsyncMock(return_value=mock_response)

        # Test mobile strategy
        await pagespeed_client.analyze_url("https://example.com", strategy="mobile")

        call_args = pagespeed_client.make_request.call_args[1]["params"]
        assert call_args["strategy"] == "mobile"

        # Test desktop strategy
        pagespeed_client.make_request.reset_mock()
        await pagespeed_client.analyze_url("https://example.com", strategy="desktop")

        call_args = pagespeed_client.make_request.call_args[1]["params"]
        assert call_args["strategy"] == "desktop"

    @pytest.mark.asyncio
    async def test_mobile_and_desktop_combined_analysis(self, pagespeed_client):
        """Test combined mobile and desktop analysis"""
        mobile_response = {
            "analysisUTCTimestamp": "2023-01-01T00:00:00.000Z",
            "lighthouseResult": {"categories": {"performance": {"score": 0.8}}},
        }
        desktop_response = {
            "analysisUTCTimestamp": "2023-01-01T00:00:00.000Z",
            "lighthouseResult": {"categories": {"performance": {"score": 0.9}}},
        }

        # Mock both calls
        pagespeed_client.make_request = AsyncMock(side_effect=[mobile_response, desktop_response])

        result = await pagespeed_client.analyze_mobile_and_desktop("https://example.com")

        # Should make two API calls
        assert pagespeed_client.make_request.call_count == 2

        # Verify result structure
        assert "mobile" in result
        assert "desktop" in result
        assert "url" in result
        assert result["url"] == "https://example.com"
        assert result["mobile"] == mobile_response
        assert result["desktop"] == desktop_response

    @pytest.mark.asyncio
    async def test_lighthouse_data_parsed_core_web_vitals(self, pagespeed_client):
        """Test that Lighthouse data is properly parsed for Core Web Vitals"""
        mock_response = {
            "lighthouseResult": {
                "categories": {"performance": {"score": 0.85}},
                "audits": {
                    "largest-contentful-paint": {
                        "score": 0.8,
                        "numericValue": 2500,
                        "displayValue": "2.5 s",
                    },
                    "max-potential-fid": {
                        "score": 0.9,
                        "numericValue": 50,
                        "displayValue": "50 ms",
                    },
                    "cumulative-layout-shift": {
                        "score": 0.95,
                        "numericValue": 0.05,
                        "displayValue": "0.05",
                    },
                    "first-contentful-paint": {
                        "score": 0.85,
                        "numericValue": 1800,
                        "displayValue": "1.8 s",
                    },
                    "speed-index": {
                        "score": 0.8,
                        "numericValue": 3200,
                        "displayValue": "3.2 s",
                    },
                },
            }
        }

        pagespeed_client.make_request = AsyncMock(return_value=mock_response)

        cwv = await pagespeed_client.get_core_web_vitals("https://example.com")

        # Verify Core Web Vitals extraction
        assert cwv["url"] == "https://example.com"
        assert cwv["strategy"] == "mobile"
        assert cwv["performance_score"] == 0.85

        # Verify LCP (Largest Contentful Paint)
        assert cwv["largest_contentful_paint"]["score"] == 0.8
        assert cwv["largest_contentful_paint"]["numericValue"] == 2500
        assert cwv["largest_contentful_paint"]["displayValue"] == "2.5 s"

        # Verify FID (First Input Delay proxy)
        assert cwv["first_input_delay"]["score"] == 0.9
        assert cwv["first_input_delay"]["numericValue"] == 50

        # Verify CLS (Cumulative Layout Shift)
        assert cwv["cumulative_layout_shift"]["score"] == 0.95
        assert cwv["cumulative_layout_shift"]["numericValue"] == 0.05

        # Verify additional metrics
        assert cwv["first_contentful_paint"]["score"] == 0.85
        assert cwv["speed_index"]["score"] == 0.8

    @pytest.mark.asyncio
    async def test_lighthouse_data_parsed_opportunities(self, pagespeed_client):
        """Test extraction of optimization opportunities from Lighthouse data"""
        mock_response = {
            "lighthouseResult": {
                "audits": {
                    "unused-css-rules": {
                        "score": 0.5,
                        "title": "Remove unused CSS",
                        "description": "Remove dead rules from stylesheets",
                        "details": {"overallSavingsMs": 1200},
                    },
                    "render-blocking-resources": {
                        "score": 0.3,
                        "title": "Eliminate render-blocking resources",
                        "description": "Resources are blocking the first paint",
                        "details": {"overallSavingsMs": 800},
                    },
                    "good-audit": {
                        "score": 1.0,  # Passed audit
                        "title": "Good thing",
                        "details": {"overallSavingsMs": 0},
                    },
                }
            }
        }

        opportunities = pagespeed_client.extract_opportunities(mock_response)

        # Should extract only failed audits with savings
        assert len(opportunities) == 2

        # Should be sorted by savings (highest first)
        assert opportunities[0]["savings_ms"] == 1200  # unused-css-rules
        assert opportunities[1]["savings_ms"] == 800  # render-blocking-resources

        # Verify opportunity structure
        opp = opportunities[0]
        assert opp["id"] == "unused-css-rules"
        assert opp["title"] == "Remove unused CSS"
        assert opp["score"] == 0.5
        assert opp["impact"] == "high"  # > 1000ms

        # Verify impact categorization
        assert opportunities[1]["impact"] == "medium"  # 500-1000ms

    def test_impact_categorization(self, pagespeed_client):
        """Test impact level categorization"""
        assert pagespeed_client._categorize_impact(1500) == "high"  # >= 1000ms
        assert pagespeed_client._categorize_impact(750) == "medium"  # 500-999ms
        assert pagespeed_client._categorize_impact(200) == "low"  # < 500ms

    @pytest.mark.asyncio
    async def test_custom_categories_and_parameters(self, pagespeed_client):
        """Test custom categories and optional parameters"""
        pagespeed_client.make_request = AsyncMock(return_value={"lighthouseResult": {}})

        # Test with custom categories
        await pagespeed_client.analyze_url(
            "https://example.com",
            strategy="desktop",
            categories=["performance", "seo"],
            locale="en",
            utm_campaign="test-campaign",
            utm_source="test-source",
        )

        call_args = pagespeed_client.make_request.call_args[1]["params"]

        # Verify all parameters are included
        assert call_args["url"] == "https://example.com"
        assert call_args["strategy"] == "desktop"
        assert call_args["category"] == "performance,seo"
        assert call_args["locale"] == "en"
        assert call_args["utm_campaign"] == "test-campaign"
        assert call_args["utm_source"] == "test-source"
        assert "key" in call_args  # API key should be included

    @pytest.mark.asyncio
    async def test_batch_url_analysis(self, pagespeed_client):
        """Test batch analysis of multiple URLs"""
        # Mock responses for different URLs

        pagespeed_client.get_core_web_vitals = AsyncMock(
            side_effect=[
                {"url": "https://site1.com", "performance_score": 0.8},
                {"url": "https://site2.com", "performance_score": 0.9},
                {"url": "https://site3.com", "performance_score": 0.7},
            ]
        )

        urls = ["https://site1.com", "https://site2.com", "https://site3.com"]
        result = await pagespeed_client.batch_analyze_urls(urls=urls, strategy="desktop", include_core_web_vitals=True)

        # Verify all URLs were analyzed
        assert pagespeed_client.get_core_web_vitals.call_count == 3

        # Verify result structure
        assert "urls" in result
        assert "total_urls" in result
        assert "successful_urls" in result
        assert "strategy" in result

        assert result["total_urls"] == 3
        assert result["successful_urls"] == 3
        assert result["strategy"] == "desktop"

        # Verify each URL has results
        for url in urls:
            assert url in result["urls"]
            assert "performance_score" in result["urls"][url]

    @pytest.mark.asyncio
    async def test_batch_analysis_with_errors(self, pagespeed_client):
        """Test batch analysis with some URL failures"""

        def mock_analysis(url, strategy):
            if url == "https://invalid-url.com":
                raise Exception("Invalid URL")
            return {"url": url, "performance_score": 0.8}

        pagespeed_client.get_core_web_vitals = AsyncMock(side_effect=mock_analysis)

        urls = [
            "https://good-url.com",
            "https://invalid-url.com",
            "https://another-good.com",
        ]
        result = await pagespeed_client.batch_analyze_urls(urls)

        # Should handle errors gracefully
        assert result["total_urls"] == 3
        assert result["successful_urls"] == 2  # 2 succeeded, 1 failed

        # Failed URL should have error info
        assert "error" in result["urls"]["https://invalid-url.com"]
        assert result["urls"]["https://invalid-url.com"]["url"] == "https://invalid-url.com"

        # Successful URLs should have data
        assert "performance_score" in result["urls"]["https://good-url.com"]
        assert "performance_score" in result["urls"]["https://another-good.com"]

    def test_cost_calculation(self, pagespeed_client):
        """Test cost calculation for PageSpeed operations"""
        # PageSpeed API is free up to 25k queries per day
        analysis_cost = pagespeed_client.calculate_cost("GET:/pagespeedonline/v5/runPagespeed")
        assert analysis_cost == Decimal("0.000")

        # Other operations might have cost
        other_cost = pagespeed_client.calculate_cost("GET:/other/endpoint")
        assert other_cost == Decimal("0.004")

    @pytest.mark.asyncio
    async def test_error_handling_invalid_url(self, pagespeed_client):
        """Test error handling for invalid URLs"""
        from core.exceptions import ExternalAPIError

        # Mock API error response
        pagespeed_client.make_request = AsyncMock(side_effect=ExternalAPIError("Invalid URL", 400))

        with pytest.raises(ExternalAPIError):
            await pagespeed_client.analyze_url("invalid-url")

    @pytest.mark.asyncio
    async def test_error_handling_quota_exceeded(self, pagespeed_client):
        """Test error handling when API quota is exceeded"""
        from core.exceptions import RateLimitError

        # Mock quota exceeded error
        pagespeed_client.make_request = AsyncMock(side_effect=RateLimitError("pagespeed", "daily"))

        with pytest.raises(RateLimitError):
            await pagespeed_client.analyze_url("https://example.com")

    @pytest.mark.asyncio
    async def test_error_handling_network_errors(self, pagespeed_client):
        """Test error handling for network-related errors"""
        import httpx

        # Test network timeout
        pagespeed_client.make_request = AsyncMock(side_effect=httpx.TimeoutException("Request timeout"))

        with pytest.raises(httpx.TimeoutException):
            await pagespeed_client.analyze_url("https://example.com")


class TestPageSpeedClientIntegration:
    @pytest.mark.asyncio
    async def test_rate_limiting_integration(self):
        """Test integration with rate limiting"""
        pagespeed_client = PageSpeedClient()

        # Mock rate limiter to indicate limit exceeded
        with patch.object(pagespeed_client.rate_limiter, "is_allowed", return_value=False):
            from core.exceptions import RateLimitError

            pagespeed_client.make_request = AsyncMock(side_effect=RateLimitError("pagespeed", "daily"))

            with pytest.raises(RateLimitError):
                await pagespeed_client.analyze_url("https://example.com")

    @pytest.mark.asyncio
    async def test_circuit_breaker_integration(self):
        """Test integration with circuit breaker"""
        pagespeed_client = PageSpeedClient()

        # Mock circuit breaker to indicate open state
        with patch.object(pagespeed_client.circuit_breaker, "can_execute", return_value=False):
            from d0_gateway.exceptions import CircuitBreakerOpenError

            pagespeed_client.make_request = AsyncMock(side_effect=CircuitBreakerOpenError("pagespeed", 5))

            with pytest.raises(CircuitBreakerOpenError):
                await pagespeed_client.analyze_url("https://example.com")

    @pytest.mark.asyncio
    async def test_caching_integration(self):
        """Test integration with response caching"""
        pagespeed_client = PageSpeedClient()

        # Test that cache is properly initialized
        assert hasattr(pagespeed_client, "cache")
        assert pagespeed_client.cache.provider == "pagespeed"

        # Test cache key generation for URL analysis
        analysis_params = {"url": "https://example.com", "strategy": "mobile"}
        cache_key = pagespeed_client.cache.generate_key("/pagespeedonline/v5/runPagespeed", analysis_params)

        # Cache key should be deterministic
        assert isinstance(cache_key, str)
        assert cache_key.startswith("api_cache:")

        # Test cache statistics are available
        stats = await pagespeed_client.cache.get_cache_stats()
        assert "provider" in stats
        assert stats["provider"] == "pagespeed"

    @pytest.mark.asyncio
    async def test_stub_mode_integration(self):
        """Test integration with stub mode"""
        with patch("core.config.get_settings") as mock_get_settings:
            mock_settings = Mock()
            mock_settings.use_stubs = True
            mock_settings.stub_base_url = "http://localhost:8000"
            mock_get_settings.return_value = mock_settings

            pagespeed_client = PageSpeedClient()

            # Should use stub configuration
            assert pagespeed_client.api_key == "stub-pagespeed-key"
            # In Docker environment, stub-server is used instead of localhost
            assert "localhost" in pagespeed_client.base_url or "stub-server" in pagespeed_client.base_url


class TestPageSpeedClientDataExtraction:
    def test_core_web_vitals_extraction_edge_cases(self):
        """Test Core Web Vitals extraction with missing data"""
        pagespeed_client = PageSpeedClient()

        # Test with missing audit data
        incomplete_response = {
            "lighthouseResult": {
                "categories": {"performance": {"score": 0.8}},
                "audits": {
                    "largest-contentful-paint": {
                        "score": 0.7,
                        "numericValue": 3000
                        # Missing displayValue
                    }
                    # Missing other audits
                },
            }
        }

        # Mock the analysis call
        pagespeed_client.make_request = AsyncMock(return_value=incomplete_response)

        # Should handle missing data gracefully
        import asyncio

        cwv = asyncio.run(pagespeed_client.get_core_web_vitals("https://example.com"))

        # Should have structure even with missing data
        assert cwv["url"] == "https://example.com"
        assert cwv["performance_score"] == 0.8
        assert cwv["largest_contentful_paint"]["score"] == 0.7
        assert cwv["first_input_delay"] is None  # Missing audit
        assert cwv["cumulative_layout_shift"] is None  # Missing audit

    def test_opportunities_extraction_edge_cases(self):
        """Test opportunities extraction with various audit states"""
        pagespeed_client = PageSpeedClient()

        test_response = {
            "lighthouseResult": {
                "audits": {
                    "passed-audit": {
                        "score": 1.0,  # Passed
                        "title": "Good audit",
                        "details": {"overallSavingsMs": 0},
                    },
                    "failed-no-savings": {
                        "score": 0.0,  # Failed but no savings
                        "title": "Failed but no impact",
                        "details": {"overallSavingsMs": 0},
                    },
                    "failed-with-savings": {
                        "score": 0.2,  # Failed with savings
                        "title": "Optimization opportunity",
                        "details": {"overallSavingsMs": 1500},
                    },
                    "no-details": {
                        "score": 0.0,  # Failed but no details
                        "title": "Missing details",
                    },
                }
            }
        }

        opportunities = pagespeed_client.extract_opportunities(test_response)

        # Should only extract audits with savings
        assert len(opportunities) == 1
        assert opportunities[0]["id"] == "failed-with-savings"
        assert opportunities[0]["impact"] == "high"

    @pytest.mark.asyncio
    async def test_comprehensive_analysis_workflow(self):
        """Test a comprehensive analysis workflow"""
        pagespeed_client = PageSpeedClient()

        # Mock comprehensive PageSpeed response
        comprehensive_response = {
            "analysisUTCTimestamp": "2023-01-01T12:00:00.000Z",
            "id": "https://example.com/",
            "lighthouseResult": {
                "categories": {
                    "performance": {"score": 0.75},
                    "accessibility": {"score": 0.9},
                    "best-practices": {"score": 0.85},
                    "seo": {"score": 0.95},
                },
                "audits": {
                    "largest-contentful-paint": {
                        "score": 0.6,
                        "numericValue": 3200,
                        "displayValue": "3.2 s",
                    },
                    "cumulative-layout-shift": {
                        "score": 0.8,
                        "numericValue": 0.12,
                        "displayValue": "0.12",
                    },
                    "unused-css-rules": {
                        "score": 0.3,
                        "title": "Remove unused CSS",
                        "description": "Reduce unused rules",
                        "details": {"overallSavingsMs": 800},
                    },
                },
            },
        }

        pagespeed_client.make_request = AsyncMock(return_value=comprehensive_response)

        # Test full analysis
        result = await pagespeed_client.analyze_url("https://example.com", strategy="desktop")

        # Test Core Web Vitals extraction
        pagespeed_client.make_request.reset_mock()
        pagespeed_client.make_request.return_value = comprehensive_response

        cwv = await pagespeed_client.get_core_web_vitals("https://example.com", strategy="desktop")

        # Test opportunities extraction
        opportunities = pagespeed_client.extract_opportunities(result)

        # Verify comprehensive analysis
        assert result["id"] == "https://example.com/"
        assert cwv["performance_score"] == 0.75
        assert cwv["largest_contentful_paint"]["numericValue"] == 3200
        assert len(opportunities) == 1
        assert opportunities[0]["id"] == "unused-css-rules"
