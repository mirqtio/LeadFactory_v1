"""
Email Delivery Models

SQLAlchemy models for tracking email delivery, bounces, suppression lists,
and delivery events for compliance and monitoring.

Acceptance Criteria:
- Email send tracking ✓
- Bounce tracking model ✓ 
- Suppression list ✓
- Event timestamps ✓
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

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
from database.base import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database.base import Base


class DeliveryStatus(str, Enum):
    """Email delivery status enumeration"""

    PENDING = "pending"
    PROCESSING = "processing"
    SENT = "sent"
    DELIVERED = "delivered"
    BOUNCED = "bounced"
    FAILED = "failed"
    DEFERRED = "deferred"
    SUPPRESSED = "suppressed"
    SPAM = "spam"
    DROPPED = "dropped"
    PROCESSED = "processed"
    BLOCKED = "blocked"


class BounceType(str, Enum):
    """Email bounce type enumeration"""

    SOFT = "soft"
    HARD = "hard"
    BLOCK = "block"
    SPAM = "spam"
    UNSUBSCRIBE = "unsubscribe"


class EventType(str, Enum):
    """Delivery event type enumeration"""

    SENT = "sent"
    DELIVERED = "delivered"
    OPENED = "opened"
    CLICKED = "clicked"
    BOUNCED = "bounced"
    DROPPED = "dropped"
    SPAMREPORT = "spamreport"
    SPAM = "spam"
    UNSUBSCRIBE = "unsubscribe"
    UNSUBSCRIBED = "unsubscribed"
    PROCESSED = "processed"
    DEFERRED = "deferred"
    BLOCKED = "blocked"
    FAILED = "failed"


class SuppressionReason(str, Enum):
    """Suppression reason enumeration"""

    UNSUBSCRIBE = "unsubscribe"
    BOUNCE = "bounce"
    SPAM_REPORT = "spam_report"
    INVALID_EMAIL = "invalid_email"
    GLOBAL_SUPPRESSION = "global_suppression"
    GROUP_SUPPRESSION = "group_suppression"
    MANUAL_SUPPRESSION = "manual_suppression"


class EmailDelivery(Base):
    """
    Email delivery tracking model

    Tracks individual email sends with delivery status,
    metadata, and SendGrid integration details.
    """

    __tablename__ = "email_deliveries"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # Unique delivery identifier
    delivery_id = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        default=lambda: str(uuid.uuid4()),
    )

    # Recipient information
    to_email = Column(String(255), nullable=False, index=True)
    to_name = Column(String(255), nullable=True)

    # Sender information
    from_email = Column(String(255), nullable=False)
    from_name = Column(String(255), nullable=True)

    # Email content
    subject = Column(String(998), nullable=False)  # Max subject length
    html_content = Column(Text, nullable=True)
    text_content = Column(Text, nullable=True)

    # Delivery tracking
    status = Column(
        String(50), nullable=False, default=DeliveryStatus.PENDING.value, index=True
    )

    # SendGrid integration
    sendgrid_message_id = Column(String(255), nullable=True, index=True)
    sendgrid_batch_id = Column(String(255), nullable=True, index=True)

    # Categories and tags for organization
    categories = Column(JSON, nullable=True)  # List of category strings
    custom_args = Column(JSON, nullable=True)  # Custom metadata

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    sent_at = Column(DateTime(timezone=True), nullable=True, index=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)

    # Business context
    business_id = Column(String(255), nullable=True, index=True)  # Associated business
    campaign_id = Column(String(255), nullable=True, index=True)  # Campaign tracking
    personalization_id = Column(
        String(255), nullable=True, index=True
    )  # Personalization reference

    # Cost tracking
    estimated_cost = Column(Float, nullable=True, default=0.0)

    # Error tracking
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=3)

    # Relationships
    bounce_tracking = relationship(
        "BounceTracking", back_populates="email_delivery", uselist=False
    )
    delivery_events = relationship(
        "DeliveryEvent", back_populates="email_delivery", cascade="all, delete-orphan"
    )

    # Indexes for performance
    __table_args__ = (
        Index("idx_email_deliveries_recipient", "to_email", "created_at"),
        Index("idx_email_deliveries_status_created", "status", "created_at"),
        Index("idx_email_deliveries_sendgrid", "sendgrid_message_id"),
        Index("idx_email_deliveries_business", "business_id", "created_at"),
        Index("idx_email_deliveries_campaign", "campaign_id", "created_at"),
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.status is None:
            self.status = DeliveryStatus.PENDING.value
        if self.delivery_id is None:
            self.delivery_id = str(uuid.uuid4())
        if self.retry_count is None:
            self.retry_count = 0
        if self.max_retries is None:
            self.max_retries = 3
        if self.estimated_cost is None:
            self.estimated_cost = 0.0

    def __repr__(self):
        return f"<EmailDelivery(id={self.id}, to_email='{self.to_email}', status='{self.status}')>"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            "id": self.id,
            "delivery_id": self.delivery_id,
            "to_email": self.to_email,
            "to_name": self.to_name,
            "from_email": self.from_email,
            "from_name": self.from_name,
            "subject": self.subject,
            "status": self.status,
            "sendgrid_message_id": self.sendgrid_message_id,
            "sendgrid_batch_id": self.sendgrid_batch_id,
            "categories": self.categories,
            "custom_args": self.custom_args,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "delivered_at": self.delivered_at.isoformat()
            if self.delivered_at
            else None,
            "business_id": self.business_id,
            "campaign_id": self.campaign_id,
            "personalization_id": self.personalization_id,
            "estimated_cost": self.estimated_cost,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
        }


class BounceTracking(Base):
    """
    Bounce tracking model

    Tracks email bounces with detailed bounce information,
    types, and SendGrid bounce data.
    """

    __tablename__ = "bounce_tracking"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # Associated email delivery
    email_delivery_id = Column(
        Integer, ForeignKey("email_deliveries.id"), nullable=False, index=True
    )

    # Bounce details
    bounce_type = Column(
        String(50), nullable=False, index=True
    )  # soft, hard, block, spam
    bounce_reason = Column(String(255), nullable=True)
    bounce_classification = Column(
        String(100), nullable=True
    )  # SendGrid classification

    # Email address that bounced
    email = Column(String(255), nullable=False, index=True)

    # SendGrid bounce data
    sendgrid_event_id = Column(String(255), nullable=True, unique=True)
    sendgrid_bounce_data = Column(JSON, nullable=True)  # Full SendGrid event data

    # SMTP details
    smtp_id = Column(String(255), nullable=True)

    # Timestamps
    bounced_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Additional metadata
    user_agent = Column(String(500), nullable=True)
    ip_address = Column(String(45), nullable=True)  # IPv6 support

    # Relationships
    email_delivery = relationship("EmailDelivery", back_populates="bounce_tracking")

    # Indexes for performance
    __table_args__ = (
        Index("idx_bounce_tracking_email", "email", "bounced_at"),
        Index("idx_bounce_tracking_type", "bounce_type", "bounced_at"),
        Index("idx_bounce_tracking_delivery", "email_delivery_id"),
    )

    def __repr__(self):
        return f"<BounceTracking(id={self.id}, email='{self.email}', type='{self.bounce_type}')>"


class SuppressionList(Base):
    """
    Email suppression list model

    Manages suppressed email addresses to maintain compliance
    and avoid sending to bounced/unsubscribed addresses.
    """

    __tablename__ = "suppression_list"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # Suppressed email address
    email = Column(String(255), nullable=False, unique=True, index=True)

    # Suppression details
    reason = Column(String(100), nullable=False, index=True)  # Why suppressed
    source = Column(String(100), nullable=True)  # Where suppression came from

    # Suppression metadata
    suppression_data = Column(JSON, nullable=True)  # Additional context

    # Timestamps
    suppressed_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Management fields
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    expires_at = Column(
        DateTime(timezone=True), nullable=True, index=True
    )  # Optional expiration

    # Administrative
    created_by = Column(String(255), nullable=True)  # User/system that added
    notes = Column(Text, nullable=True)

    # Indexes for performance
    __table_args__ = (
        Index("idx_suppression_email_active", "email", "is_active"),
        Index("idx_suppression_reason", "reason", "suppressed_at"),
        Index("idx_suppression_expires", "expires_at"),
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.is_active is None:
            self.is_active = True

    def __repr__(self):
        return f"<SuppressionList(id={self.id}, email='{self.email}', reason='{self.reason}')>"

    def is_suppressed(self) -> bool:
        """Check if suppression is currently active"""
        if not self.is_active:
            return False

        if self.expires_at:
            # Handle timezone comparison properly
            now = datetime.now(timezone.utc)
            expires_at = self.expires_at

            # If expires_at is naive, assume UTC
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)

            if now > expires_at:
                return False

        return True


class DeliveryEvent(Base):
    """
    Delivery event tracking model

    Tracks all email delivery events from SendGrid webhooks
    including opens, clicks, bounces, etc.
    """

    __tablename__ = "delivery_events"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # Associated email delivery
    email_delivery_id = Column(
        Integer, ForeignKey("email_deliveries.id"), nullable=False, index=True
    )

    # Event details
    event_type = Column(String(50), nullable=False, index=True)
    event_data = Column(JSON, nullable=True)  # Full event payload

    # SendGrid event details
    sendgrid_event_id = Column(String(255), nullable=True, unique=True)
    sendgrid_message_id = Column(String(255), nullable=True, index=True)

    # Timestamp information
    event_timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    processed_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Event metadata
    user_agent = Column(String(500), nullable=True)
    ip_address = Column(String(45), nullable=True)  # IPv6 support
    url = Column(String(1000), nullable=True)  # For click events

    # Processing tracking
    is_processed = Column(Boolean, nullable=False, default=True, index=True)
    processing_error = Column(Text, nullable=True)

    # Relationships
    email_delivery = relationship("EmailDelivery", back_populates="delivery_events")

    # Ensure unique events per delivery
    __table_args__ = (
        UniqueConstraint(
            "email_delivery_id",
            "event_type",
            "event_timestamp",
            name="uq_delivery_event_unique",
        ),
        Index("idx_delivery_events_type_time", "event_type", "event_timestamp"),
        Index("idx_delivery_events_sendgrid", "sendgrid_message_id", "event_type"),
        Index("idx_delivery_events_processed", "is_processed", "processed_at"),
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.is_processed is None:
            self.is_processed = True

    def __repr__(self):
        return f"<DeliveryEvent(id={self.id}, event_type='{self.event_type}', timestamp={self.event_timestamp})>"
