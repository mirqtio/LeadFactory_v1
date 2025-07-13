"""
Database models for LeadFactory MVP
Based on PRD specifications for all domains (D0-D11)
"""
import enum
import uuid

from sqlalchemy import (
    DECIMAL,
    JSON,
    TIMESTAMP,
    Boolean,
    CheckConstraint,
    Column,
    Date,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import (
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database.base import Base, DatabaseAgnosticEnum

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

    # Bucket columns for targeting intelligence (Phase 0.5)
    geo_bucket = Column(
        String(80), nullable=True, index=True
    )  # {affluence}-{density}-{broadband}
    vert_bucket = Column(
        String(80), nullable=True, index=True
    )  # {urgency}-{ticket}-{maturity}

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

    # Bucket columns for targeting intelligence (Phase 0.5)
    geo_bucket = Column(
        String(80), nullable=True, index=True
    )  # {affluence}-{density}-{broadband}
    vert_bucket = Column(
        String(80), nullable=True, index=True
    )  # {urgency}-{ticket}-{maturity}

    # PRD v1.2 additions
    domain_hash = Column(Text, nullable=True, index=True)
    phone_hash = Column(Text, nullable=True)

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


# Phase 0.5: Cost Tracking Models
class APICost(Base):
    """Track costs for all external API calls"""

    __tablename__ = "fct_api_cost"

    id = Column(Integer, primary_key=True)
    provider = Column(String(50), nullable=False)  # dataaxle, hunter, openai, etc.
    operation = Column(String(100), nullable=False)  # match_business, find_email, etc.
    lead_id = Column(
        Integer, nullable=True
    )  # ForeignKey("dim_lead.id", ondelete="CASCADE") when lead table exists
    campaign_id = Column(
        Integer, nullable=True
    )  # ForeignKey("dim_campaign.id", ondelete="CASCADE") when campaign table exists
    cost_usd = Column(Numeric(10, 4), nullable=False)
    timestamp = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    request_id = Column(String(100))  # For correlation with provider logs
    meta_data = Column(JSON)  # Additional context (e.g., match confidence)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    # Relationships (commented out until Lead and Campaign models exist)
    # lead = relationship("Lead", backref="api_costs")
    # campaign = relationship("Campaign", backref="api_costs")

    __table_args__ = (
        Index("idx_api_cost_provider", "provider"),
        Index("idx_api_cost_timestamp", "timestamp"),
        Index("idx_api_cost_lead", "lead_id"),
        Index("idx_api_cost_campaign", "campaign_id"),
        Index("idx_api_cost_provider_timestamp", "provider", "timestamp"),
    )


class DailyCostAggregate(Base):
    """Pre-aggregated daily costs for faster reporting"""

    __tablename__ = "agg_daily_cost"

    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)
    provider = Column(String(50), nullable=False)
    operation = Column(String(100))
    campaign_id = Column(
        Integer, nullable=True
    )  # ForeignKey("dim_campaign.id", ondelete="CASCADE") when campaign table exists
    total_cost_usd = Column(Numeric(10, 4), nullable=False)
    request_count = Column(Integer, nullable=False, default=0)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships (commented out until Campaign model exists)
    # campaign = relationship("Campaign", backref="daily_costs")

    __table_args__ = (
        Index(
            "idx_daily_cost_unique",
            "date",
            "provider",
            "operation",
            "campaign_id",
            unique=True,
        ),
    )


# Lead Explorer models - added for P0-021
class EnrichmentStatus(str, enum.Enum):
    """Status of lead enrichment process"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress" 
    COMPLETED = "completed"
    FAILED = "failed"


class AuditAction(str, enum.Enum):
    """Types of audit actions"""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class Lead(Base):
    """Lead model for managing prospect data with enrichment tracking."""
    __tablename__ = "leads"
    
    # Primary identification
    id = Column(String, primary_key=True, default=generate_uuid)
    
    # Core lead data
    email = Column(String(255), nullable=True, index=True)
    domain = Column(String(255), nullable=True, index=True)
    company_name = Column(String(500), nullable=True)
    contact_name = Column(String(255), nullable=True)
    
    # Enrichment tracking
    enrichment_status = Column(
        DatabaseAgnosticEnum(EnrichmentStatus),
        nullable=False,
        default=EnrichmentStatus.PENDING,
        index=True
    )
    enrichment_task_id = Column(String(255), nullable=True, index=True)
    enrichment_error = Column(Text, nullable=True)
    
    # Metadata
    is_manual = Column(Boolean, nullable=False, default=False, index=True)
    source = Column(String(100), nullable=True)
    
    # Soft delete
    is_deleted = Column(Boolean, nullable=False, default=False, index=True)
    
    # Timestamps
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), index=True)
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())
    deleted_at = Column(TIMESTAMP, nullable=True)
    
    # User tracking
    created_by = Column(String(255), nullable=True)
    updated_by = Column(String(255), nullable=True)
    deleted_by = Column(String(255), nullable=True)
    
    # Additional indexes for performance
    __table_args__ = (
        Index('ix_leads_email_domain', 'email', 'domain'),
        Index('ix_leads_enrichment_lookup', 'enrichment_status', 'enrichment_task_id'),
        Index('ix_leads_active_manual', 'is_deleted', 'is_manual'),
        Index('ix_leads_created_status', 'created_at', 'enrichment_status'),
        UniqueConstraint('email', name='uq_leads_email'),
        UniqueConstraint('domain', name='uq_leads_domain'),
    )


class AuditLogLead(Base):
    """Immutable audit log for all Lead mutations."""
    __tablename__ = "audit_log_leads"
    
    # Primary key
    id = Column(String, primary_key=True, default=generate_uuid)
    
    # Reference to the lead
    lead_id = Column(String, nullable=False, index=True)
    
    # Audit metadata
    action = Column(SQLEnum(AuditAction), nullable=False, index=True)
    timestamp = Column(TIMESTAMP, nullable=False, server_default=func.now(), index=True)
    
    # User context
    user_id = Column(String(255), nullable=True)
    user_ip = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    
    # Change data
    old_values = Column(Text, nullable=True)
    new_values = Column(Text, nullable=True)
    
    # Tamper detection
    checksum = Column(String(64), nullable=False)
    
    # Performance indexes
    __table_args__ = (
        Index('ix_audit_leads_lead_id_timestamp', 'lead_id', 'timestamp'),
        Index('ix_audit_leads_action_timestamp', 'action', 'timestamp'),
        Index('ix_audit_leads_user_timestamp', 'user_id', 'timestamp'),
    )
