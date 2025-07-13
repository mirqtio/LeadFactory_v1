"""
Remote health check test for deployed instances
Can be used in CI/CD pipelines to verify deployment
"""

import os
import time
import requests
import pytest


def get_base_url():
    """Get the base URL from environment or use default"""
    return os.getenv("LEADFACTORY_URL", "http://localhost:8000")


class TestRemoteHealth:
    """Test health endpoint on remote/deployed instance"""

    @pytest.mark.skipif(os.getenv("CI") == "true", reason="Skip in CI - stub server doesn't have health endpoint")
    def test_health_returns_200(self):
        """Test that health endpoint returns 200 status"""
        url = f"{get_base_url()}/health"
        response = requests.get(url, timeout=10)
        assert response.status_code == 200, f"Health check failed: {response.status_code}"

    @pytest.mark.skipif(os.getenv("CI") == "true", reason="Skip in CI - stub server doesn't have health endpoint")
    def test_health_returns_json(self):
        """Test that health endpoint returns valid JSON"""
        url = f"{get_base_url()}/health"
        response = requests.get(url, timeout=10)

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] in ["healthy", "unhealthy", "ok"]

    @pytest.mark.skipif(os.getenv("CI") == "true", reason="Skip in CI - stub server doesn't have health endpoint")
    def test_health_response_time(self):
        """Test that health endpoint responds quickly"""
        url = f"{get_base_url()}/health"

        start_time = time.time()
        response = requests.get(url, timeout=10)
        elapsed = (time.time() - start_time) * 1000  # ms

        assert response.status_code == 200
        assert elapsed < 1000, f"Response took {elapsed:.2f}ms, expected < 1000ms"

    @pytest.mark.skipif(os.getenv("CI") == "true", reason="Skip in CI - stub server doesn't have health endpoint")
    def test_health_includes_required_fields(self):
        """Test that health response includes all required fields"""
        url = f"{get_base_url()}/health"
        response = requests.get(url, timeout=10)

        assert response.status_code == 200
        data = response.json()

        # Required fields
        assert "status" in data
        assert "timestamp" in data
        assert "version" in data
        assert "environment" in data

        # Database status (should always be present)
        assert "database" in data


if __name__ == "__main__":
    # Can be run directly for manual testing
    print(f"Testing health endpoint at: {get_base_url()}")
    pytest.main([__file__, "-v"])
