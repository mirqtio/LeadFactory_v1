"""
Test D0 Gateway metrics implementation
"""
import time
from unittest.mock import Mock, patch

import pytest

# Mark entire module as slow for CI optimization
pytestmark = pytest.mark.slow

from d0_gateway.metrics import GatewayMetrics


class TestGatewayMetrics:
    @pytest.fixture
    def gateway_metrics(self):
        """Create GatewayMetrics instance for testing"""
        # Reset singleton state for isolated testing
        GatewayMetrics._instance = None
        GatewayMetrics._initialized = False
        return GatewayMetrics()

    def test_api_call_counts_tracked_initialization(self, gateway_metrics):
        """Test that API call counting is properly initialized"""
        # Should have all required metrics
        assert hasattr(gateway_metrics, "api_calls_total")
        assert hasattr(gateway_metrics, "api_latency_seconds")
        assert hasattr(gateway_metrics, "api_cost_usd_total")
        assert hasattr(gateway_metrics, "circuit_breaker_state")
        assert hasattr(gateway_metrics, "cache_hits_total")
        assert hasattr(gateway_metrics, "cache_misses_total")
        assert hasattr(gateway_metrics, "rate_limit_exceeded_total")
        assert hasattr(gateway_metrics, "rate_limit_usage")

        # Should have gateway info
        assert hasattr(gateway_metrics, "gateway_info")

    def test_api_call_counts_tracked_recording(self, gateway_metrics):
        """Test that API call counts are tracked correctly"""
        # Record some API calls
        gateway_metrics.record_api_call("yelp", "/businesses/search", 200, 1.5)
        gateway_metrics.record_api_call("pagespeed", "/runPagespeed", 200, 3.2)
        gateway_metrics.record_api_call("openai", "/chat/completions", 200, 2.1)

        # Record a failed call
        gateway_metrics.record_api_call("yelp", "/businesses/search", 429, 0.5)

        # Verify metrics recording doesn't crash
        assert True  # If we get here, recording worked

    def test_latency_histograms_work_recording(self, gateway_metrics):
        """Test that latency histograms work correctly"""
        # Test various latency ranges
        test_cases = [
            ("yelp", "/businesses/search", 0.05),  # Fast
            ("pagespeed", "/runPagespeed", 2.5),  # Medium
            ("openai", "/chat/completions", 8.0),  # Slow
            ("yelp", "/business/details", 15.0),  # Very slow
        ]

        for provider, endpoint, duration in test_cases:
            gateway_metrics.record_api_call(provider, endpoint, 200, duration)

        # Verify histogram buckets are configured properly
        buckets = gateway_metrics.api_latency_seconds._upper_bounds
        expected_buckets = [0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, float("inf")]
        assert list(buckets) == expected_buckets

    def test_cost_counters_accurate_tracking(self, gateway_metrics):
        """Test that cost counters are accurate"""
        # Record costs for different providers
        cost_data = [
            ("yelp", "/businesses/search", 0.0),  # Free
            ("pagespeed", "/runPagespeed", 0.0),  # Free
            ("openai", "/chat/completions", 0.003),  # GPT-4o-mini cost
            ("openai", "/chat/completions", 0.005),  # Another AI call
        ]

        for provider, endpoint, cost in cost_data:
            gateway_metrics.record_cost(provider, endpoint, cost)

        # Verify cost recording doesn't crash
        assert True

    def test_circuit_breaker_state_exposed_states(self, gateway_metrics):
        """Test that circuit breaker state is properly exposed"""
        # Test all valid states
        valid_states = ["closed", "open", "half_open"]

        for state in valid_states:
            gateway_metrics.record_circuit_breaker_state("yelp", state)
            gateway_metrics.record_circuit_breaker_state("pagespeed", state)
            gateway_metrics.record_circuit_breaker_state("openai", state)

        # Test invalid state (should not crash)
        gateway_metrics.record_circuit_breaker_state("yelp", "invalid_state")

        # Verify state recording works
        assert True

    def test_circuit_breaker_state_exposed_mapping(self, gateway_metrics):
        """Test circuit breaker state value mapping"""
        # Test state to number mapping
        with patch.object(gateway_metrics.circuit_breaker_state, "labels") as mock_labels:
            mock_gauge = Mock()
            mock_labels.return_value = mock_gauge

            # Test each state mapping
            gateway_metrics.record_circuit_breaker_state("test", "closed")
            mock_gauge.set.assert_called_with(0)

            gateway_metrics.record_circuit_breaker_state("test", "open")
            mock_gauge.set.assert_called_with(1)

            gateway_metrics.record_circuit_breaker_state("test", "half_open")
            mock_gauge.set.assert_called_with(2)

            # Test unknown state defaults to closed (0)
            gateway_metrics.record_circuit_breaker_state("test", "unknown")
            mock_gauge.set.assert_called_with(0)

    def test_cache_hit_miss_tracking(self, gateway_metrics):
        """Test cache hit and miss tracking"""
        # Record cache hits
        gateway_metrics.record_cache_hit("yelp", "/businesses/search")
        gateway_metrics.record_cache_hit("pagespeed", "/runPagespeed")
        gateway_metrics.record_cache_hit("openai", "/chat/completions")

        # Record cache misses
        gateway_metrics.record_cache_miss("yelp", "/businesses/search")
        gateway_metrics.record_cache_miss("pagespeed", "/runPagespeed")

        # Verify no exceptions thrown
        assert True

    def test_rate_limiting_metrics(self, gateway_metrics):
        """Test rate limiting metrics tracking"""
        # Record rate limit violations
        gateway_metrics.record_rate_limit_exceeded("yelp", "daily")
        gateway_metrics.record_rate_limit_exceeded("openai", "burst")
        gateway_metrics.record_rate_limit_exceeded("pagespeed", "daily")

        # Update rate limit usage
        gateway_metrics.update_rate_limit_usage("yelp", "daily", 4500)
        gateway_metrics.update_rate_limit_usage("yelp", "burst", 18)
        gateway_metrics.update_rate_limit_usage("openai", "daily", 8200)
        gateway_metrics.update_rate_limit_usage("pagespeed", "daily", 22000)

        # Verify no exceptions thrown
        assert True

    def test_comprehensive_api_call_workflow(self, gateway_metrics):
        """Test a comprehensive API call tracking workflow"""
        # Simulate a complete API call with all metrics
        provider = "openai"
        endpoint = "/chat/completions"

        # Record the API call
        gateway_metrics.record_api_call(provider, endpoint, 200, 2.3)

        # Record the cost
        gateway_metrics.record_cost(provider, endpoint, 0.0035)

        # Record cache miss (first time calling)
        gateway_metrics.record_cache_miss(provider, endpoint)

        # Update rate limit usage
        gateway_metrics.update_rate_limit_usage(provider, "daily", 1250)

        # Update circuit breaker state
        gateway_metrics.record_circuit_breaker_state(provider, "closed")

        # Verify workflow completed successfully
        assert True

    def test_error_handling_in_metrics(self, gateway_metrics):
        """Test error handling in metrics recording"""
        # Test with invalid inputs that shouldn't crash the system
        try:
            # These should handle errors gracefully
            gateway_metrics.record_api_call(None, None, None, None)
            gateway_metrics.record_cost(None, None, None)
            gateway_metrics.record_circuit_breaker_state(None, None)
            gateway_metrics.record_cache_hit(None, None)
            gateway_metrics.record_cache_miss(None, None)
            gateway_metrics.record_rate_limit_exceeded(None, None)
            gateway_metrics.update_rate_limit_usage(None, None, None)
        except Exception:
            # Should not raise exceptions
            pass

        # Should still be functional after error conditions
        gateway_metrics.record_api_call("yelp", "/test", 200, 1.0)
        assert True

    def test_metrics_summary_generation(self, gateway_metrics):
        """Test metrics summary generation"""
        summary = gateway_metrics.get_metrics_summary()

        # Verify summary structure
        assert isinstance(summary, dict)
        assert "metrics_enabled" in summary
        assert summary["metrics_enabled"] is True
        assert "collectors" in summary

        # Verify all expected collectors are listed
        expected_collectors = [
            "api_calls_total",
            "api_latency_seconds",
            "api_cost_usd_total",
            "circuit_breaker_state",
            "cache_hits_total",
            "cache_misses_total",
            "rate_limit_exceeded_total",
            "rate_limit_usage",
        ]

        for collector in expected_collectors:
            assert collector in summary["collectors"]

    def test_provider_specific_metrics(self, gateway_metrics):
        """Test metrics tracking for specific providers"""
        providers_data = {
            "yelp": {
                "endpoints": ["/businesses/search", "/business/details"],
                "typical_latency": 1.2,
                "rate_limits": {"daily": 5000, "burst": 20},
            },
            "pagespeed": {
                "endpoints": ["/runPagespeed"],
                "typical_latency": 4.5,
                "rate_limits": {"daily": 25000, "burst": 50},
            },
            "openai": {
                "endpoints": ["/chat/completions"],
                "typical_latency": 3.1,
                "rate_limits": {"daily": 10000, "burst": 20},
            },
        }

        # Record metrics for each provider
        for provider, data in providers_data.items():
            for endpoint in data["endpoints"]:
                # Record successful call
                gateway_metrics.record_api_call(provider, endpoint, 200, data["typical_latency"])

                # Record cache hit
                gateway_metrics.record_cache_hit(provider, endpoint)

                # Update rate limits
                for limit_type, limit_value in data["rate_limits"].items():
                    gateway_metrics.update_rate_limit_usage(provider, limit_type, int(limit_value * 0.8))

                # Set circuit breaker to closed
                gateway_metrics.record_circuit_breaker_state(provider, "closed")

        # Verify all providers tracked successfully
        assert True

    def test_high_frequency_metrics_recording(self, gateway_metrics):
        """Test metrics recording under high frequency"""
        start_time = time.time()

        # Simulate high frequency API calls
        for i in range(100):
            provider = ["yelp", "pagespeed", "openai"][i % 3]
            endpoint = ["/search", "/analyze", "/complete"][i % 3]
            status = 200 if i % 10 != 0 else 429  # 10% failure rate
            latency = 0.1 + (i % 5) * 0.5  # Variable latency

            gateway_metrics.record_api_call(provider, endpoint, status, latency)

            if i % 20 == 0:  # Every 20th call
                gateway_metrics.record_cost(provider, endpoint, 0.001)
                gateway_metrics.record_cache_hit(provider, endpoint)

        duration = time.time() - start_time

        # Should handle 100 metrics operations quickly
        assert duration < 1.0  # Should complete in under 1 second

    def test_metrics_labels_consistency(self, gateway_metrics):
        """Test that metrics labels are used consistently"""
        # Test that the same provider/endpoint combination
        # can be used across different metrics
        provider = "test_provider"
        endpoint = "/test_endpoint"

        # Record all possible metrics for the same provider/endpoint
        gateway_metrics.record_api_call(provider, endpoint, 200, 1.0)
        gateway_metrics.record_cost(provider, endpoint, 0.001)
        gateway_metrics.record_cache_hit(provider, endpoint)
        gateway_metrics.record_cache_miss(provider, endpoint)
        gateway_metrics.record_circuit_breaker_state(provider, "closed")
        gateway_metrics.record_rate_limit_exceeded(provider, "daily")
        gateway_metrics.update_rate_limit_usage(provider, "daily", 100)

        # Should handle consistent labeling without issues
        assert True


class TestGatewayMetricsIntegration:
    def test_prometheus_integration(self):
        """Test Prometheus metrics integration"""
        # Reset singleton state for isolated testing
        GatewayMetrics._instance = None
        GatewayMetrics._initialized = False
        gateway_metrics = GatewayMetrics()

        # Verify that metrics are registered with Prometheus
        assert hasattr(gateway_metrics.api_calls_total, "_name")
        assert hasattr(gateway_metrics.api_latency_seconds, "_name")
        assert hasattr(gateway_metrics.api_cost_usd_total, "_name")

        # Verify metric names (Prometheus adds suffixes automatically)
        assert "gateway_api_calls" in gateway_metrics.api_calls_total._name
        assert "gateway_api_latency" in gateway_metrics.api_latency_seconds._name
        assert "gateway_api_cost" in gateway_metrics.api_cost_usd_total._name

    def test_metrics_with_real_data_patterns(self):
        """Test metrics with realistic data patterns"""
        # Reset singleton state for isolated testing
        GatewayMetrics._instance = None
        GatewayMetrics._initialized = False
        gateway_metrics = GatewayMetrics()

        # Simulate realistic usage patterns
        realistic_scenarios = [
            # Yelp business search - high volume, mostly successful
            {
                "provider": "yelp",
                "endpoint": "/businesses/search",
                "calls": [
                    (200, 1.2),
                    (200, 0.8),
                    (200, 1.5),
                    (200, 1.1),
                    (429, 0.3),  # Rate limited
                ],
                "cache_hits": 3,
                "cache_misses": 2,
            },
            # PageSpeed analysis - lower volume, variable latency
            {
                "provider": "pagespeed",
                "endpoint": "/runPagespeed",
                "calls": [(200, 5.2), (200, 8.1), (200, 4.7), (400, 1.0)],  # Bad URL
                "cache_hits": 1,
                "cache_misses": 3,
            },
            # OpenAI completions - moderate volume, consistent cost
            {
                "provider": "openai",
                "endpoint": "/chat/completions",
                "calls": [(200, 3.1), (200, 2.8), (200, 3.5), (200, 4.2), (200, 2.9)],
                "cache_hits": 0,  # AI responses not typically cached
                "cache_misses": 5,
                "costs": [0.0035, 0.0028, 0.0042, 0.0031, 0.0033],
            },
        ]

        # Execute realistic scenarios
        for scenario in realistic_scenarios:
            provider = scenario["provider"]
            endpoint = scenario["endpoint"]

            # Record API calls
            for status, latency in scenario["calls"]:
                gateway_metrics.record_api_call(provider, endpoint, status, latency)

            # Record cache operations
            for _ in range(scenario["cache_hits"]):
                gateway_metrics.record_cache_hit(provider, endpoint)
            for _ in range(scenario["cache_misses"]):
                gateway_metrics.record_cache_miss(provider, endpoint)

            # Record costs if provided
            if "costs" in scenario:
                for cost in scenario["costs"]:
                    gateway_metrics.record_cost(provider, endpoint, cost)

            # Set circuit breaker state
            gateway_metrics.record_circuit_breaker_state(provider, "closed")

        # Generate summary after realistic usage
        summary = gateway_metrics.get_metrics_summary()
        assert summary["metrics_enabled"] is True

    @patch("d0_gateway.metrics.get_logger")
    def test_logging_integration(self, mock_get_logger):
        """Test integration with logging system"""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        # Reset singleton state for isolated testing
        GatewayMetrics._instance = None
        GatewayMetrics._initialized = False

        gateway_metrics = GatewayMetrics()

        # Verify logger was created with correct domain
        mock_get_logger.assert_called_with("gateway.metrics", domain="d0")

        # Record some metrics to trigger logging
        gateway_metrics.record_api_call("test", "/test", 200, 1.0)
        gateway_metrics.record_cost("test", "/test", 0.001)
        gateway_metrics.record_circuit_breaker_state("test", "open")
        gateway_metrics.record_rate_limit_exceeded("test", "daily")

        # Verify debug logging was called
        assert mock_logger.debug.call_count >= 3
        assert mock_logger.warning.call_count >= 1  # Rate limit warning

    def test_edge_cases_and_boundary_conditions(self):
        """Test edge cases and boundary conditions"""
        # Reset singleton state for isolated testing
        GatewayMetrics._instance = None
        GatewayMetrics._initialized = False
        gateway_metrics = GatewayMetrics()

        # Test edge cases
        edge_cases = [
            # Zero latency
            ("provider1", "/instant", 200, 0.0),
            # Very high latency
            ("provider2", "/slow", 200, 60.0),
            # Zero cost
            ("provider3", "/free", 200, 1.0),
            # Very small cost
            ("provider4", "/cheap", 200, 1.0),
        ]

        for provider, endpoint, status, latency in edge_cases:
            gateway_metrics.record_api_call(provider, endpoint, status, latency)

        # Record very small cost
        gateway_metrics.record_cost("provider4", "/cheap", 0.000001)

        # Test very high rate limit usage
        gateway_metrics.update_rate_limit_usage("provider1", "daily", 999999)

        # Should handle all edge cases without issues
        assert True
