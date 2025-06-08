"""
Test metrics endpoint integration
"""
import pytest
import sys
import os
from fastapi.testclient import TestClient

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import main


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(main.app)


class TestMetricsEndpoint:
    
    def test_metrics_endpoint_accessible(self, client):
        """Test that metrics endpoint is accessible"""
        response = client.get("/metrics")
        assert response.status_code == 200
        # Check that content type contains prometheus format
        assert "text/plain" in response.headers["content-type"]
        assert "version=0.0.4" in response.headers["content-type"]
        
    def test_metrics_content(self, client):
        """Test metrics endpoint returns Prometheus format"""
        # Make a few requests to generate metrics
        client.get("/health")
        client.get("/health")
        client.get("/nonexistent")  # 404
        
        # Get metrics
        response = client.get("/metrics")
        metrics_text = response.text
        
        # Check Prometheus format
        assert "# HELP" in metrics_text
        assert "# TYPE" in metrics_text
        
        # Check our custom metrics are present
        assert "leadfactory_http_requests_total" in metrics_text
        assert "leadfactory_http_request_duration_seconds" in metrics_text
        assert "leadfactory_app_info" in metrics_text
        
        # Check that request to /health was tracked
        assert 'endpoint="/health"' in metrics_text
        assert 'status="200"' in metrics_text
        
        # Check that 404 was tracked
        assert 'endpoint="/nonexistent"' in metrics_text
        assert 'status="404"' in metrics_text
        
    def test_metrics_not_tracked_for_metrics_endpoint(self, client):
        """Test that requests to /metrics are not tracked"""
        # Get initial metrics
        response1 = client.get("/metrics")
        metrics1 = response1.text
        
        # Get metrics again
        response2 = client.get("/metrics")
        metrics2 = response2.text
        
        # The metrics endpoint itself should not be tracked
        assert 'endpoint="/metrics"' not in metrics2
        
    def test_health_endpoint_tracked(self, client):
        """Test that health endpoint requests are tracked"""
        # Clear any previous metrics by getting a fresh client
        fresh_client = TestClient(main.app)
        
        # Make health check request
        response = fresh_client.get("/health")
        assert response.status_code == 200
        
        # Check metrics
        metrics_response = fresh_client.get("/metrics")
        metrics_text = metrics_response.text
        
        # Verify health check was tracked
        assert 'leadfactory_http_requests_total' in metrics_text
        assert 'endpoint="/health"' in metrics_text
        assert 'method="GET"' in metrics_text
        assert 'status="200"' in metrics_text