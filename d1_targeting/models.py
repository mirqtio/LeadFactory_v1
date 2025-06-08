"""
Database models for targeting domain
"""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, JSON, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid

from database.base import Base
from database.models import Target
from .types import VerticalMarket, GeographyLevel, CampaignStatus, TargetQualificationStatus


class TargetUniverse(Base):
    """Definition of a target universe for campaigns"""
    __tablename__ = "target_universes"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Targeting criteria
    verticals = Column(JSON, nullable=False)  # List of VerticalMarket values
    geography_config = Column(JSON, nullable=False)  # Geographic constraints
    qualification_rules = Column(JSON, nullable=True)  # Automatic qualification rules
    
    # Universe metrics
    estimated_size = Column(Integer, nullable=True)
    actual_size = Column(Integer, nullable=False, default=0)
    qualified_count = Column(Integer, nullable=False, default=0)
    last_refresh = Column(DateTime, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(255), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    
    # Relationships
    campaigns = relationship("Campaign", back_populates="target_universe")
    
    def __repr__(self):
        return f"<TargetUniverse(id={self.id}, name='{self.name}', size={self.actual_size})>"


class Campaign(Base):
    """Marketing campaign targeting specific universe"""
    __tablename__ = "campaigns"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Campaign configuration
    target_universe_id = Column(UUID(as_uuid=True), ForeignKey("target_universes.id"), nullable=False)
    status = Column(String(20), nullable=False, default="draft", index=True)
    campaign_type = Column(String(50), nullable=False, default="lead_generation")
    
    # Scheduling
    scheduled_start = Column(DateTime, nullable=True)
    scheduled_end = Column(DateTime, nullable=True)
    actual_start = Column(DateTime, nullable=True)
    actual_end = Column(DateTime, nullable=True)
    
    # Batch processing settings
    batch_settings = Column(JSON, nullable=True)  # BatchSchedule configuration
    
    # Campaign metrics
    total_targets = Column(Integer, nullable=False, default=0)
    contacted_targets = Column(Integer, nullable=False, default=0)
    responded_targets = Column(Integer, nullable=False, default=0)
    converted_targets = Column(Integer, nullable=False, default=0)
    excluded_targets = Column(Integer, nullable=False, default=0)
    
    # Cost tracking
    total_cost = Column(Float, nullable=False, default=0.0)
    cost_per_contact = Column(Float, nullable=True)
    cost_per_conversion = Column(Float, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(255), nullable=True)
    
    # Relationships
    target_universe = relationship("TargetUniverse", back_populates="campaigns")
    campaign_targets = relationship("CampaignTarget", back_populates="campaign")
    campaign_batches = relationship("CampaignBatch", back_populates="campaign")
    
    __table_args__ = (
        Index('idx_campaigns_status', 'status'),
        Index('idx_campaigns_schedule', 'scheduled_start', 'scheduled_end'),
    )
    
    def __repr__(self):
        return f"<Campaign(id={self.id}, name='{self.name}', status='{self.status}')>"


class CampaignTarget(Base):
    """Association between campaigns and targets with specific status"""
    __tablename__ = "campaign_targets"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=False)
    target_id = Column(UUID(as_uuid=True), ForeignKey("targets.id"), nullable=False)
    
    # Target-specific campaign status
    status = Column(String(20), nullable=False, default="pending", index=True)
    assigned_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    first_contacted = Column(DateTime, nullable=True)
    last_contacted = Column(DateTime, nullable=True)
    contact_attempts = Column(Integer, nullable=False, default=0)
    
    # Contact history
    contact_methods_used = Column(JSON, nullable=True)  # List of methods tried
    response_received = Column(Boolean, nullable=False, default=False)
    response_date = Column(DateTime, nullable=True)
    conversion_date = Column(DateTime, nullable=True)
    
    # Cost tracking for this target
    contact_cost = Column(Float, nullable=False, default=0.0)
    
    # Exclusion tracking
    excluded = Column(Boolean, nullable=False, default=False)
    exclusion_reason = Column(String(255), nullable=True)
    excluded_at = Column(DateTime, nullable=True)
    
    # Relationships
    campaign = relationship("Campaign", back_populates="campaign_targets")
    target = relationship("Target", back_populates="campaign_targets")
    
    __table_args__ = (
        UniqueConstraint('campaign_id', 'target_id', name='uq_campaign_targets'),
        Index('idx_campaign_targets_status', 'campaign_id', 'status'),
        Index('idx_campaign_targets_contact', 'campaign_id', 'first_contacted'),
    )
    
    def __repr__(self):
        return f"<CampaignTarget(campaign_id={self.campaign_id}, target_id={self.target_id}, status='{self.status}')>"


class CampaignBatch(Base):
    """Batch processing records for campaigns"""
    __tablename__ = "campaign_batches"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=False)
    
    # Batch details
    batch_number = Column(Integer, nullable=False)
    batch_size = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="pending", index=True)
    
    # Processing timestamps
    scheduled_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Results
    targets_processed = Column(Integer, nullable=False, default=0)
    targets_contacted = Column(Integer, nullable=False, default=0)
    targets_failed = Column(Integer, nullable=False, default=0)
    
    # Error tracking
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    
    # Cost tracking
    batch_cost = Column(Float, nullable=False, default=0.0)
    
    # Relationships
    campaign = relationship("Campaign", back_populates="campaign_batches")
    
    __table_args__ = (
        UniqueConstraint('campaign_id', 'batch_number', name='uq_campaign_batches'),
        Index('idx_campaign_batches_status', 'campaign_id', 'status'),
        Index('idx_campaign_batches_schedule', 'scheduled_at', 'status'),
    )
    
    def __repr__(self):
        return f"<CampaignBatch(id={self.id}, campaign_id={self.campaign_id}, batch={self.batch_number})>"


class GeographicBoundary(Base):
    """Predefined geographic boundaries for targeting"""
    __tablename__ = "geographic_boundaries"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, index=True)
    level = Column(String(20), nullable=False, index=True)  # GeographyLevel enum
    parent_id = Column(UUID(as_uuid=True), ForeignKey("geographic_boundaries.id"), nullable=True)
    
    # Geographic identifiers
    code = Column(String(20), nullable=True, index=True)  # State code, ZIP, etc.
    fips_code = Column(String(20), nullable=True, index=True)  # Federal codes
    
    # Boundary data
    center_latitude = Column(Float, nullable=True)
    center_longitude = Column(Float, nullable=True)
    boundary_polygon = Column(JSON, nullable=True)  # GeoJSON polygon
    
    # Hierarchy relationships
    country = Column(String(10), nullable=False, default="US", index=True)
    state_code = Column(String(10), nullable=True, index=True)
    county_name = Column(String(100), nullable=True, index=True)
    
    # Metadata
    population = Column(Integer, nullable=True)
    area_sq_miles = Column(Float, nullable=True)
    timezone = Column(String(50), nullable=True)
    
    # Data source
    data_source = Column(String(50), nullable=True)
    last_updated = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    children = relationship("GeographicBoundary", backref="parent", remote_side=[id])
    
    __table_args__ = (
        Index('idx_geo_hierarchy', 'level', 'country', 'state_code'),
        Index('idx_geo_code', 'level', 'code'),
        UniqueConstraint('level', 'code', 'country', name='uq_geo_boundaries'),
    )
    
    def __repr__(self):
        return f"<GeographicBoundary(id={self.id}, name='{self.name}', level='{self.level}')>"