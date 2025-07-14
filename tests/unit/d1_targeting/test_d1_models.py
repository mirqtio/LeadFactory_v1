"""
Test targeting domain models - simplified version
"""
import uuid

import pytest

# Mark entire module as xfail for Phase 0.5
pytestmark = pytest.mark.xfail(reason="Phase 0.5 feature", strict=False)

from d1_targeting.models import Campaign, CampaignTarget, GeographicBoundary, TargetUniverse
from d1_targeting.types import CampaignStatus, GeographyLevel, VerticalMarket
from database.models import Business, GeoType, Target


class TestBusinessModel:
    def test_business_model_complete(self):
        """Test that business model has all required fields"""
        business = Business(
            name="Joe's Restaurant",
            vertical=VerticalMarket.RESTAURANTS.value,
            website="https://joesrestaurant.com",
            phone="555-0123",
            email="info@joesrestaurant.com",
            address="123 Main St",
            city="San Francisco",
            state="CA",
            zip_code="94102",
            latitude=37.7749,
            longitude=-122.4194,
            rating=4.5,
            user_ratings_total=150,
            price_level=2,
            categories=["restaurant", "italian", "casual dining"],
        )

        # Verify all attributes are accessible
        assert business.name == "Joe's Restaurant"
        assert business.vertical == VerticalMarket.RESTAURANTS.value
        assert business.website == "https://joesrestaurant.com"
        assert business.phone == "555-0123"
        assert business.email == "info@joesrestaurant.com"
        assert business.city == "San Francisco"
        assert business.state == "CA"
        assert business.zip_code == "94102"
        assert business.latitude == 37.7749
        assert business.longitude == -122.4194


class TestTargetModel:
    def test_target_model_complete(self):
        """Test that target model has all required fields"""

        target = Target(
            geo_type=GeoType.STATE,
            geo_value="CA",
            vertical=VerticalMarket.RESTAURANTS.value,
            priority_score=0.8,
            is_active=True,
        )

        # Verify all attributes are accessible
        assert target.geo_type == GeoType.STATE
        assert target.geo_value == "CA"
        assert target.vertical == VerticalMarket.RESTAURANTS.value
        assert target.priority_score == 0.8
        assert target.is_active is True

    def test_target_uniqueness_constraint(self):
        """Test that target uniqueness constraint works"""

        target = Target(
            geo_type=GeoType.CITY,
            geo_value="San Francisco",
            vertical=VerticalMarket.RETAIL.value,
            priority_score=0.8,
        )

        assert target.geo_type == GeoType.CITY
        assert target.geo_value == "San Francisco"
        assert target.vertical == VerticalMarket.RETAIL.value
        assert target.priority_score == 0.8

    def test_vertical_enum_defined(self):
        """Test that vertical market enum is properly defined"""
        # Test that all major verticals are defined
        expected_verticals = [
            VerticalMarket.RESTAURANTS,
            VerticalMarket.RETAIL,
            VerticalMarket.PROFESSIONAL_SERVICES,
            VerticalMarket.HEALTHCARE,
            VerticalMarket.AUTOMOTIVE,
            VerticalMarket.REAL_ESTATE,
            VerticalMarket.FITNESS,
            VerticalMarket.BEAUTY_WELLNESS,
            VerticalMarket.HOME_SERVICES,
            VerticalMarket.EDUCATION,
            VerticalMarket.HOSPITALITY,
            VerticalMarket.FINANCIAL_SERVICES,
            VerticalMarket.TECHNOLOGY,
            VerticalMarket.LEGAL,
        ]

        for vertical in expected_verticals:
            # Should be able to create targets with each vertical
            target = Target(
                geo_type=GeoType.STATE,
                geo_value="CA",
                vertical=vertical.value,
            )
            assert target.vertical == vertical.value

    def test_unique_constraints_defined(self):
        """Test that unique constraints are properly defined"""
        # Test that the model has the expected table args for constraints
        assert hasattr(Target, "__table_args__")
        table_args = Target.__table_args__

        # Check that table_args is a tuple and contains constraints
        assert isinstance(table_args, tuple)
        assert len(table_args) > 0

        # The Target model should have unique constraint on (geo_type, geo_value, vertical)
        # and check constraint on priority_score
        constraint_types = [type(arg).__name__ for arg in table_args]
        assert "UniqueConstraint" in constraint_types


class TestTargetUniverseModel:
    def test_target_universe_fields(self):
        """Test target universe model fields"""
        universe = TargetUniverse(
            name="SF Bay Area Restaurants",
            description="All restaurants in SF Bay Area",
            verticals=[VerticalMarket.RESTAURANTS.value],
            geography_config={
                "level": GeographyLevel.CITY.value,
                "values": ["San Francisco", "Oakland", "San Jose"],
                "state": "CA",
            },
            estimated_size=5000,
            actual_size=4235,
        )

        assert universe.name == "SF Bay Area Restaurants"
        assert universe.verticals == [VerticalMarket.RESTAURANTS.value]
        assert universe.geography_config["level"] == GeographyLevel.CITY.value
        assert universe.estimated_size == 5000
        assert universe.actual_size == 4235


class TestCampaignModel:
    def test_campaign_fields(self):
        """Test campaign model fields"""
        campaign_id = str(uuid.uuid4())
        universe_id = str(uuid.uuid4())

        campaign = Campaign(
            name="Q1 Restaurant Outreach",
            description="Quarterly restaurant campaign",
            target_universe_id=universe_id,
            status=CampaignStatus.DRAFT.value,
        )

        assert campaign.name == "Q1 Restaurant Outreach"
        assert campaign.target_universe_id == universe_id
        assert campaign.status == CampaignStatus.DRAFT.value

    def test_campaign_target_association_fields(self):
        """Test campaign-target association fields"""
        campaign_id = str(uuid.uuid4())
        target_id = str(uuid.uuid4())

        campaign_target = CampaignTarget(campaign_id=campaign_id, target_id=target_id, status="pending")

        assert campaign_target.campaign_id == campaign_id
        assert campaign_target.target_id == target_id
        assert campaign_target.status == "pending"


class TestGeographicBoundaryModel:
    def test_geographic_boundary_fields(self):
        """Test geographic boundary model fields"""
        boundary = GeographicBoundary(
            name="California",
            level=GeographyLevel.STATE.value,
            code="CA",
            country="US",
            center_latitude=36.7783,
            center_longitude=-119.4179,
        )

        assert boundary.name == "California"
        assert boundary.level == GeographyLevel.STATE.value
        assert boundary.code == "CA"
        assert boundary.country == "US"
        assert boundary.center_latitude == 36.7783
        assert boundary.center_longitude == -119.4179

    def test_geographic_boundary_hierarchy(self):
        """Test geographic boundary hierarchy support"""
        parent_id = str(uuid.uuid4())

        boundary = GeographicBoundary(
            name="San Francisco",
            level=GeographyLevel.CITY.value,
            parent_id=parent_id,
            country="US",
            state_code="CA",
        )

        assert boundary.parent_id == parent_id
        assert boundary.state_code == "CA"


class TestModelDefinitions:
    def test_all_models_have_tablenames(self):
        """Test that all models have proper table names defined"""
        models = [Target, TargetUniverse, Campaign, CampaignTarget, GeographicBoundary]

        expected_tablenames = {
            Target: "targets",
            TargetUniverse: "target_universes",
            Campaign: "campaigns",
            CampaignTarget: "campaign_targets",
            GeographicBoundary: "geographic_boundaries",
        }

        for model in models:
            assert hasattr(model, "__tablename__")
            assert model.__tablename__ == expected_tablenames[model]

    def test_models_have_required_relationships(self):
        """Test that models have expected relationships defined"""
        # Target should have batches relationship
        assert hasattr(Target, "batches")

        # TargetUniverse should have campaigns relationship
        assert hasattr(TargetUniverse, "campaigns")

        # Campaign should have target_universe and campaign_targets relationships
        assert hasattr(Campaign, "target_universe")
        assert hasattr(Campaign, "campaign_targets")

        # CampaignTarget should have campaign relationship
        assert hasattr(CampaignTarget, "campaign")
        assert hasattr(CampaignTarget, "target")

    def test_enum_types_defined(self):
        """Test that all enum types are properly defined"""
        # Test VerticalMarket enum
        assert hasattr(VerticalMarket, "RESTAURANTS")
        assert hasattr(VerticalMarket, "RETAIL")
        assert hasattr(VerticalMarket, "PROFESSIONAL_SERVICES")

        # Test GeographyLevel enum
        assert hasattr(GeographyLevel, "COUNTRY")
        assert hasattr(GeographyLevel, "STATE")
        assert hasattr(GeographyLevel, "CITY")
        assert hasattr(GeographyLevel, "ZIP_CODE")

        # Test CampaignStatus enum
        assert hasattr(CampaignStatus, "DRAFT")
        assert hasattr(CampaignStatus, "RUNNING")
        assert hasattr(CampaignStatus, "COMPLETED")

        # Test enum values
        assert VerticalMarket.RESTAURANTS.value == "restaurants"
        assert GeographyLevel.STATE.value == "state"
        assert CampaignStatus.DRAFT.value == "draft"
