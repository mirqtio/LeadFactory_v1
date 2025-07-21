"""
P2-010: Collaborative Bucket Models

Database models for multi-user bucket collaboration including
ownership, permissions, activity tracking, and version control.
"""

import enum

from sqlalchemy import JSON, Boolean, Column, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, Index, Integer, String, Table, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database.base import Base


def generate_uuid():
    """Generate a new UUID"""
    import uuid

    return str(uuid.uuid4())


class BucketPermission(str, enum.Enum):
    """Permission levels for bucket access"""

    OWNER = "owner"  # Full control, can delete bucket
    ADMIN = "admin"  # Can manage permissions, edit everything
    EDITOR = "editor"  # Can edit bucket content and leads
    VIEWER = "viewer"  # Read-only access
    COMMENTER = "commenter"  # Can view and comment only


class BucketActivityType(str, enum.Enum):
    """Types of bucket activities for tracking"""

    CREATED = "created"
    UPDATED = "updated"
    SHARED = "shared"
    UNSHARED = "unshared"
    PERMISSION_CHANGED = "permission_changed"
    LEAD_ADDED = "lead_added"
    LEAD_REMOVED = "lead_removed"
    LEAD_UPDATED = "lead_updated"
    COMMENT_ADDED = "comment_added"
    COMMENT_UPDATED = "comment_updated"
    COMMENT_DELETED = "comment_deleted"
    ENRICHMENT_STARTED = "enrichment_started"
    ENRICHMENT_COMPLETED = "enrichment_completed"
    EXPORTED = "exported"
    ARCHIVED = "archived"
    RESTORED = "restored"


class NotificationType(str, enum.Enum):
    """Types of notifications for bucket activities"""

    BUCKET_SHARED = "bucket_shared"
    PERMISSION_GRANTED = "permission_granted"
    PERMISSION_REVOKED = "permission_revoked"
    COMMENT_MENTION = "comment_mention"
    LEAD_ASSIGNED = "lead_assigned"
    ENRICHMENT_COMPLETE = "enrichment_complete"
    BUCKET_UPDATED = "bucket_updated"


# Association table for bucket tags
bucket_tags = Table(
    "bucket_tags",
    Base.metadata,
    Column("bucket_id", String, ForeignKey("collaborative_buckets.id", ondelete="CASCADE")),
    Column("tag_id", String, ForeignKey("bucket_tag_definitions.id", ondelete="CASCADE")),
    Column("created_at", DateTime, server_default=func.now()),
    UniqueConstraint("bucket_id", "tag_id", name="uq_bucket_tag"),
)


class CollaborativeBucket(Base):
    """Enhanced bucket model with collaboration features"""

    __tablename__ = "collaborative_buckets"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    description = Column(Text)

    # Bucket type and configuration
    bucket_type = Column(String(80), nullable=False)  # vertical, geographic, custom
    bucket_key = Column(String(255), nullable=False)  # e.g., "healthcare", "high-affluence-urban"

    # Ownership
    owner_id = Column(String, nullable=False, index=True)  # User who created the bucket
    organization_id = Column(String, nullable=True, index=True)  # For org-level buckets

    # Visibility and sharing
    is_public = Column(Boolean, default=False)  # Public within organization
    is_archived = Column(Boolean, default=False)

    # Configuration from P1-080
    enrichment_config = Column(JSON, nullable=True)  # BucketEnrichmentConfig as JSON
    processing_strategy = Column(String(50), nullable=True)  # healthcare, saas, etc.
    priority_level = Column(String(20), nullable=True)  # high, medium, low

    # Statistics
    lead_count = Column(Integer, default=0)
    last_enriched_at = Column(DateTime, nullable=True)
    total_enrichment_cost = Column(Integer, default=0)  # In cents

    # Versioning
    version = Column(Integer, default=1)

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    permissions = relationship("BucketPermissionGrant", back_populates="bucket", cascade="all, delete-orphan")
    activities = relationship("BucketActivity", back_populates="bucket", cascade="all, delete-orphan")
    comments = relationship("BucketComment", back_populates="bucket", cascade="all, delete-orphan")
    versions = relationship("BucketVersion", back_populates="bucket", cascade="all, delete-orphan")
    notifications = relationship("BucketNotification", back_populates="bucket", cascade="all, delete-orphan")
    lead_annotations = relationship("LeadAnnotation", back_populates="bucket", cascade="all, delete-orphan")
    tags = relationship("BucketTagDefinition", secondary=bucket_tags, back_populates="buckets")

    __table_args__ = (
        Index("idx_collab_bucket_owner", "owner_id"),
        Index("idx_collab_bucket_org", "organization_id"),
        Index("idx_collab_bucket_type_key", "bucket_type", "bucket_key"),
        Index("idx_collab_bucket_archived", "is_archived"),
        UniqueConstraint("organization_id", "bucket_type", "bucket_key", name="uq_org_bucket_type_key"),
    )


class BucketPermissionGrant(Base):
    """Permissions granted to users for specific buckets"""

    __tablename__ = "bucket_permission_grants"

    id = Column(String, primary_key=True, default=generate_uuid)
    bucket_id = Column(String, ForeignKey("collaborative_buckets.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String, nullable=False, index=True)
    permission = Column(SQLEnum(BucketPermission), nullable=False)

    # Who granted this permission and when
    granted_by = Column(String, nullable=False)
    granted_at = Column(DateTime, nullable=False, server_default=func.now())
    expires_at = Column(DateTime, nullable=True)  # For temporary access

    # Relationships
    bucket = relationship("CollaborativeBucket", back_populates="permissions")

    __table_args__ = (
        UniqueConstraint("bucket_id", "user_id", name="uq_bucket_user_permission"),
        Index("idx_bucket_permission_user", "user_id"),
        Index("idx_bucket_permission_bucket", "bucket_id"),
    )


class BucketActivity(Base):
    """Audit log for all bucket activities"""

    __tablename__ = "bucket_activities"

    id = Column(String, primary_key=True, default=generate_uuid)
    bucket_id = Column(String, ForeignKey("collaborative_buckets.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String, nullable=False, index=True)
    activity_type = Column(SQLEnum(BucketActivityType), nullable=False, index=True)

    # Activity details
    entity_type = Column(String(50), nullable=True)  # lead, comment, permission, etc.
    entity_id = Column(String, nullable=True)  # ID of the affected entity

    # Change tracking
    old_values = Column(JSON, nullable=True)
    new_values = Column(JSON, nullable=True)
    activity_metadata = Column(JSON, nullable=True)  # Additional context

    # Timestamp
    created_at = Column(DateTime, nullable=False, server_default=func.now(), index=True)

    # Relationships
    bucket = relationship("CollaborativeBucket", back_populates="activities")

    __table_args__ = (
        Index("idx_bucket_activity_bucket_created", "bucket_id", "created_at"),
        Index("idx_bucket_activity_user_created", "user_id", "created_at"),
    )


class BucketComment(Base):
    """Comments on buckets or specific leads within buckets"""

    __tablename__ = "bucket_comments"

    id = Column(String, primary_key=True, default=generate_uuid)
    bucket_id = Column(String, ForeignKey("collaborative_buckets.id", ondelete="CASCADE"), nullable=False)
    lead_id = Column(String, nullable=True, index=True)  # Optional: comment on specific lead
    parent_comment_id = Column(String, ForeignKey("bucket_comments.id", ondelete="CASCADE"), nullable=True)

    # Comment content
    user_id = Column(String, nullable=False, index=True)
    content = Column(Text, nullable=False)

    # Mentions
    mentioned_users = Column(JSON, nullable=True)  # List of user IDs mentioned

    # Status
    is_edited = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    bucket = relationship("CollaborativeBucket", back_populates="comments")
    replies = relationship("BucketComment", backref="parent", remote_side=[id])

    __table_args__ = (
        Index("idx_bucket_comment_bucket", "bucket_id"),
        Index("idx_bucket_comment_lead", "lead_id"),
        Index("idx_bucket_comment_user", "user_id"),
    )


class BucketVersion(Base):
    """Version history for bucket configurations"""

    __tablename__ = "bucket_versions"

    id = Column(String, primary_key=True, default=generate_uuid)
    bucket_id = Column(String, ForeignKey("collaborative_buckets.id", ondelete="CASCADE"), nullable=False)
    version_number = Column(Integer, nullable=False)

    # What changed
    change_type = Column(String(50), nullable=False)  # config, leads, metadata
    change_summary = Column(Text, nullable=False)

    # Snapshot of bucket state
    bucket_snapshot = Column(JSON, nullable=False)  # Full bucket config at this version
    lead_ids_snapshot = Column(JSON, nullable=True)  # List of lead IDs in bucket

    # Who made the change
    changed_by = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    # Relationships
    bucket = relationship("CollaborativeBucket", back_populates="versions")

    __table_args__ = (
        UniqueConstraint("bucket_id", "version_number", name="uq_bucket_version"),
        Index("idx_bucket_version_bucket_created", "bucket_id", "created_at"),
    )


class BucketNotification(Base):
    """Notifications for bucket activities"""

    __tablename__ = "bucket_notifications"

    id = Column(String, primary_key=True, default=generate_uuid)
    bucket_id = Column(String, ForeignKey("collaborative_buckets.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String, nullable=False, index=True)  # Recipient
    notification_type = Column(SQLEnum(NotificationType), nullable=False)

    # Notification content
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)

    # Related entities
    related_user_id = Column(String, nullable=True)  # User who triggered the notification
    related_entity_type = Column(String(50), nullable=True)
    related_entity_id = Column(String, nullable=True)

    # Status
    is_read = Column(Boolean, default=False, index=True)
    is_email_sent = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    read_at = Column(DateTime, nullable=True)

    # Relationships
    bucket = relationship("CollaborativeBucket", back_populates="notifications")

    __table_args__ = (
        Index("idx_bucket_notification_user_read", "user_id", "is_read"),
        Index("idx_bucket_notification_created", "created_at"),
    )


class LeadAnnotation(Base):
    """Annotations and notes on specific leads within buckets"""

    __tablename__ = "lead_annotations"

    id = Column(String, primary_key=True, default=generate_uuid)
    bucket_id = Column(String, ForeignKey("collaborative_buckets.id", ondelete="CASCADE"), nullable=False)
    lead_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)

    # Annotation content
    annotation_type = Column(String(50), nullable=False)  # note, tag, status, priority
    content = Column(Text, nullable=True)
    annotation_metadata = Column(JSON, nullable=True)  # Type-specific data

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    bucket = relationship("CollaborativeBucket", back_populates="lead_annotations")

    __table_args__ = (
        Index("idx_lead_annotation_bucket_lead", "bucket_id", "lead_id"),
        Index("idx_lead_annotation_user", "user_id"),
        UniqueConstraint("bucket_id", "lead_id", "user_id", "annotation_type", name="uq_lead_annotation"),
    )


class BucketTagDefinition(Base):
    """Tags that can be applied to buckets for organization"""

    __tablename__ = "bucket_tag_definitions"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    color = Column(String(7), nullable=True)  # Hex color code

    # Tag metadata
    created_by = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    # Relationships
    buckets = relationship("CollaborativeBucket", secondary=bucket_tags, back_populates="tags")


class BucketShareLink(Base):
    """Shareable links for buckets with configurable permissions"""

    __tablename__ = "bucket_share_links"

    id = Column(String, primary_key=True, default=generate_uuid)
    bucket_id = Column(String, ForeignKey("collaborative_buckets.id", ondelete="CASCADE"), nullable=False)

    # Link configuration
    share_token = Column(String(64), nullable=False, unique=True, index=True)
    permission = Column(SQLEnum(BucketPermission), nullable=False, default=BucketPermission.VIEWER)

    # Access control
    max_uses = Column(Integer, nullable=True)  # None = unlimited
    current_uses = Column(Integer, default=0)
    expires_at = Column(DateTime, nullable=True)

    # Creator info
    created_by = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    # Status
    is_active = Column(Boolean, default=True, index=True)

    # Relationships
    bucket = relationship("CollaborativeBucket")

    __table_args__ = (
        Index("idx_share_link_token", "share_token"),
        Index("idx_share_link_bucket", "bucket_id"),
    )


class ActiveCollaboration(Base):
    """Track active users currently viewing/editing buckets"""

    __tablename__ = "active_collaborations"

    id = Column(String, primary_key=True, default=generate_uuid)
    bucket_id = Column(String, ForeignKey("collaborative_buckets.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String, nullable=False, index=True)

    # Session info
    session_id = Column(String, nullable=False, unique=True)
    connection_type = Column(String(20), nullable=False)  # websocket, polling

    # Activity tracking
    last_activity_at = Column(DateTime, nullable=False, server_default=func.now())
    current_view = Column(String(50), nullable=True)  # What part of bucket they're viewing
    is_editing = Column(Boolean, default=False)

    # Timestamps
    connected_at = Column(DateTime, nullable=False, server_default=func.now())

    # Relationships
    bucket = relationship("CollaborativeBucket")

    __table_args__ = (
        Index("idx_active_collab_bucket", "bucket_id"),
        Index("idx_active_collab_user", "user_id"),
        UniqueConstraint("bucket_id", "user_id", name="uq_bucket_user_active"),
    )
