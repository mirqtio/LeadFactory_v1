"""
Test D0 Gateway metrics and monitoring
"""
import pytest
from unittest.mock import Mock, patch

from d0_gateway.metrics import GatewayMetrics


class TestGatewayMetrics:

    @pytest.fixture
    def gateway_metrics(self):
        """Create gateway metrics instance for testing"""
        return GatewayMetrics()

    def test_api_call_counts_tracked_initialization(self, gateway_metrics):
        """Test that API call counts are tracked and properly initialized"""
        # Should have API call counter
        assert hasattr(gateway_metrics, 'api_calls_total')
        # Prometheus client may modify metric names
        assert 'gateway_api_calls' in gateway_metrics.api_calls_total._name

        # Should have proper labels
        expected_labels = ['provider', 'endpoint', 'status_code']
        assert gateway_metrics.api_calls_total._labelnames == tuple(expected_labels)

        # Should have latency histogram
        assert hasattr(gateway_metrics, 'api_latency_seconds')
        assert 'gateway_api_latency' in gateway_metrics.api_latency_seconds._name

    def test_latency_histograms_work_configuration(self, gateway_metrics):
        """Test that latency histograms are properly configured"""
        # Should have latency histogram with proper buckets
        latency_metric = gateway_metrics.api_latency_seconds

        # Check bucket configuration
        expected_buckets = [0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
        # Prometheus adds +Inf bucket automatically
        actual_buckets = list(latency_metric._upper_bounds[:-1])
        assert actual_buckets == expected_buckets

        # Should have proper labels for latency
        expected_labels = ['provider', 'endpoint']
        assert latency_metric._labelnames == tuple(expected_labels)

    def test_cost_counters_accurate_initialization(self, gateway_metrics):
        """Test that cost counters are accurate and properly initialized"""
        # Should have cost counter
        assert hasattr(gateway_metrics, 'api_cost_usd_total')
        assert 'gateway_api_cost' in gateway_metrics.api_cost_usd_total._name

        # Should have proper labels for cost tracking
        expected_labels = ['provider', 'endpoint']
        assert gateway_metrics.api_cost_usd_total._labelnames == tuple(expected_labels)

    def test_circuit_breaker_state_exposed_initialization(self, gateway_metrics):
        """Test that circuit breaker state is exposed"""
        # Should have circuit breaker gauge
        assert hasattr(gateway_metrics, 'circuit_breaker_state')
        assert 'gateway_circuit_breaker' in gateway_metrics.circuit_breaker_state._name

        # Should have provider label
        expected_labels = ['provider']
        assert gateway_metrics.circuit_breaker_state._labelnames == tuple(expected_labels)

    def test_api_call_recording(self, gateway_metrics):
        """Test API call recording functionality"""
        # Mock the counter to verify calls
        with patch.object(gateway_metrics.api_calls_total, 'labels') as mock_labels:
            mock_counter = Mock()
            mock_labels.return_value = mock_counter

            # Record an API call
            gateway_metrics.record_api_call(
                provider="test_provider",
                endpoint="/test/endpoint",
                status_code=200,
                duration=1.5
            )

            # Verify counter was called correctly
            mock_labels.assert_called_once_with(
                provider="test_provider",
                endpoint="/test/endpoint",
                status_code="200"
            )
            mock_counter.inc.assert_called_once()

    def test_latency_recording(self, gateway_metrics):
        """Test latency histogram recording"""
        # Mock the histogram to verify calls
        with patch.object(gateway_metrics.api_latency_seconds, 'labels') as mock_labels:
            mock_histogram = Mock()
            mock_labels.return_value = mock_histogram

            # Record an API call with latency
            gateway_metrics.record_api_call(
                provider="test_provider",
                endpoint="/test/endpoint",
                status_code=200,
                duration=2.5
            )

            # Verify histogram was called correctly
            mock_labels.assert_called_once_with(
                provider="test_provider",
                endpoint="/test/endpoint"
            )
            mock_histogram.observe.assert_called_once_with(2.5)

    def test_cost_recording_accurate(self, gateway_metrics):
        """Test that cost recording is accurate"""
        # Mock the counter to verify calls
        with patch.object(gateway_metrics.api_cost_usd_total, 'labels') as mock_labels:
            mock_counter = Mock()
            mock_labels.return_value = mock_counter

            # Record API cost
            test_cost = 0.00045
            gateway_metrics.record_cost(
                provider="openai",
                endpoint="/v1/chat/completions",
                cost_usd=test_cost
            )

            # Verify cost was recorded accurately
            mock_labels.assert_called_once_with(
                provider="openai",
                endpoint="/v1/chat/completions"
            )
            mock_counter.inc.assert_called_once_with(test_cost)

    def test_circuit_breaker_state_exposed_recording(self, gateway_metrics):
        """Test circuit breaker state recording and exposure"""
        # Mock the gauge to verify calls
        with patch.object(gateway_metrics.circuit_breaker_state, 'labels') as mock_labels:
            mock_gauge = Mock()
            mock_labels.return_value = mock_gauge

            # Test all circuit breaker states
            test_cases = [
                ('closed', 0),
                ('open', 1),
                ('half_open', 2)
            ]

            for state_name, expected_value in test_cases:
                gateway_metrics.record_circuit_breaker_state("test_provider", state_name)

                # Verify gauge was set correctly
                mock_labels.assert_called_with(provider="test_provider")
                mock_gauge.set.assert_called_with(expected_value)

    def test_cache_metrics_recording(self, gateway_metrics):
        """Test cache hit/miss metrics recording"""
        # Test cache hit recording
        with patch.object(gateway_metrics.cache_hits_total, 'labels') as mock_labels:
            mock_counter = Mock()
            mock_labels.return_value = mock_counter

            gateway_metrics.record_cache_hit("pagespeed", "/runPagespeed")

            mock_labels.assert_called_once_with(
                provider="pagespeed",
                endpoint="/runPagespeed"
            )
            mock_counter.inc.assert_called_once()

        # Test cache miss recording
        with patch.object(gateway_metrics.cache_misses_total, 'labels') as mock_labels:
            mock_counter = Mock()
            mock_labels.return_value = mock_counter

            gateway_metrics.record_cache_miss("pagespeed", "/runPagespeed")

            mock_labels.assert_called_once_with(
                provider="pagespeed",
                endpoint="/runPagespeed"
            )
            mock_counter.inc.assert_called_once()

    def test_rate_limit_metrics_recording(self, gateway_metrics):
        """Test rate limiting metrics recording"""
        # Test rate limit exceeded recording
        with patch.object(gateway_metrics.rate_limit_exceeded_total, 'labels') as mock_labels:
            mock_counter = Mock()
            mock_labels.return_value = mock_counter

            gateway_metrics.record_rate_limit_exceeded("openai", "daily")

            mock_labels.assert_called_once_with(
                provider="openai",
                limit_type="daily"
            )
            mock_counter.inc.assert_called_once()

        # Test rate limit usage update
        with patch.object(gateway_metrics.rate_limit_usage, 'labels') as mock_labels:
            mock_gauge = Mock()
            mock_labels.return_value = mock_gauge

            gateway_metrics.update_rate_limit_usage("openai", "daily", 150)

            mock_labels.assert_called_once_with(
                provider="openai",
                limit_type="daily"
            )
            mock_gauge.set.assert_called_once_with(150)

    def test_metrics_summary(self, gateway_metrics):
        """Test metrics summary functionality"""
        summary = gateway_metrics.get_metrics_summary()

        # Should return summary with expected structure
        assert isinstance(summary, dict)
        assert summary['metrics_enabled'] is True
        assert 'collectors' in summary

        # Should include all expected metric names
        expected_metrics = [
            'api_calls_total',
            'api_latency_seconds',
            'api_cost_usd_total',
            'circuit_breaker_state',
            'cache_hits_total',
            'cache_misses_total',
            'rate_limit_exceeded_total',
            'rate_limit_usage'
        ]

        for metric in expected_metrics:
            assert metric in summary['collectors']

    def test_gateway_info_initialization(self, gateway_metrics):
        """Test gateway info metric initialization"""
        # Should have gateway info metric
        assert hasattr(gateway_metrics, 'gateway_info')
        assert 'gateway_info' in gateway_metrics.gateway_info._name

    def test_error_handling_in_metrics(self, gateway_metrics):
        """Test error handling in metrics recording"""
        # Mock a metric to raise an exception
        with patch.object(gateway_metrics.api_calls_total, 'labels', side_effect=Exception("Metric error")):
            # Should not raise exception, but handle gracefully
            try:
                gateway_metrics.record_api_call("test", "/test", 200, 1.0)
                # If we get here, error was handled gracefully
                assert True
            except Exception:
                pytest.fail("Metrics recording should handle errors gracefully")

    def test_comprehensive_api_call_flow(self, gateway_metrics):
        """Test comprehensive API call recording flow"""
        # Mock all relevant metrics
        with patch.object(gateway_metrics.api_calls_total, 'labels') as mock_calls, \
             patch.object(gateway_metrics.api_latency_seconds, 'labels') as mock_latency, \
             patch.object(gateway_metrics.api_cost_usd_total, 'labels') as mock_cost:

            mock_call_counter = Mock()
            mock_latency_histogram = Mock()
            mock_cost_counter = Mock()

            mock_calls.return_value = mock_call_counter
            mock_latency.return_value = mock_latency_histogram
            mock_cost.return_value = mock_cost_counter

            # Simulate a complete API call flow
            provider = "openai"
            endpoint = "/v1/chat/completions"
            status_code = 200
            duration = 1.25
            cost = 0.00035

            # Record API call
            gateway_metrics.record_api_call(provider, endpoint, status_code, duration)

            # Record cost separately
            gateway_metrics.record_cost(provider, endpoint, cost)

            # Verify all metrics were recorded
            mock_calls.assert_called_once_with(
                provider=provider,
                endpoint=endpoint,
                status_code="200"
            )
            mock_call_counter.inc.assert_called_once()

            mock_latency.assert_called_once_with(
                provider=provider,
                endpoint=endpoint
            )
            mock_latency_histogram.observe.assert_called_once_with(duration)

            mock_cost.assert_called_once_with(
                provider=provider,
                endpoint=endpoint
            )
            mock_cost_counter.inc.assert_called_once_with(cost)


class TestGatewayMetricsIntegration:

    def test_prometheus_integration(self):
        """Test integration with Prometheus client"""
        # Create metrics instance
        metrics = GatewayMetrics()

        # Verify metrics are accessible via the instance
        expected_attributes = [
            'api_calls_total',
            'api_latency_seconds', 
            'api_cost_usd_total',
            'circuit_breaker_state'
        ]

        for attr in expected_attributes:
            assert hasattr(metrics, attr), f"Metrics instance missing attribute: {attr}"
            metric_obj = getattr(metrics, attr)
            assert hasattr(metric_obj, '_name'), f"Metric {attr} missing _name attribute"

        # Test that metrics work by recording some data
        metrics.record_api_call('test', '/test', 200, 1.0)
        metrics.record_cache_hit('test', '/test')
        metrics.record_cost('test', '/test', 0.01)

        # Verify metrics have recorded data (just basic functionality test)
        # For counters, we can use collect() method to get current value
        api_calls_samples = list(metrics.api_calls_total.collect()[0].samples)
        cache_hits_samples = list(metrics.cache_hits_total.collect()[0].samples)
        cost_samples = list(metrics.api_cost_usd_total.collect()[0].samples)
        
        assert len(api_calls_samples) > 0, "API calls counter should have samples"
        assert len(cache_hits_samples) > 0, "Cache hits counter should have samples"
        assert len(cost_samples) > 0, "Cost counter should have samples"

    def test_metrics_labels_consistency(self):
        """Test that metric labels are consistent across related metrics"""
        metrics = GatewayMetrics()

        # API metrics should have consistent labeling
        api_call_labels = metrics.api_calls_total._labelnames
        api_latency_labels = metrics.api_latency_seconds._labelnames

        # Both should include provider and endpoint
        assert 'provider' in api_call_labels
        assert 'endpoint' in api_call_labels
        assert 'provider' in api_latency_labels
        assert 'endpoint' in api_latency_labels

        # Cost and latency should have same labels (provider, endpoint)
        api_cost_labels = metrics.api_cost_usd_total._labelnames
        assert set(api_cost_labels) == set(api_latency_labels)

    def test_concurrent_metrics_recording(self):
        """Test concurrent metrics recording"""
        import threading
        import time

        metrics = GatewayMetrics()
        results = []

        def record_metrics(thread_id):
            try:
                for i in range(10):
                    metrics.record_api_call(
                        f"provider_{thread_id}",
                        f"/endpoint_{i}",
                        200,
                        0.1 * i
                    )
                    metrics.record_cost(f"provider_{thread_id}", f"/endpoint_{i}", 0.001)
                results.append(True)
            except Exception as e:
                results.append(f"Thread {thread_id} failed: {e}")

        # Start multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=record_metrics, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # All threads should complete successfully
        assert all(result is True for result in results), f"Concurrent recording failed: {results}"
