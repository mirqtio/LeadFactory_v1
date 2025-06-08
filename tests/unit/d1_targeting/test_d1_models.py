"""
Test targeting domain models - simplified version
"""
import pytest
from datetime import datetime
import uuid

from d1_targeting.models import Target, TargetUniverse, Campaign, CampaignTarget, GeographicBoundary
from d1_targeting.types import VerticalMarket, GeographyLevel, CampaignStatus


class TestTargetModel:
    
    def test_target_model_complete(self):
        """Test that target model has all required fields"""
        target = Target(
            business_name="Joe's Restaurant",
            vertical=VerticalMarket.RESTAURANTS.value,
            website="https://joesrestaurant.com",
            phone="555-0123",
            email="info@joesrestaurant.com",
            address="123 Main St",
            city="San Francisco",
            state="CA",
            zip_code="94102",
            country="US",
            latitude=37.7749,
            longitude=-122.4194,
            rating=4.5,
            review_count=150,
            price_level=2,
            categories=["restaurant", "italian", "casual dining"],
            source_provider="yelp",
            external_id="yelp_123456"
        )
        
        # Verify all attributes are accessible
        assert target.business_name == "Joe's Restaurant"
        assert target.vertical == VerticalMarket.RESTAURANTS.value
        assert target.website == "https://joesrestaurant.com"
        assert target.phone == "555-0123"
        assert target.email == "info@joesrestaurant.com"
        assert target.city == "San Francisco"
        assert target.state == "CA"
        assert target.zip_code == "94102"
        assert target.latitude == 37.7749
        assert target.longitude == -122.4194
        assert target.source_provider == "yelp"
        assert target.external_id == "yelp_123456"
    
    def test_geo_hierarchy_validated(self):
        """Test that geographic hierarchy fields are properly defined"""
        target = Target(
            business_name="Test Business",
            vertical=VerticalMarket.RETAIL.value,
            source_provider="test"
        )
        
        # Test setting geographic fields
        target.country = "US"
        target.state = "CA"
        target.city = "San Francisco"
        target.zip_code = "94102"
        target.latitude = 37.7749
        target.longitude = -122.4194
        
        # Verify fields are accessible
        assert target.country == "US"
        assert target.state == "CA"
        assert target.city == "San Francisco"
        assert target.zip_code == "94102"
        assert target.latitude == 37.7749
        assert target.longitude == -122.4194
    
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
            VerticalMarket.LEGAL
        ]
        
        for vertical in expected_verticals:
            # Should be able to create targets with each vertical
            target = Target(
                business_name=f"Test {vertical.value} Business",
                vertical=vertical.value,
                source_provider="test"
            )
            assert target.vertical == vertical.value
    
    def test_unique_constraints_defined(self):
        """Test that unique constraints are properly defined"""
        # Test that the model has the expected table args for constraints
        assert hasattr(Target, '__table_args__')
        table_args = Target.__table_args__
        
        # Should have unique constraint on source_provider + external_id
        constraint_names = []
        for arg in table_args:
            if hasattr(arg, 'name'):
                constraint_names.append(arg.name)
        
        assert 'uq_targets_source_external' in constraint_names


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
                "state": "CA"
            },
            estimated_size=5000,
            actual_size=4235
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
            status=CampaignStatus.DRAFT.value
        )
        
        assert campaign.name == "Q1 Restaurant Outreach"
        assert campaign.target_universe_id == universe_id
        assert campaign.status == CampaignStatus.DRAFT.value
    
    def test_campaign_target_association_fields(self):
        """Test campaign-target association fields"""
        campaign_id = str(uuid.uuid4())
        target_id = str(uuid.uuid4())
        
        campaign_target = CampaignTarget(
            campaign_id=campaign_id,
            target_id=target_id,
            status="pending"
        )
        
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
            center_longitude=-119.4179
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
            state_code="CA"
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
            GeographicBoundary: "geographic_boundaries"
        }
        
        for model in models:
            assert hasattr(model, '__tablename__')
            assert model.__tablename__ == expected_tablenames[model]
    
    def test_models_have_required_relationships(self):
        """Test that models have expected relationships defined"""
        # Target should have campaign_targets relationship
        assert hasattr(Target, 'campaign_targets')
        
        # TargetUniverse should have campaigns relationship
        assert hasattr(TargetUniverse, 'campaigns')
        
        # Campaign should have target_universe, campaign_targets, and campaign_batches relationships
        assert hasattr(Campaign, 'target_universe')
        assert hasattr(Campaign, 'campaign_targets')
        assert hasattr(Campaign, 'campaign_batches')
        
        # CampaignTarget should have campaign and target relationships
        assert hasattr(CampaignTarget, 'campaign')
        assert hasattr(CampaignTarget, 'target')
    
    def test_enum_types_defined(self):
        """Test that all enum types are properly defined"""
        # Test VerticalMarket enum
        assert hasattr(VerticalMarket, 'RESTAURANTS')
        assert hasattr(VerticalMarket, 'RETAIL')
        assert hasattr(VerticalMarket, 'PROFESSIONAL_SERVICES')
        
        # Test GeographyLevel enum
        assert hasattr(GeographyLevel, 'COUNTRY')
        assert hasattr(GeographyLevel, 'STATE')
        assert hasattr(GeographyLevel, 'CITY')
        assert hasattr(GeographyLevel, 'ZIP_CODE')
        
        # Test CampaignStatus enum
        assert hasattr(CampaignStatus, 'DRAFT')
        assert hasattr(CampaignStatus, 'RUNNING')
        assert hasattr(CampaignStatus, 'COMPLETED')
        
        # Test enum values
        assert VerticalMarket.RESTAURANTS.value == "restaurants"
        assert GeographyLevel.STATE.value == "state"
        assert CampaignStatus.DRAFT.value == "draft"