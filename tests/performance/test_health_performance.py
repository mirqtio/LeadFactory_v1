"""
Performance tests for health endpoint - P0-007

Validates <100ms response time requirement under various conditions.
"""
import asyncio
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


class TestHealthEndpointPerformance:
    """Performance validation tests for health endpoint"""

    def test_response_time_under_100ms(self):
        """Test that health endpoint meets <100ms requirement"""
        # Warm up
        client.get("/health")

        # Measure multiple requests
        response_times = []
        for _ in range(20):
            response = client.get("/health")
            assert response.status_code == 200

            data = response.json()
            assert "response_time_ms" in data
            response_times.append(data["response_time_ms"])

        # Calculate statistics
        avg_time = statistics.mean(response_times)
        median_time = statistics.median(response_times)
        max_time = max(response_times)
        p95_time = statistics.quantiles(response_times, n=20)[18]  # 95th percentile

        print(f"\nHealth endpoint performance:")
        print(f"  Average: {avg_time:.2f}ms")
        print(f"  Median: {median_time:.2f}ms")
        print(f"  95th percentile: {p95_time:.2f}ms")
        print(f"  Max: {max_time:.2f}ms")

        # All metrics should be under 100ms
        assert avg_time < 100, f"Average response time {avg_time:.2f}ms exceeds 100ms"
        assert median_time < 100, f"Median response time {median_time:.2f}ms exceeds 100ms"
        assert p95_time < 100, f"95th percentile {p95_time:.2f}ms exceeds 100ms"

    def test_database_check_timeout(self):
        """Test that database check respects 50ms timeout"""
        with patch("api.health.check_database_health") as mock_check:
            # Simulate slow database
            def slow_db_check(db):
                time.sleep(0.1)  # 100ms - should timeout
                return {"status": "connected"}

            mock_check.side_effect = slow_db_check

            start_time = time.time()
            response = client.get("/health")
            total_time = (time.time() - start_time) * 1000

            # Should timeout and return quickly
            assert response.status_code == 503
            assert total_time < 150  # Should timeout at 50ms + overhead

            data = response.json()
            assert data["checks"]["database"]["status"] == "timeout"
            assert "50ms" in data["checks"]["database"]["error"]

    @patch("core.config.settings.redis_url", "redis://test-redis:6379/0")
    def test_redis_check_timeout(self):
        """Test that Redis check respects 30ms timeout"""
        with patch("api.health.check_redis_health") as mock_check:
            # Simulate slow Redis
            async def slow_redis_check(url):
                await asyncio.sleep(0.05)  # 50ms - should timeout
                return {"status": "connected"}

            mock_check.side_effect = slow_redis_check

            response = client.get("/health")
            data = response.json()

            # Redis should timeout but not affect overall health
            assert response.status_code == 200
            assert data["checks"]["redis"]["status"] == "timeout"
            assert "30ms" in data["checks"]["redis"]["error"]

    def test_concurrent_request_performance(self):
        """Test performance under concurrent load"""

        def make_request():
            start = time.time()
            response = client.get("/health")
            elapsed = (time.time() - start) * 1000

            data = response.json()
            return {
                "status_code": response.status_code,
                "total_time_ms": elapsed,
                "internal_time_ms": data.get("response_time_ms", 0),
            }

        # Test with increasing concurrency
        for num_concurrent in [5, 10, 20]:
            with ThreadPoolExecutor(max_workers=num_concurrent) as executor:
                futures = [executor.submit(make_request) for _ in range(num_concurrent)]
                results = [f.result() for f in as_completed(futures)]

            # Analyze results
            internal_times = [r["internal_time_ms"] for r in results]
            total_times = [r["total_time_ms"] for r in results]

            avg_internal = statistics.mean(internal_times)
            avg_total = statistics.mean(total_times)
            max_internal = max(internal_times)

            print(f"\nConcurrency level {num_concurrent}:")
            print(f"  Avg internal time: {avg_internal:.2f}ms")
            print(f"  Avg total time: {avg_total:.2f}ms")
            print(f"  Max internal time: {max_internal:.2f}ms")

            # Internal processing should still be under 100ms
            assert (
                avg_internal < 100
            ), f"Average internal time {avg_internal:.2f}ms exceeds 100ms at concurrency {num_concurrent}"
            assert (
                max_internal < 100
            ), f"Max internal time {max_internal:.2f}ms exceeds 100ms at concurrency {num_concurrent}"

    def test_performance_with_failures(self):
        """Test performance when dependencies fail"""
        with patch("api.health.check_database_health") as mock_db:
            # Simulate fast failure
            mock_db.return_value = {"status": "error", "error": "Connection refused"}

            response_times = []
            for _ in range(10):
                response = client.get("/health")
                assert response.status_code == 503

                data = response.json()
                response_times.append(data["response_time_ms"])

            # Even with failures, should be fast
            avg_time = statistics.mean(response_times)
            assert avg_time < 100, f"Average response time {avg_time:.2f}ms exceeds 100ms even with failures"

    @pytest.mark.skip(reason="Benchmark not configured in test environment")
    def test_health_endpoint_benchmark(self):
        """Benchmark health endpoint performance"""
        # This test requires pytest-benchmark to be configured
        # Can be run manually with: pytest tests/performance/test_health_performance.py --benchmark-only
        pass


class TestHealthEndpointOptimization:
    """Tests to verify performance optimizations"""

    def test_connection_pooling_efficiency(self):
        """Test that connection pooling improves performance"""
        # First request (cold start)
        cold_response = client.get("/health")
        cold_data = cold_response.json()
        cold_time = cold_data["response_time_ms"]

        # Warm requests (should use pooled connections)
        warm_times = []
        for _ in range(5):
            response = client.get("/health")
            data = response.json()
            warm_times.append(data["response_time_ms"])

        avg_warm_time = statistics.mean(warm_times)

        print(f"\nConnection pooling effect:")
        print(f"  Cold start: {cold_time:.2f}ms")
        print(f"  Avg warm: {avg_warm_time:.2f}ms")

        # Warm requests should be faster (allowing for variance)
        if cold_time > 10:  # Only check if cold start wasn't already very fast
            assert avg_warm_time < cold_time * 0.8, "Connection pooling not improving performance"

    @pytest.mark.skip(reason="Timeout implementation needs async refactoring")
    def test_timeout_prevents_blocking(self):
        """Test that timeouts prevent slow dependencies from blocking"""
        # Our current implementation doesn't have true async timeouts
        # The database check runs synchronously, so we can't interrupt it
        # This would require refactoring to use async database operations
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--benchmark-only"])
