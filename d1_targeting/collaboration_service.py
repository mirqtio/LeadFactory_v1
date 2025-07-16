"""
P2-010: Collaborative Bucket Service

Service layer for bucket collaboration including permissions,
activity tracking, notifications, and WebSocket management.
"""
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from fastapi import HTTPException, WebSocket, status
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from .collaboration_models import (
    BucketActivity,
    BucketActivityType,
    BucketNotification,
    BucketPermission,
    BucketPermissionGrant,
    BucketVersion,
    CollaborativeBucket,
    NotificationType,
)
from .collaboration_schemas import WSMessage


class WebSocketManager:
    """Manages WebSocket connections for real-time collaboration"""

    def __init__(self):
        # bucket_id -> {user_id -> websocket}
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}
        # user_id -> set of bucket_ids
        self.user_buckets: Dict[str, Set[str]] = {}

    async def connect(self, websocket: WebSocket, bucket_id: str, user_id: str):
        """Accept a new WebSocket connection"""
        await websocket.accept()

        # Add to bucket connections
        if bucket_id not in self.active_connections:
            self.active_connections[bucket_id] = {}
        self.active_connections[bucket_id][user_id] = websocket

        # Track user's buckets
        if user_id not in self.user_buckets:
            self.user_buckets[user_id] = set()
        self.user_buckets[user_id].add(bucket_id)

    def disconnect(self, websocket: WebSocket, bucket_id: str, user_id: str):
        """Remove a WebSocket connection"""
        # Remove from bucket connections
        if bucket_id in self.active_connections:
            self.active_connections[bucket_id].pop(user_id, None)
            if not self.active_connections[bucket_id]:
                del self.active_connections[bucket_id]

        # Remove from user's buckets
        if user_id in self.user_buckets:
            self.user_buckets[user_id].discard(bucket_id)
            if not self.user_buckets[user_id]:
                del self.user_buckets[user_id]

    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Send a message to a specific WebSocket"""
        await websocket.send_text(message)

    async def send_bucket_message(self, bucket_id: str, message: WSMessage, exclude_user: Optional[str] = None):
        """Broadcast a message to all users in a bucket"""
        if bucket_id in self.active_connections:
            # Convert message to JSON
            message_json = message.model_dump_json()

            # Send to all connected users in the bucket
            disconnected_users = []
            for user_id, websocket in self.active_connections[bucket_id].items():
                if user_id != exclude_user:
                    try:
                        await websocket.send_text(message_json)
                    except Exception:
                        # Connection closed, mark for removal
                        disconnected_users.append(user_id)

            # Clean up disconnected users
            for user_id in disconnected_users:
                self.disconnect(websocket, bucket_id, user_id)

    async def send_user_message(self, user_id: str, message: WSMessage):
        """Send a message to all of a user's connections"""
        if user_id in self.user_buckets:
            message_json = message.model_dump_json()

            for bucket_id in self.user_buckets[user_id]:
                if bucket_id in self.active_connections:
                    websocket = self.active_connections[bucket_id].get(user_id)
                    if websocket:
                        try:
                            await websocket.send_text(message_json)
                        except Exception:
                            pass

    def get_bucket_users(self, bucket_id: str) -> List[str]:
        """Get list of users currently connected to a bucket"""
        if bucket_id in self.active_connections:
            return list(self.active_connections[bucket_id].keys())
        return []

    def get_user_buckets(self, user_id: str) -> List[str]:
        """Get list of buckets a user is connected to"""
        if user_id in self.user_buckets:
            return list(self.user_buckets[user_id])
        return []


class BucketCollaborationService:
    """Service for bucket collaboration operations"""

    def __init__(self, db: Session):
        self.db = db

    async def check_bucket_exists(self, bucket_id: str) -> CollaborativeBucket:
        """Check if bucket exists and return it"""
        bucket = self.db.query(CollaborativeBucket).filter(CollaborativeBucket.id == bucket_id).first()

        if not bucket:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bucket not found")

        return bucket

    async def get_user_permission(self, bucket_id: str, user_id: str) -> Optional[BucketPermission]:
        """Get user's permission for a bucket"""
        permission_grant = (
            self.db.query(BucketPermissionGrant)
            .filter(
                and_(
                    BucketPermissionGrant.bucket_id == bucket_id,
                    BucketPermissionGrant.user_id == user_id,
                    or_(
                        BucketPermissionGrant.expires_at.is_(None), BucketPermissionGrant.expires_at > datetime.utcnow()
                    ),
                )
            )
            .first()
        )

        return permission_grant.permission if permission_grant else None

    async def check_permission(
        self, bucket_id: str, user_id: str, required_permissions: List[BucketPermission]
    ) -> BucketPermission:
        """Check if user has required permission for bucket"""
        user_permission = await self.get_user_permission(bucket_id, user_id)

        if not user_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="You don't have permission to access this bucket"
            )

        # Permission hierarchy: OWNER > ADMIN > EDITOR > COMMENTER > VIEWER
        permission_hierarchy = {
            BucketPermission.OWNER: 5,
            BucketPermission.ADMIN: 4,
            BucketPermission.EDITOR: 3,
            BucketPermission.COMMENTER: 2,
            BucketPermission.VIEWER: 1,
        }

        user_level = permission_hierarchy.get(user_permission, 0)
        required_level = max(permission_hierarchy.get(perm, 0) for perm in required_permissions)

        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action requires {required_permissions[0].value} permission or higher",
            )

        return user_permission

    async def create_activity(
        self,
        bucket_id: str,
        user_id: str,
        activity_type: BucketActivityType,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> BucketActivity:
        """Create an activity log entry"""
        activity = BucketActivity(
            bucket_id=bucket_id,
            user_id=user_id,
            activity_type=activity_type,
            entity_type=entity_type,
            entity_id=entity_id,
            old_values=old_values,
            new_values=new_values,
            metadata=metadata,
        )
        self.db.add(activity)
        self.db.commit()
        self.db.refresh(activity)

        return activity

    async def create_notification(
        self,
        bucket_id: str,
        user_id: str,
        notification_type: NotificationType,
        title: str,
        message: str,
        related_user_id: Optional[str] = None,
        related_entity_type: Optional[str] = None,
        related_entity_id: Optional[str] = None,
    ) -> BucketNotification:
        """Create a notification for a user"""
        notification = BucketNotification(
            bucket_id=bucket_id,
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            message=message,
            related_user_id=related_user_id,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
        )
        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)

        # TODO: Send email notification if configured

        return notification

    async def create_version_snapshot(
        self,
        bucket: CollaborativeBucket,
        user_id: str,
        change_type: str,
        change_summary: str,
        include_leads: bool = False,
    ) -> BucketVersion:
        """Create a version snapshot of the bucket"""
        # Create bucket snapshot
        bucket_snapshot = {
            "name": bucket.name,
            "description": bucket.description,
            "bucket_type": bucket.bucket_type,
            "bucket_key": bucket.bucket_key,
            "is_public": bucket.is_public,
            "enrichment_config": bucket.enrichment_config,
            "processing_strategy": bucket.processing_strategy,
            "priority_level": bucket.priority_level,
            "tags": [{"id": tag.id, "name": tag.name} for tag in bucket.tags],
        }

        # Get lead IDs if requested
        lead_ids_snapshot = None
        if include_leads:
            from database.models import Business

            if bucket.bucket_type == "vertical":
                leads = self.db.query(Business.id).filter(Business.vert_bucket == bucket.bucket_key).all()
            else:
                leads = self.db.query(Business.id).filter(Business.geo_bucket == bucket.bucket_key).all()

            lead_ids_snapshot = [lead.id for lead in leads]

        # Create version
        version = BucketVersion(
            bucket_id=bucket.id,
            version_number=bucket.version,
            change_type=change_type,
            change_summary=change_summary,
            bucket_snapshot=bucket_snapshot,
            lead_ids_snapshot=lead_ids_snapshot,
            changed_by=user_id,
        )
        self.db.add(version)
        self.db.commit()
        self.db.refresh(version)

        return version

    async def get_bucket_stats(self, bucket_id: str) -> Dict[str, Any]:
        """Get statistics for a bucket"""
        from database.models import Business

        bucket = await self.check_bucket_exists(bucket_id)

        # Get lead count
        if bucket.bucket_type == "vertical":
            lead_count = self.db.query(Business).filter(Business.vert_bucket == bucket.bucket_key).count()
        else:
            lead_count = self.db.query(Business).filter(Business.geo_bucket == bucket.bucket_key).count()

        # Get collaborator count
        collaborator_count = (
            self.db.query(BucketPermissionGrant).filter(BucketPermissionGrant.bucket_id == bucket_id).count()
        )

        # Get activity count (last 30 days)
        activity_count = (
            self.db.query(BucketActivity)
            .filter(
                BucketActivity.bucket_id == bucket_id,
                BucketActivity.created_at >= datetime.utcnow() - timedelta(days=30),
            )
            .count()
        )

        # Get comment count
        comment_count = (
            self.db.query(BucketComment)
            .filter(BucketComment.bucket_id == bucket_id, BucketComment.is_deleted == False)
            .count()
        )

        return {
            "lead_count": lead_count,
            "collaborator_count": collaborator_count,
            "activity_count_30d": activity_count,
            "comment_count": comment_count,
            "version_count": bucket.version,
            "last_enriched_at": bucket.last_enriched_at,
            "total_enrichment_cost_cents": bucket.total_enrichment_cost,
        }


# Helper functions for use in API endpoints
async def check_bucket_permission(
    db: Session, bucket_id: str, user_id: str, required_permissions: List[BucketPermission]
) -> BucketPermission:
    """Check if user has required permission for bucket"""
    service = BucketCollaborationService(db)
    return await service.check_permission(bucket_id, user_id, required_permissions)


async def create_activity(
    db: Session,
    bucket_id: str,
    user_id: str,
    activity_type: BucketActivityType,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    old_values: Optional[Dict[str, Any]] = None,
    new_values: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> BucketActivity:
    """Create an activity log entry"""
    service = BucketCollaborationService(db)
    return await service.create_activity(
        bucket_id=bucket_id,
        user_id=user_id,
        activity_type=activity_type,
        entity_type=entity_type,
        entity_id=entity_id,
        old_values=old_values,
        new_values=new_values,
        metadata=metadata,
    )


async def create_notification(
    db: Session,
    bucket_id: str,
    user_id: str,
    notification_type: NotificationType,
    title: str,
    message: str,
    related_user_id: Optional[str] = None,
    related_entity_type: Optional[str] = None,
    related_entity_id: Optional[str] = None,
) -> BucketNotification:
    """Create a notification for a user"""
    service = BucketCollaborationService(db)
    return await service.create_notification(
        bucket_id=bucket_id,
        user_id=user_id,
        notification_type=notification_type,
        title=title,
        message=message,
        related_user_id=related_user_id,
        related_entity_type=related_entity_type,
        related_entity_id=related_entity_id,
    )


async def create_version_snapshot(
    db: Session,
    bucket: CollaborativeBucket,
    user_id: str,
    change_type: str,
    change_summary: str,
    include_leads: bool = False,
) -> BucketVersion:
    """Create a version snapshot of the bucket"""
    service = BucketCollaborationService(db)
    return await service.create_version_snapshot(
        bucket=bucket,
        user_id=user_id,
        change_type=change_type,
        change_summary=change_summary,
        include_leads=include_leads,
    )
