"""
P2-010: Collaborative Bucket Schemas

Pydantic schemas for collaborative bucket API endpoints
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from d1_targeting.collaboration_models import BucketActivityType, BucketPermission, NotificationType


# Base schemas
class UserInfo(BaseModel):
    """Basic user information for collaboration"""

    user_id: str
    name: str | None = None
    email: str | None = None
    avatar_url: str | None = None


class BucketTagBase(BaseModel):
    """Base schema for bucket tags"""

    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    color: str | None = Field(None, pattern="^#[0-9A-Fa-f]{6}$")


class BucketTagCreate(BucketTagBase):
    """Schema for creating a tag"""


class BucketTagResponse(BucketTagBase):
    """Schema for tag responses"""

    id: str
    created_by: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Bucket schemas
class BucketBase(BaseModel):
    """Base schema for buckets"""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    bucket_type: str = Field(..., description="Type of bucket: vertical, geographic, custom")
    bucket_key: str = Field(..., description="Unique key for the bucket type")
    is_public: bool = Field(False, description="Whether bucket is public within organization")
    enrichment_config: dict[str, Any] | None = None
    processing_strategy: str | None = None
    priority_level: str | None = None


class BucketCreate(BucketBase):
    """Schema for creating a bucket"""

    organization_id: str | None = None
    tags: list[str] | None = Field(default_factory=list, description="List of tag IDs")


class BucketUpdate(BaseModel):
    """Schema for updating a bucket"""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    is_public: bool | None = None
    enrichment_config: dict[str, Any] | None = None
    processing_strategy: str | None = None
    priority_level: str | None = None
    tags: list[str] | None = None


class BucketResponse(BucketBase):
    """Schema for bucket responses"""

    id: str
    owner_id: str
    organization_id: str | None
    lead_count: int
    last_enriched_at: datetime | None
    total_enrichment_cost: int  # In cents
    version: int
    created_at: datetime
    updated_at: datetime
    tags: list[BucketTagResponse] = Field(default_factory=list)

    # Current user's permission
    user_permission: BucketPermission | None = None

    # Active collaborators count
    active_collaborators: int | None = None

    model_config = ConfigDict(from_attributes=True)


class BucketListResponse(BaseModel):
    """Schema for listing buckets"""

    buckets: list[BucketResponse]
    total: int
    page: int
    page_size: int


# Permission schemas
class PermissionGrantBase(BaseModel):
    """Base schema for permission grants"""

    user_id: str
    permission: BucketPermission
    expires_at: datetime | None = None


class PermissionGrantCreate(PermissionGrantBase):
    """Schema for granting permissions"""

    send_notification: bool = Field(True, description="Send notification to user")


class PermissionGrantUpdate(BaseModel):
    """Schema for updating permissions"""

    permission: BucketPermission
    expires_at: datetime | None = None


class PermissionGrantResponse(PermissionGrantBase):
    """Schema for permission grant responses"""

    id: str
    bucket_id: str
    granted_by: str
    granted_at: datetime
    user_info: UserInfo | None = None

    model_config = ConfigDict(from_attributes=True)


# Activity schemas
class ActivityBase(BaseModel):
    """Base schema for activities"""

    activity_type: BucketActivityType
    entity_type: str | None = None
    entity_id: str | None = None
    old_values: dict[str, Any] | None = None
    new_values: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


class ActivityCreate(ActivityBase):
    """Schema for creating an activity (usually internal)"""

    user_id: str
    bucket_id: str


class ActivityResponse(ActivityBase):
    """Schema for activity responses"""

    id: str
    bucket_id: str
    user_id: str
    created_at: datetime
    user_info: UserInfo | None = None

    model_config = ConfigDict(from_attributes=True)


class ActivityFeedResponse(BaseModel):
    """Schema for activity feed"""

    activities: list[ActivityResponse]
    total: int
    page: int
    page_size: int


# Comment schemas
class CommentBase(BaseModel):
    """Base schema for comments"""

    content: str = Field(..., min_length=1)
    lead_id: str | None = None
    parent_comment_id: str | None = None
    mentioned_users: list[str] | None = Field(default_factory=list)


class CommentCreate(CommentBase):
    """Schema for creating a comment"""


class CommentUpdate(BaseModel):
    """Schema for updating a comment"""

    content: str = Field(..., min_length=1)
    mentioned_users: list[str] | None = None


class CommentResponse(CommentBase):
    """Schema for comment responses"""

    id: str
    bucket_id: str
    user_id: str
    is_edited: bool
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    user_info: UserInfo | None = None
    reply_count: int | None = None

    model_config = ConfigDict(from_attributes=True)


# Notification schemas
class NotificationBase(BaseModel):
    """Base schema for notifications"""

    notification_type: NotificationType
    title: str
    message: str
    related_user_id: str | None = None
    related_entity_type: str | None = None
    related_entity_id: str | None = None


class NotificationResponse(NotificationBase):
    """Schema for notification responses"""

    id: str
    bucket_id: str
    user_id: str
    is_read: bool
    is_email_sent: bool
    created_at: datetime
    read_at: datetime | None
    bucket_info: dict[str, Any] | None = None

    model_config = ConfigDict(from_attributes=True)


class NotificationListResponse(BaseModel):
    """Schema for listing notifications"""

    notifications: list[NotificationResponse]
    unread_count: int
    total: int
    page: int
    page_size: int


# Version history schemas
class VersionResponse(BaseModel):
    """Schema for version history responses"""

    id: str
    bucket_id: str
    version_number: int
    change_type: str
    change_summary: str
    bucket_snapshot: dict[str, Any]
    lead_ids_snapshot: list[str] | None
    changed_by: str
    created_at: datetime
    user_info: UserInfo | None = None

    model_config = ConfigDict(from_attributes=True)


class VersionListResponse(BaseModel):
    """Schema for listing versions"""

    versions: list[VersionResponse]
    total: int
    page: int
    page_size: int


# Lead annotation schemas
class LeadAnnotationBase(BaseModel):
    """Base schema for lead annotations"""

    lead_id: str
    annotation_type: str = Field(..., description="note, tag, status, priority")
    content: str | None = None
    metadata: dict[str, Any] | None = None


class LeadAnnotationCreate(LeadAnnotationBase):
    """Schema for creating a lead annotation"""


class LeadAnnotationUpdate(BaseModel):
    """Schema for updating a lead annotation"""

    content: str | None = None
    metadata: dict[str, Any] | None = None


class LeadAnnotationResponse(LeadAnnotationBase):
    """Schema for lead annotation responses"""

    id: str
    bucket_id: str
    user_id: str
    created_at: datetime
    updated_at: datetime
    user_info: UserInfo | None = None

    model_config = ConfigDict(from_attributes=True)


# Share link schemas
class ShareLinkCreate(BaseModel):
    """Schema for creating a share link"""

    permission: BucketPermission = Field(BucketPermission.VIEWER)
    max_uses: int | None = Field(None, ge=1)
    expires_at: datetime | None = None


class ShareLinkResponse(BaseModel):
    """Schema for share link responses"""

    id: str
    bucket_id: str
    share_token: str
    share_url: str  # Full URL for sharing
    permission: BucketPermission
    max_uses: int | None
    current_uses: int
    expires_at: datetime | None
    created_by: str
    created_at: datetime
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


# Active collaboration schemas
class ActiveCollaboratorInfo(BaseModel):
    """Information about an active collaborator"""

    user_id: str
    user_info: UserInfo | None = None
    session_id: str
    connection_type: str
    last_activity_at: datetime
    current_view: str | None
    is_editing: bool
    connected_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CollaborationStatusResponse(BaseModel):
    """Schema for collaboration status"""

    bucket_id: str
    active_collaborators: list[ActiveCollaboratorInfo]
    total_collaborators: int


# WebSocket message schemas
class WSMessageType(str):
    """WebSocket message types"""

    USER_JOINED = "user_joined"
    USER_LEFT = "user_left"
    BUCKET_UPDATED = "bucket_updated"
    LEAD_UPDATED = "lead_updated"
    COMMENT_ADDED = "comment_added"
    PERMISSION_CHANGED = "permission_changed"
    ACTIVITY_CREATED = "activity_created"


class WSMessage(BaseModel):
    """WebSocket message schema"""

    type: str
    bucket_id: str
    user_id: str
    data: dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# Bulk operation schemas
class BulkLeadOperation(BaseModel):
    """Schema for bulk lead operations"""

    lead_ids: list[str] = Field(..., min_items=1)
    operation: str = Field(..., description="add, remove, update")
    metadata: dict[str, Any] | None = None


class BulkOperationResponse(BaseModel):
    """Schema for bulk operation responses"""

    success_count: int
    failure_count: int
    failures: list[dict[str, str]] | None = None  # lead_id -> error message
