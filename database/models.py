"""
Database models for LeadFactory MVP
Based on PRD specifications for all domains (D0-D11)
"""

import enum
import uuid

from sqlalchemy import DECIMAL, JSON, TIMESTAMP, Boolean, CheckConstraint, Column, Date
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import Float, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
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

    __table_args__ = (Index("idx_gateway_usage_provider_created", "provider", "created_at"),)


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
    geo_bucket = Column(String(80), nullable=True, index=True)  # {affluence}-{density}-{broadband}
    vert_bucket = Column(String(80), nullable=True, index=True)  # {urgency}-{ticket}-{maturity}

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
    geo_bucket = Column(String(80), nullable=True, index=True)  # {affluence}-{density}-{broadband}
    vert_bucket = Column(String(80), nullable=True, index=True)  # {urgency}-{ticket}-{maturity}

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
    last_enriched_at = Column(TIMESTAMP, nullable=True)  # Track when last enriched

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
    from d3_assessment.models import AssessmentResult  # Used in relationships  # noqa: F401
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
    lead_id = Column(String(100), nullable=True)  # ForeignKey("dim_lead.id", ondelete="CASCADE") when lead table exists
    campaign_id = Column(
        Integer, nullable=True
    )  # ForeignKey("dim_campaign.id", ondelete="CASCADE") when campaign table exists
    cost_usd = Column(Numeric(10, 4), nullable=False)
    timestamp = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
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
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

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
        DatabaseAgnosticEnum(EnrichmentStatus), nullable=False, default=EnrichmentStatus.PENDING, index=True
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
        Index("ix_leads_email_domain", "email", "domain"),
        Index("ix_leads_enrichment_lookup", "enrichment_status", "enrichment_task_id"),
        Index("ix_leads_active_manual", "is_deleted", "is_manual"),
        Index("ix_leads_created_status", "created_at", "enrichment_status"),
        UniqueConstraint("email", name="uq_leads_email"),
        UniqueConstraint("domain", name="uq_leads_domain"),
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
        Index("ix_audit_leads_lead_id_timestamp", "lead_id", "timestamp"),
        Index("ix_audit_leads_action_timestamp", "action", "timestamp"),
        Index("ix_audit_leads_user_timestamp", "user_id", "timestamp"),
    )


# P1-060: Cost Guardrails Models
class GuardrailLimit(Base):
    """Configuration for cost guardrails and limits"""

    __tablename__ = "guardrail_limits"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    scope = Column(String(50), nullable=False)  # global, provider, campaign, operation, provider_operation
    period = Column(String(50), nullable=False)  # hourly, daily, weekly, monthly, total
    limit_usd = Column(Numeric(10, 4), nullable=False)

    # Scope-specific filters
    provider = Column(String(50), nullable=True, index=True)
    campaign_id = Column(Integer, nullable=True, index=True)
    operation = Column(String(100), nullable=True)

    # Thresholds and actions
    warning_threshold = Column(Float, nullable=False, default=0.8)
    critical_threshold = Column(Float, nullable=False, default=0.95)
    actions = Column(JSON, nullable=False)  # List of actions: log, alert, throttle, block, circuit_break

    # Circuit breaker settings
    circuit_breaker_enabled = Column(Boolean, nullable=False, default=False)
    circuit_breaker_failure_threshold = Column(Integer, nullable=False, default=5)
    circuit_breaker_recovery_timeout = Column(Integer, nullable=False, default=300)

    # Metadata
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    violations = relationship("GuardrailViolation", back_populates="limit")


class GuardrailViolation(Base):
    """Records of guardrail violations"""

    __tablename__ = "guardrail_violations"

    id = Column(Integer, primary_key=True)
    timestamp = Column(TIMESTAMP, nullable=False, server_default=func.now(), index=True)
    limit_id = Column(Integer, ForeignKey("guardrail_limits.id"), nullable=False)
    limit_name = Column(String(100), nullable=False)
    scope = Column(String(50), nullable=False)
    severity = Column(String(50), nullable=False, index=True)  # info, warning, critical, emergency
    current_spend = Column(Numeric(10, 4), nullable=False)
    limit_amount = Column(Numeric(10, 4), nullable=False)
    percentage_used = Column(Float, nullable=False)

    # Context
    provider = Column(String(50), nullable=True, index=True)
    campaign_id = Column(Integer, nullable=True)
    operation = Column(String(100), nullable=True)
    action_taken = Column(JSON, nullable=False)  # List of actions taken
    meta_data = Column(JSON, nullable=True)

    # Relationships
    limit = relationship("GuardrailLimit", back_populates="violations")

    __table_args__ = (Index("ix_guardrail_violations_timestamp_severity", "timestamp", "severity"),)


class RateLimit(Base):
    """Rate limit configuration for providers"""

    __tablename__ = "rate_limits"

    id = Column(Integer, primary_key=True)
    provider = Column(String(50), nullable=False)
    operation = Column(String(100), nullable=True)

    # Token bucket settings
    requests_per_minute = Column(Integer, nullable=False)
    burst_size = Column(Integer, nullable=False)

    # Cost-based rate limiting
    cost_per_minute = Column(Numeric(10, 4), nullable=True)
    cost_burst_size = Column(Numeric(10, 4), nullable=True)

    # Metadata
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (Index("ix_rate_limits_provider_operation", "provider", "operation", unique=True),)


class AlertHistory(Base):
    """History of alerts sent for guardrail violations"""

    __tablename__ = "alert_history"

    id = Column(Integer, primary_key=True)
    violation_id = Column(Integer, ForeignKey("guardrail_violations.id"), nullable=False)
    alert_channel = Column(String(50), nullable=False)  # email, slack, webhook, etc.
    recipient = Column(String(255), nullable=False)
    severity = Column(String(50), nullable=False)
    message = Column(Text, nullable=False)
    sent_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), index=True)
    success = Column(Boolean, nullable=False, default=True)
    error_message = Column(Text, nullable=True)
    meta_data = Column(JSON, nullable=True)

    # Relationships
    violation = relationship("GuardrailViolation")

    __table_args__ = (Index("ix_alert_history_sent_at_channel", "sent_at", "alert_channel"),)


# P0-021: Manual Badge System Models for CPO Lead Management
class BadgeType(str, enum.Enum):
    """Types of badges that can be assigned to leads"""

    PRIORITY = "priority"  # High priority lead
    QUALIFIED = "qualified"  # Qualified lead
    CONTACTED = "contacted"  # Lead has been contacted
    OPPORTUNITY = "opportunity"  # Sales opportunity
    CUSTOMER = "customer"  # Converted to customer
    BLOCKED = "blocked"  # Lead is blocked/unqualified
    FOLLOW_UP = "follow_up"  # Requires follow-up
    DEMO_SCHEDULED = "demo_scheduled"  # Demo scheduled
    PROPOSAL_SENT = "proposal_sent"  # Proposal sent
    CUSTOM = "custom"  # Custom badge


class Badge(Base):
    """Badge definitions for categorizing leads"""

    __tablename__ = "badges"

    # Primary identification
    id = Column(String, primary_key=True, default=generate_uuid)

    # Badge details
    name = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=True)
    badge_type = Column(DatabaseAgnosticEnum(BadgeType), nullable=False, index=True)

    # Visual properties
    color = Column(String(7), nullable=False, default="#007bff")  # Hex color
    icon = Column(String(50), nullable=True)  # Bootstrap icon name

    # Behavior
    is_system = Column(Boolean, nullable=False, default=False)  # System vs user-created
    is_active = Column(Boolean, nullable=False, default=True, index=True)

    # Metadata
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())
    created_by = Column(String(255), nullable=True)

    # Relationships
    lead_badges = relationship("LeadBadge", back_populates="badge", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_badges_name_active", "name", "is_active"),
        Index("ix_badges_type_active", "badge_type", "is_active"),
        UniqueConstraint("name", name="uq_badges_name"),
    )


class LeadBadge(Base):
    """Association table for leads and badges with audit trail"""

    __tablename__ = "lead_badges"

    # Primary identification
    id = Column(String, primary_key=True, default=generate_uuid)

    # Foreign keys
    lead_id = Column(String, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    badge_id = Column(String, ForeignKey("badges.id", ondelete="CASCADE"), nullable=False, index=True)

    # Assignment details
    assigned_by = Column(String(255), nullable=True)  # User who assigned the badge
    assigned_at = Column(TIMESTAMP, nullable=False, server_default=func.now())

    # Optional metadata
    notes = Column(Text, nullable=True)  # Reason for assignment
    expires_at = Column(TIMESTAMP, nullable=True)  # Optional expiration

    # Soft delete for audit trail
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    removed_at = Column(TIMESTAMP, nullable=True)
    removed_by = Column(String(255), nullable=True)
    removal_reason = Column(Text, nullable=True)

    # Relationships
    lead = relationship("Lead", backref="lead_badges")
    badge = relationship("Badge", back_populates="lead_badges")

    __table_args__ = (
        Index("ix_lead_badges_lead_active", "lead_id", "is_active"),
        Index("ix_lead_badges_badge_active", "badge_id", "is_active"),
        Index("ix_lead_badges_assigned_at", "assigned_at"),
        UniqueConstraint("lead_id", "badge_id", name="uq_lead_badges_lead_badge"),
    )


class BadgeAuditLog(Base):
    """Audit log for badge assignments and removals"""

    __tablename__ = "badge_audit_logs"

    # Primary identification
    id = Column(String, primary_key=True, default=generate_uuid)

    # Reference data
    lead_id = Column(String, nullable=False, index=True)
    badge_id = Column(String, nullable=False, index=True)
    lead_badge_id = Column(String, nullable=True)  # Reference to LeadBadge record

    # Audit details
    action = Column(String(20), nullable=False, index=True)  # assign, remove, expire
    timestamp = Column(TIMESTAMP, nullable=False, server_default=func.now(), index=True)

    # User context
    user_id = Column(String(255), nullable=True)
    user_ip = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)

    # Change details
    old_values = Column(JSON, nullable=True)
    new_values = Column(JSON, nullable=True)
    notes = Column(Text, nullable=True)

    # Metadata
    meta_data = Column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_badge_audit_lead_timestamp", "lead_id", "timestamp"),
        Index("ix_badge_audit_badge_timestamp", "badge_id", "timestamp"),
        Index("ix_badge_audit_action_timestamp", "action", "timestamp"),
        Index("ix_badge_audit_user_timestamp", "user_id", "timestamp"),
    )
