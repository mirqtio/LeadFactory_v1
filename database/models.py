"""
Database models for LeadFactory MVP
Based on PRD specifications for all domains (D0-D11)
"""
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from decimal import Decimal

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text, 
    ForeignKey, UniqueConstraint, CheckConstraint, Index,
    DECIMAL, JSON, Date, TIMESTAMP, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import UUID, INET, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from database.base import Base


def generate_uuid():
    """Generate a new UUID"""
    return str(uuid.uuid4())


# Enums
class GeoType(str, enum.Enum):
    ZIP = "zip"
    CITY = "city"
    METRO = "metro"
    STATE = "state"


class BatchStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class EmailStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    OPENED = "opened"
    CLICKED = "clicked"
    BOUNCED = "bounced"
    COMPLAINED = "complained"
    UNSUBSCRIBED = "unsubscribed"


class PurchaseStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    REFUNDED = "refunded"
    FAILED = "failed"


class ExperimentStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


# D0: Gateway Models
class GatewayUsage(Base):
    __tablename__ = "gateway_usage"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    provider = Column(String(50), nullable=False)
    endpoint = Column(String(100), nullable=False)
    cost_usd = Column(DECIMAL(10, 6))
    cache_hit = Column(Boolean, default=False)
    response_time_ms = Column(Integer)
    status_code = Column(Integer)
    error_message = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    __table_args__ = (
        Index("idx_gateway_usage_provider_created", "provider", "created_at"),
    )


class GatewayRateLimit(Base):
    __tablename__ = "gateway_rate_limits"
    
    provider = Column(String(50), primary_key=True)
    daily_limit = Column(Integer, nullable=False)
    daily_used = Column(Integer, default=0)
    burst_limit = Column(Integer, nullable=False)
    reset_at = Column(TIMESTAMP, nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())


# D1: Targeting Models
class Target(Base):
    __tablename__ = "targets"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    geo_type = Column(SQLEnum(GeoType), nullable=False)
    geo_value = Column(String(100), nullable=False)
    vertical = Column(String(50), nullable=False)
    estimated_businesses = Column(Integer)
    priority_score = Column(DECIMAL(3, 2), default=0.5)
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    # Relationships
    batches = relationship("Batch", back_populates="target")
    
    __table_args__ = (
        UniqueConstraint("geo_type", "geo_value", "vertical"),
        CheckConstraint("priority_score >= 0 AND priority_score <= 1"),
    )


class Batch(Base):
    __tablename__ = "batches"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    target_id = Column(String, ForeignKey("targets.id"))
    batch_date = Column(Date, nullable=False)
    planned_size = Column(Integer, nullable=False)
    actual_size = Column(Integer)
    status = Column(SQLEnum(BatchStatus), default=BatchStatus.PENDING)
    started_at = Column(TIMESTAMP)
    completed_at = Column(TIMESTAMP)
    error_message = Column(Text)
    
    # Relationships
    target = relationship("Target", back_populates="batches")
    
    __table_args__ = (
        UniqueConstraint("target_id", "batch_date"),
        Index("idx_batch_date_status", "batch_date", "status"),
    )


# D2: Business Model (Core entity)
class Business(Base):
    __tablename__ = "businesses"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    yelp_id = Column(String(100), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    url = Column(String(500))
    phone = Column(String(20))
    email = Column(String(255))
    
    # Location
    address = Column(String(500))
    city = Column(String(100))
    state = Column(String(2))
    zip_code = Column(String(10))
    latitude = Column(Float)
    longitude = Column(Float)
    
    # Business info
    vertical = Column(String(50))
    categories = Column(JSON)
    
    # Enrichment data
    place_id = Column(String(100))  # Google Place ID
    rating = Column(DECIMAL(2, 1))
    user_ratings_total = Column(Integer)
    price_level = Column(Integer)
    opening_hours = Column(JSON)
    website = Column(String(500))
    business_status = Column(String(20), default="OPERATIONAL")
    
    # Metadata
    raw_data = Column(JSON)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    assessments = relationship("AssessmentResult", back_populates="business")
    scores = relationship("ScoringResult", back_populates="business")
    emails = relationship("Email", back_populates="business")
    purchases = relationship("Purchase", back_populates="business")
    
    __table_args__ = (
        Index("idx_business_vertical_city", "vertical", "city"),
        Index("idx_business_created", "created_at"),
    )


# D3: Assessment Models
class AssessmentResult(Base):
    __tablename__ = "assessment_results"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    business_id = Column(String, ForeignKey("businesses.id"))
    assessment_type = Column(String(50), nullable=False)
    
    # PageSpeed metrics
    performance_score = Column(Integer)
    seo_score = Column(Integer)
    accessibility_score = Column(Integer)
    best_practices_score = Column(Integer)
    lcp_ms = Column(Integer)
    fid_ms = Column(Integer)
    cls = Column(DECIMAL(5, 3))
    
    # Analysis results
    issues_json = Column(JSON)
    recommendations_json = Column(JSON)
    
    # Metadata
    cost_usd = Column(DECIMAL(10, 6))
    duration_ms = Column(Integer)
    error_message = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    # Relationships
    business = relationship("Business", back_populates="assessments")
    
    __table_args__ = (
        Index("idx_assessment_business_type", "business_id", "assessment_type"),
    )


# D5: Scoring Models
class ScoringResult(Base):
    __tablename__ = "scoring_results"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    business_id = Column(String, ForeignKey("businesses.id"))
    
    score_raw = Column(DECIMAL(5, 4))
    score_pct = Column(Integer)
    tier = Column(String(1))  # A, B, C, D
    confidence = Column(DECIMAL(3, 2))
    scoring_version = Column(Integer)
    score_breakdown = Column(JSON)
    passed_gate = Column(Boolean)
    
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    # Relationships
    business = relationship("Business", back_populates="scores")
    
    __table_args__ = (
        CheckConstraint("tier IN ('A', 'B', 'C', 'D')"),
        Index("idx_scoring_business_created", "business_id", "created_at"),
        Index("idx_scoring_tier_created", "tier", "created_at"),
    )


# D7: Purchase Models
class Purchase(Base):
    __tablename__ = "purchases"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    business_id = Column(String, ForeignKey("businesses.id"))
    stripe_session_id = Column(String(255), unique=True)
    stripe_payment_intent_id = Column(String(255))
    stripe_customer_id = Column(String(255))
    
    amount_cents = Column(Integer, nullable=False)
    currency = Column(String(3), default="USD")
    customer_email = Column(String(255), nullable=False)
    
    # Attribution
    source = Column(String(50))
    campaign = Column(String(100))
    attribution_metadata = Column(JSON)
    
    # Status tracking
    status = Column(SQLEnum(PurchaseStatus), default=PurchaseStatus.PENDING)
    completed_at = Column(TIMESTAMP)
    refunded_at = Column(TIMESTAMP)
    
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    business = relationship("Business", back_populates="purchases")
    
    __table_args__ = (
        Index("idx_purchase_status_created", "status", "created_at"),
    )


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    
    id = Column(String(255), primary_key=True)  # Stripe event ID
    type = Column(String(50), nullable=False)
    processed_at = Column(TIMESTAMP, server_default=func.now())
    payload = Column(JSON)


# D9: Email Models
class Email(Base):
    __tablename__ = "emails"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    business_id = Column(String, ForeignKey("businesses.id"))
    
    # Content
    subject = Column(String(500), nullable=False)
    preview_text = Column(String(200))
    html_body = Column(Text, nullable=False)
    text_body = Column(Text)
    
    # Tracking
    sendgrid_message_id = Column(String(100))
    status = Column(SQLEnum(EmailStatus), default=EmailStatus.PENDING)
    
    # Timestamps
    sent_at = Column(TIMESTAMP)
    delivered_at = Column(TIMESTAMP)
    opened_at = Column(TIMESTAMP)
    clicked_at = Column(TIMESTAMP)
    bounced_at = Column(TIMESTAMP)
    unsubscribed_at = Column(TIMESTAMP)
    complained_at = Column(TIMESTAMP)
    
    # Additional data
    bounce_reason = Column(Text)
    spam_score = Column(DECIMAL(3, 1))
    
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    # Relationships
    business = relationship("Business", back_populates="emails")
    clicks = relationship("EmailClick", back_populates="email")
    
    __table_args__ = (
        Index("idx_email_business_created", "business_id", "created_at"),
        Index("idx_email_status", "status"),
    )


class EmailSuppression(Base):
    __tablename__ = "email_suppressions"
    
    email_hash = Column(String(64), primary_key=True)  # SHA-256 of lowercase email
    reason = Column(String(100), nullable=False)
    source = Column(String(50), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())


class EmailClick(Base):
    __tablename__ = "email_clicks"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    email_id = Column(String, ForeignKey("emails.id"))
    url = Column(Text, nullable=False)
    clicked_at = Column(TIMESTAMP, server_default=func.now())
    ip_address = Column(String(45))  # Support IPv6
    user_agent = Column(Text)
    
    # Relationships
    email = relationship("Email", back_populates="clicks")


# D11: Pipeline/Experiment Models
class PipelineRun(Base):
    __tablename__ = "pipeline_runs"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    flow_name = Column(String(100), nullable=False)
    flow_run_id = Column(String(100), unique=True)
    
    started_at = Column(TIMESTAMP, nullable=False)
    completed_at = Column(TIMESTAMP)
    
    status = Column(String(20), default="running")
    error_message = Column(Text)
    
    # Metrics
    total_businesses = Column(Integer)
    total_assessed = Column(Integer)
    total_qualified = Column(Integer)
    total_emails_sent = Column(Integer)
    total_purchases = Column(Integer)
    
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    __table_args__ = (
        Index("idx_pipeline_run_created", "created_at"),
    )


class Experiment(Base):
    __tablename__ = "experiments"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    
    status = Column(SQLEnum(ExperimentStatus), default=ExperimentStatus.DRAFT)
    hypothesis = Column(Text)
    success_metrics = Column(JSON)
    
    variants = Column(JSON, nullable=False)  # [{name, weight, config}]
    
    started_at = Column(TIMESTAMP)
    ended_at = Column(TIMESTAMP)
    
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    # Relationships
    assignments = relationship("ExperimentAssignment", back_populates="experiment")


class ExperimentAssignment(Base):
    __tablename__ = "experiment_assignments"
    
    experiment_id = Column(String, ForeignKey("experiments.id"), primary_key=True)
    business_id = Column(String, ForeignKey("businesses.id"), primary_key=True)
    variant = Column(String(50), nullable=False)
    assigned_at = Column(TIMESTAMP, server_default=func.now())
    
    # Relationships
    experiment = relationship("Experiment", back_populates="assignments")