"""
Integration tests for health endpoint - P0-007

Tests health endpoint with real database and Redis connections.
"""
import asyncio
import time
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from core.config import get_settings
from main import app

client = TestClient(app)
settings = get_settings()


@pytest.mark.integration
class TestHealthEndpointIntegration:
    """Integration tests for health endpoint with real dependencies"""
    
    def test_health_with_real_database(self):
        """Test health endpoint with actual database connection"""
        response = client.get("/health")
        
        # Should get a response regardless of database state
        assert response.status_code in [200, 503]
        data = response.json()
        
        assert "status" in data
        assert "checks" in data
        assert "database" in data["checks"]
        
        # If database is connected, verify the response
        if response.status_code == 200:
            assert data["checks"]["database"]["status"] == "connected"
            assert "latency_ms" in data["checks"]["database"]
            assert data["checks"]["database"]["latency_ms"] >= 0
    
    @pytest.mark.skipif(
        settings.redis_url == "redis://localhost:6379/0",
        reason="Redis not configured"
    )
    def test_health_with_real_redis(self):
        """Test health endpoint with actual Redis connection"""
        response = client.get("/health")
        data = response.json()
        
        # Redis check should be present if configured
        if "redis" in data["checks"]:
            redis_status = data["checks"]["redis"]["status"]
            assert redis_status in ["connected", "error", "timeout"]
            
            if redis_status == "connected":
                assert "latency_ms" in data["checks"]["redis"]
                assert data["checks"]["redis"]["latency_ms"] >= 0
    
    def test_health_performance_with_real_dependencies(self):
        """Test health endpoint performance with real connections"""
        # Warm up connections
        client.get("/health")
        
        # Measure performance
        times = []
        for _ in range(5):
            start_time = time.time()
            response = client.get("/health")
            elapsed_ms = (time.time() - start_time) * 1000
            
            assert response.status_code in [200, 503]
            times.append(elapsed_ms)
            
            # Check reported response time
            data = response.json()
            assert "response_time_ms" in data
            
            # The internal response time should be under 100ms
            if response.status_code == 200:
                assert data["response_time_ms"] < 100
        
        # Average request time should be reasonable
        avg_time = sum(times) / len(times)
        assert avg_time < 200, f"Average request time {avg_time:.2f}ms"
    
    def test_detailed_health_with_real_dependencies(self):
        """Test detailed health endpoint with real connections"""
        response = client.get("/health/detailed")
        
        assert response.status_code in [200, 503]
        data = response.json()
        
        # Should have all the basic health data
        assert "status" in data
        assert "checks" in data
        assert "response_time_ms" in data
        
        # Should have system information
        assert "system" in data
        system = data["system"]
        
        # Verify system info matches settings
        assert system["use_stubs"] == settings.use_stubs
        assert system["features"]["emails"] == settings.enable_emails
        assert system["features"]["enrichment"] == settings.enable_enrichment
        assert system["limits"]["max_daily_emails"] == settings.max_daily_emails
    
    def test_health_database_reconnection(self):
        """Test health endpoint handles database reconnection"""
        # First request establishes connection
        response1 = client.get("/health")
        data1 = response1.json()
        
        # Make multiple requests to test connection pooling
        for _ in range(3):
            response = client.get("/health")
            data = response.json()
            
            # Status should be consistent
            assert response.status_code == response1.status_code
            
            # Database status should remain consistent
            if "database" in data["checks"]:
                assert data["checks"]["database"]["status"] == data1["checks"]["database"]["status"]
    
    @pytest.mark.asyncio
    async def test_health_concurrent_with_real_dependencies(self):
        """Test concurrent health checks with real dependencies"""
        async def make_async_request():
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, client.get, "/health")
        
        # Make 5 concurrent requests
        tasks = [make_async_request() for _ in range(5)]
        responses = await asyncio.gather(*tasks)
        
        # All should complete successfully
        assert all(r.status_code in [200, 503] for r in responses)
        
        # Check response times
        for response in responses:
            data = response.json()
            assert "response_time_ms" in data
            
            # Internal processing should be fast even with real dependencies
            if response.status_code == 200:
                assert data["response_time_ms"] < 100


@pytest.mark.integration
class TestHealthEndpointDatabaseScenarios:
    """Test various database scenarios"""
    
    def test_health_with_database_query_timeout(self):
        """Test health endpoint handles slow database queries"""
        with patch('api.health.check_database_health') as mock_check:
            # Simulate slow database query
            def slow_check(db):
                time.sleep(0.1)  # 100ms delay
                return {"status": "connected", "latency_ms": 100}
            
            mock_check.side_effect = slow_check
            
            response = client.get("/health")
            
            # Should timeout and return unhealthy
            assert response.status_code == 503
            data = response.json()
            assert data["checks"]["database"]["status"] == "timeout"
    
    def test_health_with_invalid_database_url(self):
        """Test health endpoint with invalid database configuration"""
        with patch('core.config.settings.database_url', 'postgresql://invalid:5432/db'):
            # The health check should handle this gracefully
            response = client.get("/health")
            
            # Should return 503 if database is misconfigured
            if response.status_code == 503:
                data = response.json()
                assert data["status"] == "unhealthy"
                assert "database" in data["checks"]
                assert data["checks"]["database"]["status"] in ["error", "timeout"]


@pytest.mark.integration
@pytest.mark.slow
class TestHealthEndpointStressTest:
    """Stress tests for health endpoint"""
    
    def test_health_under_sustained_load(self):
        """Test health endpoint under sustained load"""
        duration_seconds = 5
        start_time = time.time()
        request_count = 0
        response_times = []
        
        while time.time() - start_time < duration_seconds:
            req_start = time.time()
            response = client.get("/health")
            req_time = (time.time() - req_start) * 1000
            
            assert response.status_code in [200, 503]
            response_times.append(req_time)
            request_count += 1
            
            # Don't overwhelm the server
            time.sleep(0.01)  # 10ms between requests
        
        # Calculate statistics
        avg_response_time = sum(response_times) / len(response_times)
        max_response_time = max(response_times)
        requests_per_second = request_count / duration_seconds
        
        print(f"Stress test results:")
        print(f"  Total requests: {request_count}")
        print(f"  Requests/second: {requests_per_second:.2f}")
        print(f"  Avg response time: {avg_response_time:.2f}ms")
        print(f"  Max response time: {max_response_time:.2f}ms")
        
        # Performance assertions
        assert avg_response_time < 150, f"Average response time too high: {avg_response_time:.2f}ms"
        assert max_response_time < 500, f"Max response time too high: {max_response_time:.2f}ms"
        assert requests_per_second > 10, f"Throughput too low: {requests_per_second:.2f} req/s"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])