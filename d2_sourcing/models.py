"""
Database models for lead sourcing domain
"""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, JSON, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime
import uuid

from database.base import Base


class Business(Base):
    """Core business entity for lead sourcing"""
    __tablename__ = "businesses"
    
    # Primary identification
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    yelp_id = Column(String(255), unique=True, nullable=True, index=True)
    
    # Basic business information
    name = Column(String(255), nullable=False, index=True)
    alias = Column(String(255), nullable=True)
    image_url = Column(String(500), nullable=True)
    is_claimed = Column(Boolean, nullable=True)
    is_closed = Column(Boolean, nullable=False, default=False, index=True)
    
    # Location information
    address1 = Column(String(255), nullable=True)
    address2 = Column(String(255), nullable=True)
    address3 = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True, index=True)
    zip_code = Column(String(20), nullable=True, index=True)
    country = Column(String(10), nullable=False, default="US", index=True)
    state = Column(String(10), nullable=True, index=True)
    display_address = Column(JSON, nullable=True)  # Array of formatted address lines
    
    # Coordinates
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    
    # Contact information
    phone = Column(String(50), nullable=True, index=True)
    display_phone = Column(String(50), nullable=True)
    
    # Business metrics
    review_count = Column(Integer, nullable=True, default=0)
    rating = Column(Float, nullable=True)
    price = Column(String(10), nullable=True)  # $, $$, $$$, $$$$
    
    # Categories (stored as JSONB for efficient querying)
    categories = Column(JSONB, nullable=True)  # Array of category objects
    
    # Business hours (stored as JSONB)
    hours = Column(JSONB, nullable=True)  # Structured hours data
    
    # Special features
    transactions = Column(JSON, nullable=True)  # Array of supported transactions
    attributes = Column(JSONB, nullable=True)  # Business attributes
    
    # Data quality and sourcing
    data_quality_score = Column(Float, nullable=True)
    source_confidence = Column(Float, nullable=True, default=1.0)
    last_verified = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    yelp_metadata = relationship("YelpMetadata", back_populates="business", uselist=False)
    sourced_locations = relationship("SourcedLocation", back_populates="business")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_businesses_location', 'city', 'state', 'zip_code'),
        Index('idx_businesses_geo', 'latitude', 'longitude'),
        Index('idx_businesses_rating', 'rating', 'review_count'),
        Index('idx_businesses_categories', 'categories', postgresql_using='gin'),
        Index('idx_businesses_attributes', 'attributes', postgresql_using='gin'),
        Index('idx_businesses_search', 'name', 'city', 'state'),
    )
    
    def __repr__(self):
        return f"<Business(id={self.id}, name='{self.name}', city='{self.city}')>"


class YelpMetadata(Base):
    """Yelp-specific metadata for businesses"""
    __tablename__ = "yelp_metadata"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id = Column(UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False, unique=True)
    
    # Yelp-specific fields
    yelp_url = Column(String(500), nullable=True)
    photos = Column(JSON, nullable=True)  # Array of photo URLs
    special_hours = Column(JSONB, nullable=True)  # Special/holiday hours
    messaging = Column(JSONB, nullable=True)  # Messaging info
    
    # API response metadata
    raw_response = Column(JSONB, nullable=True)  # Full Yelp API response
    api_version = Column(String(20), nullable=True)
    response_timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Data processing flags
    processed = Column(Boolean, nullable=False, default=False)
    enriched = Column(Boolean, nullable=False, default=False)
    normalized = Column(Boolean, nullable=False, default=False)
    
    # Quality metrics
    completeness_score = Column(Float, nullable=True)  # How complete is the data
    freshness_score = Column(Float, nullable=True)     # How recent is the data
    accuracy_score = Column(Float, nullable=True)      # Estimated accuracy
    
    # Update tracking
    last_fetched = Column(DateTime, nullable=False, default=datetime.utcnow)
    fetch_count = Column(Integer, nullable=False, default=1)
    last_changed = Column(DateTime, nullable=True)
    
    # Relationships
    business = relationship("Business", back_populates="yelp_metadata")
    
    __table_args__ = (
        Index('idx_yelp_metadata_processed', 'processed', 'enriched'),
        Index('idx_yelp_metadata_freshness', 'last_fetched', 'freshness_score'),
    )
    
    def __repr__(self):
        return f"<YelpMetadata(business_id={self.business_id}, processed={self.processed})>"


class SourcedLocation(Base):
    """Track different data sources for the same business location"""
    __tablename__ = "sourced_locations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id = Column(UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False)
    
    # Source identification
    source_provider = Column(String(50), nullable=False, index=True)  # yelp, google, manual, etc.
    source_id = Column(String(255), nullable=False, index=True)        # Provider's ID
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
    name_similarity = Column(Float, nullable=True)   # Name similarity score
    
    # Source metadata
    source_data = Column(JSONB, nullable=True)  # Full source response
    discovered_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_updated = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Processing flags
    is_primary = Column(Boolean, nullable=False, default=False)  # Primary data source
    is_duplicate = Column(Boolean, nullable=False, default=False)
    is_conflicting = Column(Boolean, nullable=False, default=False)
    needs_review = Column(Boolean, nullable=False, default=False)
    
    # Relationships
    business = relationship("Business", back_populates="sourced_locations")
    
    __table_args__ = (
        UniqueConstraint('source_provider', 'source_id', name='uq_sourced_locations_provider_id'),
        Index('idx_sourced_locations_business', 'business_id', 'is_primary'),
        Index('idx_sourced_locations_confidence', 'match_confidence', 'is_duplicate'),
        Index('idx_sourced_locations_review', 'needs_review', 'is_conflicting'),
    )
    
    def __repr__(self):
        return f"<SourcedLocation(business_id={self.business_id}, provider='{self.source_provider}', id='{self.source_id}')>"