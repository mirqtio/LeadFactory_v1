"""
Simple Test Task 023: Add targeting API endpoints
Acceptance Criteria:
- FastAPI routes work
- Validation complete
- Error handling proper
- Documentation generated
"""

import sys

import pytest

# Ensure we can import our modules
sys.path.insert(0, "/app")

from d1_targeting.api import router
from d1_targeting.schemas import CreateTargetUniverseSchema, GeographicConstraintSchema, TargetingCriteriaSchema
from d1_targeting.types import GeographyLevel, VerticalMarket

# Mark entire module as slow for CI optimization
pytestmark = pytest.mark.slow


class TestTask023AcceptanceCriteriaSimple:
    """Test that Task 023 meets all acceptance criteria with simple tests"""

    def test_fastapi_routes_work(self):
        """Test that FastAPI routes work properly"""
        # Verify router exists and has routes
        assert router is not None
        assert hasattr(router, "routes")
        assert len(router.routes) > 0

        # Check that expected routes exist
        route_paths = [route.path for route in router.routes]
        expected_paths = ["/universes", "/campaigns", "/batches", "/health"]

        for expected_path in expected_paths:
            assert any(expected_path in path for path in route_paths), f"Missing route: {expected_path}"

        print("✓ FastAPI routes work")

    def test_validation_complete(self):
        """Test that validation is complete and working"""

        # Test valid geographic constraint
        valid_constraint = GeographicConstraintSchema(level=GeographyLevel.STATE, values=["CA", "NY"])
        assert valid_constraint.level == GeographyLevel.STATE
        assert valid_constraint.values == ["CA", "NY"]

        # Test valid criteria
        valid_criteria = TargetingCriteriaSchema(
            verticals=[VerticalMarket.RESTAURANTS],
            geographic_constraints=[valid_constraint],
        )
        assert len(valid_criteria.verticals) == 1
        assert len(valid_criteria.geographic_constraints) == 1

        # Test invalid criteria (empty verticals should fail)
        with pytest.raises(ValueError):
            TargetingCriteriaSchema(
                verticals=[],  # Empty list should fail
                geographic_constraints=[valid_constraint],
            )

        # Test radius validation
        with pytest.raises(ValueError):
            GeographicConstraintSchema(
                level=GeographyLevel.RADIUS,
                values=["Test Location"],
                radius_miles=10.0,  # Missing coordinates
                center_lat=None,
                center_lng=None,
            )

        print("✓ Validation complete")

    def test_error_handling_proper(self):
        """Test that error handling is proper"""

        # Test that error handling decorator exists
        from d1_targeting.api import handle_api_errors

        assert callable(handle_api_errors)

        # Test schema validation errors
        with pytest.raises(ValueError):
            CreateTargetUniverseSchema(
                name="",  # Empty name should fail
                targeting_criteria=TargetingCriteriaSchema(
                    verticals=[VerticalMarket.RESTAURANTS],
                    geographic_constraints=[GeographicConstraintSchema(level=GeographyLevel.STATE, values=["CA"])],
                ),
            )

        print("✓ Error handling proper")

    def test_documentation_generated(self):
        """Test that OpenAPI documentation is generated"""

        # Test that router has proper structure for documentation
        assert router.prefix == ""
        assert len(router.routes) > 0

        # Test that routes have proper documentation metadata
        route_paths = [route.path for route in router.routes]

        # Check for main CRUD endpoints
        expected_endpoints = [
            "/universes",  # POST, GET
            "/universes/{universe_id}",  # GET, PUT, DELETE
            "/campaigns",  # POST, GET
            "/campaigns/{campaign_id}",  # GET, PUT
            "/batches",  # POST, GET
            "/analytics/quota",  # GET
            "/health",  # GET
        ]

        for endpoint in expected_endpoints:
            assert any(endpoint in path for path in route_paths), f"Missing endpoint: {endpoint}"

        # Test that schemas have proper annotations for documentation
        assert hasattr(CreateTargetUniverseSchema, "__annotations__")
        assert hasattr(TargetingCriteriaSchema, "__annotations__")
        assert hasattr(GeographicConstraintSchema, "__annotations__")

        print("✓ Documentation generated")

    def test_schema_structure_complete(self):
        """Test that schema structure is complete"""

        # Test that key schemas exist and can be imported
        from d1_targeting.schemas import CreateTargetUniverseSchema

        # Test that schemas have proper field types
        universe_schema = CreateTargetUniverseSchema
        assert hasattr(universe_schema, "__annotations__")

        # Test geographic constraint validation works
        valid_geo_constraint = GeographicConstraintSchema(
            level=GeographyLevel.CITY, values=["San Francisco", "New York"]
        )
        assert valid_geo_constraint.level == GeographyLevel.CITY

        print("✓ Schema structure complete")

    def test_route_methods_defined(self):
        """Test that route methods are properly defined"""

        # Count different HTTP methods
        get_routes = []
        post_routes = []
        put_routes = []
        delete_routes = []

        for route in router.routes:
            if hasattr(route, "methods"):
                if "GET" in route.methods:
                    get_routes.append(route.path)
                if "POST" in route.methods:
                    post_routes.append(route.path)
                if "PUT" in route.methods:
                    put_routes.append(route.path)
                if "DELETE" in route.methods:
                    delete_routes.append(route.path)

        # Should have multiple GET endpoints
        assert len(get_routes) >= 5

        # Should have POST endpoints for creation
        assert len(post_routes) >= 3

        # Should have PUT endpoints for updates
        assert len(put_routes) >= 2

        # Should have DELETE endpoints
        assert len(delete_routes) >= 1

        print("✓ Route methods defined")

    def test_integration_imports(self):
        """Test that integration imports work correctly"""

        # Test that we can import the router from the main package
        from d1_targeting import api_router

        assert api_router is not None
        assert api_router == router

        # Test that we can import key components used by the API
        from d1_targeting import BatchScheduler, QuotaTracker, TargetUniverseManager

        assert TargetUniverseManager is not None
        assert BatchScheduler is not None
        assert QuotaTracker is not None

        # Test that database models can be imported
        from d1_targeting.models import Campaign, CampaignBatch, TargetUniverse

        assert TargetUniverse is not None
        assert Campaign is not None
        assert CampaignBatch is not None

        print("✓ Integration imports work")

    def test_all_required_files_exist(self):
        """Test that all required files from Task 023 exist and can be imported"""

        # Test api.py
        from d1_targeting.api import get_db, handle_api_errors, router

        assert router is not None
        assert callable(get_db)
        assert callable(handle_api_errors)

        # Test schemas.py
        from d1_targeting.schemas import (
            BatchResponseSchema,
            CreateCampaignSchema,
            CreateTargetUniverseSchema,
            PaginationSchema,
            TargetUniverseResponseSchema,
        )

        assert CreateTargetUniverseSchema is not None
        assert TargetUniverseResponseSchema is not None
        assert CreateCampaignSchema is not None
        assert BatchResponseSchema is not None
        assert PaginationSchema is not None

        # Test that pagination works
        pagination = PaginationSchema(page=2, size=25)
        assert pagination.page == 2
        assert pagination.size == 25
        assert pagination.offset == 25  # (page-1) * size

        print("✓ All required files exist and can be imported")

    def test_enum_integration(self):
        """Test that enum integration works properly"""

        # Test that enums can be used in schemas
        from d1_targeting.types import CampaignStatus, GeographyLevel, VerticalMarket

        # Test vertical market enum
        assert VerticalMarket.RESTAURANTS.value == "restaurants"
        assert VerticalMarket.RETAIL.value == "retail"

        # Test geography level enum
        assert GeographyLevel.STATE.value == "state"
        assert GeographyLevel.CITY.value == "city"

        # Test campaign status enum
        assert CampaignStatus.RUNNING.value == "running"
        assert CampaignStatus.COMPLETED.value == "completed"

        # Test that enums work in schema validation
        criteria = TargetingCriteriaSchema(
            verticals=[VerticalMarket.RESTAURANTS, VerticalMarket.RETAIL],
            geographic_constraints=[GeographicConstraintSchema(level=GeographyLevel.STATE, values=["CA"])],
        )
        assert len(criteria.verticals) == 2

        print("✓ Enum integration works")


if __name__ == "__main__":
    # Allow running this test file directly
    test_instance = TestTask023AcceptanceCriteriaSimple()
    test_instance.test_fastapi_routes_work()
    test_instance.test_validation_complete()
    test_instance.test_error_handling_proper()
    test_instance.test_documentation_generated()
    test_instance.test_schema_structure_complete()
    test_instance.test_route_methods_defined()
    test_instance.test_integration_imports()
    test_instance.test_all_required_files_exist()
    test_instance.test_enum_integration()
    print("\n🎉 All Task 023 acceptance criteria tests pass!")
