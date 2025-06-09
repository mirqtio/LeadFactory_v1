"""
Test d2_sourcing domain models
"""
import pytest
import uuid
from datetime import datetime

from d2_sourcing.models import Business, YelpMetadata, SourcedLocation


class TestBusinessModel:

    def test_business_model_complete(self):
        """Test that business model has all required fields"""
        business = Business(
            name="Joe's Restaurant",
            yelp_id="joe-restaurant-sf",
            alias="joes-restaurant",
            image_url="https://example.com/image.jpg",
            is_claimed=True,
            is_closed=False,
            address1="123 Main St",
            city="San Francisco",
            state="CA",
            zip_code="94102",
            country="US",
            latitude=37.7749,
            longitude=-122.4194,
            phone="+14155551234",
            display_phone="(415) 555-1234",
            review_count=150,
            rating=4.5,
            price="$$",
            categories=[
                {"alias": "italian", "title": "Italian"},
                {"alias": "restaurants", "title": "Restaurants"}
            ],
            hours=[
                {
                    "open": [
                        {"is_overnight": False, "start": "1100", "end": "2200", "day": 0}
                    ],
                    "hours_type": "REGULAR",
                    "is_open_now": True
                }
            ],
            transactions=["pickup", "delivery"],
            attributes={
                "outdoor_seating": True,
                "takes_reservations": True,
                "wheelchair_accessible": True
            }
        )

        # Verify all attributes are accessible
        assert business.name == "Joe's Restaurant"
        assert business.yelp_id == "joe-restaurant-sf"
        assert business.city == "San Francisco"
        assert business.state == "CA"
        assert business.latitude == 37.7749
        assert business.longitude == -122.4194
        assert business.rating == 4.5
        assert business.review_count == 150
        assert business.price == "$$"
        assert len(business.categories) == 2
        assert business.categories[0]["alias"] == "italian"
        assert business.attributes["outdoor_seating"] is True

    def test_yelp_id_unique_constraint(self):
        """Test that Yelp ID unique constraint is defined"""
        # Check that the model has the unique constraint on yelp_id
        business_columns = Business.__table__.columns
        yelp_id_column = business_columns['yelp_id']

        assert yelp_id_column.unique is True
        assert yelp_id_column.index is True

    def test_jsonb_fields_work(self):
        """Test that JSONB fields work correctly"""
        business = Business(
            name="Test Business",
            categories=[
                {"alias": "test", "title": "Test Category"},
                {"alias": "sample", "title": "Sample Category"}
            ],
            attributes={
                "parking": {"street": True, "lot": False},
                "noise_level": "quiet",
                "good_for": {"breakfast": True, "lunch": True}
            },
            hours=[
                {
                    "open": [
                        {"is_overnight": False, "start": "0900", "end": "1700", "day": 1}
                    ],
                    "hours_type": "REGULAR"
                }
            ]
        )

        # Test categories JSONB field
        assert isinstance(business.categories, list)
        assert business.categories[0]["alias"] == "test"
        assert business.categories[1]["title"] == "Sample Category"

        # Test attributes JSONB field
        assert isinstance(business.attributes, dict)
        assert business.attributes["parking"]["street"] is True
        assert business.attributes["noise_level"] == "quiet"
        assert business.attributes["good_for"]["breakfast"] is True

        # Test hours JSON field
        assert isinstance(business.hours, list)
        assert business.hours[0]["hours_type"] == "REGULAR"

    def test_indexes_created(self):
        """Test that expected indexes are defined"""
        table_args = Business.__table_args__

        # Extract index names
        index_names = []
        for arg in table_args:
            if hasattr(arg, 'name'):
                index_names.append(arg.name)

        # Verify expected indexes exist
        expected_indexes = [
            'idx_businesses_location',
            'idx_businesses_geo',
            'idx_businesses_rating',
            'idx_businesses_categories',
            'idx_businesses_attributes',
            'idx_businesses_search'
        ]

        for expected_index in expected_indexes:
            assert expected_index in index_names


class TestYelpMetadataModel:

    def test_yelp_metadata_fields(self):
        """Test YelpMetadata model fields"""
        business_id = str(uuid.uuid4())

        metadata = YelpMetadata(
            business_id=business_id,
            yelp_url="https://www.yelp.com/biz/joes-restaurant",
            photos=["photo1.jpg", "photo2.jpg"],
            special_hours=[
                {"date": "2024-12-25", "is_closed": True}
            ],
            messaging={"use_case_text": "Request a Quote"},
            raw_response={"id": "test", "name": "Test Business"},
            api_version="v3",
            processed=True,
            enriched=False,
            normalized=True,
            completeness_score=0.85,
            freshness_score=0.95,
            accuracy_score=0.90,
            fetch_count=3
        )

        assert metadata.business_id == business_id
        assert metadata.yelp_url == "https://www.yelp.com/biz/joes-restaurant"
        assert len(metadata.photos) == 2
        assert metadata.photos[0] == "photo1.jpg"
        assert metadata.special_hours[0]["is_closed"] is True
        assert metadata.messaging["use_case_text"] == "Request a Quote"
        assert metadata.raw_response["name"] == "Test Business"
        assert metadata.processed is True
        assert metadata.enriched is False
        assert metadata.completeness_score == 0.85
        assert metadata.fetch_count == 3

    def test_yelp_metadata_relationships(self):
        """Test YelpMetadata relationships"""
        # Verify the relationship is defined
        assert hasattr(YelpMetadata, 'business')
        assert YelpMetadata.business.property.back_populates == 'yelp_metadata'


class TestSourcedLocationModel:

    def test_sourced_location_fields(self):
        """Test SourcedLocation model fields"""
        business_id = str(uuid.uuid4())

        location = SourcedLocation(
            business_id=business_id,
            source_provider="yelp",
            source_id="yelp_123456",
            source_url="https://api.yelp.com/businesses/yelp_123456",
            source_name="Joe's Italian Restaurant",
            source_address="123 Main Street, San Francisco, CA 94102",
            source_coordinates={"lat": 37.7749, "lng": -122.4194},
            source_phone="4155551234",
            source_categories=["italian", "restaurants"],
            match_confidence=0.95,
            distance_meters=0.0,
            name_similarity=0.98,
            source_data={"rating": 4.5, "review_count": 150},
            is_primary=True,
            is_duplicate=False,
            is_conflicting=False,
            needs_review=False
        )

        assert location.business_id == business_id
        assert location.source_provider == "yelp"
        assert location.source_id == "yelp_123456"
        assert location.source_name == "Joe's Italian Restaurant"
        assert location.source_coordinates["lat"] == 37.7749
        assert location.source_coordinates["lng"] == -122.4194
        assert location.match_confidence == 0.95
        assert location.name_similarity == 0.98
        assert location.source_data["rating"] == 4.5
        assert location.is_primary is True
        assert location.needs_review is False

    def test_sourced_location_unique_constraint(self):
        """Test unique constraint on source_provider + source_id"""
        table_args = SourcedLocation.__table_args__

        # Find unique constraint
        constraint_names = []
        for arg in table_args:
            if hasattr(arg, 'name') and 'uq_' in arg.name:
                constraint_names.append(arg.name)

        assert 'uq_sourced_locations_provider_id' in constraint_names


class TestModelRelationships:

    def test_business_yelp_metadata_relationship(self):
        """Test Business-YelpMetadata relationship"""
        # Verify relationships are defined
        assert hasattr(Business, 'yelp_metadata')
        assert hasattr(YelpMetadata, 'business')

        # Verify back_populates is correct
        assert Business.yelp_metadata.property.back_populates == 'business'
        assert YelpMetadata.business.property.back_populates == 'yelp_metadata'

    def test_business_sourced_locations_relationship(self):
        """Test Business-SourcedLocation relationship"""
        # Verify relationships are defined
        assert hasattr(Business, 'sourced_locations')
        assert hasattr(SourcedLocation, 'business')

        # Verify back_populates is correct
        assert Business.sourced_locations.property.back_populates == 'business'
        assert SourcedLocation.business.property.back_populates == 'sourced_locations'


class TestModelDefinitions:

    def test_all_models_have_tablenames(self):
        """Test that all models have proper table names"""
        models = [Business, YelpMetadata, SourcedLocation]
        expected_tablenames = {
            Business: "businesses",
            YelpMetadata: "yelp_metadata",
            SourcedLocation: "sourced_locations"
        }

        for model in models:
            assert hasattr(model, '__tablename__')
            assert model.__tablename__ == expected_tablenames[model]

    def test_primary_keys_defined(self):
        """Test that all models have UUID primary keys"""
        models = [Business, YelpMetadata, SourcedLocation]

        for model in models:
            pk_columns = [col for col in model.__table__.columns if col.primary_key]
            assert len(pk_columns) == 1
            assert pk_columns[0].name == 'id'

    def test_timestamp_fields(self):
        """Test that models have appropriate timestamp fields"""
        # Business should have created_at and updated_at
        business_columns = [col.name for col in Business.__table__.columns]
        assert 'created_at' in business_columns
        assert 'updated_at' in business_columns

        # YelpMetadata should have response_timestamp and last_fetched
        metadata_columns = [col.name for col in YelpMetadata.__table__.columns]
        assert 'response_timestamp' in metadata_columns
        assert 'last_fetched' in metadata_columns

        # SourcedLocation should have discovered_at and last_updated
        location_columns = [col.name for col in SourcedLocation.__table__.columns]
        assert 'discovered_at' in location_columns
        assert 'last_updated' in location_columns
