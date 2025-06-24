"""
Database models for lead sourcing domain
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from database.base import Base
from database.models import Business


class YelpMetadata(Base):
    """Yelp-specific metadata for businesses"""

    __tablename__ = "yelp_metadata"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    business_id = Column(
        String(36), ForeignKey("businesses.id"), nullable=False, unique=True
    )

    # Yelp-specific fields
    yelp_url = Column(String(500), nullable=True)
    photos = Column(JSON, nullable=True)  # Array of photo URLs
    special_hours = Column(JSON, nullable=True)  # Special/holiday hours
    messaging = Column(JSON, nullable=True)  # Messaging info

    # API response metadata
    raw_response = Column(JSON, nullable=True)  # Full Yelp API response
    api_version = Column(String(20), nullable=True)
    response_timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Data processing flags
    processed = Column(Boolean, nullable=False, default=False)
    enriched = Column(Boolean, nullable=False, default=False)
    normalized = Column(Boolean, nullable=False, default=False)

    # Quality metrics
    completeness_score = Column(Float, nullable=True)  # How complete is the data
    freshness_score = Column(Float, nullable=True)  # How recent is the data
    accuracy_score = Column(Float, nullable=True)  # Estimated accuracy

    # Update tracking
    last_fetched = Column(DateTime, nullable=False, default=datetime.utcnow)
    fetch_count = Column(Integer, nullable=False, default=1)
    last_changed = Column(DateTime, nullable=True)

    # Relationships
    business = relationship("Business")

    __table_args__ = (
        Index("idx_yelp_metadata_processed", "processed", "enriched"),
        Index("idx_yelp_metadata_freshness", "last_fetched", "freshness_score"),
    )

    def __repr__(self):
        return f"<YelpMetadata(business_id={self.business_id}, processed={self.processed})>"


class SourcedLocation(Base):
    """Track different data sources for the same business location"""

    __tablename__ = "sourced_locations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    business_id = Column(String(36), ForeignKey("businesses.id"), nullable=False)

    # Source identification
    source_provider = Column(
        String(50), nullable=False, index=True
    )  # yelp, google, manual, etc.
    source_id = Column(String(255), nullable=False, index=True)  # Provider's ID
    source_url = Column(String(500), nullable=True)

    # Location-specific data
    source_name = Column(String(255), nullable=True)
    source_address = Column(Text, nullable=True)
    source_coordinates = Column(JSON, nullable=True)  # {lat, lng}
    source_phone = Column(String(50), nullable=True)
    source_categories = Column(JSON, nullable=True)

    # Confidence and matching
    match_confidence = Column(Float, nullable=False, default=1.0)
    distance_meters = Column(Float, nullable=True)  # Distance from primary location
    name_similarity = Column(Float, nullable=True)  # Name similarity score

    # Source metadata
    source_data = Column(JSON, nullable=True)  # Full source response
    discovered_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_updated = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Processing flags
    is_primary = Column(Boolean, nullable=False, default=False)  # Primary data source
    is_duplicate = Column(Boolean, nullable=False, default=False)
    is_conflicting = Column(Boolean, nullable=False, default=False)
    needs_review = Column(Boolean, nullable=False, default=False)

    # Relationships
    business = relationship("Business")

    __table_args__ = (
        UniqueConstraint(
            "source_provider", "source_id", name="uq_sourced_locations_provider_id"
        ),
        Index("idx_sourced_locations_business", "business_id", "is_primary"),
        Index("idx_sourced_locations_confidence", "match_confidence", "is_duplicate"),
        Index("idx_sourced_locations_review", "needs_review", "is_conflicting"),
    )

    def __repr__(self):
        return f"<SourcedLocation(business_id={self.business_id}, provider='{self.source_provider}', id='{self.source_id}')>"
