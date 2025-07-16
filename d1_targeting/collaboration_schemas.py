"""
P2-010: Collaborative Bucket Schemas

Pydantic schemas for collaborative bucket API endpoints
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from d1_targeting.collaboration_models import BucketActivityType, BucketPermission, NotificationType


# Base schemas
class UserInfo(BaseModel):
    """Basic user information for collaboration"""

    user_id: str
    name: Optional[str] = None
    email: Optional[str] = None
    avatar_url: Optional[str] = None


class BucketTagBase(BaseModel):
    """Base schema for bucket tags"""

    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    color: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$")


class BucketTagCreate(BucketTagBase):
    """Schema for creating a tag"""

    pass


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
    description: Optional[str] = None
    bucket_type: str = Field(..., description="Type of bucket: vertical, geographic, custom")
    bucket_key: str = Field(..., description="Unique key for the bucket type")
    is_public: bool = Field(False, description="Whether bucket is public within organization")
    enrichment_config: Optional[Dict[str, Any]] = None
    processing_strategy: Optional[str] = None
    priority_level: Optional[str] = None


class BucketCreate(BucketBase):
    """Schema for creating a bucket"""

    organization_id: Optional[str] = None
    tags: Optional[List[str]] = Field(default_factory=list, description="List of tag IDs")


class BucketUpdate(BaseModel):
    """Schema for updating a bucket"""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    is_public: Optional[bool] = None
    enrichment_config: Optional[Dict[str, Any]] = None
    processing_strategy: Optional[str] = None
    priority_level: Optional[str] = None
    tags: Optional[List[str]] = None


class BucketResponse(BucketBase):
    """Schema for bucket responses"""

    id: str
    owner_id: str
    organization_id: Optional[str]
    lead_count: int
    last_enriched_at: Optional[datetime]
    total_enrichment_cost: int  # In cents
    version: int
    created_at: datetime
    updated_at: datetime
    tags: List[BucketTagResponse] = Field(default_factory=list)

    # Current user's permission
    user_permission: Optional[BucketPermission] = None

    # Active collaborators count
    active_collaborators: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class BucketListResponse(BaseModel):
    """Schema for listing buckets"""

    buckets: List[BucketResponse]
    total: int
    page: int
    page_size: int


# Permission schemas
class PermissionGrantBase(BaseModel):
    """Base schema for permission grants"""

    user_id: str
    permission: BucketPermission
    expires_at: Optional[datetime] = None


class PermissionGrantCreate(PermissionGrantBase):
    """Schema for granting permissions"""

    send_notification: bool = Field(True, description="Send notification to user")


class PermissionGrantUpdate(BaseModel):
    """Schema for updating permissions"""

    permission: BucketPermission
    expires_at: Optional[datetime] = None


class PermissionGrantResponse(PermissionGrantBase):
    """Schema for permission grant responses"""

    id: str
    bucket_id: str
    granted_by: str
    granted_at: datetime
    user_info: Optional[UserInfo] = None

    model_config = ConfigDict(from_attributes=True)


# Activity schemas
class ActivityBase(BaseModel):
    """Base schema for activities"""

    activity_type: BucketActivityType
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    old_values: Optional[Dict[str, Any]] = None
    new_values: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


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
    user_info: Optional[UserInfo] = None

    model_config = ConfigDict(from_attributes=True)


class ActivityFeedResponse(BaseModel):
    """Schema for activity feed"""

    activities: List[ActivityResponse]
    total: int
    page: int
    page_size: int


# Comment schemas
class CommentBase(BaseModel):
    """Base schema for comments"""

    content: str = Field(..., min_length=1)
    lead_id: Optional[str] = None
    parent_comment_id: Optional[str] = None
    mentioned_users: Optional[List[str]] = Field(default_factory=list)


class CommentCreate(CommentBase):
    """Schema for creating a comment"""

    pass


class CommentUpdate(BaseModel):
    """Schema for updating a comment"""

    content: str = Field(..., min_length=1)
    mentioned_users: Optional[List[str]] = None


class CommentResponse(CommentBase):
    """Schema for comment responses"""

    id: str
    bucket_id: str
    user_id: str
    is_edited: bool
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    user_info: Optional[UserInfo] = None
    reply_count: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


# Notification schemas
class NotificationBase(BaseModel):
    """Base schema for notifications"""

    notification_type: NotificationType
    title: str
    message: str
    related_user_id: Optional[str] = None
    related_entity_type: Optional[str] = None
    related_entity_id: Optional[str] = None


class NotificationResponse(NotificationBase):
    """Schema for notification responses"""

    id: str
    bucket_id: str
    user_id: str
    is_read: bool
    is_email_sent: bool
    created_at: datetime
    read_at: Optional[datetime]
    bucket_info: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class NotificationListResponse(BaseModel):
    """Schema for listing notifications"""

    notifications: List[NotificationResponse]
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
    bucket_snapshot: Dict[str, Any]
    lead_ids_snapshot: Optional[List[str]]
    changed_by: str
    created_at: datetime
    user_info: Optional[UserInfo] = None

    model_config = ConfigDict(from_attributes=True)


class VersionListResponse(BaseModel):
    """Schema for listing versions"""

    versions: List[VersionResponse]
    total: int
    page: int
    page_size: int


# Lead annotation schemas
class LeadAnnotationBase(BaseModel):
    """Base schema for lead annotations"""

    lead_id: str
    annotation_type: str = Field(..., description="note, tag, status, priority")
    content: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class LeadAnnotationCreate(LeadAnnotationBase):
    """Schema for creating a lead annotation"""

    pass


class LeadAnnotationUpdate(BaseModel):
    """Schema for updating a lead annotation"""

    content: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class LeadAnnotationResponse(LeadAnnotationBase):
    """Schema for lead annotation responses"""

    id: str
    bucket_id: str
    user_id: str
    created_at: datetime
    updated_at: datetime
    user_info: Optional[UserInfo] = None

    model_config = ConfigDict(from_attributes=True)


# Share link schemas
class ShareLinkCreate(BaseModel):
    """Schema for creating a share link"""

    permission: BucketPermission = Field(BucketPermission.VIEWER)
    max_uses: Optional[int] = Field(None, ge=1)
    expires_at: Optional[datetime] = None


class ShareLinkResponse(BaseModel):
    """Schema for share link responses"""

    id: str
    bucket_id: str
    share_token: str
    share_url: str  # Full URL for sharing
    permission: BucketPermission
    max_uses: Optional[int]
    current_uses: int
    expires_at: Optional[datetime]
    created_by: str
    created_at: datetime
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


# Active collaboration schemas
class ActiveCollaboratorInfo(BaseModel):
    """Information about an active collaborator"""

    user_id: str
    user_info: Optional[UserInfo] = None
    session_id: str
    connection_type: str
    last_activity_at: datetime
    current_view: Optional[str]
    is_editing: bool
    connected_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CollaborationStatusResponse(BaseModel):
    """Schema for collaboration status"""

    bucket_id: str
    active_collaborators: List[ActiveCollaboratorInfo]
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
    data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# Bulk operation schemas
class BulkLeadOperation(BaseModel):
    """Schema for bulk lead operations"""

    lead_ids: List[str] = Field(..., min_items=1)
    operation: str = Field(..., description="add, remove, update")
    metadata: Optional[Dict[str, Any]] = None


class BulkOperationResponse(BaseModel):
    """Schema for bulk operation responses"""

    success_count: int
    failure_count: int
    failures: Optional[List[Dict[str, str]]] = None  # lead_id -> error message
