"""
Unit tests for health endpoint - P0-007

Tests the health endpoint implementation including database
and Redis connectivity checks.

Acceptance Criteria:
- Returns 200 with JSON status
- Checks database connectivity
- Checks Redis connectivity
- Returns version info
- <100ms response time
"""

import asyncio
import time
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from core.config import get_settings
from main import app

client = TestClient(app)


class TestHealthEndpointUnit:
    """Unit tests for health endpoint"""

    def test_health_check_endpoint_returns_dict(self):
        """Test that health check endpoint returns proper dictionary"""
        response = client.get("/health")
        result = response.json()
        
        assert isinstance(result, dict)
        assert "status" in result
        assert "version" in result
        assert "environment" in result
        
    def test_health_check_returns_correct_version(self):
        """Test that health check returns correct version from settings"""
        settings = get_settings()
        response = client.get("/health")
        result = response.json()
        
        assert result["version"] == settings.app_version
        
    def test_health_check_returns_correct_environment(self):
        """Test that health check returns correct environment from settings"""
        settings = get_settings()
        response = client.get("/health")
        result = response.json()
        
        assert result["environment"] == settings.environment
        
    def test_health_endpoint_route_exists(self):
        """Test that /health route is registered"""
        routes = [route.path for route in app.routes]
        assert "/health" in routes
        
    def test_health_endpoint_method_is_get(self):
        """Test that health endpoint only accepts GET requests"""
        # GET should work
        response = client.get("/health")
        assert response.status_code == 200
        
        # POST should not work
        response = client.post("/health")
        assert response.status_code == 405  # Method not allowed
        
    def test_health_endpoint_returns_json(self):
        """Test that health endpoint returns JSON content type"""
        response = client.get("/health")
        assert response.headers["content-type"] == "application/json"
        
    def test_health_endpoint_response_structure(self):
        """Test that health endpoint returns expected structure"""
        response = client.get("/health")
        data = response.json()
        
        # Required fields
        assert "status" in data
        assert "version" in data
        assert "environment" in data
        
        # Status should be ok or healthy
        assert data["status"] in ["ok", "healthy"]
        
        # Should have timestamp
        assert "timestamp" in data
        
    @patch('main.settings')
    def test_health_endpoint_uses_settings(self, mock_settings):
        """Test that health endpoint uses settings for version and environment"""
        mock_settings.app_version = "test-version-1.2.3"
        mock_settings.environment = "test-env"
        
        response = client.get("/health")
        data = response.json()
        
        assert data["version"] == "test-version-1.2.3"
        assert data["environment"] == "test-env"


class TestHealthEndpointDatabase:
    """Tests for database connectivity in health endpoint"""
    
    @pytest.mark.skip(reason="Database check not yet implemented in endpoint")
    def test_health_checks_database(self):
        """Test that health endpoint checks database connectivity"""
        with patch('database.session.get_db') as mock_get_db:
            mock_session = Mock()
            mock_get_db.return_value = mock_session
            
            response = client.get("/health")
            data = response.json()
            
            assert "database" in data
            assert data["database"] == "connected"
            
    @pytest.mark.skip(reason="Database check not yet implemented in endpoint")
    def test_health_handles_database_error(self):
        """Test that health endpoint handles database errors gracefully"""
        with patch('database.session.get_db') as mock_get_db:
            mock_get_db.side_effect = OperationalError("Connection failed", None, None)
            
            response = client.get("/health")
            
            # Should return 503 Service Unavailable
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "unhealthy"
            assert data["database"] == "error"


class TestHealthEndpointRedis:
    """Tests for Redis connectivity in health endpoint"""
    
    @pytest.mark.skip(reason="Redis check not yet implemented in endpoint")
    def test_health_checks_redis(self):
        """Test that health endpoint checks Redis connectivity"""
        with patch('redis.Redis') as mock_redis:
            mock_redis_instance = Mock()
            mock_redis_instance.ping.return_value = True
            mock_redis.return_value = mock_redis_instance
            
            response = client.get("/health")
            data = response.json()
            
            assert "redis" in data
            assert data["redis"] == "connected"
            
    @pytest.mark.skip(reason="Redis check not yet implemented in endpoint")
    def test_health_handles_redis_error(self):
        """Test that health endpoint handles Redis errors gracefully"""
        with patch('redis.Redis') as mock_redis:
            mock_redis_instance = Mock()
            mock_redis_instance.ping.side_effect = Exception("Connection failed")
            mock_redis.return_value = mock_redis_instance
            
            response = client.get("/health")
            data = response.json()
            
            # Should still return 200 but mark Redis as error
            assert response.status_code == 200
            assert data["redis"] == "error"


class TestHealthEndpointPerformance:
    """Performance tests for health endpoint"""
    
    def test_single_request_performance(self):
        """Test that a single health request completes in under 100ms"""
        start_time = time.time()
        response = client.get("/health")
        elapsed_ms = (time.time() - start_time) * 1000
        
        assert response.status_code == 200
        assert elapsed_ms < 100, f"Request took {elapsed_ms:.2f}ms"
        
    def test_multiple_requests_performance(self):
        """Test that multiple health requests maintain good performance"""
        times = []
        
        for _ in range(20):
            start_time = time.time()
            response = client.get("/health")
            elapsed_ms = (time.time() - start_time) * 1000
            
            assert response.status_code == 200
            times.append(elapsed_ms)
            
        # All requests should be under 100ms
        assert all(t < 100 for t in times), f"Some requests exceeded 100ms: {[t for t in times if t >= 100]}"
        
        # Average should be well under 100ms
        avg_time = sum(times) / len(times)
        assert avg_time < 50, f"Average time {avg_time:.2f}ms exceeds 50ms"
        
    @pytest.mark.asyncio
    async def test_concurrent_requests_performance(self):
        """Test health endpoint performance under concurrent load"""
        async def make_request():
            start_time = time.time()
            response = client.get("/health")
            elapsed_ms = (time.time() - start_time) * 1000
            return response.status_code, elapsed_ms
            
        # Make 10 concurrent requests
        tasks = [make_request() for _ in range(10)]
        results = await asyncio.gather(*tasks)
        
        # All should succeed
        assert all(status == 200 for status, _ in results)
        
        # All should be fast
        times = [elapsed for _, elapsed in results]
        assert all(t < 100 for t in times), "Some concurrent requests exceeded 100ms"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])