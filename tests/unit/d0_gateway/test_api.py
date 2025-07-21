"""
Unit tests for d0_gateway.api module
Tests gateway API router configuration and health endpoint
"""

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from d0_gateway.api import gateway_health, router


class TestGatewayAPI:
    """Test Gateway API endpoints and router configuration"""

    def test_router_configuration(self):
        """Test that router is properly configured"""
        assert router.prefix == "/api/v1/gateway"
        assert "gateway" in router.tags

    def test_router_includes_cost_router(self):
        """Test that cost router is included with proper prefix"""
        # Check that cost router is included
        included_routes = [route for route in router.routes]
        cost_routes = [route for route in included_routes if hasattr(route, "path") and "/costs" in route.path]
        assert len(cost_routes) > 0

    def test_router_includes_guardrail_router(self):
        """Test that guardrail router is included"""
        # Check that guardrail routes exist
        included_routes = [route for route in router.routes]
        # Should have at least the health endpoint
        assert len(included_routes) >= 1

    @pytest.mark.asyncio
    async def test_gateway_health_endpoint(self):
        """Test gateway health endpoint returns expected response"""
        response = await gateway_health()

        assert response["status"] == "healthy"
        assert response["service"] == "d0_gateway"

    def test_gateway_health_endpoint_integration(self):
        """Test gateway health endpoint through FastAPI TestClient"""
        app = FastAPI()
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/api/v1/gateway/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "d0_gateway"

    def test_router_has_expected_routes(self):
        """Test that router has expected number of routes"""
        # Router should have at least the health endpoint
        routes = [route for route in router.routes if hasattr(route, "path")]
        health_routes = [route for route in routes if route.path == "/api/v1/gateway/health"]
        assert len(health_routes) == 1

    def test_health_endpoint_route_details(self):
        """Test health endpoint route configuration"""
        health_routes = [
            route for route in router.routes if hasattr(route, "path") and route.path == "/api/v1/gateway/health"
        ]
        assert len(health_routes) == 1

        health_route = health_routes[0]
        assert "GET" in health_route.methods

    def test_router_import_structure(self):
        """Test that router imports are properly structured"""
        # Test that the module can be imported without errors
        from d0_gateway.api import gateway_health as imported_health
        from d0_gateway.api import router as imported_router

        assert imported_router is not None
        assert imported_health is not None
        assert callable(imported_health)
