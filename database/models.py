"""
Database models for LeadFactory MVP
Based on PRD specifications for all domains (D0-D11)
"""
import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional

from sqlalchemy import (DECIMAL, JSON, TIMESTAMP, Boolean, CheckConstraint,
                        Column, Date, DateTime)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import (Float, ForeignKey, Index, Integer, String, Text,
                        UniqueConstraint)
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database.base import Base, UUID

# D6 report models are imported separately for now due to module path issues
# from d6_reports.models import ReportGeneration, ReportTemplate, ReportSection, ReportDelivery


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
    assessments = relationship(
        "AssessmentResult",
        back_populates="business",
        foreign_keys="AssessmentResult.business_id",
    )
    scores = relationship("ScoringResult", back_populates="business")
    emails = relationship("Email", back_populates="business")
    purchases = relationship("Purchase", back_populates="business")

    __table_args__ = (
        Index("idx_business_vertical_city", "vertical", "city"),
        Index("idx_business_created", "created_at"),
    )


# D3: Assessment Models moved to d3_assessment/models.py


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

    __table_args__ = (Index("idx_purchase_status_created", "status", "created_at"),)


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


# D11: Pipeline/Experiment Models moved to d11_orchestration/models.py

# Import domain-specific models for relationships
try:
    from d3_assessment.models import AssessmentResult
except ImportError:
    # Handle case where d3_assessment models might not be available
    pass
