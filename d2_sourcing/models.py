"""
Database models for lead sourcing domain
"""

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from database.base import Base

# YelpMetadata class removed per P0-009 - Yelp provider no longer supported


class Company(Base):
    """
    Company model for d2_sourcing domain.

    Basic company information used for testing centralized fixtures.
    """

    __tablename__ = "d2_companies"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    domain = Column(String(255), nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Company(id={self.id}, name='{self.name}', domain='{self.domain}')>"


class SourcedLocation(Base):
    """Track different data sources for the same business location"""

    __tablename__ = "sourced_locations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    business_id = Column(String(36), ForeignKey("businesses.id"), nullable=False)

    # Source identification
    source_provider = Column(String(50), nullable=False, index=True)  # yelp, google, manual, etc.
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
    last_updated = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Processing flags
    is_primary = Column(Boolean, nullable=False, default=False)  # Primary data source
    is_duplicate = Column(Boolean, nullable=False, default=False)
    is_conflicting = Column(Boolean, nullable=False, default=False)
    needs_review = Column(Boolean, nullable=False, default=False)

    # Relationships
    business = relationship("Business")

    __table_args__ = (
        UniqueConstraint("source_provider", "source_id", name="uq_sourced_locations_provider_id"),
        Index("idx_sourced_locations_business", "business_id", "is_primary"),
        Index("idx_sourced_locations_confidence", "match_confidence", "is_duplicate"),
        Index("idx_sourced_locations_review", "needs_review", "is_conflicting"),
    )

    def __repr__(self):
        return f"<SourcedLocation(business_id={self.business_id}, provider='{self.source_provider}', id='{self.source_id}')>"
