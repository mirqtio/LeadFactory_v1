"""
Additional tests for missing API coverage in d10_analytics.

Focuses on improving test coverage for key API functionality that was missed
in the initial test suite.
"""

import json
from datetime import date
from unittest.mock import Mock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from account_management.models import AccountUser
from core.auth import get_current_user_dependency, require_organization_access
from d10_analytics.api import (
    _build_filters,
    _generate_csv_content,
    _generate_export_content,
    _generate_unit_econ_csv,
    create_error_response,
    export_cache,
    get_warehouse,
    router,
)
from d10_analytics.schemas import SegmentFilter


class TestAPIMissingCoverage:
    """Test API functionality that was missed in initial coverage"""

    @pytest.fixture
    def app(self):
        """Create FastAPI test app"""
        app = FastAPI()
        app.include_router(router)
        return app

    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return TestClient(app)

    @pytest.fixture
    def mock_user(self):
        """Create mock authenticated user"""
        user = Mock(spec=AccountUser)
        user.id = "test_user_id"
        user.email = "test@example.com"
        user.organization_id = "test_org_id"
        user.name = "Test User"
        return user

    @pytest.fixture
    def mock_warehouse(self):
        """Create mock warehouse"""
        warehouse = Mock()
        warehouse.get_daily_metrics = Mock()
        warehouse.calculate_funnel_conversions = Mock()
        warehouse.analyze_cohort_retention = Mock()
        warehouse.export_raw_events = Mock()
        return warehouse

    def setup_dependencies(self, client, mock_warehouse, mock_user):
        """Setup all dependency overrides"""
        client.app.dependency_overrides[get_warehouse] = lambda: mock_warehouse
        client.app.dependency_overrides[get_current_user_dependency] = lambda: mock_user
        client.app.dependency_overrides[require_organization_access] = lambda: "test_org_id"

    def test_build_filters_with_all_fields(self):
        """Test _build_filters with all segment filter fields"""
        segment_filter = SegmentFilter(
            campaign_ids=["campaign_1", "campaign_2"],
            business_verticals=["restaurant", "retail"],
            geographic_regions=["US-CA", "US-NY"],
            funnel_stages=["targeting", "assessment"],
        )

        filters = _build_filters(segment_filter)

        assert "campaign_ids" in filters
        assert filters["campaign_ids"] == ["campaign_1", "campaign_2"]
        assert "verticals" in filters
        assert filters["verticals"] == ["restaurant", "retail"]
        assert "regions" in filters
        assert filters["regions"] == ["US-CA", "US-NY"]
        assert "stages" in filters
        assert filters["stages"] == ["targeting", "assessment"]

        print("✓ _build_filters with all fields works correctly")

    def test_build_filters_with_none(self):
        """Test _build_filters with None segment filter"""
        filters = _build_filters(None)

        assert filters == {}

        print("✓ _build_filters with None works correctly")

    def test_build_filters_with_partial_fields(self):
        """Test _build_filters with partial segment filter fields"""
        segment_filter = SegmentFilter(
            campaign_ids=["campaign_1"],
            business_verticals=None,
            geographic_regions=["US-CA"],
            funnel_stages=None,
        )

        filters = _build_filters(segment_filter)

        assert "campaign_ids" in filters
        assert filters["campaign_ids"] == ["campaign_1"]
        assert "regions" in filters
        assert filters["regions"] == ["US-CA"]
        assert "verticals" not in filters
        assert "stages" not in filters

        print("✓ _build_filters with partial fields works correctly")

    def test_unit_economics_endpoint_date_parameter(self, client, mock_warehouse, mock_user):
        """Test unit economics endpoint with date parameter"""
        self.setup_dependencies(client, mock_warehouse, mock_user)

        # Test with specific date
        response = client.get("/api/v1/analytics/unit_econ?date=2025-01-15")
        assert response.status_code == 200

        data = response.json()
        assert "request_id" in data
        assert "date_range" in data
        assert "summary" in data
        assert "daily_data" in data

        # Verify date range
        assert data["date_range"]["start_date"] == "2025-01-15"
        assert data["date_range"]["end_date"] == "2025-01-15"

        print("✓ Unit economics endpoint with date parameter works correctly")

    def test_unit_economics_endpoint_date_range_parameters(self, client, mock_warehouse, mock_user):
        """Test unit economics endpoint with date range parameters"""
        self.setup_dependencies(client, mock_warehouse, mock_user)

        # Test with date range
        response = client.get("/api/v1/analytics/unit_econ?start_date=2025-01-15&end_date=2025-01-16")
        assert response.status_code == 200

        data = response.json()
        assert "request_id" in data
        assert "date_range" in data
        assert "summary" in data
        assert "daily_data" in data

        # Verify date range
        assert data["date_range"]["start_date"] == "2025-01-15"
        assert data["date_range"]["end_date"] == "2025-01-16"

        print("✓ Unit economics endpoint with date range parameters works correctly")

    def test_unit_economics_endpoint_default_date_range(self, client, mock_warehouse, mock_user):
        """Test unit economics endpoint with default date range"""
        self.setup_dependencies(client, mock_warehouse, mock_user)

        # Test with no date parameters (should use default)
        response = client.get("/api/v1/analytics/unit_econ")
        assert response.status_code == 200

        data = response.json()
        assert "request_id" in data
        assert "date_range" in data
        assert "summary" in data
        assert "daily_data" in data

        # Should have a 30-day default range
        start_date = data["date_range"]["start_date"]
        end_date = data["date_range"]["end_date"]
        assert start_date is not None
        assert end_date is not None

        print("✓ Unit economics endpoint with default date range works correctly")

    def test_unit_economics_endpoint_invalid_date_format(self, client, mock_warehouse, mock_user):
        """Test unit economics endpoint with invalid date format"""
        self.setup_dependencies(client, mock_warehouse, mock_user)

        # Test with invalid date format
        response = client.get("/api/v1/analytics/unit_econ?date=invalid-date")
        assert response.status_code == 400

        error_data = response.json()
        assert "detail" in error_data
        assert "Invalid date format" in error_data["detail"]

        print("✓ Unit economics endpoint with invalid date format handles error correctly")

    def test_unit_economics_endpoint_invalid_date_range(self, client, mock_warehouse, mock_user):
        """Test unit economics endpoint with invalid date range"""
        self.setup_dependencies(client, mock_warehouse, mock_user)

        # Test with start_date after end_date
        response = client.get("/api/v1/analytics/unit_econ?start_date=2025-01-16&end_date=2025-01-15")
        assert response.status_code == 400

        error_data = response.json()
        assert "detail" in error_data
        assert "start_date must be before end_date" in error_data["detail"]

        print("✓ Unit economics endpoint with invalid date range handles error correctly")

    def test_unit_economics_endpoint_csv_format(self, client, mock_warehouse, mock_user):
        """Test unit economics endpoint with CSV format"""
        self.setup_dependencies(client, mock_warehouse, mock_user)

        # Test CSV format
        response = client.get("/api/v1/analytics/unit_econ?date=2025-01-15&format=csv")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"

        # Should be CSV content
        content = response.content.decode()
        assert "Unit Economics Summary" in content
        assert "Daily Data" in content

        print("✓ Unit economics endpoint with CSV format works correctly")

    def test_unit_economics_endpoint_caching(self, client, mock_warehouse, mock_user):
        """Test unit economics endpoint caching"""
        self.setup_dependencies(client, mock_warehouse, mock_user)

        # Clear cache first
        export_cache.clear()

        # First request - should cache
        response1 = client.get("/api/v1/analytics/unit_econ?date=2025-01-15")
        assert response1.status_code == 200

        # Second request - should use cache
        response2 = client.get("/api/v1/analytics/unit_econ?date=2025-01-15")
        assert response2.status_code == 200

        # Should be same response
        assert response1.json()["request_id"] == response2.json()["request_id"]

        print("✓ Unit economics endpoint caching works correctly")

    def test_unit_economics_pdf_endpoint_date_parameter(self, client, mock_warehouse, mock_user):
        """Test unit economics PDF endpoint with date parameter"""
        self.setup_dependencies(client, mock_warehouse, mock_user)

        # Test with specific date
        response = client.get("/api/v1/analytics/unit_econ/pdf?date=2025-01-15")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"

        # Should have PDF content
        content = response.content
        assert len(content) > 0  # Should have some content

        print("✓ Unit economics PDF endpoint with date parameter works correctly")

    def test_unit_economics_pdf_endpoint_parameters(self, client, mock_warehouse, mock_user):
        """Test unit economics PDF endpoint with all parameters"""
        self.setup_dependencies(client, mock_warehouse, mock_user)

        # Test with all parameters
        response = client.get(
            "/api/v1/analytics/unit_econ/pdf?date=2025-01-15&include_charts=true&include_detailed_analysis=true"
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"

        # Test with charts disabled
        response = client.get(
            "/api/v1/analytics/unit_econ/pdf?date=2025-01-15&include_charts=false&include_detailed_analysis=false"
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"

        print("✓ Unit economics PDF endpoint with parameters works correctly")

    def test_unit_economics_pdf_endpoint_invalid_date(self, client, mock_warehouse, mock_user):
        """Test unit economics PDF endpoint with invalid date"""
        self.setup_dependencies(client, mock_warehouse, mock_user)

        # Test with invalid date format
        response = client.get("/api/v1/analytics/unit_econ/pdf?date=invalid-date")
        assert response.status_code == 400

        error_data = response.json()
        assert "detail" in error_data
        assert "Invalid date format" in error_data["detail"]

        print("✓ Unit economics PDF endpoint with invalid date handles error correctly")

    def test_unit_economics_pdf_endpoint_caching(self, client, mock_warehouse, mock_user):
        """Test unit economics PDF endpoint caching"""
        self.setup_dependencies(client, mock_warehouse, mock_user)

        # Clear cache first
        export_cache.clear()

        # First request - should cache
        response1 = client.get("/api/v1/analytics/unit_econ/pdf?date=2025-01-15")
        assert response1.status_code == 200

        # Second request - should use cache
        response2 = client.get("/api/v1/analytics/unit_econ/pdf?date=2025-01-15")
        assert response2.status_code == 200

        # Should be same content
        assert response1.content == response2.content

        print("✓ Unit economics PDF endpoint caching works correctly")

    def test_export_status_endpoint_not_found(self, client, mock_warehouse, mock_user):
        """Test export status endpoint with non-existent export"""
        self.setup_dependencies(client, mock_warehouse, mock_user)

        # Test with non-existent export ID
        response = client.get("/api/v1/analytics/export/non-existent-id")
        assert response.status_code == 404

        error_data = response.json()
        assert "detail" in error_data
        assert error_data["detail"]["error"] == "not_found"

        print("✓ Export status endpoint not found works correctly")

    def test_export_status_endpoint_processing(self, client, mock_warehouse, mock_user):
        """Test export status endpoint with processing export"""
        self.setup_dependencies(client, mock_warehouse, mock_user)

        # Setup processing export
        export_id = "test-export-123"
        export_cache[export_id] = {
            "status": "processing",
            "created_at": "2025-01-15T10:00:00",
        }

        response = client.get(f"/api/v1/analytics/export/{export_id}")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "processing"
        assert data["export_id"] == export_id

        print("✓ Export status endpoint processing works correctly")

    def test_export_status_endpoint_failed(self, client, mock_warehouse, mock_user):
        """Test export status endpoint with failed export"""
        self.setup_dependencies(client, mock_warehouse, mock_user)

        # Setup failed export
        export_id = "test-export-456"
        export_cache[export_id] = {
            "status": "failed",
            "error": "Database connection error",
            "created_at": "2025-01-15T10:00:00",
        }

        response = client.get(f"/api/v1/analytics/export/{export_id}")
        assert response.status_code == 500

        data = response.json()
        assert data["status"] == "failed"
        assert data["error"] == "Database connection error"

        print("✓ Export status endpoint failed works correctly")

    def test_export_status_endpoint_completed(self, client, mock_warehouse, mock_user):
        """Test export status endpoint with completed export"""
        self.setup_dependencies(client, mock_warehouse, mock_user)

        # Setup completed export
        export_id = "test-export-789"
        export_cache[export_id] = {
            "status": "completed",
            "content": "test,csv,content\n1,2,3",
            "created_at": "2025-01-15T10:00:00",
        }

        response = client.get(f"/api/v1/analytics/export/{export_id}")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"

        content = response.content.decode()
        assert "test,csv,content" in content

        print("✓ Export status endpoint completed works correctly")

    def test_create_error_response_custom_status(self):
        """Test create_error_response with custom status code"""
        error_response = create_error_response(
            error_type="custom_error",
            message="Custom error message",
            details={"field": "value"},
            status_code=422,
        )

        assert error_response.status_code == 422
        assert error_response.detail["error"] == "custom_error"
        assert error_response.detail["message"] == "Custom error message"
        assert error_response.detail["details"]["field"] == "value"
        assert "request_id" in error_response.detail

        print("✓ create_error_response with custom status works correctly")

    def test_health_check_endpoint_error(self, client, mock_warehouse, mock_user):
        """Test health check endpoint with error"""
        self.setup_dependencies(client, mock_warehouse, mock_user)

        # Mock warehouse method to raise error
        mock_warehouse.get_daily_metrics.side_effect = Exception("Database error")

        response = client.get("/api/v1/analytics/health")
        assert response.status_code == 200  # Health check always returns 200

        data = response.json()
        assert data["status"] == "unhealthy"
        assert "error" in data["dependencies"]

        print("✓ Health check endpoint error handling works correctly")

    def test_warehouse_dependency(self):
        """Test warehouse dependency function"""
        warehouse = get_warehouse()
        assert warehouse is not None
        assert hasattr(warehouse, "get_daily_metrics")
        assert hasattr(warehouse, "calculate_funnel_conversions")
        assert hasattr(warehouse, "analyze_cohort_retention")
        assert hasattr(warehouse, "export_raw_events")

        print("✓ Warehouse dependency works correctly")


def test_api_missing_coverage_integration():
    """Integration test for missing API coverage"""
    print("Running API missing coverage integration tests...")

    # Test filter building
    segment_filter = SegmentFilter(
        campaign_ids=["test"],
        business_verticals=["test"],
        geographic_regions=["test"],
        funnel_stages=["test"],
    )
    filters = _build_filters(segment_filter)
    assert len(filters) == 4
    print("✓ Filter building integration test passed")

    # Test error response creation
    error_response = create_error_response("test_error", "Test message")
    assert error_response.status_code == 400
    assert error_response.detail["error"] == "test_error"
    print("✓ Error response creation integration test passed")

    # Test warehouse dependency
    warehouse = get_warehouse()
    assert warehouse is not None
    print("✓ Warehouse dependency integration test passed")

    print("✓ All API missing coverage integration tests passed")


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-v"]))
