"""
Test core metrics functionality
"""
import asyncio

import pytest

from core.metrics import (
    CONTENT_TYPE_LATEST,
    get_metrics_response,
    metrics,
    track_api_call,
    track_funnel_step,
    track_time,
)


class TestMetricsCollector:
    def test_track_request(self):
        """Test tracking HTTP requests"""
        metrics.track_request("GET", "/api/test", 200, 0.5)

        # Verify metrics were recorded
        metrics_data, content_type = get_metrics_response()
        assert content_type == CONTENT_TYPE_LATEST
        assert b"leadfactory_http_requests_total" in metrics_data
        assert b"leadfactory_http_request_duration_seconds" in metrics_data

    def test_track_business_processed(self):
        """Test tracking business processing"""
        metrics.track_business_processed("yelp", "success")
        metrics.track_business_processed("yelp", "failed")

        metrics_data, _ = get_metrics_response()
        assert b"leadfactory_businesses_processed_total" in metrics_data
        assert b'source="yelp"' in metrics_data
        assert b'status="success"' in metrics_data
        assert b'status="failed"' in metrics_data

    def test_track_assessment_created(self):
        """Test tracking assessment creation"""
        metrics.track_assessment_created("pagespeed", 2.5, "success")

        metrics_data, _ = get_metrics_response()
        assert b"leadfactory_assessments_created_total" in metrics_data
        assert b"leadfactory_assessment_duration_seconds" in metrics_data
        assert b'assessment_type="pagespeed"' in metrics_data

    def test_track_email_sent(self):
        """Test tracking email sending"""
        metrics.track_email_sent("campaign_1", "success")
        metrics.track_email_sent("campaign_1", "bounced")

        metrics_data, _ = get_metrics_response()
        assert b"leadfactory_emails_sent_total" in metrics_data
        assert b'campaign="campaign_1"' in metrics_data

    def test_track_purchase(self):
        """Test tracking purchases"""
        metrics.track_purchase("website_report", 199.00, "price_test")

        metrics_data, _ = get_metrics_response()
        assert b"leadfactory_purchases_completed_total" in metrics_data
        assert b"leadfactory_revenue_usd_total" in metrics_data
        assert b'product_type="website_report"' in metrics_data
        assert b'experiment="price_test"' in metrics_data

    def test_track_error(self):
        """Test tracking errors"""
        metrics.track_error("api_timeout", "d0_gateway")

        metrics_data, _ = get_metrics_response()
        assert b"leadfactory_errors_total" in metrics_data
        assert b'error_type="api_timeout"' in metrics_data
        assert b'domain="d0_gateway"' in metrics_data

    def test_update_gauges(self):
        """Test updating gauge metrics"""
        metrics.update_active_campaigns(5)
        metrics.update_quota_usage("yelp", 1500)
        metrics.update_conversion_rate(0.025, "subject_line_test", "variant_a")

        metrics_data, _ = get_metrics_response()
        assert b"leadfactory_active_campaigns 5" in metrics_data
        assert b'leadfactory_daily_quota_usage{provider="yelp"} 1500' in metrics_data
        assert b"leadfactory_conversion_rate" in metrics_data

    def test_track_database_metrics(self):
        """Test tracking database metrics"""
        metrics.track_database_query("select", "businesses", 0.025)
        metrics.update_db_connections(10)

        metrics_data, _ = get_metrics_response()
        assert b"leadfactory_database_query_duration_seconds" in metrics_data
        assert b"leadfactory_database_connections_active 10" in metrics_data

    def test_track_cache_metrics(self):
        """Test tracking cache metrics"""
        metrics.track_cache_hit("redis")
        metrics.track_cache_hit("redis")
        metrics.track_cache_miss("redis")

        metrics_data, _ = get_metrics_response()
        assert b"leadfactory_cache_hits_total" in metrics_data
        assert b"leadfactory_cache_misses_total" in metrics_data


class TestMetricsDecorators:
    @pytest.mark.asyncio
    async def test_track_time_async_decorator(self):
        """Test async function time tracking decorator"""

        @track_time("test_operation")
        async def slow_async_function():
            await asyncio.sleep(0.1)
            return "done"

        result = await slow_async_function()
        assert result == "done"

        # Check that time was tracked
        metrics_data, _ = get_metrics_response()
        assert b"leadfactory_assessment_duration_seconds" in metrics_data
        assert b'assessment_type="test_operation"' in metrics_data

    def test_track_time_sync_decorator(self):
        """Test sync function time tracking decorator"""

        @track_time("sync_operation")
        def slow_sync_function():
            import time

            time.sleep(0.1)
            return "done"

        result = slow_sync_function()
        assert result == "done"

        # Check that time was tracked
        metrics_data, _ = get_metrics_response()
        assert b"leadfactory_assessment_duration_seconds" in metrics_data
        assert b'assessment_type="sync_operation"' in metrics_data


class TestHelperFunctions:
    def test_track_funnel_step(self):
        """Test funnel step tracking helper"""
        track_funnel_step("targeting", success=True)
        track_funnel_step("enrichment", success=False)

        metrics_data, _ = get_metrics_response()
        assert b"leadfactory_businesses_processed_total" in metrics_data
        assert b'source="targeting"' in metrics_data
        assert b'status="success"' in metrics_data
        assert b'source="enrichment"' in metrics_data
        assert b'status="dropped"' in metrics_data

    def test_track_api_call(self):
        """Test API call tracking helper"""
        track_api_call("yelp", "search", success=True)
        track_api_call("pagespeed", "analyze", success=False)

        metrics_data, _ = get_metrics_response()
        assert b"leadfactory_http_requests_total" in metrics_data
        assert b'endpoint="yelp:search"' in metrics_data
        assert b'status="success"' in metrics_data
        assert b'endpoint="pagespeed:analyze"' in metrics_data
        assert b'status="failed"' in metrics_data


class TestMetricsIntegration:
    def test_metrics_response_format(self):
        """Test that metrics response is in Prometheus format"""
        # Add some metrics
        metrics.track_request("GET", "/health", 200, 0.01)
        metrics.track_business_processed("yelp", "success")

        metrics_data, content_type = get_metrics_response()

        # Check content type
        assert content_type == "text/plain; version=0.0.4; charset=utf-8"

        # Check format
        assert isinstance(metrics_data, bytes)
        metrics_text = metrics_data.decode("utf-8")

        # Should contain HELP and TYPE lines
        assert "# HELP" in metrics_text
        assert "# TYPE" in metrics_text

        # Should contain metric values
        assert "leadfactory_http_requests_total" in metrics_text
        assert "leadfactory_businesses_processed_total" in metrics_text

    def test_app_info_metric(self):
        """Test application info metric"""
        metrics_data, _ = get_metrics_response()
        metrics_text = metrics_data.decode("utf-8")

        assert 'leadfactory_app_info{environment="production",version="1.0.0"} 1' in metrics_text
